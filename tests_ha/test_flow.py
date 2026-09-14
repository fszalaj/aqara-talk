"""Real HA flow, options, panel and authorization checks."""
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.components import frontend
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aqara_talk.config import DOMAIN, settings_path
from custom_components.aqara_talk.runtime import RuntimeDiscoveryError

FOUND = {
    "runtime_kind": "frigate", "runtime_url": "http://frigate:5000",
    "frigate_entry_id": "owner", "frigate_client_id": "living-room",
    "camera_name": "doorbell", "streams": ["doorbell", "talk"],
    "matches": ["doorbell"], "talk_streams": ["talk"],
    "talk_hosts": {"talk": "192.168.1.20"}, "suggested_host": "192.168.1.20",
}


async def test_camera_flow_and_duplicate(hass):
    hass.states.async_set("camera.doorbell", "idle", {"friendly_name": "Doorbell"})
    with patch("custom_components.aqara_talk.config_flow.discover", AsyncMock(return_value=FOUND)), \
         patch("custom_components.aqara_talk.async_setup_entry", AsyncMock(return_value=True)):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"camera_entity": "camera.missing"})
        assert result["errors"] == {"base": "camera_missing"}
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"camera_entity": "camera.doorbell"})
        assert result["step_id"] == "streams"
        data = {"host": "192.168.1.20", "name": "Doorbell", "video_stream": "doorbell", "talk_stream": "talk"}
        created = await hass.config_entries.flow.async_configure(result["flow_id"], data)
        assert created["type"] == "create_entry"
        entry = created["result"]
        assert entry.unique_id == "192.168.1.20"
        assert entry.data["frigate_client_id"] == "living-room"
        again = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        again = await hass.config_entries.flow.async_configure(again["flow_id"], {"camera_entity": "camera.doorbell"})
        again = await hass.config_entries.flow.async_configure(again["flow_id"], data)
        assert again["reason"] == "already_configured"
        await hass.async_block_till_done()


async def test_generic_retry_and_old_entry_reconfigure(hass):
    hass.states.async_set("camera.generic", "idle")
    entry = MockConfigEntry(domain=DOMAIN, unique_id="192.168.1.20", data={"host": "192.168.1.20", "name": "Old"})
    entry.add_to_hass(hass)
    with patch("custom_components.aqara_talk.config_flow.discover", AsyncMock(side_effect=[
        RuntimeDiscoveryError("integration_missing"), RuntimeDiscoveryError("cannot_connect"),
        {**FOUND, "runtime_kind": "go2rtc"},
    ])), patch("custom_components.aqara_talk.async_setup_entry", AsyncMock(return_value=True)), \
         patch.object(hass.config_entries, "async_reload", AsyncMock(return_value=True)):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"camera_entity": "camera.generic"})
        assert result["step_id"] == "runtime"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"runtime_url": "http://go2rtc:1984"})
        assert result["errors"] == {"base": "cannot_connect"}
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"runtime_url": "http://go2rtc:1984"})
        assert result["step_id"] == "streams"
        data = {"host": "192.168.1.21", "name": "Old", "video_stream": "doorbell", "talk_stream": "talk"}
        result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
        assert result["errors"] == {"base": "invalid_input"}
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {**data, "host": "192.168.1.20"})
        assert result["reason"] == "reconfigure_successful"
        assert entry.unique_id == "192.168.1.20"
        assert entry.data["camera_entity"] == "camera.generic"


async def test_options_persist_duration(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="192.168.1.20", data={"host": "192.168.1.20"})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"max_duration": 240})
    assert result["type"] == "create_entry"
    assert entry.options["max_duration"] == 240
    assert '240' in settings_path(hass.config.config_dir, "192.168.1.20").read_text()


