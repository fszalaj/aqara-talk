# Enable RTSP and add the camera

Aqara Talk selects an existing Home Assistant camera and uses a stream from your chosen Frigate or go2rtc runtime. Complete this page first if either is missing. If both already work, keep them and continue with [Aqara Talk setup](setup.md).

## Enable RTSP on the G410

1. Add the G410 to **Aqara Home** and power the outdoor doorbell from its wired power input. RTSP is unavailable on battery-only power; powering only the indoor chime does not power the outdoor unit.
2. Open the G410 in Aqara Home, open its settings, and choose **Device settings > RTSP LAN Preview**. Enable the preview. Menu wording can differ with app language or version.
3. Copy the channel URL and record the RTSP username and password from that screen. These are the camera's local RTSP credentials, not your Aqara account login. Use the exact displayed address and channel; do not assume a resolution or frame rate from an example.
4. Reserve the camera's current IPv4 in your router's DHCP settings so the stream and talk bridge continue to reach it. Keep the RTSP credentials in your private runtime configuration.

A typical channel URL looks like `rtsp://CAMERA_IP:8554/ch1`. If your runtime expects credentials in the URL, use `rtsp://RTSP_USER:RTSP_PASSWORD@CAMERA_IP:8554/ch1`, percent-encoding reserved characters in each credential. The app may change the address or credentials after a reset, so copy them again if needed. RTSP is a LAN service; keep it off the public internet.

Aqara documents the wired-power RTSP requirement on the [G410 product page](https://www.aqara.com/en/product/doorbell-camera-hub-g410/). See its [support page](https://store-support.aqara.com/products/doorbell-camera-hub-g410) for the current app and device instructions.

## Frigate

1. Add the camera in your existing Frigate instance using the RTSP URL. If its camera setup wizard is available, use **Settings > Global configuration > Camera management > Add Camera**. Otherwise follow [Frigate's camera configuration](https://docs.frigate.video/configuration/cameras/).
2. Give the primary go2rtc video stream the same name as the Frigate camera, for example `doorbell`, or configure an explicit `live.streams` mapping. Route Frigate's video input through its existing restream so live viewing and recording share the camera connection. See [go2rtc setup](https://docs.frigate.video/configuration/go2rtc/) and [restreaming](https://docs.frigate.video/configuration/restream/).
3. Confirm moving video in Frigate. Install the **Frigate integration** from HACS, restart Home Assistant and add **Frigate** under **Settings > Devices & services**. Enter the URL of that Frigate instance, reachable from Home Assistant. Follow the [integration instructions](https://docs.frigate.video/integrations/home-assistant/), including its MQTT prerequisites. The Frigate app alone does not install the HA integration.
4. Find the resulting `camera.*` entity in Home Assistant and confirm it is available. Select this entity when adding Aqara Talk; it identifies the owning Frigate integration. Install **Advanced Camera Card** as described in [Cards](cards.md#frigate-advanced-camera-card).

If Frigate has video but Home Assistant does not, check the integration URL, RTSP reachability and stream-name mapping using [Frigate's troubleshooting guide](https://docs.frigate.video/troubleshooting/go2rtc/). Do not add a second physical camera source merely to make the entity appear.

## Standalone go2rtc

1. Add the copied RTSP URL to `streams` in your existing go2rtc configuration, for example under `doorbell`. Reuse an existing stream if it already reaches the G410. Validate/reload using your runtime's normal procedure and confirm moving video in its viewer. See [go2rtc configuration](https://github.com/AlexxIT/go2rtc#configuration).
2. In Home Assistant, open **Settings > Devices & services > Add integration > Generic Camera**. Set **Stream source URL** to the existing go2rtc restream, for example `rtsp://GO2RTC_HOST:8554/doorbell`. Use your actual listener port and its credentials if authentication is enabled. This is the go2rtc host, not the camera IP.
3. With a stream URL only, leave Still image URL empty and ensure Home Assistant's [Stream integration](https://www.home-assistant.io/integrations/stream/) is loaded; `default_config` normally loads it. Complete the form and confirm the camera entity is available. See [Generic Camera](https://www.home-assistant.io/integrations/generic/).
4. Install the **WebRTC Camera integration and card**, point it to this same go2rtc API, and select the new camera entity in Aqara Talk. Enter that existing API URL when prompted. Follow [Cards](cards.md#go2rtc-webrtc-camera); do not start another go2rtc instance.

The Generic Camera entity supplies the selection and normal HA preview. Aqara Talk's call card uses WebRTC Camera and the discovered talk relay for microphone transmission. Generic Camera's native more-info player does not provide the bridge's call controls.

## Continue with Aqara Talk

Once the HA entity is available and the runtime video works, [install Aqara Talk through HACS](../README.md#install-with-hacs), select that entity, and follow the sidebar's runtime setup. Use trusted HTTPS for Home Assistant on both internal and external connections. This camera setup establishes video; the later microphone probe and a conversation with a listener verify talkback.
