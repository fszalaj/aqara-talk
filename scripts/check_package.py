"""Offline packaging and copyable example contracts."""

import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
from urllib.parse import parse_qs, urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components/aqara_talk"
manifest = json.loads((COMPONENT / "manifest.json").read_text())
assert manifest["domain"] == "aqara_talk"
assert {p.name for p in COMPONENT.parent.iterdir() if p.is_dir()} == {"aqara_talk"}
for key in ("name", "version", "documentation", "issue_tracker", "codeowners"):
    assert manifest[key], key
assert json.loads((ROOT / "hacs.json").read_text()) == {"name": "Aqara Talk"}
readme = (ROOT / "README.md").read_text()
for redirect, params in (
    ("hacs_repository", {"owner": ["fszalaj"], "repository": ["aqara-talk"], "category": ["integration"]}),
    ("config_flow_start", {"domain": [manifest["domain"]]}),
):
    links = re.findall(r"\]\((https://my\.home-assistant\.io/redirect/[^)]+)\)", readme)
    assert any(urlparse(link).path == f"/redirect/{redirect}/"
               and parse_qs(urlparse(link).query) == params for link in links), redirect
icon = (COMPONENT / "brand/icon.png").read_bytes()
assert icon[:8] == b"\x89PNG\r\n\x1a\n"
assert struct.unpack(">II", icon[16:24]) == (512, 512)
for path in ROOT.rglob("*.md"):
    if ".venv" in path.parts:
        continue
    for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
        if not target.startswith(("https://", "http://", "#")):
            assert (path.parent / target.split("#")[0]).exists(), (path, target)

examples = {p.stem: yaml.safe_load(p.read_text()) for p in (ROOT / "examples").glob("*.yaml")}
spec = importlib.util.spec_from_file_location("config", COMPONENT / "config.py")
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)
sources = config.get_config({"test": {"host": "192.0.2.10"}})["sources"]
for filename, runtime, kind in (
    ("frigate", "frigate", "talk_source"),
    ("frigate-probe", "frigate", "probe_source"),
    ("go2rtc", "generic", "talk_source"),
):
    example = examples[filename]
    streams = example.get("go2rtc", example)["streams"]
    assert streams["aqara_talk"][1].replace("REPLACE_CAMERA_IP", "192.0.2.10") == sources[runtime][kind]
    assert streams["aqara_talk"][0].endswith("?video=h264&audio=opus&audio=aac#backchannel=0")
    assert streams["doorbell"][1] == "ffmpeg:doorbell#audio=opus"

card = examples["card"]
webrtc = examples["webrtc-card"]
assert webrtc["type"] == "custom:webrtc-camera" and webrtc["ui"] is True
assert len(webrtc["streams"]) == 2
for stream, name, media in zip(webrtc["streams"], ("Listen", "Speak"), ("video,audio", "video,audio,microphone")):
    assert stream == {"url": "aqara_talk", "name": name, "mode": "webrtc", "media": media}
assert examples["camera-view"]["cards"][0]["cards"][0] == card
assert card["live"]["auto_unmute"] == ["call"]
assert card["live"]["auto_mute"] == ["call"]
assert card["live"]["microphone"] == {"always_connected": False, "auto_unmute": ["call"]}
template = examples["view-assist-camera"]["custom_fields"]["camera"]["card"].strip()
assert template.startswith("[[[") and template.endswith("]]]")
body = template[3:-3]
for entity in ("camera.aqara_doorbell", "camera.aqara_doorbell_snapshot", "camera.other"):
    script = "const variables = " + json.dumps({"var_camera": entity}) + ";\n"
    script += "console.log(JSON.stringify((function(){" + body + "})()));"
    result = json.loads(subprocess.check_output(["node", "-e", script], text=True))
    if entity == "camera.other":
        assert result["type"] == "picture-entity" and result["entity"] == entity
    else:
        assert result["cards"][0] == card
print(f"Package, HACS links and {len(examples)} YAML example contracts passed.")