async def test_old_entry_panel_reload_and_websocket(hass, hass_ws_client):
    assert await async_setup_component(hass, "frontend", {})
    entry = MockConfigEntry(domain=DOMAIN, unique_id="192.168.1.20", data={"host": "192.168.1.20"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert frontend.async_panel_exists(hass, "aqara-talk")
    panel = hass.data[frontend.DATA_PANELS]["aqara-talk"]
    assert panel.require_admin
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "aqara_talk/list"})
    result = await client.receive_json()
    assert result["result"]["entries"][0]["entry_id"] == entry.entry_id
    await client.send_json({"id": 2, "type": "aqara_talk/setup", "entry_id": entry.entry_id})
    assert (await client.receive_json())["result"]["status"] == "unconfigured"
    await client.send_json({"id": 3, "type": "aqara_talk/setup", "entry_id": "other-domain"})
    assert (await client.receive_json())["error"]["code"] == "not_found"
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert hass.data[frontend.DATA_PANELS]["aqara-talk"] is panel
    assert await hass.config_entries.async_remove(entry.entry_id)
    assert not frontend.async_panel_exists(hass, "aqara-talk")


async def test_websocket_denies_non_admin(hass, hass_ws_client, hass_read_only_access_token):
    from custom_components.aqara_talk.panel import ws_list, ws_setup
    from homeassistant.components import websocket_api
    websocket_api.async_register_command(hass, ws_list)
    websocket_api.async_register_command(hass, ws_setup)
    client = await hass_ws_client(hass, hass_read_only_access_token)
    for serial, command in enumerate(("aqara_talk/list", "aqara_talk/setup"), 1):
        data = {"id": serial, "type": command}
        if command.endswith("setup"):
            data["entry_id"] = "anything"
        await client.send_json(data)
        assert (await client.receive_json())["error"]["code"] == "unauthorized"


@pytest.mark.parametrize('change,status', [
    ({}, 'ready_to_test'),
    ({'frigate_entry_id': 'new-owner'}, 'runtime_changed'),
    ({'frigate_client_id': 'new-client'}, 'runtime_changed'),
    ({'runtime_url': 'http://other-frigate:5000'}, 'runtime_changed'),
    ({'talk_hosts': {'talk': '192.168.1.99'}}, 'talk_camera_mismatch'),
    ({'talk_streams': []}, 'talk_stream_missing'),
    ({'video_hosts': {'doorbell': '192.168.1.99'}}, 'video_camera_mismatch'),
])
async def test_setup_verifies_current_owner_and_camera(hass, hass_ws_client, change, status):
    from custom_components.aqara_talk.panel import ws_setup
    from homeassistant.components import websocket_api
    websocket_api.async_register_command(hass, ws_setup)
    data = {key: FOUND[key] for key in ('runtime_kind','runtime_url','frigate_entry_id','frigate_client_id')}
    data.update(host='192.168.1.20', camera_entity='camera.doorbell', video_stream='doorbell', talk_stream='talk')
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)
    hass.data[DOMAIN] = {entry.entry_id: data}
    client = await hass_ws_client(hass)
    with patch('custom_components.aqara_talk.panel.discover', AsyncMock(return_value={**FOUND, **change})):
        await client.send_json({'id':1,'type':'aqara_talk/setup','entry_id':entry.entry_id})
        result = (await client.receive_json())['result']
    assert result['status'] == status
    if status != 'ready_to_test':
        assert result['card'] is None


async def test_malformed_entry_returns_safe_status(hass, hass_ws_client):
    from custom_components.aqara_talk.panel import ws_setup
    from homeassistant.components import websocket_api
    websocket_api.async_register_command(hass, ws_setup)
    entry = MockConfigEntry(domain=DOMAIN, data={'camera_entity':'camera.doorbell','video_stream':'doorbell'})
    entry.add_to_hass(hass)
    hass.data[DOMAIN] = {entry.entry_id: dict(entry.data)}
    client = await hass_ws_client(hass)
    await client.send_json({'id':1,'type':'aqara_talk/setup','entry_id':entry.entry_id})
    result = (await client.receive_json())['result']
    assert result['status'] == 'invalid_response'
    assert result['card'] is None
