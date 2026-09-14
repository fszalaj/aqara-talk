"""Validated camera settings and go2rtc configuration suggestions."""

from ipaddress import ip_address
import json
import os
from pathlib import Path
import tempfile

import voluptuous as vol

DOMAIN = "aqara_talk"
DEFAULT_MAX_DURATION = 180


def max_duration(value):
    """Normalize whole seconds from the Home Assistant numeric selector."""
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not 1 <= value <= 3600 or int(value) != value):
        raise vol.Invalid("Enter a whole number of seconds from 1 to 3600")
    return int(value)


def camera_ip(value):
    """Accept numeric unicast addresses without shell syntax or scope IDs."""
    if not isinstance(value, str) or "%" in value:
        raise vol.Invalid("Enter a numeric unicast camera IP address")
    try:
        address = ip_address(value)
    except ValueError as err:
        raise vol.Invalid("Enter a numeric unicast camera IP address") from err
    if (address.version != 4 or address.is_unspecified or address.is_multicast
            or address.is_loopback or address.is_reserved or address.is_link_local):
        raise vol.Invalid("Enter a routable unicast camera IPv4 address")
    return str(address)


def settings_path(config_dir, host):
    return Path(config_dir) / DOMAIN / f"{camera_ip(host)}.json"


def write_settings(config_dir, host, duration):
    target = settings_path(config_dir, host)
    duration = max_duration(duration)
    target.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    target.parent.chmod(0o755)
    fd, temporary = tempfile.mkstemp(prefix=".settings-", dir=target.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump({"max_duration": duration}, stream)
            stream.write("\n")
            os.fchmod(stream.fileno(), 0o644)
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def remove_settings(config_dir, host):
    settings_path(config_dir, host).unlink(missing_ok=True)


INPUT_SCHEMA = vol.Schema({
    vol.Required("host"): camera_ip,
    vol.Optional("name"): vol.All(str, str.strip, vol.Length(min=1, max=100)),
})
SERVICE_SCHEMA = vol.Schema({vol.Optional("entry_id"): vol.All(str, vol.Length(min=1))})
OPTIONS_SCHEMA = vol.Schema({
    vol.Optional("max_duration", default=DEFAULT_MAX_DURATION): max_duration,
})


def get_config(entries, entry_id=None):
    """Select a loaded entry and return source strings without physical I/O."""
    if entry_id is None:
        if len(entries) != 1:
            raise ValueError("Specify entry_id when there is not exactly one loaded entry")
        entry_id = next(iter(entries))
    if entry_id not in entries:
        raise ValueError("Unknown or unloaded Aqara Talk entry_id")
    host = camera_ip(entries[entry_id]["host"])
    duration = max_duration(entries[entry_id].get("max_duration", DEFAULT_MAX_DURATION))
    sources = {}
    for runtime, base, ffmpeg in (
        ("frigate", "/homeassistant", "/usr/lib/ffmpeg/7.0/bin/ffmpeg"),
        ("generic", "/config", "/usr/bin/ffmpeg"),
    ):
        command = (f"exec:python3 {base}/custom_components/aqara_talk/bridge.py"
                   f" {host} --input-format alaw --ffmpeg {ffmpeg}")
        suffix = "#backchannel=1#audio=pcma/8000#killsignal=15#killtimeout=5"
        sources[runtime] = {
            "probe_source": command + " --max-duration 20 --probe --probe-report /config/aqara-talk-probe.json" + suffix,
            "talk_source": command + f" --settings-file {base}/{DOMAIN}/{host}.json" + suffix,
        }
    return {"entry_id": entry_id, "host": host, "max_duration": duration, "sources": sources}
