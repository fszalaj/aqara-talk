# Troubleshooting

| Symptom | Check |
| --- | --- |
| No camera available in setup | First [enable RTSP and add the camera](camera.md) through Frigate or Generic Camera. Aqara Talk reuses the resulting entity; it does not create one. |
| Existing entry asks for camera setup | Address-only entries still work. Use the entry's Reconfigure action to attach camera/runtime metadata. Configure changes duration. |
| Aqara Talk sidebar unavailable | The panel is admin-only. Check that the integration loaded, refresh the frontend after an upgrade, and sign in as an administrator. |
| Camera or Frigate integration missing | Check the selected camera still exists and its owning Frigate entry is loaded. Use Reconfigure if it was replaced. |
| Frigate client incompatible | Update or repair the installed Frigate integration so its runtime configuration and go2rtc stream API can be read. Discovery does not fall back to an anonymous endpoint. |
| Runtime URL rejected | Enter the existing go2rtc HTTP(S) API base URL without credentials, query or fragment. Camera IPv4 is a separate field. Literal link-local, multicast and unspecified addresses are not accepted. |
| Runtime unreachable or unauthorized | Check reachability from Home Assistant and the existing runtime's access configuration. Frigate uses its installed integration's authentication. Standalone discovery does not accept credentials in the URL. |
| Redirect or invalid runtime response | Use the direct API base URL. Discovery rejects redirects, non-JSON, malformed or oversized responses. |
| No streams or ambiguous camera mapping | Configure the original video stream in the runtime, retry and select its exact name. Idle streams are valid; entity IDs are not guessed as stream names. |
| Selected video stream missing | Restore it in the runtime or use Reconfigure to select the correct existing stream, then Recheck. |
| Talk stream missing or not recognized | Apply the panel's runtime fragment after checking bridge/settings mounts, Python/FFmpeg and exec permission. Select a separate talk relay pointing to this camera's physical IPv4, restart the runtime, then Recheck. |
| Card resource or backing integration missing | Install and load the matching viewer and register its resource; see [cards](cards.md). A frontend resource alone does not supply the Frigate or WebRTC integration. |
| Runtime says ready, but there is no sound | Ready to test only confirms metadata. Run the microphone probe and a two-way sound test with a listener at the camera. |
| Copy card JSON is unavailable or fails | Use trusted HTTPS for the clipboard, or copy the displayed configuration manually. |
| Duplicate camera address or changed camera IP | Keep one entry per physical IPv4. Reconfigure preserves the address; remove and re-add for a changed IP and update the runtime settings path. |
| HACS cannot find repository | Add `https://github.com/fszalaj/aqara-talk` as a HACS custom repository of type Integration, then download Aqara Talk. |
| HACS shows a different installed version | A release with a lower version number does not trigger an update notification. Open Aqara Talk in HACS, use Redownload and select the intended release, then restart Home Assistant. Keep the existing integration entry and runtime configuration. |
| `python3` / FFmpeg / bridge missing | Check inside the container executing go2rtc. Verify mounts and the actual FFmpeg version path. |
| Settings file missing, unreadable or invalid | Check the generated `--settings-file` path inside the actual runtime. Mount the entire settings directory read-only, not a single JSON file. Confirm Home Assistant loaded the integration successfully. Video remains independent. |
| Saved duration does not affect new calls | Check the runtime sees the updated settings file. If Home Assistant logs a settings write error, the previous file remains active until a successful save. If the command uses `--max-duration`, [replace the fixed-duration command](setup.md#replace-a-fixed-duration-command) once. |
| Probe report absent | Confirm the exec source started and `/config` is writable; reports must use an absolute path outside `custom_components`. |
| Probe has zero `input_bytes` | Verify card microphone control, browser/site permission, selected microphone and WebRTC delivery. |
| Input exists, no `aac_frames` | Verify FFmpeg supports AAC encoding and inspect runtime errors. Do not move to speaker testing yet. |
| Camera bridge already busy | Hang up the existing caller. The local lock does not arbitrate separate runtimes or native camera apps. |
| START / heartbeat failure | Check camera IPv4, TCP 54324, firmware and competing callers. The probe does not test camera connectivity. |
| Frames sent, no audible speech | Check UDP 54323 and confirm sound with a person at the camera. Transport counters are insufficient. |
| Audio stops at a repeatable interval | Check the [call duration](setup.md#optional-call-duration). Hang up before starting another call. UI changes apply to the next call. |
| Backlog exceeds 500 ms | Inspect runtime load and input pacing. The bridge stops rather than accumulating delayed speech. |

Video negotiation and microphone permission are separate. Preserve H264 video plus Opus and AAC audio in the relay selection used by the examples. This does not grant microphone access: the client still needs HTTPS and working `getUserMedia` permission. Check each client's permissions and internal/external URL separately. This project does not configure HomeKit.

For dashboard, popup, still-image navigation and View Assist configuration, use [cards](cards.md). A still thumbnail should navigate to the camera view rather than start another live stream.

When reporting a problem, provide versions, installation type, failing stage and redacted counters/errors. Remove camera addresses, credentials, private hostnames and unrelated configuration. Do not publish raw environment exports or logs without checking them.
