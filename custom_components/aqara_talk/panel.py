"""Admin-only setup and the existing camera card."""

import hashlib
import json
from pathlib import Path

import voluptuous as vol
from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import callback

from .config import DEFAULT_MAX_DURATION, DOMAIN
from .runtime import RuntimeDiscoveryError, build_setup, discover

PANEL_PATH = "aqara-talk"


async def async_setup_panel(hass):
    directory = Path(__file__).parent
    await hass.http.async_register_static_paths([
        StaticPathConfig("/aqara_talk/panel.js", str(directory / "frontend/panel.js"), True),
    ])
    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_setup)


async def async_register_panel(hass):
    if PANEL_PATH in hass.data.get(frontend.DATA_PANELS, {}):
        return
    raw = await hass.async_add_executor_job((Path(__file__).parent / "manifest.json").read_text)
    version = json.loads(raw)["version"]
    script = await hass.async_add_executor_job((Path(__file__).parent / "frontend/panel.js").read_bytes)
    version += "-" + hashlib.sha256(script).hexdigest()[:12]
    if frontend.async_panel_exists(hass, PANEL_PATH):
        return
    await panel_custom.async_register_panel(
        hass, PANEL_PATH, "aqara-talk-panel", sidebar_title="Aqara Talk",
        sidebar_icon="mdi:doorbell-video", module_url=f"/aqara_talk/panel.js?v={version}",
        require_admin=True,
    )


@websocket_api.websocket_command({vol.Required("type"): "aqara_talk/list"})
@websocket_api.require_admin
@callback
def ws_list(hass, connection, msg):
    connection.send_result(msg["id"], {"entries": [
        {"entry_id": entry.entry_id, "title": entry.title,
         "camera_entity": entry.data.get("camera_entity"),
         "runtime_kind": entry.data.get("runtime_kind")}
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.entry_id in hass.data.get(DOMAIN, {})
    ]})


@websocket_api.websocket_command({
    vol.Required("type"): "aqara_talk/setup", vol.Required("entry_id"): str,
})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_setup(hass, connection, msg):
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN or entry.entry_id not in hass.data.get(DOMAIN, {}):
        connection.send_error(msg["id"], "not_found", "Aqara Talk entry is not loaded")
        return
    result = {
        "entry_id": entry.entry_id, "title": entry.title, "status": "unconfigured",
        "camera_entity": entry.data.get("camera_entity"),
        "runtime_kind": entry.data.get("runtime_kind"),
        "max_duration": entry.options.get("max_duration", DEFAULT_MAX_DURATION),
        "card": None, "runtime_yaml": "", "streams": [], "talk_stream": "",
    }
    if entry.data.get("camera_entity") and entry.data.get("video_stream"):
        try:
            result.update(build_setup(dict(entry.data), result["max_duration"]))
            found = await discover(hass, entry.data["camera_entity"],
                                   entry.data["runtime_kind"], entry.data.get("runtime_url", ""))
        except RuntimeDiscoveryError as err:
            result["status"] = err.code
        except (KeyError, ValueError, TypeError, vol.Invalid):
            result["status"] = "invalid_response"
        else:
            result["streams"] = found["streams"]
            if entry.data["runtime_kind"] == "frigate" and any(
                entry.data.get(key) != found.get(key) for key in (
                    "frigate_entry_id", "frigate_client_id", "runtime_url",
                )
            ):
                result["status"] = "runtime_changed"
                result["card"] = None
            elif entry.data["video_stream"] not in found["streams"]:
                result["status"] = "video_stream_missing"
            elif (video_host := found.get("video_hosts", {}).get(entry.data["video_stream"])) and video_host != entry.data["host"]:
                result["status"] = "video_camera_mismatch"
            elif result["talk_stream"] not in found["talk_streams"]:
                result["status"] = "talk_stream_missing"
            elif found.get("talk_hosts", {}).get(result["talk_stream"]) != entry.data["host"]:
                result["status"] = "talk_camera_mismatch"
            elif entry.data["runtime_kind"] == "go2rtc" and "webrtc" not in hass.config.components:
                result["status"] = "integration_missing"
            else:
                result["status"] = "ready_to_test"
    if result["status"] != "ready_to_test":
        result["card"] = None
    connection.send_result(msg["id"], result)
