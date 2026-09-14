# Runtime setup

Install Aqara Talk through the [HACS buttons in the README](../README.md#install-with-hacs), restart Home Assistant and add the integration. You need an existing Home Assistant camera and a working video stream in your existing Frigate or go2rtc runtime. Start with [enabling RTSP and adding the camera](camera.md) if either is missing.

## 1. Select the camera and inspect the runtime

1. Select your existing camera entity in the native integration form. For a Frigate camera, Aqara Talk discovers the owning Frigate instance and its configured live stream names through the installed integration. It reuses that integration's authentication.
2. For another camera integration, enter your existing go2rtc API base URL, reachable from Home Assistant, such as `http://GO2RTC_HOST:1984`. Use HTTP or HTTPS without embedded credentials, query strings or fragments. This is the runtime URL, not the camera's address. Home Assistant's internal go2rtc is not automatically selected.
3. Choose the video stream from the available names. Exact Frigate mappings can suggest it; ambiguous mappings require your choice. An idle stream is valid. If the list is empty, configure your original video stream in the runtime and retry.
4. Optionally select an existing talk stream for this camera. It must be distinct from the video stream; otherwise the generated relay would point to itself. The detected bridge command must target the same physical camera IPv4. Otherwise leave this blank so the panel proposes a separate relay name. Confirm the **physical camera's numeric unicast IPv4 address**, even when a source provides a suggestion. Hostnames and IPv6 are not accepted. Keep or edit the suggested display name.
5. Open **Aqara Talk** in the sidebar. This admin-only panel shows diagnostics and the generated runtime YAML. After setup, use **Recheck** to refresh discovery. When the selected video and bridge stream are found, the panel loads your installed viewer card automatically. **Ready to test** is a configuration check, not proof of microphone delivery or audible speech.

Frigate discovery has been verified with integration 5.15.6. If the installed client cannot provide the required API, setup reports an incompatibility instead of bypassing its authentication.

Existing address-only entries continue working. On the integration entry, use **Reconfigure** to select the camera and runtime. **Configure** changes call duration. One entry is allowed per physical camera IPv4. Reconfigure preserves that address; if it changes, remove and re-add the entry and update the runtime's settings path.

### Configuration action

The sidebar is the normal setup path. You can also run this response action in **Developer tools > Actions**:

```yaml
action: aqara_talk.get_config
data: {}
```

The response retains `sources.frigate` and `sources.generic`, each with `probe_source` and `talk_source`, alongside the entry's address and duration. Camera/runtime-linked entries also return `card`, `runtime_yaml` and `talk_stream`. Existing address-only entries retain their original response. With multiple cameras, pass the desired configuration entry's `entry_id` in `data`.

This action only generates configuration. The panel's Recheck reads runtime metadata; neither operation contacts the camera speaker or changes remote runtime configuration. No temporary go2rtc API stream write substitutes for persistent host setup.

## 2. Connect your existing go2rtc

Enable Aqara LAN RTSP and use wired power for the G410. Back up the configuration and start with working video. Keep **one go2rtc instance and its existing physical camera source**. The sidebar generates a fragment using your selected stream names. The static examples use `doorbell` for video and `aqara_talk` for the talk relay; replace those example names consistently. Merge the generated fragment into existing YAML without replacing other streams or camera configuration. The relay assumes a local RTSP listener on port 8554 without authentication; adjust its URL to your existing RTSP port and authentication settings.

Replace `REPLACE_*` values only in your private configuration. URL-percent-encode RTSP credentials. For Frigate, prefer externally supplied `FRIGATE_` variables and supported `{FRIGATE_VARIABLE_NAME}` substitution; its YAML `environment_vars` section still stores values in plaintext. See [Frigate environment variables](https://docs.frigate.video/configuration/advanced/#environment_vars).

The go2rtc runtime must reach the camera on TCP 54324 and UDP 54323. Keep its API restricted to trusted local services; do not expose port 1984 to the internet. Only trusted administrators should edit `exec` sources, which run processes inside the runtime.

### Runtime paths and mounts

On integration setup, Home Assistant creates `<config_dir>/aqara_talk/<cameraIPv4>.json` (normally `/config/aqara_talk/<cameraIPv4>.json`) containing the call duration. The generated paths below are defaults; verify them **inside the container or host actually running go2rtc**, and adjust the generated commands if your installation uses different paths.

| Runtime | Bridge path | Settings path | FFmpeg path |
| --- | --- | --- | --- |
| Frigate Home Assistant app (`sources.frigate`) | `/homeassistant/custom_components/aqara_talk/bridge.py` | `/homeassistant/aqara_talk/<cameraIPv4>.json` | `/usr/lib/ffmpeg/7.0/bin/ffmpeg` |
| go2rtc or Frigate Docker (`sources.generic`) | `/config/custom_components/aqara_talk/bridge.py` | `/config/aqara_talk/<cameraIPv4>.json` | `/usr/bin/ffmpeg` |

Frigate includes Python 3 and FFmpeg. For standalone go2rtc, provide both, with AAC and Opus encoding available. Check `python3 --version`, the actual FFmpeg binary's `-version`, and read access to both the bridge and settings file inside the runtime. HACS downloads the bridge to Home Assistant; it cannot install dependencies, create mounts or grant exec permission in another runtime. Prepare these once on the actual runtime host before applying the generated fragment. A generated command cannot establish these prerequisites.

For Docker, mount **both directories read-only** from the host paths holding Home Assistant's files, for example:

```yaml
volumes:
  - /HOST_HA_CONFIG/custom_components/aqara_talk:/config/custom_components/aqara_talk:ro
  - /HOST_HA_CONFIG/aqara_talk:/config/aqara_talk:ro
```

Replace `/HOST_HA_CONFIG` with the real host path. Both source directories must exist before starting the container; add the integration first so it creates the settings directory. Mount the **settings directory**, not one JSON file: Home Assistant atomically replaces files when settings change, and a single-file mount can retain an old value. Home Assistant needs write access to its own settings directory; the go2rtc runtime needs only read access. Files use mode `0644` and contain no credentials, but their names contain camera LAN addresses.

For the Frigate Home Assistant app, confirm its `/homeassistant` mapping exposes both directories and use read-only access where the app supports it. A separate Docker mount example does not configure an app's managed mounts. If either path is unavailable in your app version, provide a supported mapping before enabling talkback.

The diagnostic report also needs a writable `/config` location inside the runtime, outside the read-only component and settings mounts. Missing, invalid or unreadable call settings prevent talkback; the existing video source remains unaffected.

### Frigate

The Frigate-generated sidebar YAML uses the Home Assistant app paths above. Use `sources.frigate` and [frigate.yaml](../examples/frigate.yaml) for this installation. Set `go2rtc_allow_arbitrary_exec: true` in **Settings > Apps > Frigate > Configuration**. This is an app option, not a key in Frigate YAML. Check the FFmpeg path against your app image.

For Frigate Docker, replace the generated exec command with `sources.generic.talk_source` from the configuration action, use the directory mounts above and keep the `go2rtc:` wrapper in Frigate YAML. Discovery identifies the Frigate instance, but does not prove its container mount paths or FFmpeg location.

Check the running go2rtc version in startup logs. The tested version is **1.9.14**. If you need to replace a bundled version, follow [Frigate's custom go2rtc instructions](https://docs.frigate.video/configuration/advanced/#custom-go2rtc-version). Back up any existing override and verify the binary's source, CPU architecture and published checksums. Restarting Frigate interrupts live streams and recording.

### go2rtc

Use `sources.generic` and [go2rtc.yaml](../examples/go2rtc.yaml), whose `streams` key is at the top level. Provide the dependencies and directory mounts above in your existing Linux runtime. A bare go2rtc image may lack Python or FFmpeg. Check startup logs for the running version; **1.9.14** is the tested version.

## 3. Probe microphone delivery

First use the generated **`probe_source`** in place of the talk relay's `exec` line. Keep `--probe`, `--probe-report` and `--max-duration 20`. Frigate users can copy [frigate-probe.yaml](../examples/frigate-probe.yaml). Validate the configuration and restart your go2rtc runtime, then press **Recheck** in the sidebar and explicitly enable the rendered card's microphone. Install the appropriate [viewer prerequisites](cards.md) first.

The probe validates microphone input and FFmpeg's AAC output without opening the camera speaker. Inspect `/config/aqara-talk-probe.json` inside the runtime after the probe ends (for Frigate, this is Frigate’s configuration directory): `input_bytes` and `aac_frames` must both be above zero. Check the report's status too; timeout or interruption may end a bounded probe. This stage does not test speaker output.

## 4. Enable talkback

Replace the probe `exec` line with the generated **`talk_source`**, validate and restart the runtime. The talk command uses your configured duration; the diagnostic probe remains independently capped at 20 seconds.

Press **Recheck** after restarting the runtime. Open Home Assistant over trusted HTTPS, including its internal URL used by the mobile app. Allow microphone access. Verify moving video and listening audio, then speak with a listener at the camera, hang up, and check that video and any recordings continue. If a call reaches its configured duration, hang up before starting a new one.

Use the [card and navigation guide](cards.md) for popups, View Assist and doorbell notifications. Stop other talk clients before testing: the per-camera lock coordinates only processes sharing this runtime's temporary directory, not separate containers or the Aqara app.

## Optional call duration

Open **Settings > Devices & services > Aqara Talk > Configure** and set **Maximum call duration (seconds)**. This automatically stops speaker output if you forget to end a call. The default is **180 seconds (3 minutes)**; whole seconds from 1 to 3600 are accepted.

Save the value. It applies to the next call; an ongoing call keeps its original limit. The probe stays capped at 20 seconds. Hang up when a call times out before calling again.

Direct CLI users can use `--max-duration SECONDS` instead of `--settings-file PATH`; the options cannot be combined. For an existing fixed-duration command, follow the one-time change below.

### Replace a fixed-duration command

If the runtime command uses `--max-duration`, it keeps that fixed value. To control duration from the UI, make the installed component and the whole settings directory readable in the runtime, replace the talk `exec` line with the generated `talk_source`, validate and restart that runtime once. Check the settings file inside the runtime as described under [paths and mounts](#runtime-paths-and-mounts). Subsequent UI changes apply to the next call without restarting.

## Manual installation

To install without HACS, copy `custom_components/aqara_talk` into Home Assistant's `custom_components` directory. Restart Home Assistant and add **Aqara Talk** in **Settings > Devices & services**. Continue at step 1 above.

## Removal

Hang up, remove the probe/talk `exec` sources and restore the original stream/card configuration. Restart the go2rtc runtime and verify video and any recordings. Then remove the Home Assistant integration and uninstall it through HACS or remove its files. Removing files first leaves go2rtc pointing at a missing executable.
