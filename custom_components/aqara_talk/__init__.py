"""Store camera configuration and suggest an external go2rtc source."""

import logging

import voluptuous as vol

from homeassistant.core import SupportsResponse
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady, ServiceValidationError

from .config import DEFAULT_MAX_DURATION, DOMAIN, SERVICE_SCHEMA, get_config, write_settings, remove_settings

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    from .panel import async_setup_panel
    await async_setup_panel(hass)
    return True


async def async_setup_entry(hass, entry):
    try:
        await hass.async_add_executor_job(
            write_settings, hass.config.config_dir, entry.data["host"],
            entry.options.get("max_duration", DEFAULT_MAX_DURATION),
        )
    except OSError as err:
        raise ConfigEntryNotReady("Could not write Aqara Talk settings") from err
    except (ValueError, vol.Invalid) as err:
        raise ConfigEntryError("Invalid Aqara Talk settings") from err
    entry.async_on_unload(entry.add_update_listener(async_options_updated))
    entries = hass.data.setdefault(DOMAIN, {})
    entries[entry.entry_id] = dict(entry.data)
    from .panel import async_register_panel
    await async_register_panel(hass)

    async def handle_get_config(call):
        try:
            current = {}
            for entry_id, data in hass.data.get(DOMAIN, {}).items():
                registered = hass.config_entries.async_get_entry(entry_id)
                if registered is not None:
                    current[entry_id] = {
                        **data,
                        "max_duration": registered.options.get("max_duration", DEFAULT_MAX_DURATION),
                    }
            result = get_config(current, call.data.get("entry_id"))
            data = current[result["entry_id"]]
            if data.get("camera_entity") and data.get("video_stream"):
                from .runtime import build_setup
                result.update(build_setup(data, result["max_duration"]))
            return result
        except (ValueError, vol.Invalid) as err:
            raise ServiceValidationError(str(err)) from err

    if not hass.services.has_service(DOMAIN, "get_config"):
        hass.services.async_register(
            DOMAIN, "get_config", handle_get_config,
            schema=SERVICE_SCHEMA, supports_response=SupportsResponse.ONLY,
        )
    return True


async def async_unload_entry(hass, entry):
    entries = hass.data[DOMAIN]
    entries.pop(entry.entry_id, None)
    if not entries:
        hass.services.async_remove(DOMAIN, "get_config")
        hass.data.pop(DOMAIN)
    return True


async def async_options_updated(hass, entry):
    try:
        await hass.async_add_executor_job(
            write_settings, hass.config.config_dir, entry.data["host"],
            entry.options.get("max_duration", DEFAULT_MAX_DURATION),
        )
    except (OSError, ValueError, vol.Invalid) as err:
        _LOGGER.error("Could not update Aqara Talk settings for %s: %s", entry.data["host"], err)


async def async_remove_entry(hass, entry):
    await hass.async_add_executor_job(remove_settings, hass.config.config_dir, entry.data["host"])
    if not any(other.entry_id != entry.entry_id for other in hass.config_entries.async_entries(DOMAIN)):
        from homeassistant.components import frontend
        from .panel import PANEL_PATH
        frontend.async_remove_panel(hass, PANEL_PATH)
