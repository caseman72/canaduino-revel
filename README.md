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
- WiFi diagnostics (RSSI, IP, connected SSID)
- Dual WiFi network support with runtime switching (P3 button)
- Remote restart capability (P5 button)

## MQTT

Connects to HiveMQ Cloud via TLS (port 8883). Topic prefix: `revel`

Home Assistant auto-discovery enabled with MAC-based unique IDs.

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
| Data | SDA/A4 (GPIO 11) | 4.7kΩ pull-up to VCC required |
| VCC | 5V | |
| GND | GND | |

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
