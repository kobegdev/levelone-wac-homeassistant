"""Log manager for LevelOne WAC - collects and rotates AP and controller logs."""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from .api import LevelOneAPApi, LevelOneWACApi

_LOGGER = logging.getLogger(__name__)


class LogManager:
    """Manages log collection and rotation for controller and APs."""

    def __init__(self, config_dir: str, retention_days: int = 7) -> None:
        self._log_dir = Path(config_dir) / "levelone_wac_logs"
        self._retention_days = retention_days
        self._log_dir.mkdir(parents=True, exist_ok=True)

    @property
    def retention_days(self) -> int:
        return self._retention_days

    @retention_days.setter
    def retention_days(self, value: int) -> None:
        self._retention_days = max(1, min(31, value))

    def _device_log_dir(self, device_name: str) -> Path:
        """Get log directory for a specific device."""
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in device_name)
        device_dir = self._log_dir / safe_name
        device_dir.mkdir(parents=True, exist_ok=True)
        return device_dir

    def _log_file_path(self, device_name: str, date: datetime | None = None) -> Path:
        """Get log file path for a device and date."""
        if date is None:
            date = datetime.now()
        return self._device_log_dir(device_name) / f"{date.strftime('%Y-%m-%d')}.log"

    def _append_log(self, device_name: str, log_content: str) -> None:
        """Append log content to today's log file, avoiding duplicates."""
        if not log_content or not log_content.strip():
            return

        log_file = self._log_file_path(device_name)

        # Read existing content to avoid duplicates
        existing_lines: set[str] = set()
        if log_file.exists():
            try:
                existing_lines = set(log_file.read_text(encoding="utf-8").splitlines())
            except Exception:
                pass

        new_lines = []
        for line in log_content.strip().splitlines():
            line = line.strip()
            if line and line not in existing_lines:
                new_lines.append(line)

        if new_lines:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")

    def rotate_logs(self) -> None:
        """Delete log files older than retention period."""
        cutoff = datetime.now() - timedelta(days=self._retention_days)
        try:
            for device_dir in self._log_dir.iterdir():
                if not device_dir.is_dir():
                    continue
                for log_file in device_dir.iterdir():
                    if not log_file.suffix == ".log":
                        continue
                    try:
                        file_date = datetime.strptime(log_file.stem, "%Y-%m-%d")
                        if file_date < cutoff:
                            log_file.unlink()
                            _LOGGER.debug("Rotated log: %s", log_file)
                    except ValueError:
                        continue
                # Remove empty directories
                if not any(device_dir.iterdir()):
                    device_dir.rmdir()
        except Exception as err:
            _LOGGER.error("Error rotating logs: %s", err)

    async def collect_controller_log(self, api: LevelOneWACApi, name: str = "controller") -> None:
        """Collect log from controller (opcode=3 on sysinfo)."""
        try:
            result = await api._post("sysinfo", "opcode=3")
            if isinstance(result, dict):
                log_text = result.get("log", "")
                if log_text:
                    self._append_log(name, log_text)
        except Exception as err:
            _LOGGER.debug("Failed to collect controller log: %s", err)

    async def collect_ap_log(self, api: LevelOneAPApi, device_name: str) -> None:
        """Collect log from AP (funcode=5, action=3)."""
        try:
            result = await api._post("sys_dev", "funname=5&action=3")
            if isinstance(result, str) and result.strip():
                self._append_log(device_name, result)
            elif isinstance(result, dict):
                log_text = result.get("log", result.get("sys_log", ""))
                if isinstance(log_text, str) and log_text.strip():
                    self._append_log(device_name, log_text)
        except Exception as err:
            _LOGGER.debug("Failed to collect AP log for %s: %s", device_name, err)

    def get_log_content(self, device_name: str, days: int | None = None) -> str:
        """Get log content for a device for the last N days."""
        if days is None:
            days = self._retention_days
        lines = []
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            log_file = self._log_file_path(device_name, date)
            if log_file.exists():
                try:
                    lines.append(f"=== {date.strftime('%Y-%m-%d')} ===")
                    lines.append(log_file.read_text(encoding="utf-8").strip())
                except Exception:
                    pass
        return "\n".join(lines)
