"""API client for LevelOne WAC controller and APs."""

import logging
from urllib.parse import quote

import aiohttp

_LOGGER = logging.getLogger(__name__)


class LevelOneWACApi:
    """API client for LevelOne WAC-2013 controller."""

    def __init__(self, host: str, username: str, password: str) -> None:
        self._host = host
        self._username = username
        self._password = password
        self._token: str | None = None
        self._session: aiohttp.ClientSession | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self._host}"

    async def _ensure_session(self) -> None:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def login(self) -> bool:
        """Login to the controller and get a session token."""
        await self._ensure_session()
        try:
            async with self._session.post(
                f"{self.base_url}/cgi-bin/login",
                data=f"opcode=1&username={quote(self._username)}&password={quote(self._password)}",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json(content_type=None)
                if str(data.get("result")) == "1":
                    self._token = data.get("token")
                    return True
                return False
        except Exception as err:
            _LOGGER.error("Controller login error: %s", err)
            return False

    def _cookies(self) -> dict[str, str]:
        return {"stork": self._token or "", "username": self._username}

    async def _post(self, endpoint: str, data: str) -> dict | None:
        """POST to a CGI endpoint with authentication and auto-relogin."""
        await self._ensure_session()
        try:
            async with self._session.post(
                f"{self.base_url}/cgi-bin/{endpoint}",
                data=data,
                cookies=self._cookies(),
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                result = await resp.json(content_type=None)
                if isinstance(result, dict) and str(result.get("result")) == "-1":
                    if await self.login():
                        async with self._session.post(
                            f"{self.base_url}/cgi-bin/{endpoint}",
                            data=data,
                            cookies=self._cookies(),
                            timeout=aiohttp.ClientTimeout(total=15),
                        ) as resp2:
                            return await resp2.json(content_type=None)
                return result
        except Exception as err:
            _LOGGER.error("Controller API error (%s): %s", endpoint, err)
            return None

    async def get_system_info(self) -> dict | None:
        """Get controller system info (CPU, RAM, traffic)."""
        return await self._post("sysinfo", "opcode=2")

    async def get_ap_list(self) -> list[dict]:
        """Get list of all managed access points."""
        data = await self._post(
            "sysinfo", "opcode=10&configname=ap_list&showrule=0&searchip=&searchmac="
        )
        if data and "ApDevList" in data:
            aps = data["ApDevList"].get("data", [])
            return [ap for ap in aps if ap.get("m_dev_mac")]
        return []

    async def test_connection(self) -> bool:
        """Test if we can connect and authenticate."""
        if not await self.login():
            return False
        info = await self.get_system_info()
        return info is not None and "mac" in (info or {})


class LevelOneAPApi:
    """API client for LevelOne Access Points (WAP-8231, WAP-8131, WAB-8021)."""

    def __init__(self, host: str, username: str, password: str) -> None:
        self._host = host
        self._username = username
        self._password = password
        self._token: str | None = None
        self._session: aiohttp.ClientSession | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self._host}"

    async def _ensure_session(self) -> None:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def login(self) -> bool:
        """Login to the AP and get a session token."""
        await self._ensure_session()
        try:
            async with self._session.post(
                f"{self.base_url}/cgi-bin/login",
                data=f"funname=1&action=1&username={quote(self._username)}&password={quote(self._password)}",
                headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json(content_type=None)
                if str(data.get("result")) == "0":
                    self._token = data.get("token")
                    return True
                return False
        except Exception as err:
            _LOGGER.debug("AP %s login error: %s", self._host, err)
            return False

    def _cookies(self) -> dict[str, str]:
        return {"stork": self._token or ""}

    async def _post(self, endpoint: str, data: str) -> dict | str | None:
        """POST to an AP CGI endpoint with authentication and auto-relogin."""
        await self._ensure_session()
        try:
            async with self._session.post(
                f"{self.base_url}/cgi-bin/{endpoint}",
                data=data,
                cookies=self._cookies(),
                headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                try:
                    result = await resp.json(content_type=None)
                except Exception:
                    return await resp.text()
                if isinstance(result, dict) and str(result.get("result")) == "-1":
                    if await self.login():
                        async with self._session.post(
                            f"{self.base_url}/cgi-bin/{endpoint}",
                            data=data,
                            cookies=self._cookies(),
                            headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
                            timeout=aiohttp.ClientTimeout(total=15),
                        ) as resp2:
                            try:
                                return await resp2.json(content_type=None)
                            except Exception:
                                return await resp2.text()
                return result
        except Exception as err:
            _LOGGER.debug("AP %s API error (%s): %s", self._host, endpoint, err)
            return None

    async def get_sysinfo(self) -> dict | None:
        """Get CPU, RAM, uptime, traffic from AP."""
        result = await self._post("sys_dev", "funname=9&action=1")
        return result if isinstance(result, dict) else None

    async def get_info(self) -> dict | None:
        """Get model, firmware, name from AP."""
        result = await self._post("sys_dev", "funname=9&action=2")
        return result if isinstance(result, dict) else None

    async def get_wireless_clients(self) -> list[dict]:
        """Get connected wireless clients with signal strength."""
        result = await self._post("wireless", "funname=5&action=1")
        if not isinstance(result, dict) or "clients" not in result:
            return []
        clients = []
        for radio in result.get("clients", []):
            sta_list = radio.get("DevStalist", {})
            radio_id = sta_list.get("radio", "")
            for sta in sta_list.get("sta", []):
                if sta.get("mac"):
                    sta["radio_band"] = "2.4G" if str(radio_id) == "0" else "5G"
                    clients.append(sta)
        return clients

    async def get_throughput(self) -> dict:
        """Get WiFi throughput per radio (bits/s)."""
        result = await self._post("wireless", "funname=7&action=1")
        throughput = {"2.4G_up": 0, "2.4G_down": 0, "5G_up": 0, "5G_down": 0}
        if not isinstance(result, dict) or "WiFi_Throughput" not in result:
            return throughput
        for entry in result["WiFi_Throughput"].get("Throughput", []):
            name = entry.get("name", "")
            data = entry.get("data", [])
            if not name or not data:
                continue
            # Last non-empty value is the current throughput
            last_val = 0
            for v in reversed(data):
                try:
                    val = int(str(v).strip().strip('"'))
                    if val > 0:
                        last_val = val
                        break
                except (ValueError, TypeError):
                    continue
            radio_type = entry.get("radio_type", "")
            if radio_type == "1":  # 5G
                if "UP" in name:
                    throughput["5G_up"] = last_val
                elif "DOWN" in name:
                    throughput["5G_down"] = last_val
            elif radio_type == "2":  # 2.4G
                if "UP" in name:
                    throughput["2.4G_up"] = last_val
                elif "DOWN" in name:
                    throughput["2.4G_down"] = last_val
        return throughput

    async def test_connection(self) -> bool:
        """Test if we can connect and authenticate to the AP."""
        if not await self.login():
            return False
        info = await self.get_sysinfo()
        return info is not None and "cpu_usage" in (info or {})
