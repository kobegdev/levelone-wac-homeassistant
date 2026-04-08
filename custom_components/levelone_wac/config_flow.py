"""Config flow for LevelOne WAC integration."""

from datetime import timedelta

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import LevelOneWACApi
from .const import (
    CONF_AP_PASSWORD,
    CONF_AP_USERNAME,
    CONF_HOST,
    CONF_LOG_RETENTION_DAYS,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_LOG_RETENTION_DAYS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_LOG_RETENTION_DAYS,
)


class LevelOneWACConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for LevelOne WAC."""

    VERSION = 1

    def __init__(self) -> None:
        self._controller_data: dict = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow handler."""
        return LevelOneWACOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Step 1: Controller credentials."""
        errors = {}

        if user_input is not None:
            api = LevelOneWACApi(
                user_input[CONF_HOST],
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
            )
            try:
                if await api.test_connection():
                    await api.close()
                    self._controller_data = user_input
                    return await self.async_step_ap_credentials()
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
            finally:
                await api.close()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                    ): vol.All(int, vol.Range(min=10, max=300)),
                }
            ),
            errors=errors,
        )

    async def async_step_ap_credentials(self, user_input=None) -> FlowResult:
        """Step 2: AP credentials and log settings."""
        if user_input is not None:
            data = {**self._controller_data, **user_input}
            await self.async_set_unique_id(data[CONF_HOST])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"WAC {data[CONF_HOST]}",
                data=data,
            )

        return self.async_show_form(
            step_id="ap_credentials",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AP_USERNAME, default="admin"): str,
                    vol.Required(CONF_AP_PASSWORD, default="admin"): str,
                    vol.Optional(
                        CONF_LOG_RETENTION_DAYS, default=DEFAULT_LOG_RETENTION_DAYS
                    ): vol.All(int, vol.Range(min=1, max=MAX_LOG_RETENTION_DAYS)),
                }
            ),
        )


class LevelOneWACOptionsFlow(OptionsFlow):
    """Options flow for LevelOne WAC."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            new_data = {**self._config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(
                self._config_entry, data=new_data
            )
            coordinator = self.hass.data.get(DOMAIN, {}).get(self._config_entry.entry_id)
            if coordinator:
                # Update controller API credentials
                coordinator.controller_api._username = user_input[CONF_USERNAME]
                coordinator.controller_api._password = user_input[CONF_PASSWORD]
                coordinator.controller_api._token = None
                # Update AP credentials
                coordinator.update_ap_credentials(
                    user_input[CONF_AP_USERNAME],
                    user_input[CONF_AP_PASSWORD],
                )
                coordinator.update_interval = timedelta(
                    seconds=user_input[CONF_SCAN_INTERVAL]
                )
                coordinator.log_manager.retention_days = user_input[CONF_LOG_RETENTION_DAYS]
            return self.async_create_entry(title="", data={})

        current = self._config_entry.data
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=current.get(CONF_HOST, ""),
                    ): str,
                    vol.Required(
                        CONF_USERNAME,
                        default=current.get(CONF_USERNAME, ""),
                    ): str,
                    vol.Required(
                        CONF_PASSWORD,
                        default=current.get(CONF_PASSWORD, ""),
                    ): str,
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(int, vol.Range(min=10, max=300)),
                    vol.Required(
                        CONF_AP_USERNAME,
                        default=current.get(CONF_AP_USERNAME, "admin"),
                    ): str,
                    vol.Required(
                        CONF_AP_PASSWORD,
                        default=current.get(CONF_AP_PASSWORD, "admin"),
                    ): str,
                    vol.Optional(
                        CONF_LOG_RETENTION_DAYS,
                        default=current.get(CONF_LOG_RETENTION_DAYS, DEFAULT_LOG_RETENTION_DAYS),
                    ): vol.All(int, vol.Range(min=1, max=MAX_LOG_RETENTION_DAYS)),
                }
            ),
        )
