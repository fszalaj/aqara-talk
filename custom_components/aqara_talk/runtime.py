"""Read runtime metadata and generate credential-free setup suggestions."""

import asyncio
from ipaddress import ip_address
import json
from pathlib import PurePosixPath
import re
import shlex
from urllib.parse import quote, urlsplit

import aiohttp
import yaml
import voluptuous as vol
from homeassistant.helpers import aiohttp_client, entity_registry

from .config import camera_ip, get_config

MAX_RESPONSE = 2 * 1024 * 1024


class RuntimeDiscoveryError(Exception):
    """A safe, translatable discovery failure."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def validate_url(value):
    """Allow explicitly configured HTTP endpoints without embedded secrets."""
    try:
        url = urlsplit(value)
        if (not isinstance(value, str) or any(c.isspace() for c in value)
                or url.scheme not in ("http", "https") or not url.hostname
                or url.username is not None or url.password is not None
                or "?" in value or "#" in value or "\\" in value):
            raise ValueError
        _ = url.port
        try:
            address = ip_address(url.hostname)
        except ValueError:
            address = None
        if address and (address.is_link_local or address.is_multicast or address.is_unspecified):
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise RuntimeDiscoveryError("invalid_url") from None
    return value.rstrip("/")


def _name(value):
    return isinstance(value, str) and bool(value.strip()) and bool(re.fullmatch(r"[\w .-]{1,200}", value))


async def _read_runtime(hass, url, path, *, json_response=True):
    try:
        async with asyncio.timeout(8):
            async with aiohttp_client.async_get_clientsession(hass).get(
                url + path, allow_redirects=False
            ) as response:
                if response.status in (401, 403):
                    raise RuntimeDiscoveryError("unauthorized")
                if 300 <= response.status < 400:
                    raise RuntimeDiscoveryError("redirect_not_allowed")
                if response.status != 200:
                    raise RuntimeDiscoveryError("cannot_connect")
                if json_response and response.content_type != "application/json":
                    raise RuntimeDiscoveryError("invalid_response")
                if response.content_length and response.content_length > MAX_RESPONSE:
                    raise RuntimeDiscoveryError("invalid_response")
                body = bytearray()
                async for chunk in response.content.iter_chunked(65536):
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE:
                        raise RuntimeDiscoveryError("invalid_response")
                return await hass.async_add_executor_job(
                    json.loads if json_response else yaml.safe_load, bytes(body),
                )
    except RuntimeDiscoveryError:
        raise
    except (ValueError, UnicodeError, yaml.YAMLError, RecursionError):
        raise RuntimeDiscoveryError("invalid_response") from None
    except (aiohttp.ClientError, TimeoutError, OSError):
        raise RuntimeDiscoveryError("cannot_connect") from None


def _sources(stream):
    if not isinstance(stream, dict):
        return []
    producers = stream.get("producers") or []
    if not isinstance(producers, list):
        return []
    return [p["url"] for p in producers if isinstance(p, dict) and isinstance(p.get("url"), str)]


def _bridge_host(source):
    if not source.startswith("exec:"):
        return ""
    try:
        argv = shlex.split(source[5:].split("#", 1)[0])
        if (len(argv) >= 3 and re.fullmatch(r"python3(?:\.\d+)?", PurePosixPath(argv[0]).name)
                and argv[1].startswith("/") and argv[1].endswith("/aqara_talk/bridge.py")):
            return camera_ip(argv[2])
    except (ValueError, vol.Invalid):
        pass
    return ""


async def discover(hass, camera_entity, runtime_kind="frigate", runtime_url=""):
    """Inspect configuration and idle stream metadata without starting a camera."""
    if not isinstance(camera_entity, str) or not camera_entity.startswith("camera."):
        raise RuntimeDiscoveryError("camera_missing")
    state = hass.states.get(camera_entity)
    if state is None:
        raise RuntimeDiscoveryError("camera_missing")
    if state.state in ("unknown", "unavailable"):
        raise RuntimeDiscoveryError("camera_unavailable")
    registry_entry = entity_registry.async_get(hass).async_get(camera_entity)
    entry = hass.config_entries.async_get_entry(registry_entry.config_entry_id) if registry_entry else None
    camera_name = state.attributes.get("camera_name", "")
    camera_name = camera_name if _name(camera_name) else ""
    matches = []
    config = {}
    frigate_entry_id = ""
    frigate_client_id = ""
    if runtime_kind == "frigate":
        if not entry or entry.domain != "frigate":
            raise RuntimeDiscoveryError("integration_missing")
        frigate_entry_id = entry.entry_id
        client_id = state.attributes.get("client_id", "")
        frigate_client_id = client_id if _name(client_id) else ""
        runtime_url = validate_url(entry.data.get("url", ""))
        integration_data = hass.data.get("frigate", {})
        runtime = integration_data.get(entry.entry_id, {}) if isinstance(integration_data, dict) else {}
        client = runtime.get("client") if isinstance(runtime, dict) else None
        if not callable(getattr(client, "async_get_config", None)) or not callable(getattr(client, "api_wrapper", None)):
            raise RuntimeDiscoveryError("frigate_client_incompatible")
        try:
            async with asyncio.timeout(8):
                config = await client.async_get_config()
                streams = await client.api_wrapper("get", runtime_url + "/api/go2rtc/streams")
        except (TypeError, AttributeError):
            raise RuntimeDiscoveryError("frigate_client_incompatible") from None
        except Exception as error:
            cause = error.__cause__ or error
            code = "unauthorized" if getattr(cause, "status", None) in (401, 403) else "cannot_connect"
            raise RuntimeDiscoveryError(code) from None
        if not isinstance(config, dict):
            raise RuntimeDiscoveryError("invalid_response")
        cameras = config.get("cameras", {})
        camera = cameras.get(camera_name, {}) if isinstance(cameras, dict) else {}
        live = camera.get("live", {}) if isinstance(camera, dict) else {}
        if isinstance(live, dict):
            mapping = live.get("streams", {})
            if isinstance(mapping, dict):
                matches = [name for name in mapping.values() if _name(name)]
            legacy = live.get("stream_name")
            if not matches and _name(legacy):
                matches = [legacy]
    elif runtime_kind in ("go2rtc", "generic"):
        runtime_url = validate_url(runtime_url)
        streams = await _read_runtime(hass, runtime_url, "/api/streams")
        standalone_config = await _read_runtime(hass, runtime_url, "/api/config", json_response=False)
        if not isinstance(standalone_config, dict):
            raise RuntimeDiscoveryError("invalid_response")
        config = {"go2rtc": standalone_config}
    else:
        raise RuntimeDiscoveryError("invalid_response")
    if not isinstance(streams, dict):
        raise RuntimeDiscoveryError("invalid_response")
    names = sorted(name for name in streams if _name(name))
    matches = sorted(set(name for name in matches if name in names))
    if not matches and camera_name in names:
        matches = [camera_name]
    configured = config.get("go2rtc", {})
    configured = configured.get("streams", {}) if isinstance(configured, dict) else {}
    configured = configured if isinstance(configured, dict) else {}

    def sources_for(name):
        sources = configured.get(name, [])
        if isinstance(sources, str):
            sources = [sources]
        return _sources(streams[name]) + ([s for s in sources if isinstance(s, str)] if isinstance(sources, list) else [])

    talk_hosts = {}
    for name in names:
        hosts = {_bridge_host(source) for source in sources_for(name)} - {""}
        if len(hosts) == 1:
            talk_hosts[name] = next(iter(hosts))
    talk_streams = sorted(talk_hosts)
    video_hosts = {}
    for name in names:
        host_candidates = set()
        for source in sources_for(name):
            try:
                parsed = urlsplit(source)
                host = camera_ip(parsed.hostname)
                if parsed.scheme in ("rtsp", "rtsps", "http", "https") and host != urlsplit(runtime_url).hostname:
                    host_candidates.add(host)
            except (ValueError, TypeError, vol.Invalid):
                pass
        if len(host_candidates) == 1:
            video_hosts[name] = next(iter(host_candidates))
    host_candidates = {video_hosts[name] for name in matches if name in video_hosts}
    return {"runtime_kind": runtime_kind, "runtime_url": runtime_url,
            "frigate_entry_id": frigate_entry_id, "frigate_client_id": frigate_client_id,
            "camera_name": camera_name, "streams": names, "matches": matches,
            "suggested_host": next(iter(host_candidates)) if len(host_candidates) == 1 else "",
            "talk_streams": talk_streams, "talk_hosts": talk_hosts,
            "video_hosts": video_hosts, "status": "ok"}


def build_setup(data, duration=180):
    """Generate a local restream and a card using existing bridge commands."""
    host = camera_ip(data["host"])
    video = data["video_stream"]
    talk = data.get("talk_stream") or "aqara_talk_" + host.replace(".", "_")
    if not _name(video) or not _name(talk) or video == talk:
        raise RuntimeDiscoveryError("invalid_response")
    kind = data.get("runtime_kind", "frigate")
    runtime = "frigate" if kind == "frigate" else "generic"
    sources = get_config({"setup": {"host": host, "max_duration": duration}})["sources"][runtime]
    fragment = {"streams": {talk: [
        "rtsp://127.0.0.1:8554/" + quote(video, safe="") + "?video=h264&audio=opus&audio=aac#backchannel=0",
        sources["talk_source"],
    ]}}
    if kind == "frigate":
        fragment = {"go2rtc": fragment}
        camera = {"camera_entity": data["camera_entity"], "live_provider": "go2rtc",
                  "go2rtc": {"stream": talk, "metadata_fetch_timeout_seconds": 10},
                  "capabilities": {"force": ["2-way-audio"]}}
        if data.get("frigate_client_id"):
            camera["frigate"] = {"client_id": data["frigate_client_id"]}
        card = {"type": "custom:advanced-camera-card", "cameras": [camera],
                "view": {"default": "live"},
                "dimensions": {"aspect_ratio_mode": "static", "aspect_ratio": "4:3",
                               "height": "min(50vh, 72vw, 480px)"},
                "menu": {"style": "outside", "position": "bottom", "auto_hide": [],
                         "buttons": {key: {"enabled": True} for key in ("mute", "call", "microphone")}},
                "live": {"controls": {"builtin": True}, "auto_unmute": ["call"], "auto_mute": ["call"],
                         "microphone": {"always_connected": False, "auto_unmute": ["call"]}}}
    else:
        card = {"type": "custom:webrtc-camera", "ui": True,
                "server": validate_url(data["runtime_url"]), "streams": [
            {"url": talk, "name": "Listen", "mode": "webrtc", "media": "video,audio"},
            {"url": talk, "name": "Speak", "mode": "webrtc", "media": "video,audio,microphone"}]}
    return {"card": card, "runtime_yaml": yaml.safe_dump(fragment, sort_keys=False), "talk_stream": talk}
