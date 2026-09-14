"""Runtime read-only discovery and secret redaction contracts."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from homeassistant.helpers import entity_registry
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.aqara_talk.runtime import RuntimeDiscoveryError, build_setup, discover, validate_url


def camera(hass):
    entry = MockConfigEntry(domain="frigate", data={"url": "http://192.168.1.2:5000"})
    entry.add_to_hass(hass)
    registered = entity_registry.async_get(hass).async_get_or_create(
        "camera", "frigate", "door-camera", config_entry=entry, suggested_object_id="door")
    hass.states.async_set(registered.entity_id, "idle", {"camera_name": "door", "client_id": "frigate_custom"})
    return entry, registered.entity_id


@pytest.mark.parametrize("live", [{"streams": {"Main": "video"}}, {"stream_name": "video"}])
async def test_frigate_mapping_redacts_and_accepts_idle(hass, live):
    entry, entity = camera(hass)
    client = MagicMock()
    client.async_get_config = AsyncMock(return_value={"cameras": {"door": {"live": live}}})
    client.api_wrapper = AsyncMock(return_value={
        "video": {"producers": [{"url": "rtsp://private:secret@192.168.1.3/ch1"}]},
        "idle": {"producers": None}, "empty": {"producers": []},
        "talk": {"producers": [{"url": "exec:python3 /config/custom_components/aqara_talk/bridge.py 192.168.1.3"}]},
        "rtsp://private:secret@bad": {},
    })
    hass.data["frigate"] = {entry.entry_id: {"client": client}}
    result = await discover(hass, entity)
    assert result["matches"] == ["video"]
    assert result["suggested_host"] == "192.168.1.3"
    assert result["talk_streams"] == ["talk"]
    assert result["frigate_client_id"] == "frigate_custom"
    assert "secret" not in str(result) and "private" not in str(result)
    assert "idle" in result["streams"] and "empty" in result["streams"]
    client.api_wrapper.assert_awaited_once_with("get", "http://192.168.1.2:5000/api/go2rtc/streams")


async def test_missing_integration_client_and_safe_error(hass):
    hass.states.async_set("camera.generic", "idle")
    with pytest.raises(RuntimeDiscoveryError, match="integration_missing"):
        await discover(hass, "camera.generic")
    entry, entity = camera(hass)
    with pytest.raises(RuntimeDiscoveryError, match="frigate_client_incompatible"):
        await discover(hass, entity)
    client = MagicMock(async_get_config=AsyncMock(side_effect=Exception("private:secret")))
    hass.data["frigate"] = {entry.entry_id: {"client": client}}
    with pytest.raises(RuntimeDiscoveryError, match="cannot_connect") as error:
        await discover(hass, entity)
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("failure", [None, TypeError("private:secret"), AttributeError("private:secret")])
async def test_incompatible_frigate_wrapper_is_safe(hass, failure):
    entry, entity = camera(hass)
    client = MagicMock(async_get_config=AsyncMock(return_value={}))
    client.api_wrapper = None if failure is None else AsyncMock(side_effect=failure)
    hass.data["frigate"] = {entry.entry_id: {"client": client}}
    with pytest.raises(RuntimeDiscoveryError, match="frigate_client_incompatible") as error:
        await discover(hass, entity)
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("base", ["http://192.168.1.2:5000/", "https://proxy.local/frigate/"])
async def test_frigate_exact_endpoint_preserves_port_and_prefix(hass, base):
    entry, entity = camera(hass)
    hass.config_entries.async_update_entry(entry, data={"url": base})
    client = MagicMock(async_get_config=AsyncMock(return_value={}), api_wrapper=AsyncMock(return_value={}))
    hass.data["frigate"] = {entry.entry_id: {"client": client}}
    await discover(hass, entity)
    client.api_wrapper.assert_awaited_once_with("get", base.rstrip("/") + "/api/go2rtc/streams")


@pytest.mark.parametrize("url", ["http://user:password@host", "http://host?token=secret", "http://host#secret", "http://169.254.169.254", "http://224.0.0.1", "http://0.0.0.0", "file:///tmp/a"])
def test_bad_url(url):
    with pytest.raises(RuntimeDiscoveryError, match="invalid_url"):
        validate_url(url)


@pytest.mark.parametrize("url", ["http://localhost:1984", "http://127.0.0.1:1984", "https://192.168.1.2"])
def test_admin_local_url(url):
    assert validate_url(url) == url


async def response_chunks(body):
    yield body


@pytest.mark.parametrize("status,body,expected", [(401, b"secret", "unauthorized"), (403,b"secret","unauthorized"), (302,b"secret","redirect_not_allowed"), (500,b"secret","cannot_connect"), (200,b"invalid secret","invalid_response"), (200,b"x" * (2*1024*1024+1),"invalid_response")], ids=["unauthorized", "forbidden", "redirect", "server_error", "bad_json", "too_large"])
async def test_http_error_redaction(hass, status, body, expected):
    hass.states.async_set("camera.generic", "idle")
    response = MagicMock(status=status, content_type="application/json", content_length=None)
    response.content.iter_chunked.side_effect = lambda _: response_chunks(body)
    session = MagicMock()
    session.get.return_value.__aenter__ = AsyncMock(return_value=response)
    with patch("custom_components.aqara_talk.runtime.aiohttp_client.async_get_clientsession", return_value=session):
        with pytest.raises(RuntimeDiscoveryError, match=expected) as error:
            await discover(hass, "camera.generic", "go2rtc", "http://localhost:1984")
    assert "secret" not in str(error.value)
    session.get.assert_called_once_with("http://localhost:1984/api/streams", allow_redirects=False)


async def test_standalone_idle(hass):
    hass.states.async_set("camera.generic", "idle")
    response = MagicMock(status=200, content_type="application/json", content_length=None)
    response.content.iter_chunked.return_value = response_chunks(b'{"idle":{"producers":null}}')
    config_response = MagicMock(status=200, content_type="text/plain", content_length=None)
    config_response.content.iter_chunked.return_value = response_chunks(b"streams:\n  idle: rtsp://user:secret@192.168.1.3/ch1")
    session = MagicMock()
    session.get.return_value.__aenter__ = AsyncMock(side_effect=[response, config_response])
    with patch("custom_components.aqara_talk.runtime.aiohttp_client.async_get_clientsession", return_value=session):
        result = await discover(hass, "camera.generic", "go2rtc", "http://localhost:1984")
    assert result["streams"] == ["idle"] and result["suggested_host"] == ""


def test_setup_existing_sources_and_card():
    data = {"host": "192.168.1.3", "camera_entity": "camera.door", "runtime_kind": "frigate", "video_stream": "Door Main", "frigate_client_id": "frigate_custom"}
    setup = build_setup(data)
    sources = yaml.safe_load(setup["runtime_yaml"])["go2rtc"]["streams"][setup["talk_stream"]]
    assert "Door%20Main?" in sources[0]
    assert "--settings-file /homeassistant/aqara_talk/192.168.1.3.json" in sources[1]
    assert setup["card"]["live"]["auto_mute"] == ["call"]
    assert setup["card"]["live"]["auto_unmute"] == ["call"]
    assert setup["card"]["cameras"][0]["frigate"]["client_id"] == "frigate_custom"
    data.update(runtime_kind="go2rtc", talk_stream="existing_talk", runtime_url="http://go2rtc:1984")
    setup = build_setup(data)
    assert setup["talk_stream"] == "existing_talk"
    assert setup["card"]["server"] == "http://go2rtc:1984"
    assert setup["card"]["streams"][1]["media"] == "video,audio,microphone"
    assert "/config/custom_components/aqara_talk/bridge.py" in setup["runtime_yaml"]


async def test_standalone_idle_bridge_config_and_host(hass):
    hass.states.async_set("camera.generic", "idle")
    stream_response = MagicMock(status=200, content_type="application/json", content_length=None)
    stream_response.content.iter_chunked.return_value = response_chunks(b'{"talk":{"producers":null},"other":{"producers":[]}}')
    config_response = MagicMock(status=200, content_type="text/plain", content_length=None)
    config_response.content.iter_chunked.return_value = response_chunks(b'''streams:
  talk:
    - rtsp://private:secret@192.168.1.3/ch1
    - exec:python3 /config/custom_components/aqara_talk/bridge.py 192.168.1.3 --input-format alaw#backchannel=1
  other:
    - exec:python3 /config/custom_components/aqara_talk/bridge.py 192.168.1.4 --input-format alaw#backchannel=1
''')
    session = MagicMock()
    session.get.return_value.__aenter__ = AsyncMock(side_effect=[stream_response, config_response])
    with patch("custom_components.aqara_talk.runtime.aiohttp_client.async_get_clientsession", return_value=session):
        result = await discover(hass, "camera.generic", "go2rtc", "http://localhost:1984")
    assert result["talk_hosts"] == {"talk": "192.168.1.3", "other": "192.168.1.4"}
    assert "secret" not in str(result) and "private" not in str(result)
    assert [call.args[0] for call in session.get.call_args_list] == ["http://localhost:1984/api/streams", "http://localhost:1984/api/config"]


@pytest.mark.parametrize("source", ["rtsp://secret:secret@127.0.0.1/a", "rtsp://secret:secret@192.168.1.2/a", "rtsp://secret:secret@camera.local/a"])
async def test_no_suggestion_for_restream_or_hostname(hass, source):
    entry, entity = camera(hass)
    client = MagicMock()
    client.async_get_config = AsyncMock(return_value={"cameras": {"door": {"live": {"stream_name": "video"}}}})
    client.api_wrapper = AsyncMock(return_value={"video": {"producers": [{"url": source}]}})
    hass.data["frigate"] = {entry.entry_id: {"client": client}}
    result = await discover(hass, entity)
    assert result["suggested_host"] == "" and "secret" not in str(result)


async def test_frigate_auth_cause(hass):
    from aiohttp import ClientResponseError
    entry, entity = camera(hass)
    error = Exception("secret")
    error.__cause__ = ClientResponseError(MagicMock(), (), status=401, message="secret")
    client = MagicMock(async_get_config=AsyncMock(side_effect=error))
    hass.data["frigate"] = {entry.entry_id: {"client": client}}
    with pytest.raises(RuntimeDiscoveryError, match="unauthorized"):
        await discover(hass, entity)


async def test_http_timeout(hass):
    hass.states.async_set("camera.generic", "idle")
    session = MagicMock()
    session.get.return_value.__aenter__ = AsyncMock(side_effect=TimeoutError("secret"))
    with patch("custom_components.aqara_talk.runtime.aiohttp_client.async_get_clientsession", return_value=session):
        with pytest.raises(RuntimeDiscoveryError, match="cannot_connect"):
            await discover(hass, "camera.generic", "go2rtc", "http://localhost:1984")


@pytest.mark.parametrize('state', ['unknown', 'unavailable'])
async def test_offline_camera_is_not_reported_as_owner_drift(hass, state):
    hass.states.async_set('camera.offline', state)
    with pytest.raises(RuntimeDiscoveryError) as error:
        await discover(hass, 'camera.offline')
    assert error.value.code == 'camera_unavailable'
