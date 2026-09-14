# Cards, popups and navigation

The **Aqara Talk** admin sidebar automatically renders your installed viewer after camera selection and runtime discovery. **Advanced Camera Card + Frigate integration** are required for Frigate; **WebRTC Camera integration and card** are required for standalone go2rtc. Aqara Talk supplies the setup panel and bridge, and uses these viewers for playback and calls. It does not create a camera entity; use the [camera setup guide](camera.md) if one is missing.

Install and register the appropriate card resource first. The panel reports a missing backing integration separately from a missing card resource. After [one-time runtime setup](setup.md), press **Recheck**. A discovered bridge stream makes the card ready to test; verify microphone delivery and sound separately.

## Optional dashboard card

Use **Copy card JSON** in the sidebar and paste the generated configuration into a Manual card on a dashboard of your choice. This includes your selected camera, runtime instance and stream names. Aqara Talk never overwrites dashboards. The static examples below are alternatives for custom layouts; their example entity and stream names must be adapted. The sidebar itself requires an administrator account; an optional dashboard uses Home Assistant's normal dashboard access rules.

## go2rtc: WebRTC Camera

1. Complete [runtime setup](setup.md), using `sources.generic` and [go2rtc.yaml](../examples/go2rtc.yaml).
2. Install [WebRTC Camera by AlexxIT](https://github.com/AlexxIT/WebRTC#installation) through HACS, restart Home Assistant and add **WebRTC Camera** in **Settings > Devices & services**.
3. In its integration setup, enter the URL of your **existing** go2rtc API, reachable from Home Assistant (for example `http://GO2RTC_HOST:1984/`). Do not leave the URL blank: the integration can otherwise start its own go2rtc. Keep that API private; the card uses Home Assistant's authenticated signaling proxy.
4. Return to the Aqara Talk sidebar and press **Recheck** to use its automatic card. For a separate dashboard, use **Copy card JSON** or adapt [webrtc-card.yaml](../examples/webrtc-card.yaml), which uses the example stream `aqara_talk`. That static card does not need a camera entity or Frigate integration; Aqara Talk onboarding still selects an existing Home Assistant camera. WebRTC Camera normally registers its card resource automatically. For YAML-managed resources, add `/webrtc/webrtc-camera.js` with type `module`.
5. Open Home Assistant over HTTPS. The card starts in **Listen**, without microphone access. Use its volume button to enable listening audio. Click its stream name to select **Speak** and grant microphone permission. Switching to **Speak** does not automatically unmute listening audio; the volume button is a separate control. Select **Listen** again to end transmission. These are two choices in one card, not simultaneous camera players.

This example follows the upstream [two-way audio configuration](https://github.com/AlexxIT/WebRTC#two-way-audio). Verify sound with a listener at the camera. When a call ends, return to Listen before selecting Speak again.

## Frigate: Advanced Camera Card

Install **Advanced Camera Card** and the **Frigate Home Assistant integration**, which supplies the authenticated go2rtc proxy. The supplied card settings were used with ACC 8.1.x.

The generated card places its menu below the video using ACC's [outside menu](https://github.com/dermotduffy/advanced-camera-card/blob/v8.1.0/docs/configuration/menu.md), keeping it separate from the answered-call controls. The static examples retain an overlay menu for compact custom layouts.

1. Complete the probe/talk steps in [setup](setup.md).
2. Select your existing Frigate camera during Aqara Talk setup. Return to the sidebar and press **Recheck** after preparing the runtime.
3. Use the automatically rendered card there. For an optional dashboard, use **Copy card JSON**, adapt [card.yaml](../examples/card.yaml), or add [camera-view.yaml](../examples/camera-view.yaml) as one view in your dashboard's raw configuration. The example dashboard URL is `dashboard-doorbell`, and its view path is `doorbell`.
4. When adapting static examples, replace `camera.aqara_doorbell` with the existing camera entity and `aqara_talk` with the exact bridge relay name. Preserve the discovered Frigate client selection from the generated card if multiple instances exist. Do not create an entity to match an example.
5. Open the view. Verify moving video and listening audio first, then press the phone button and allow the microphone. End the call explicitly after testing.

`live_provider: go2rtc` selects the Frigate proxy. Do not paste your camera credentials into the card or expose port 1984 to browsers. `force: [2-way-audio]` exposes the control for the custom backchannel; it does not manufacture a working microphone or camera connection. A client without WebRTC/getUserMedia cannot talk using this card.

The card starts muted. Pressing the phone button starts a call and automatically enables both listening audio (`live.auto_unmute: [call]`) and the microphone (`live.microphone.auto_unmute: [call]`). The microphone connects only on demand. Hanging up explicitly mutes listening audio (`live.auto_mute: [call]`) and ends microphone transmission. The explicit listening setting also covers ACC's low-performance profile, whose default disables automatic muting. The mute button also enables listening without a call. Both sides must be checked acoustically. The server command applies the [configured call duration](setup.md#optional-call-duration). When the limit ends speaker output, hang up before calling again.

## Optional raised answered-call controls (Advanced Camera Card)

If the three answered-call buttons overlap the camera menu, install **card-mod** and merge [call-controls-style.yaml](../examples/call-controls-style.yaml) into the camera card. It moves only the answered-call toolbar to 120px above the video bottom, leaving the main menu in place. The shadow selector matches ACC 8.1.x and must be rechecked after card upgrades. Reduce the offset for an unusually short video frame. The base card needs no card-mod or config-template-card.

## Existing popups

Replace the live-camera card inside every existing doorbell popup with your chosen card above, keeping your popup's own header/back/close controls. For Bubble Card, keep its existing `card_type: pop-up` and hash, and put the camera card in its content stack. Do not nest another live camera behind it. Popup plugins are optional and not bundled with this integration.

For a still thumbnail, keep `camera_view: auto` and change only its tap action:

```yaml
tap_action:
  action: navigate
  navigation_path: /dashboard-doorbell/doorbell
```

That opens the complete call view instead of Home Assistant's native more-info player. A native picture-entity/more-info player does not inherit these cards' talk controls.

## View Assist

The View Assist fragment below uses the Frigate/Advanced Camera Card route. View Assist's generic Camera template can still contain a native picture-entity even after a separate doorbell popup has been upgraded.

1. Back up the current dashboard and `views/camera/camera.yaml` in the View Assist directory under Home Assistant's configuration.
2. Copy the **entire current Camera template** to `views/camera/user_camera.yaml` in that same directory. Preserve its variables, selection, hold mode, timeout, styling and back action. Do not overwrite vendor files.
3. Replace only `custom_fields.camera.card` with the field in [view-assist-camera.yaml](../examples/view-assist-camera.yaml). It is a fragment, not a complete View Assist view.
4. Replace the two example aliases in its JavaScript list with every entity representing your G410 (add additional aliases if required). Normalize its returned camera card to the actual Frigate entity. Other cameras keep native playback.
5. Reload/reinstall the Camera view through your installed View Assist view manager so that it reads the user override; verify the saved dashboard contains the replacement. The loader must prefer `user_camera.yaml` over `camera.yaml` (verified with Camera 2.1.1). Check this behavior if your version differs.
6. Test `/view-assist/camera?camera=YOUR_ENTITY_ID`, camera selection, back and timeout on the actual satellite. Also replace live cards in Clock popups or any separate doorbell view. Retain still thumbnails and point them at the call view.

## Doorbell notifications

[notification.yaml](../examples/notification.yaml) is an action fragment for the Home Assistant Companion notify service. Replace the phone service and dashboard/view path; preserve your existing doorbell trigger. Its relative `url` (iOS) and `clickAction` (Android) open the complete view rather than a popup fragment that may not exist at cold launch. Other notification applications have their own deep-link schema.

Test a notification with the app closed and open, on Wi-Fi and cellular. Both internal and external Home Assistant URLs need trusted HTTPS and a reachable WebRTC media path. Browser success alone does not verify native-app navigation, permission or audio.

References: [Advanced Camera Card](https://github.com/dermotduffy/advanced-camera-card), [card-mod](https://github.com/thomasloven/lovelace-card-mod), [Companion notification URLs](https://companion.home-assistant.io/docs/notifications/notifications-basic/#opening-a-url).
