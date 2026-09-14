"""Select a camera and inspect its streaming runtime."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .config import DEFAULT_MAX_DURATION, DOMAIN, INPUT_SCHEMA, OPTIONS_SCHEMA, write_settings
from .runtime import RuntimeDiscoveryError, discover


class AqaraTalkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._data = {}
        self._discovery = {}
        self._existing = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AqaraTalkOptionsFlow()

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            camera = user_input.get("camera_entity", "")
            state = self.hass.states.get(camera)
            if not camera.startswith("camera.") or state is None:
                errors["base"] = "camera_missing"
            else:
                self._data["camera_entity"] = camera
                self._data.setdefault("name", state.name)
                try:
                    self._discovery = await discover(self.hass, camera)
                except RuntimeDiscoveryError as err:
                    if err.code == "integration_missing":
                        return await self.async_step_runtime()
                    errors["base"] = err.code
                else:
                    self._data.update({k: self._discovery[k] for k in (
                        "runtime_kind", "runtime_url", "frigate_entry_id", "frigate_client_id", "camera_name",
                    ) if k in self._discovery})
                    return await self.async_step_streams()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("camera_entity", description={
                    "suggested_value": self._data.get("camera_entity"),
                }): selector.EntitySelector(selector.EntitySelectorConfig(domain="camera")),
            }),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        self._existing = self._get_reconfigure_entry()
        self._data = dict(self._existing.data)
        return await self.async_step_user(user_input)

    async def async_step_runtime(self, user_input=None):
        errors = {}
        if user_input is not None:
            self._data.update(runtime_kind="go2rtc", runtime_url=user_input["runtime_url"])
            self._data.pop("frigate_entry_id", None)
            try:
                self._discovery = await discover(
                    self.hass, self._data["camera_entity"], "go2rtc", user_input["runtime_url"],
                )
            except RuntimeDiscoveryError as err:
                errors["base"] = err.code
            else:
                self._data["runtime_url"] = self._discovery["runtime_url"]
                return await self.async_step_streams()
        return self.async_show_form(
            step_id="runtime", errors=errors,
            data_schema=vol.Schema({vol.Required("runtime_url", description={
                "suggested_value": self._data.get("runtime_url", "http://localhost:1984"),
            }): str}),
        )

    async def async_step_streams(self, user_input=None):
        errors = {}
        names = self._discovery.get("streams", [])
        if not names:
            return self.async_show_form(step_id="no_streams", errors={}, data_schema=vol.Schema({}))
        matches = self._discovery.get("matches", [])
        if user_input is not None:
            try:
                validated = INPUT_SCHEMA({"host": user_input["host"], "name": user_input["name"]})
                if self._existing and validated["host"] != self._existing.data["host"]:
                    raise vol.Invalid("Camera identity changed")
                if user_input["video_stream"] not in names:
                    raise vol.Invalid("Stream disappeared")
                talk = user_input.get("talk_stream", "")
                if talk and (talk not in names or talk == user_input["video_stream"]):
                    raise vol.Invalid("Talk stream disappeared")
            except (KeyError, vol.Invalid):
                errors["base"] = "invalid_input"
            else:
                video_host = self._discovery.get("video_hosts", {}).get(user_input["video_stream"])
                if video_host and video_host != validated["host"]:
                    return await self._show_streams(user_input, {"base": "video_camera_mismatch"})
                if talk and self._discovery.get("talk_hosts", {}).get(talk) != validated["host"]:
                    errors["base"] = "talk_camera_mismatch"
                    return await self._show_streams(user_input, errors)
                self._data.update(validated, video_stream=user_input["video_stream"], talk_stream=talk)
                if self._existing:
                    return self.async_update_reload_and_abort(self._existing, data_updates=self._data)
                await self.async_set_unique_id(validated["host"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=validated["name"], data=self._data)
        return await self._show_streams(user_input, errors)

    async def _show_streams(self, user_input=None, errors=None):
        names = self._discovery.get("streams", [])
        matches = self._discovery.get("matches", [])
        suggested = {**self._data, **(user_input or {})}
        video = suggested.get("video_stream") or (matches[0] if len(matches) == 1 else None)
        talk_candidates = self._discovery.get("talk_streams", [])
        talk = suggested.get("talk_stream") or (talk_candidates[0] if len(talk_candidates) == 1 else "")
        if video == talk:
            video = None
        host = suggested.get("host", self._discovery.get("suggested_host", ""))
        return self.async_show_form(
            step_id="streams", errors=errors,
            description_placeholders={"matches": ", ".join(matches) or "-"},
            data_schema=vol.Schema({
                vol.Required("video_stream", description={"suggested_value": video}):
                    selector.SelectSelector(selector.SelectSelectorConfig(options=names)),
                vol.Optional("talk_stream", description={"suggested_value": talk}):
                    selector.SelectSelector(selector.SelectSelectorConfig(
                        options=[{"value": "", "label": "-"}, *[{"value": n, "label": n} for n in names]],
                    )),
                vol.Required("host", description={"suggested_value": host}): str,
                vol.Required("name", description={"suggested_value": suggested.get("name", "Aqara Talk")}): str,
            }),
        )

    async def async_step_no_streams(self, user_input=None):
        if self._data.get("runtime_kind") == "go2rtc":
            return await self.async_step_runtime({"runtime_url": self._data["runtime_url"]})
        return await self.async_step_user({"camera_entity": self._data["camera_entity"]})


class AqaraTalkOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                data = OPTIONS_SCHEMA(user_input)
            except vol.Invalid:
                errors["base"] = "invalid_duration"
            else:
                try:
                    await self.hass.async_add_executor_job(
                        write_settings, self.hass.config.config_dir,
                        self.config_entry.data["host"], data["max_duration"],
                    )
                except (OSError, ValueError, vol.Invalid):
                    errors["base"] = "storage_error"
                else:
                    return self.async_create_entry(title="", data=data)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional("max_duration", default=self.config_entry.options.get(
                    "max_duration", DEFAULT_MAX_DURATION,
                )): selector.NumberSelector(selector.NumberSelectorConfig(
                    min=1, max=3600, step=1, mode=selector.NumberSelectorMode.BOX,
                    unit_of_measurement="s",
                )),
            }),
            errors=errors,
        )
