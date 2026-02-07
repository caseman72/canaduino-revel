# Revel Monitor

ESPHome-based temperature monitor for Revel van using a Canaduino PLC and Arduino Nano ESP32.

## Hardware

- **Controller**: [Canaduino MEGA328 PLC](https://www.universal-solder.ca/product/canaduino-mega328-plc-100-v2-smd-for-arduino-nano/) with Arduino Nano ESP32
- **Temperature Sensor**: DS18B20 on 1-Wire bus (GPIO 11 / Canaduino SDA/A4 terminal)

## Features

- Revel van temperature monitoring (DS18B20)
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

See `secrets.example.h` for the template.

## Wiring

### DS18B20 Temperature Sensor
| Wire | Canaduino Terminal | Notes |
|------|-------------------|-------|
| Data | SDA/A4 (GPIO 11) | 4.7kΩ pull-up to VCC required |
| VCC | 5V | |
| GND | GND | |

## First Flash (USB)

Connect the Nano ESP32 via USB and run:

```bash
esphome run revel-monitor.yaml
```

Select the USB/serial port when prompted.

## License

MIT
