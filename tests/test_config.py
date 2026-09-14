"""Offline contracts only; these tests do not claim Home Assistant runtime validation."""

import importlib.util
import json
from pathlib import Path
import shlex
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import voluptuous as vol

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/aqara_talk"
spec = importlib.util.spec_from_file_location("aqara_talk_config", COMPONENT / "config.py")
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


class ConfigTests(unittest.TestCase):
    def test_numeric_camera_address(self):
        self.assertEqual(config.camera_ip("192.168.1.20"), "192.168.1.20")
        for host in ("camera.local", "127.0.0.1", "0.0.0.0", "224.0.0.1",
                     "255.255.255.255", "::", "::1", "ff02::1", "fe80::1%eth0",
                     "fd00::20", "::ffff:127.0.0.1", "192.168.1.20;id", "192.168.1.20#x", "../camera", "192.168.1.20/../camera", 123):
            with self.subTest(host=host), self.assertRaises(vol.Invalid):
                config.camera_ip(host)

    def test_form_and_service_schema(self):
        self.assertEqual(config.INPUT_SCHEMA({"host": "192.168.1.20", "name": " Door "}),
                         {"host": "192.168.1.20", "name": "Door"})
        for data in ({}, {"host": "192.168.1.20", "name": " "},
                     {"host": "192.168.1.20", "command": "id"}):
            with self.subTest(data=data), self.assertRaises(vol.Invalid):
                config.INPUT_SCHEMA(data)
        self.assertEqual(config.SERVICE_SCHEMA({}), {})
        self.assertEqual(config.SERVICE_SCHEMA({"entry_id": "one"}), {"entry_id": "one"})
        for data in ({"entry_id": ""}, {"host": "192.168.1.20"}):
            with self.assertRaises(vol.Invalid):
                config.SERVICE_SCHEMA(data)

    def test_selection_preserves_entries(self):
        entries = {"one": {"host": "192.168.1.20"}, "two": {"host": "192.168.1.21"}}
        before = json.dumps(entries, sort_keys=True)
        self.assertEqual(config.get_config(entries, "two")["host"], "192.168.1.21")
        for selected in (None, "missing"):
            with self.assertRaises(ValueError):
                config.get_config(entries, selected)
        with self.assertRaises(ValueError):
            config.get_config({})
        self.assertEqual(json.dumps(entries, sort_keys=True), before)
        self.assertEqual(config.get_config({"one": entries["one"]})["entry_id"], "one")

    def test_sources(self):
        result = config.get_config({"one": {"host": "192.168.1.20"}})
        self.assertEqual(result["max_duration"], 180)
        for runtime, base in (("frigate", "/homeassistant"), ("generic", "/config")):
            sources = result["sources"][runtime]
            for kind, source in sources.items():
                command, *options = source.split("#")
                self.assertEqual(options, ["backchannel=1", "audio=pcma/8000",
                                           "killsignal=15", "killtimeout=5"])
                args = shlex.split(command.removeprefix("exec:"))
                self.assertEqual(args[:5], ["python3", f"{base}/custom_components/aqara_talk/bridge.py",
                                            "192.168.1.20", "--input-format", "alaw"])
                if kind == "probe_source":
                    self.assertEqual(args[args.index("--max-duration") + 1], "20")
                else:
                    self.assertNotIn("--max-duration", args)
                    self.assertEqual(args[args.index("--settings-file") + 1],
                                     f"{base}/aqara_talk/192.168.1.20.json")
                self.assertEqual("--probe" in args, kind == "probe_source")
                if kind == "probe_source":
                    self.assertEqual(args[-2:], ["--probe-report", "/config/aqara-talk-probe.json"])

    def test_hacs_metadata(self):
        manifest = json.loads((COMPONENT / "manifest.json").read_text())
        self.assertEqual((manifest["domain"], manifest["version"]), ("aqara_talk", "0.1.0"))
        self.assertTrue(manifest["config_flow"])
        self.assertEqual(manifest["requirements"], [])
        self.assertEqual(json.loads((ROOT / "hacs.json").read_text())["name"], "Aqara Talk")
        strings = json.loads((COMPONENT / "strings.json").read_text())
        self.assertEqual(strings, json.loads((COMPONENT / "translations/en.json").read_text()))
        self.assertEqual(strings["config"]["step"]["user"]["data"].keys(),
                         json.loads((COMPONENT / "translations/pl.json").read_text())
                         ["config"]["step"]["user"]["data"].keys())
        self.assertIn("Copyright (c) 2026 fszalaj", (ROOT / "LICENSE").read_text())
        self.assertEqual((ROOT / "LICENSE").read_bytes(), (COMPONENT / "LICENSE").read_bytes())

    def test_duration_validation_and_sources(self):
        self.assertEqual(config.OPTIONS_SCHEMA({}), {"max_duration": 180})
        for value in (1, 180, 180.0, 3600, 3600.0):
            with self.subTest(value=value):
                duration = config.OPTIONS_SCHEMA({"max_duration": value})["max_duration"]
                self.assertIs(type(duration), int)
                result = config.get_config({"one": {"host": "192.168.1.20", "max_duration": value}})
                self.assertEqual(result["max_duration"], int(value))
                for sources in result["sources"].values():
                    self.assertIn("/aqara_talk/192.168.1.20.json#", sources["talk_source"])
                    self.assertIn("--max-duration 20 --probe", sources["probe_source"])
        for value in (True, False, 0, -1, 3601, 180.5, float("nan"), float("inf"),
                      float("-inf"), "180", "180;id", None, [], {}):
            with self.subTest(value=value), self.assertRaises(vol.Invalid):
                config.OPTIONS_SCHEMA({"max_duration": value})


    def test_atomic_settings_and_failure_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            target = config.settings_path(directory, "192.168.1.20")
            config.write_settings(directory, "192.168.1.20", 180)
            original_replace = config.os.replace
            def replace(source, destination):
                self.assertEqual(Path(source).stat().st_mode & 0o777, 0o644)
                self.assertEqual(json.loads(target.read_text()), {"max_duration": 180})
                original_replace(source, destination)
            with patch.object(config.os, "replace", side_effect=replace):
                config.write_settings(directory, "192.168.1.20", 60)
            self.assertEqual(json.loads(target.read_text()), {"max_duration": 60})
            self.assertEqual(target.parent.stat().st_mode & 0o777, 0o755)
            with patch.object(config.os, "replace", side_effect=OSError("read only")):
                with self.assertRaises(OSError):
                    config.write_settings(directory, "192.168.1.20", 90)
            self.assertEqual(list(target.parent.iterdir()), [target])
            self.assertEqual(json.loads(target.read_text()), {"max_duration": 60})
            for host in ("../escape", "camera.local", "::1"):
                with self.assertRaises(vol.Invalid):
                    config.settings_path(directory, host)


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_fresh_options_multiple_entries_and_cleanup(self):
        modules = {
            "homeassistant.core": SimpleNamespace(SupportsResponse=SimpleNamespace(ONLY="only")),
            "homeassistant.exceptions": SimpleNamespace(ServiceValidationError=ValueError,
                                                       ConfigEntryNotReady=RuntimeError,
                                                       ConfigEntryError=ValueError),
            "aqara_talk_service.config": config,
            "aqara_talk_service.panel": SimpleNamespace(async_register_panel=AsyncMock(), PANEL_PATH="aqara-talk"),
            "homeassistant.components": SimpleNamespace(frontend=SimpleNamespace(async_remove_panel=Mock())),
        }
        self.enterContext(patch.dict(sys.modules, modules))
        spec = importlib.util.spec_from_file_location("aqara_talk_service", COMPONENT / "__init__.py")
        integration = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(integration)
        entries = {
            "one": SimpleNamespace(entry_id="one", data={"host": "192.168.1.20"}, options={}),
            "two": SimpleNamespace(entry_id="two", data={"host": "192.168.1.21"},
                                   options={"max_duration": 60}),
        }
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        for entry in entries.values():
            entry.async_on_unload = Mock()
            entry.add_update_listener = Mock(return_value=Mock())
        async def executor(func, *args):
            return func(*args)
        services = Mock()
        services.has_service.return_value = False
        hass = SimpleNamespace(data={}, services=services,
                               config=SimpleNamespace(config_dir=temporary.name),
                               async_add_executor_job=executor,
                               config_entries=SimpleNamespace(async_get_entry=entries.get,
                                   async_entries=lambda domain: list(entries.values())))
        await integration.async_setup_entry(hass, entries["one"])
        path = config.settings_path(temporary.name, entries["one"].data["host"])
        self.assertEqual(json.loads(path.read_text()), {"max_duration": 180})
        entries["one"].add_update_listener.assert_called_once_with(integration.async_options_updated)
        entries["one"].async_on_unload.assert_called_once_with(
            entries["one"].add_update_listener.return_value)
        handler = services.async_register.call_args.args[2]
        call = SimpleNamespace(data={})
        entries["one"].options = {"max_duration": True}
        with self.assertRaises(ValueError):
            await handler(call)
        entries["one"].options = {}
        self.assertEqual((await handler(call))["max_duration"], 180)
        entries["one"].options = {"max_duration": 240.0, "host": "192.168.1.99"}
        await integration.async_options_updated(hass, entries["one"])
        self.assertEqual(json.loads(path.read_text()), {"max_duration": 240})
        with patch.object(integration, "write_settings", side_effect=OSError("read only")):
            with self.assertLogs(integration._LOGGER, level="ERROR"):
                await integration.async_options_updated(hass, entries["one"])
        with patch.object(integration, "write_settings", side_effect=vol.Invalid("invalid duration")):
            with self.assertLogs(integration._LOGGER, level="ERROR"):
                await integration.async_options_updated(hass, entries["one"])
        result = await handler(call)
        self.assertEqual((result["max_duration"], result["host"]), (240, "192.168.1.20"))
        services.has_service.return_value = True
        await integration.async_setup_entry(hass, entries["two"])
        services.async_register.assert_called_once()
        with self.assertRaises(ValueError):
            await handler(call)
        for entry_id, duration in (("one", 240), ("two", 60)):
            result = await handler(SimpleNamespace(data={"entry_id": entry_id}))
            self.assertEqual(result["max_duration"], duration)
        removed = entries.pop("two")
        with self.assertRaises(ValueError):
            await handler(SimpleNamespace(data={"entry_id": "two"}))
        await integration.async_unload_entry(hass, removed)
        services.async_remove.assert_not_called()
        await integration.async_unload_entry(hass, entries["one"])
        services.async_remove.assert_called_once_with(config.DOMAIN, "get_config")
        self.assertNotIn(config.DOMAIN, hass.data)
        self.assertTrue(path.exists())
        await integration.async_remove_entry(hass, entries["one"])
        self.assertFalse(path.exists())
        self.assertTrue(config.settings_path(temporary.name, removed.data["host"]).exists())
        with patch.object(integration, "write_settings", side_effect=OSError("read only")):
            with self.assertRaises(RuntimeError):
                await integration.async_setup_entry(hass, entries["one"])
        self.assertNotIn(config.DOMAIN, hass.data)
        with self.assertRaises(ValueError):
            await handler(call)
        with patch.object(integration, "write_settings", side_effect=vol.Invalid("bad settings")):
            with self.assertRaises(ValueError):
                await integration.async_setup_entry(hass, entries["one"])
        self.assertNotIn(config.DOMAIN, hass.data)


if __name__ == "__main__":
    unittest.main()
