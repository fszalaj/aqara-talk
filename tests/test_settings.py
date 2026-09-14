"""Settings handoff checks without camera access or a Home Assistant installation."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from test_bridge import b
from test_config import COMPONENT, config


class SettingsTests(unittest.TestCase):
    def test_strict_reader_and_cli_failure_before_run(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "settings.json"
            for duration in (1, 180, 3600):
                target.write_text(json.dumps({"max_duration": duration}))
                self.assertEqual(b.read_settings(str(target)), duration)
            invalid = [b"", b"{", b"[]", b"null", b'{}', b'{"max_duration":1,"other":2}',
                       b'\xff', b' ' * 4097]
            invalid += [json.dumps({"max_duration": value}).encode()
                        for value in (True, False, 0, 3601, 1.0, "180", None)]
            for raw in invalid:
                with self.subTest(raw=raw[:80]):
                    target.write_bytes(raw)
                    self.assert_cli_rejected(["--settings-file", str(target)], str(target))
            target.unlink()
            self.assert_cli_rejected(["--settings-file", str(target)], str(target))
            self.assert_cli_rejected(["--settings-file", "relative.json"], "absolute")
            self.assert_cli_rejected(["--settings-file", ""], "absolute")
            self.assert_cli_rejected(["--settings-file", str(target), "--probe"], "--probe")
            self.assert_cli_rejected(["--settings-file", str(target), "--max-duration", "20"],
                                     "not allowed")
            with patch.object(Path, "open", side_effect=PermissionError("denied")):
                self.assert_cli_rejected(["--settings-file", str(target)], str(target))

    def assert_cli_rejected(self, arguments, message):
        with patch.object(sys, "argv", ["bridge", "192.168.1.20", *arguments]), \
             patch.object(b, "run") as run, patch.object(b.socket, "socket") as socket, \
             patch.object(b.subprocess, "Popen") as popen, \
             patch.object(sys, "stderr", new_callable=io.StringIO) as stderr:
            with self.assertRaises(SystemExit) as error:
                b.main()
            self.assertEqual(error.exception.code, 2)
            self.assertIn(message, stderr.getvalue())
            run.assert_not_called()
            socket.assert_not_called()
            popen.assert_not_called()

    def test_cli_defaults_direct_duration_and_fresh_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "settings.json"
            for arguments, expected in (([], 180), (["--max-duration", "42"], 42),
                                        (["--probe", "--max-duration", "20"], 20),
                                        (["--settings-file", str(target)], 60),
                                        (["--settings-file", str(target)], 120)):
                target.write_text(json.dumps({"max_duration": expected}))
                with patch.object(sys, "argv", ["bridge", "192.168.1.20", *arguments]), \
                     patch.object(b, "run") as run, patch.object(b.signal, "signal"), \
                     patch.object(b.select, "select", return_value=([0], [], [])), \
                     patch.object(b.os, "read", return_value=b""):
                    self.assertEqual(b.main(), 0)
                    self.assertEqual(run.call_args.args[0].max_duration, expected)


class OptionsTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_awaits_write_and_reports_storage_failure(self):
        class ConfigFlow:
            def __init_subclass__(cls, **kwargs):
                pass
        modules = {
            "homeassistant": SimpleNamespace(config_entries=SimpleNamespace(
                ConfigFlow=ConfigFlow, OptionsFlow=object)),
            "homeassistant.core": SimpleNamespace(callback=lambda f: f),
            "homeassistant.helpers": SimpleNamespace(selector=SimpleNamespace(
                NumberSelector=lambda value: int, NumberSelectorConfig=lambda **kw: kw,
                NumberSelectorMode=SimpleNamespace(BOX="box"))),
            "aqara_talk_options.config": config,
            "aqara_talk_options.runtime": SimpleNamespace(RuntimeDiscoveryError=ValueError, discover=AsyncMock()),
        }
        spec = importlib.util.spec_from_file_location(
            "aqara_talk_options.config_flow", COMPONENT / "config_flow.py")
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            flow = module.AqaraTalkOptionsFlow()
            flow.config_entry = SimpleNamespace(data={"host": "192.168.1.20"}, options={})
            target = config.settings_path(directory, "192.168.1.20")
            async def executor(func, *args):
                flow.async_create_entry.assert_not_called()
                return func(*args)
            flow.hass = SimpleNamespace(config=SimpleNamespace(config_dir=directory),
                                        async_add_executor_job=executor)
            flow.async_create_entry = Mock(return_value={"type": "create_entry"})
            flow.async_show_form = Mock(side_effect=lambda **kwargs: kwargs)
            self.assertEqual(await flow.async_step_init({"max_duration": 75.0}),
                             {"type": "create_entry"})
            self.assertEqual(json.loads(target.read_text()), {"max_duration": 75})
            flow.async_create_entry.assert_called_once_with(title="", data={"max_duration": 75})
            flow.async_create_entry.reset_mock()
            flow.hass.async_add_executor_job = AsyncMock(side_effect=OSError("read only"))
            result = await flow.async_step_init({"max_duration": 100})
            self.assertEqual(result["errors"], {"base": "storage_error"})
            flow.async_create_entry.assert_not_called()
            self.assertEqual(json.loads(target.read_text()), {"max_duration": 75})
            flow.hass.async_add_executor_job.reset_mock()
            result = await flow.async_step_init({"max_duration": True})
            self.assertEqual(result["errors"], {"base": "invalid_duration"})
            flow.hass.async_add_executor_job.assert_not_called()


if __name__ == "__main__":
    unittest.main()
