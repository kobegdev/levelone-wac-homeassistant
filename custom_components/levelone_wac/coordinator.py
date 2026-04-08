"""Data update coordinator for LevelOne WAC."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LevelOneAPApi, LevelOneWACApi

_LOGGER = logging.getLogger(__name__)


class LevelOneWACCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch data from controller and APs."""

    def __init__(
        self,
        hass: HomeAssistant,
        controller_api: LevelOneWACApi,
        ap_username: str,
        ap_password: str,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="LevelOne WAC",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.controller_api = controller_api
        self._ap_username = ap_username
        self._ap_password = ap_password
        self._ap_apis: dict[str, LevelOneAPApi] = {}

    def _get_ap_api(self, ip: str) -> LevelOneAPApi:
        """Get or create an API client for a specific AP."""
        if ip not in self._ap_apis:
            self._ap_apis[ip] = LevelOneAPApi(ip, self._ap_username, self._ap_password)
        return self._ap_apis[ip]

    def update_ap_credentials(self, username: str, password: str) -> None:
        """Update AP credentials and reset AP API clients."""
        self._ap_username = username
        self._ap_password = password
        for api in self._ap_apis.values():
            api._username = username
            api._password = password
            api._token = None

    async def _async_update_data(self) -> dict:
        """Fetch data from the controller and all APs."""
        try:
            system_info = await self.controller_api.get_system_info()
            ap_list = await self.controller_api.get_ap_list()

            if system_info is None:
                raise UpdateFailed("Failed to get controller system info")

            ap_direct_data = {}
            for ap in ap_list:
                ip = ap.get("m_dev_ip", "")
                mac = ap.get("m_dev_mac", "")
                if not ip or not mac:
                    continue
                try:
                    status = int(ap.get("m_dev_status", -99))
                except (ValueError, TypeError):
                    status = -99
                if status < -1:
                    ap_direct_data[mac] = {"available": False}
                    continue

                api = self._get_ap_api(ip)
                sysinfo = await api.get_sysinfo()
                clients = await api.get_wireless_clients()
                throughput = await api.get_throughput()

                if sysinfo:
                    ap_direct_data[mac] = {
                        "available": True,
                        "sysinfo": sysinfo,
                        "clients": clients,
                        "throughput": throughput,
                    }
                else:
                    ap_direct_data[mac] = {"available": False}

            return {
                "controller": system_info,
                "access_points": ap_list,
                "ap_direct": ap_direct_data,
            }
        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err

    async def async_close(self) -> None:
        """Close all API sessions."""
        await self.controller_api.close()
        for api in self._ap_apis.values():
            await api.close()
