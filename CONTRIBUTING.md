# Contributing

Use Python 3.13 on Linux or macOS, Node.js for the View Assist template contract check, and FFmpeg with the AAC encoder available on PATH. Install `requirements-dev.txt` in a virtual environment, then run:

```sh
python -m unittest discover -s tests -v
python scripts/check_package.py
gitleaks dir --redact .
gitleaks git --redact .
```

These are the offline bridge, settings and package checks. They do not import Home Assistant and do not replace the Home Assistant integration tests below.

For config-flow, runtime discovery and panel integration checks, use a separate Python 3.14 environment compatible with Home Assistant 2026.9.2. Install `requirements-test-ha.txt`, then run from the repository root:

```sh
python -m pip install -r requirements-test-ha.txt
python -m pytest tests_ha
node --check custom_components/aqara_talk/frontend/panel.js
node --test tests_js/*.test.mjs
```

The Home Assistant suite uses the actual Home Assistant test runtime with mocked network responses. It covers native flows, discovery and admin/panel contracts without changing a remote Frigate/go2rtc configuration. Keep this environment separate from the lightweight offline test dependencies. The Node checks exercise frontend contracts; they do not replace a browser check of native forms, resource loading and card rendering.

Tests use local sockets, synthetic audio and mock camera sessions; they do not call a physical doorbell. Keep FFmpeg installed so encoder tests do not silently skip. Offline tests do not establish native microphone permission, firmware compatibility or acoustic success.

Keep changes small. For bridge changes, cover cancellation, STOP/cleanup, concurrent callers and settings validation with runnable tests. Verify two-way sound and recording continuity on hardware before making new compatibility claims. Use one existing go2rtc runtime.

Keep credentials, private hostnames, camera addresses, recordings and unredacted logs out of patches and issues. Review examples and commit metadata as well as automated secret scans.

For releases, keep the manifest version, release tag and changelog consistent. Run the checks from a fresh checkout and inspect CI. CI must not run physical camera tests. HACS custom repository installation is separate from inclusion in its default catalog.
