"""Sensor platform for LevelOne WAC integration."""

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LevelOneWACCoordinator

_LOGGER = logging.getLogger(__name__)

_MEASUREMENT_KEYS = {
    "cpu_usage", "mem_usage", "m_stanum", "total_clients",
    "system_up_time", "m_channel", "ap_cpu_usage", "ap_mem_usage",
    "client_count", "tp_24g_up", "tp_24g_down", "tp_5g_up", "tp_5g_down",
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors from a config entry."""
    coordinator: LevelOneWACCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []

    # Controller sensors
    controller = coordinator.data.get("controller", {})
    if controller:
        entities.extend([
            WACControllerSensor(coordinator, entry, "cpu_usage", "CPU Usage", PERCENTAGE, "mdi:cpu-64-bit"),
            WACControllerSensor(coordinator, entry, "mem_usage", "Memory Usage", PERCENTAGE, "mdi:memory"),
            WACControllerSensor(coordinator, entry, "mem_total", "Memory Total", None, "mdi:memory"),
            WACControllerSensor(coordinator, entry, "system_up_time", "Uptime", "min", "mdi:clock-outline"),
            WACControllerSensor(coordinator, entry, "total_clients", "Total Clients", None, "mdi:account-multiple"),
        ])

    # AP sensors
    for ap in coordinator.data.get("access_points", []):
        mac = ap.get("m_dev_mac", "")
        if not mac:
            continue

        # Controller-sourced AP sensors
        entities.extend([
            WACAccessPointSensor(coordinator, entry, ap, "m_dev_status", "Status", None, "mdi:access-point"),
            WACAccessPointSensor(coordinator, entry, ap, "m_onlinetime", "Uptime", None, "mdi:clock-outline"),
        ])
        # Per-radio sensors from controller
        for radio in ap.get("m_radio", []):
            radio_type = radio.get("m_radio_type", "")
            if radio_type == "0":
                continue
            band = "2.4G" if _is_24g(radio_type) else "5G"
            entities.extend([
                WACRadioSensor(coordinator, entry, ap, radio, band, "m_channel", "Channel", None, "mdi:sine-wave"),
                WACRadioSensor(coordinator, entry, ap, radio, band, "m_wlan_txpower", "TX Power", PERCENTAGE, "mdi:signal"),
                WACRadioSensor(coordinator, entry, ap, radio, band, "m_stanum", "Clients", None, "mdi:wifi"),
            ])

        # Direct AP sensors (CPU, RAM, clients)
        entities.extend([
            WACAPDirectSensor(coordinator, entry, ap, "ap_cpu_usage", "CPU Usage", PERCENTAGE, "mdi:cpu-64-bit"),
            WACAPDirectSensor(coordinator, entry, ap, "ap_mem_usage", "Memory Usage", PERCENTAGE, "mdi:memory"),
            WACAPDirectSensor(coordinator, entry, ap, "ap_mem_total", "Memory Total", None, "mdi:memory"),
            WACAPDirectSensor(coordinator, entry, ap, "client_count", "Connected Clients", None, "mdi:account-multiple-outline"),
            WACAPDirectSensor(coordinator, entry, ap, "tp_24g_up", "2.4G Upload", "bit/s", "mdi:upload"),
            WACAPDirectSensor(coordinator, entry, ap, "tp_24g_down", "2.4G Download", "bit/s", "mdi:download"),
            WACAPDirectSensor(coordinator, entry, ap, "tp_5g_up", "5G Upload", "bit/s", "mdi:upload"),
            WACAPDirectSensor(coordinator, entry, ap, "tp_5g_down", "5G Download", "bit/s", "mdi:download"),
        ])

    async_add_entities(entities)


def _is_24g(radio_type: str) -> bool:
    try:
        return int(radio_type) < 50
    except (ValueError, TypeError):
        return True


class WACControllerSensor(CoordinatorEntity, SensorEntity):
    """Sensor for WAC controller metrics."""

    def __init__(self, coordinator, entry, key, name, unit, icon):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"WAC Controller {name}"
        self._attr_unique_id = f"{entry.entry_id}_controller_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_state_class = (
            SensorStateClass.MEASUREMENT if key in _MEASUREMENT_KEYS else None
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_controller")},
            name="WAC Controller",
            manufacturer="LevelOne",
            model="WAC-2013",
            configuration_url=f"http://{entry.data['host']}",
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        controller = self.coordinator.data.get("controller", {})
        if self._key == "total_clients":
            total = 0
            for ap in self.coordinator.data.get("access_points", []):
                try:
                    total += int(ap.get("m_stanum", 0))
                except (ValueError, TypeError):
                    pass
            self._attr_native_value = total
        elif self._key == "system_up_time":
            try:
                self._attr_native_value = round(int(controller.get(self._key, 0)) / 60)
            except (ValueError, TypeError):
                self._attr_native_value = 0
        elif self._key == "mem_total":
            self._attr_native_value = controller.get(self._key)
        else:
            value = controller.get(self._key)
            if value is not None:
                try:
                    self._attr_native_value = int(value)
                except (ValueError, TypeError):
                    self._attr_native_value = value
        self.async_write_ha_state()


class WACAccessPointSensor(CoordinatorEntity, SensorEntity):
    """Sensor for AP metrics from controller."""

    def __init__(self, coordinator, entry, ap, key, name, unit, icon):
        super().__init__(coordinator)
        self._mac = ap.get("m_dev_mac", "")
        self._key = key
        ap_name = ap.get("m_dev_name") or self._mac
        self._attr_name = f"{ap_name} {name}"
        self._attr_unique_id = f"{entry.entry_id}_{self._mac}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_state_class = (
            SensorStateClass.MEASUREMENT if key in _MEASUREMENT_KEYS else None
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{self._mac}")},
            name=ap_name,
            manufacturer="LevelOne",
            model=ap.get("m_dev_modelname", "Unknown"),
            sw_version=ap.get("m_sw_ver", ""),
            via_device=(DOMAIN, f"{entry.entry_id}_controller"),
        )

    def _find_ap(self) -> dict | None:
        for ap in self.coordinator.data.get("access_points", []):
            if ap.get("m_dev_mac") == self._mac:
                return ap
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        ap = self._find_ap()
        if ap is None:
            self._attr_available = False
            self.async_write_ha_state()
            return
        self._attr_available = True
        value = ap.get(self._key)
        if self._key == "m_dev_status":
            try:
                self._attr_native_value = "online" if int(value) >= -1 else "offline"
            except (ValueError, TypeError):
                self._attr_native_value = "unknown"
        elif value is not None:
            try:
                self._attr_native_value = int(value)
            except (ValueError, TypeError):
                self._attr_native_value = value
        self.async_write_ha_state()


class WACRadioSensor(CoordinatorEntity, SensorEntity):
    """Sensor for AP radio metrics from controller."""

    def __init__(self, coordinator, entry, ap, radio, band, key, name, unit, icon):
        super().__init__(coordinator)
        self._mac = ap.get("m_dev_mac", "")
        self._radio_type = radio.get("m_radio_type", "")
        self._key = key
        self._band = band
        ap_name = ap.get("m_dev_name") or self._mac
        self._attr_name = f"{ap_name} {band} {name}"
        self._attr_unique_id = f"{entry.entry_id}_{self._mac}_{band}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_state_class = (
            SensorStateClass.MEASUREMENT if key in _MEASUREMENT_KEYS else None
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{self._mac}")},
            name=ap_name,
            manufacturer="LevelOne",
            model=ap.get("m_dev_modelname", "Unknown"),
            sw_version=ap.get("m_sw_ver", ""),
            via_device=(DOMAIN, f"{entry.entry_id}_controller"),
        )

    def _find_radio(self) -> dict | None:
        for ap in self.coordinator.data.get("access_points", []):
            if ap.get("m_dev_mac") == self._mac:
                for radio in ap.get("m_radio", []):
                    if radio.get("m_radio_type") == self._radio_type:
                        return radio
        return None

    @callback
    def _handle_coordinator_update(self) -> None:
        radio = self._find_radio()
        if radio is None:
            self._attr_available = False
            self.async_write_ha_state()
            return
        self._attr_available = True
        value = radio.get(self._key)
        if value is not None:
            try:
                self._attr_native_value = int(value)
            except (ValueError, TypeError):
                self._attr_native_value = value
        self.async_write_ha_state()


class WACAPDirectSensor(CoordinatorEntity, SensorEntity):
    """Sensor for AP metrics queried directly from the AP."""

    def __init__(self, coordinator, entry, ap, key, name, unit, icon):
        super().__init__(coordinator)
        self._mac = ap.get("m_dev_mac", "")
        self._key = key
        ap_name = ap.get("m_dev_name") or self._mac
        self._attr_name = f"{ap_name} {name}"
        self._attr_unique_id = f"{entry.entry_id}_{self._mac}_direct_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_state_class = (
            SensorStateClass.MEASUREMENT if key in _MEASUREMENT_KEYS else None
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{self._mac}")},
            name=ap_name,
            manufacturer="LevelOne",
            model=ap.get("m_dev_modelname", "Unknown"),
            sw_version=ap.get("m_sw_ver", ""),
            via_device=(DOMAIN, f"{entry.entry_id}_controller"),
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        ap_direct = self.coordinator.data.get("ap_direct", {}).get(self._mac, {})
        if not ap_direct.get("available", False):
            self._attr_available = False
            self.async_write_ha_state()
            return

        self._attr_available = True
        sysinfo = ap_direct.get("sysinfo", {})
        clients = ap_direct.get("clients", [])

        if self._key == "ap_cpu_usage":
            try:
                self._attr_native_value = int(sysinfo.get("cpu_usage", 0))
            except (ValueError, TypeError):
                self._attr_native_value = 0
        elif self._key == "ap_mem_usage":
            try:
                self._attr_native_value = int(sysinfo.get("mem_usage", 0))
            except (ValueError, TypeError):
                self._attr_native_value = 0
        elif self._key == "ap_mem_total":
            self._attr_native_value = sysinfo.get("mem_total")
        elif self._key == "client_count":
            self._attr_native_value = len(clients)
        elif self._key.startswith("tp_"):
            throughput = ap_direct.get("throughput", {})
            tp_map = {
                "tp_24g_up": "2.4G_up",
                "tp_24g_down": "2.4G_down",
                "tp_5g_up": "5G_up",
                "tp_5g_down": "5G_down",
            }
            self._attr_native_value = throughput.get(tp_map.get(self._key, ""), 0)

        self.async_write_ha_state()
