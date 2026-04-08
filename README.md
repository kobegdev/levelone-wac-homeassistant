# LevelOne WAC Controller - Home Assistant Integration

Custom integration for [Home Assistant](https://www.home-assistant.io/) to monitor LevelOne wireless access controllers and access points.

## Supported Devices

### Controller
- **WAC-2013** - Gigabit Ethernet Wireless LAN Controller

### Access Points
- **WAP-8231** - AX1800 Dual Band Wi-Fi 6 In-Wall PoE Wireless Access Point
- **WAP-8131** - AX1800 Dual Band Wi-Fi 6 PoE Wireless Access Point
- **WAB-8021** - Dual Band Wireless Access Point

Other LevelOne APs managed by the WAC-2013 may also work.

## Features

### Controller Sensors
- CPU Usage (%)
- Memory Usage (%)
- Memory Total
- Uptime (minutes)
- Total Clients (sum across all APs)

### Per Access Point Sensors (from Controller)
- Status (online/offline)
- Uptime
- Per Radio (2.4G / 5G):
  - Channel
  - TX Power (%)
  - Connected Clients

### Per Access Point Sensors (direct from AP)
- CPU Usage (%)
- Memory Usage (%)
- Memory Total
- Connected Clients (with count)

## Prerequisites

### Network Access
The Home Assistant instance needs network access to both the controller and the access points:

- **Controller**: Usually accessible on the management network (e.g. `10.10.0.4`)
- **Access Points**: May be on a separate network (e.g. `192.168.200.0/23`)

If the APs are on a different VLAN/subnet, you need to ensure your Home Assistant instance can reach them. Options include:

1. **VLAN tagging**: Add the AP VLAN as a tagged VLAN on the Home Assistant network port, then configure the VLAN interface via the HA web UI:
   - **Settings > System > Network > VLAN interface** — set a static IP in the AP subnet
   - Note: The `ha network vlan` CLI command can create the interface, but assigning the IP via CLI may not work reliably for all VLAN IDs (especially VLAN 1). Use the web UI instead.
   - Important: Avoid IP conflicts — verify the chosen IP is not already in use on the AP network.

2. **Second network interface**: USB Ethernet adapter or Wi-Fi connected to the AP network

3. **Routing**: Configure proper routing between the networks (requires IP forwarding on the gateway)

4. **SD card network config**: For HA OS, you can place NetworkManager connection files on the boot partition under `CONFIG/network/` (no file extension, Unix line endings) to configure VLAN interfaces persistently.

## Installation

### HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations**
3. Click the three dots menu (top right) and select **Custom repositories**
4. Add this repository URL: `https://github.com/kobegdev/levelone-wac-homeassistant`
5. Select category: **Integration**
6. Click **Add**
7. Search for "LevelOne WAC" and install it
8. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/levelone_wac` folder to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings > Devices & Services > Add Integration**
2. Search for **LevelOne WAC Controller**
3. **Step 1 - Controller**: Enter the controller IP address, username, and password
4. **Step 2 - Access Points**: Enter the AP login credentials (default: `admin` / `admin`)

### Options

After setup, you can change settings via **Settings > Devices & Services > LevelOne WAC Controller > Configure**:

- **Scan interval**: How often to poll data (10-300 seconds, default: 30)
- **AP Username**: Username for direct AP access
- **AP Password**: Password for direct AP access

## API Documentation

This integration communicates with two different APIs:

### Controller API (WAC-2013)
- CGI-based API at `/cgi-bin/` endpoints
- Uses `opcode` parameters for different operations
- Authentication via session token cookie (`stork`)

### Access Point API
- CGI-based API at `/cgi-bin/` endpoints
- Uses `funname`/`action` parameters mapped to function codes
- Authentication via session token cookie (`stork`)
- Different API from the controller

## License

MIT License
