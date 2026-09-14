# Aqara Talk

Two-way audio for the **Aqara G410** in Home Assistant. Use **Frigate** or **go2rtc** with a dashboard card to see, listen and talk to someone at the door.

## Prepare the camera

1. In **Aqara Home**, open the G410, then **Device settings > RTSP LAN Preview** and enable RTSP. The G410 needs wired power for RTSP. Copy the channel URL and the RTSP username/password shown there.
2. Add the video stream to your chosen Frigate or go2rtc runtime, then add its camera entity to Home Assistant. If video already works in Home Assistant through that runtime, reuse it.

The [camera setup guide](docs/camera.md) covers both routes, credentials, stream names and checking the live image before installing Aqara Talk. Camera and account details belong only in your own configuration.

## Install with HACS

[![Open Aqara Talk in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=fszalaj&repository=aqara-talk&category=integration)

1. Open the button above and download **Aqara Talk**. Alternatively, add `https://github.com/fszalaj/aqara-talk` in **HACS > Custom repositories**, category **Integration**.
2. Restart Home Assistant, then add **Aqara Talk** under **Settings > Devices & services > Add integration**. Select your existing camera. Its owning Frigate integration supplies runtime discovery; a camera added through another integration needs your existing go2rtc API URL. Select the video stream, optionally select an existing talk stream, and confirm the physical camera's IPv4 address.
3. Open **Aqara Talk** in the sidebar. The admin panel checks the selected streams and shows the exact runtime YAML. Once the bridge stream and viewer prerequisites are present, it renders the matching Advanced Camera Card or WebRTC Camera card automatically.
4. For a new runtime, make the installed bridge and settings directories readable inside go2rtc, confirm Python/FFmpeg and enable exec where required, then merge the generated YAML and restart that runtime. Follow the [one-time host setup](docs/setup.md), then press **Recheck**. Verify two-way sound with a listener at the camera.

[![Add Aqara Talk to Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=aqara_talk)

[Manual installation](docs/setup.md#manual-installation) is also available. To install a specific release over an existing download, use **Redownload** in HACS and select that release; keep your integration entry and settings. A lower version number will not generate an automatic update notification.

## Choose your setup

| Runtime | Home Assistant viewer | Examples |
| --- | --- | --- |
| Frigate, using its go2rtc | **Frigate integration + Advanced Camera Card** | [Runtime](examples/frigate.yaml), [card](examples/card.yaml) |
| go2rtc | **WebRTC Camera integration and card** by AlexxIT | [Runtime](examples/go2rtc.yaml), [card](examples/webrtc-card.yaml) |

Both options need a Linux runtime with **Python 3 and FFmpeg**, access to the camera, and read access to the installed bridge and its settings directory. Frigate includes Python and FFmpeg; a standalone go2rtc image must provide them. The tested go2rtc version is **1.9.14**. Open Home Assistant over trusted **HTTPS** to allow microphone access.

HACS downloads the integration, bridge and admin sidebar panel. Install the viewer and its backing integration from the table above. HACS cannot create mounts or install dependencies in an external runtime. Aqara Talk reads runtime metadata and generates configuration; it does not write remote configuration or overwrite dashboards. **Ready to test** means the configured stream was found, not that sound has been verified.

Existing address-only entries keep working. Use **Reconfigure** to attach a camera and runtime for the sidebar. Each physical camera IPv4 can have one entry; remove and re-add an entry if that address changes. [Copy a card to an optional dashboard](docs/cards.md).

## Supported cameras

| Model | Status |
| --- | --- |
| **G410** | Supported. |
| **G5 Pro** | Untested. Talkback compatibility has not been established. |

The bridge uses TCP 54324 for camera control and UDP 54323 for audio. RTSP video support alone does not establish talkback compatibility.

## Call duration

Set the [maximum call duration](docs/setup.md#optional-call-duration) in **Settings > Devices & services > Aqara Talk > Configure**. It automatically stops speaker output if you forget to end a call. The default is **180 seconds (3 minutes)**; changes apply to the next call.

[Cards, popups and notifications](docs/cards.md) · [Troubleshooting](docs/troubleshooting.md) · [Release notes](CHANGELOG.md) · [MIT license](LICENSE)

Unofficial project, unaffiliated with Aqara.
