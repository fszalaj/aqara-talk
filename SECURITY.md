# Security and privacy

The camera control protocol used here does not authenticate speaker requests. Restrict camera control TCP 54324 and audio UDP 54323 to the trusted runtime; do not expose these ports publicly. Keep go2rtc administration private and use Home Assistant's authenticated proxy with trusted HTTPS for viewers.

The Aqara Talk sidebar and its setup WebSocket commands require a Home Assistant administrator. It loads a separately installed, registered camera-card resource. A copied card on another dashboard follows Home Assistant's normal dashboard access rules.

Runtime discovery reads configuration and stream metadata without starting the speaker or writing remote configuration. Frigate discovery reuses the owning integration's client and authentication. Explicit standalone URLs accept HTTP(S) without embedded credentials, query strings or fragments; requests reject redirects and enforce time and response-size limits. Discovery returns selected names and safe diagnostics instead of raw source URLs or credentials. The selected entity, runtime URL, stream names and camera IPv4 are stored as integration configuration; protect Home Assistant and its backups.

HACS downloads files into Home Assistant; it cannot grant access to a separate runtime. Check the generated paths, runtime permissions and persistent YAML before applying a fragment. A configured bridge stream is readiness evidence only, not proof that microphone data arrives or the physical speaker works.

An `exec` source runs a command inside the go2rtc runtime. Only trusted administrators should edit its configuration, bridge code or settings. Enabling Frigate's arbitrary exec option permits configured commands to run in that container. Mount the component and settings directories read-only into the runtime.

Home Assistant writes call settings to `<config_dir>/aqara_talk/<cameraIPv4>.json` (normally under `/config`). The file contains only the duration, without credentials; its filename reveals the camera's LAN address. The settings directory is set to mode `0755` and files to `0644` so another runtime user can read them. Protect the host and its backups accordingly. A missing, unreadable or invalid settings file prevents talkback from starting; it does not stop the existing video source.

The default call limit is 180 seconds and can be changed in the integration UI. The diagnostic probe has a separate 20-second limit. Direct CLI users can select `--max-duration` instead of `--settings-file`. The per-camera lock coordinates only bridge processes sharing a temporary directory; it does not lock out separate runtimes or camera applications.

Do not attach credentials, addresses, device IDs, recordings, microphone samples, full Home Assistant exports or unredacted logs to issues. Share versions, the failing stage and redacted diagnostic counters. Report vulnerabilities through GitHub's private vulnerability-reporting feature when available; otherwise open a minimal issue asking for a private contact without disclosing an exploit or secrets.

If a credential enters Git history, rotate it and remove it from reachable history. Ignoring or deleting the working file is insufficient.
