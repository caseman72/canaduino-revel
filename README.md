# Revel Monitor

ESPHome-based monitor for Revel van using a Canaduino PLC and Arduino Nano ESP32. Monitors temperature, DC voltage, and Lithionics LiFePO4 batteries via BLE.

## Hardware

- **Controller**: [Canaduino MEGA328 PLC](https://www.universal-solder.ca/product/canaduino-mega328-plc-100-v2-smd-for-arduino-nano/) with Arduino Nano ESP32
- **Temperature Sensor**: DS18B20 on 1-Wire bus (GPIO 11 / Canaduino SDA/A4 terminal)
- **Batteries**: 3x Lithionics LiFePO4 with NeverDie BMS (BLE)

## Features

- Revel van temperature monitoring (DS18B20)
- DC voltage monitoring (0-25V ADC sensor)
- Lithionics battery monitoring via BLE (voltage, cell voltages, SOC, current, temperature, capacity)
- Relay-controlled fan output
- Starlink power via REL3, with RF remote override on DI3 (QIACHIP 433MHz relay)
- WiFi diagnostics (RSSI, IP, connected SSID)
- Dual WiFi network support with automatic failover (ESPHome `networks:` block)
- Remote restart capability (P5 button)

## MQTT

Connects to a local Mosquitto broker at `hive.manion.org` (port 1883). Topic prefix: `revel`

Home Assistant auto-discovery enabled with MAC-based unique IDs.

> **Note:** `hive.manion.org` is a public A-record pointing at a **Tailscale-only IP**
> (`100.77.186.118`). The ESP32 can't run Tailscale, so it reaches the broker through the
> van's GL.iNet router (`AC-917`), which bridges LAN → tailnet. See
> [Router: reaching the Tailscale broker](#router-reaching-the-tailscale-broker) if the
> device shows "unavailable" in Home Assistant.

## Router: reaching the Tailscale broker

Because the broker lives on Tailscale and the ESP32 doesn't, the GL.iNet router
(GL-AXT1800, `172.16.8.1`) has to forward and **masquerade** the van LAN into the tailnet.
Two pieces are required:

1. **Forwarding** — in the GL.iNet web UI: *Tailscale → "Allow Remote Access LAN" = ON*.
   This creates the `lan → tailscale0` forwarding rule (set once, persists).
2. **Masquerade** — *not* set by that toggle. Without it, the broker's replies have no route
   back to the van LAN and the ESP32 shows "unavailable". Apply it on the router:

   ```sh
   uci set firewall.tailscale0.masq='1'
   uci commit firewall
   /etc/init.d/firewall reload
   ```

This lives in `/etc/config/firewall` and **survives reboots**. The only thing that wipes it
is changing the Tailscale toggles in the GL.iNet web UI (that regenerates the zone) — just
re-apply if you do.

A documented, idempotent runbook script is in [`router/fix-mqtt-tailscale.sh`](router/fix-mqtt-tailscale.sh)
(run it *on the router*):

```sh
./fix-mqtt-tailscale.sh diagnose   # read-only health check
./fix-mqtt-tailscale.sh apply      # apply the masquerade fix + verify
```

Verify the path from any LAN host (laptop on `AC-917`):

```sh
nc -z hive.manion.org 1883
mosquitto_sub -h hive.manion.org -u canaduino -t 'revel/#' -v
```

## Setup

1. Copy `secrets.example.h` to `secrets.h` and fill in your credentials
2. Flash via USB: `esphome run revel-monitor.yaml`
3. OTA updates: `./upload.sh`

## Secrets

The `secrets.h` file is gitignored and contains:
- Primary and secondary WiFi credentials
- MQTT broker URL and credentials
- OTA password
- Lithionics battery BLE MAC addresses

See `secrets.example.h` for the template.

## Wiring

### DS18B20 Temperature Sensor
| Wire | Canaduino Terminal | Notes |
|------|-------------------|-------|
| Data | SDA/A4 (GPIO 11) | Breakout module includes the 4.7kΩ pull-up (bare sensor would need one) |
| VCC | 5V | |
| GND | GND | |

### Starlink Power + RF Remote Override
| Connection | Canaduino Terminal | Notes |
|------------|-------------------|-------|
| Van 12V (yellow) | REL3 COM (D4 / GPIO 7) | HA switch "Starlink Power", state restored on reboot |
| Starlink module REM | REL3 NO | Contact closes when REL3 is ON → Starlink enabled |
| RF box REM output (12V) | DI3 (D12 / GPIO 47) | Van 12V switched by QIACHIP (latching mode); PLC opto inputs rated to 24V. Rising edge → REL3 ON, falling edge → REL3 OFF |

Previously the RF box output fed the Starlink module's REM directly; now the RF box
only feeds DI3, and REL3 is the sole switch on the Starlink REM line.

While DI3 is held ON, HA can still turn REL3 off; cycling the RF relay off→on
(new rising edge) is required to turn it back on via RF.

## BLE Battery Discovery

The `ble_discovery/` directory contains Python tools for discovering Lithionics battery BLE addresses and protocol details:

```bash
cd ble_discovery
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python lithionics_scanner.py scan          # Find batteries
python lithionics_scanner.py enumerate MAC # List GATT services
python lithionics_scanner.py monitor MAC   # Raw BLE data
python lithionics_scanner.py parse MAC --uuid 0000ffe1-0000-1000-8000-00805f9b34fb
```

Batteries use the HM-10 BLE UART service (`0xFFE0`) and send CSV data via notifications on characteristic `0xFFE1`.

## First Flash (USB)

Connect the Nano ESP32 via USB and run:

```bash
esphome run revel-monitor.yaml
```

Select the USB/serial port when prompted.

## License

MIT
