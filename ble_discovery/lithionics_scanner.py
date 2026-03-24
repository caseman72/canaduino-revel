#!/usr/bin/env python3
"""Lithionics Battery BLE Discovery & Monitoring Tool.

Usage:
    python lithionics_scanner.py scan [--duration SECONDS]
    python lithionics_scanner.py enumerate ADDRESS
    python lithionics_scanner.py monitor ADDRESS [--uuid CHAR_UUID] [--duration SECONDS]
    python lithionics_scanner.py parse ADDRESS --uuid CHAR_UUID [--duration SECONDS]
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic


SCRIPT_DIR = Path(__file__).parent


# --- Scan mode ---

async def cmd_scan(args):
    """Scan for BLE devices, highlighting Lithionics batteries (Li3-*)."""
    duration = args.duration or 10
    print(f"Scanning for BLE devices ({duration}s)...\n")

    devices = await BleakScanner.discover(timeout=duration, return_adv=True)

    results = []
    lithionics = []

    for addr, (device, adv) in sorted(devices.items(), key=lambda x: x[1][1].rssi, reverse=True):
        name = adv.local_name or device.name or "Unknown"
        entry = {
            "address": addr,
            "name": name,
            "rssi": adv.rssi,
            "service_uuids": adv.service_uuids or [],
            "manufacturer_data": {str(k): v.hex() for k, v in adv.manufacturer_data.items()},
        }
        results.append(entry)

        is_lithionics = name.startswith("Li3-") or name.startswith("NeverDie")
        if is_lithionics:
            lithionics.append(entry)

        marker = " <<< LITHIONICS" if is_lithionics else ""
        print(f"  {name:30s}  {addr}  RSSI: {adv.rssi:4d}{marker}")
        if adv.service_uuids:
            print(f"    Service UUIDs: {adv.service_uuids}")
        if adv.manufacturer_data:
            for mid, mdata in adv.manufacturer_data.items():
                print(f"    Manufacturer 0x{mid:04x}: {mdata.hex()}")

    print(f"\nFound {len(results)} devices total, {len(lithionics)} Lithionics batteries.")

    outfile = SCRIPT_DIR / "scan_results.json"
    with open(outfile, "w") as f:
        json.dump({"scan_time": datetime.now().isoformat(), "devices": results, "lithionics": lithionics}, f, indent=2)
    print(f"Results saved to {outfile}")

    if lithionics:
        print("\nLithionics batteries found:")
        for bat in lithionics:
            print(f"  {bat['name']}  {bat['address']}  RSSI: {bat['rssi']}")


# --- Enumerate mode ---

async def cmd_enumerate(args):
    """Connect to a device and enumerate all GATT services/characteristics."""
    address = args.address
    print(f"Connecting to {address}...")

    async with BleakClient(address) as client:
        print(f"Connected: {client.is_connected}")
        print(f"MTU: {client.mtu_size}\n")

        service_map = []

        for service in client.services:
            svc_info = {
                "uuid": service.uuid,
                "description": service.description or "Unknown",
                "characteristics": [],
            }
            print(f"Service: {service.uuid}")
            print(f"  Description: {service.description or 'Unknown'}")

            for char in service.characteristics:
                props = char.properties
                char_info = {
                    "uuid": char.uuid,
                    "description": char.description or "Unknown",
                    "properties": props,
                    "handle": char.handle,
                }

                print(f"  Characteristic: {char.uuid}")
                print(f"    Description: {char.description or 'Unknown'}")
                print(f"    Properties: {', '.join(props)}")
                print(f"    Handle: {char.handle}")

                if "read" in props:
                    try:
                        value = await client.read_gatt_char(char.uuid)
                        char_info["value_hex"] = value.hex()
                        char_info["value_ascii"] = value.decode("ascii", errors="replace")
                        print(f"    Value (hex): {value.hex()}")
                        print(f"    Value (ascii): {value.decode('ascii', errors='replace')}")
                    except Exception as e:
                        print(f"    Read error: {e}")
                        char_info["read_error"] = str(e)

                for desc in char.descriptors:
                    print(f"    Descriptor: {desc.uuid} = {desc.description}")

                svc_info["characteristics"].append(char_info)

            service_map.append(svc_info)
            print()

        outfile = SCRIPT_DIR / "gatt_services.json"
        with open(outfile, "w") as f:
            json.dump({"address": address, "time": datetime.now().isoformat(), "services": service_map}, f, indent=2)
        print(f"Service map saved to {outfile}")


# --- Monitor mode ---

async def cmd_monitor(args):
    """Subscribe to BLE notifications and display raw data."""
    address = args.address
    char_uuid = args.uuid
    duration = args.duration or 60
    logfile = SCRIPT_DIR / "raw_data.log"

    print(f"Connecting to {address}...")

    async with BleakClient(address) as client:
        print(f"Connected (MTU: {client.mtu_size})")

        log_fh = open(logfile, "a")
        log_fh.write(f"\n--- Session {datetime.now().isoformat()} addr={address} ---\n")

        notify_chars = []
        if char_uuid:
            notify_chars.append(char_uuid)
        else:
            # Subscribe to all notify-capable characteristics
            for service in client.services:
                for char in service.characteristics:
                    if "notify" in char.properties or "indicate" in char.properties:
                        notify_chars.append(char.uuid)

        if not notify_chars:
            print("No notify-capable characteristics found!")
            return

        print(f"Subscribing to {len(notify_chars)} characteristic(s):")
        for uuid in notify_chars:
            print(f"  {uuid}")
        print(f"\nMonitoring for {duration}s (Ctrl+C to stop)...\n")

        def make_callback(uuid):
            def callback(sender: BleakGATTCharacteristic, data: bytearray):
                ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                hex_str = data.hex()
                ascii_str = data.decode("ascii", errors="replace")
                short_uuid = uuid.split("-")[0] if "-" in uuid else uuid

                print(f"[{ts}] {short_uuid} | hex: {hex_str}")
                print(f"         {'':>{len(short_uuid)}} | asc: {ascii_str}")

                log_fh.write(f"{ts} {uuid} hex={hex_str} ascii={ascii_str}\n")
                log_fh.flush()

            return callback

        for uuid in notify_chars:
            await client.start_notify(uuid, make_callback(uuid))

        try:
            await asyncio.sleep(duration)
        except asyncio.CancelledError:
            pass

        for uuid in notify_chars:
            try:
                await client.stop_notify(uuid)
            except Exception:
                pass

        log_fh.close()
        print(f"\nRaw data logged to {logfile}")


# --- Parse mode ---

def parse_data_record(fields):
    """Parse a data record (no prefix): pack_v, cell1-4, bms_temp, batt_temp, direction, soc, status."""
    if len(fields) < 10:
        return None
    try:
        return {
            "pack_voltage": int(fields[0]) / 100.0,
            "cell1_voltage": int(fields[1]) / 100.0,
            "cell2_voltage": int(fields[2]) / 100.0,
            "cell3_voltage": int(fields[3]) / 100.0,
            "cell4_voltage": int(fields[4]) / 100.0,
            "bms_temp_f": int(fields[5]),
            "battery_temp_f": int(fields[6]),
            "charging": int(fields[7]) == 1,
            "soc_pct": int(fields[8]),
            "status_code": fields[9],
        }
    except (ValueError, IndexError):
        return None


def parse_status_record(fields):
    """Parse a status record (&-prefix): battery_id, capacity, power, errors, can_status."""
    if len(fields) < 8 or fields[0] != "&":
        return None
    try:
        return {
            "battery_id": int(fields[1]),
            "remaining_capacity_ah": int(fields[2]),
            "power_raw": fields[3],
            "error1": fields[4],
            "error2": fields[5],
            "can_charger_status": fields[6],
            "can_status": fields[7],
        }
    except (ValueError, IndexError):
        return None


def parse_summary_record(fields):
    """Parse a summary record ($-prefix): consumed, status_hex, temps, aging, serial."""
    if len(fields) < 9 or fields[0] != "$":
        return None
    try:
        return {
            "total_consumed_ah": int(fields[1]),
            "last_status_hex": fields[2],
            "highest_temp_f": int(fields[3]),
            "lowest_temp_f": int(fields[4]),
            "unknown_field5": fields[5],
            "aging_factor_temp": int(fields[6]),
            "aging_factor_soc": int(fields[7]),
            "serial_number": fields[8],
        }
    except (ValueError, IndexError):
        return None


async def cmd_parse(args):
    """Subscribe to notifications and parse Lithionics battery data."""
    address = args.address
    char_uuid = args.uuid
    duration = args.duration or 60

    if not char_uuid:
        print("Error: --uuid is required for parse mode")
        sys.exit(1)

    print(f"Connecting to {address}...")

    async with BleakClient(address) as client:
        print(f"Connected (MTU: {client.mtu_size})")
        print(f"Subscribing to {char_uuid}")
        print(f"Parsing for {duration}s (Ctrl+C to stop)...\n")

        line_buffer = ""
        last_data = {}
        last_status = {}
        last_summary = {}

        def display():
            """Print parsed battery state."""
            if not last_data:
                return

            d = last_data
            s = last_status
            sm = last_summary

            direction = "CHARGING" if d.get("charging") else "DISCHARGING"
            serial = sm.get("serial_number", "?")

            print("\033[2J\033[H")  # clear screen
            print(f"=== Lithionics Battery: {serial} ===")
            print(f"  Pack Voltage:  {d['pack_voltage']:7.2f} V")
            print(f"  Cell 1:        {d['cell1_voltage']:7.3f} V")
            print(f"  Cell 2:        {d['cell2_voltage']:7.3f} V")
            print(f"  Cell 3:        {d['cell3_voltage']:7.3f} V")
            print(f"  Cell 4:        {d['cell4_voltage']:7.3f} V")
            print(f"  BMS Temp:      {d['bms_temp_f']:4d} F")
            print(f"  Battery Temp:  {d['battery_temp_f']:4d} F")
            print(f"  SOC:           {d['soc_pct']:4d} %")
            print(f"  Direction:     {direction}")
            print(f"  Status Code:   {d['status_code']}")

            if s:
                print(f"  Capacity:      {s['remaining_capacity_ah']:4d} Ah")
                print(f"  Power (raw):   {s['power_raw']}")
                print(f"  Errors:        {s['error1']} / {s['error2']}")
                print(f"  CAN Status:    {s['can_charger_status']} / {s['can_status']}")

            if sm:
                print(f"  Total Used:    {sm['total_consumed_ah']} Ah")
                print(f"  High/Low Temp: {sm['highest_temp_f']}F / {sm['lowest_temp_f']}F")
                print(f"  Aging T/S:     {sm['aging_factor_temp']} / {sm['aging_factor_soc']}")

            print(f"\n  Last update: {datetime.now().strftime('%H:%M:%S')}")

        def callback(sender: BleakGATTCharacteristic, data: bytearray):
            nonlocal line_buffer, last_data, last_status, last_summary

            line_buffer += data.decode("ascii", errors="replace")

            while "\n" in line_buffer:
                line, line_buffer = line_buffer.split("\n", 1)
                line = line.strip("\r").strip()
                if not line:
                    continue

                fields = line.split(",")

                if line.startswith("$"):
                    parsed = parse_summary_record(fields)
                    if parsed:
                        last_summary = parsed
                elif line.startswith("&"):
                    parsed = parse_status_record(fields)
                    if parsed:
                        last_status = parsed
                else:
                    parsed = parse_data_record(fields)
                    if parsed:
                        last_data = parsed

                display()

        await client.start_notify(char_uuid, callback)

        try:
            await asyncio.sleep(duration)
        except asyncio.CancelledError:
            pass

        await client.stop_notify(char_uuid)
        print("\nDone.")


# --- CLI ---

def main():
    parser = argparse.ArgumentParser(description="Lithionics Battery BLE Discovery Tool")
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="Scan for BLE devices")
    p_scan.add_argument("--duration", type=int, default=10, help="Scan duration in seconds (default: 10)")

    p_enum = sub.add_parser("enumerate", help="Enumerate GATT services/characteristics")
    p_enum.add_argument("address", help="BLE device address (MAC or UUID)")

    p_mon = sub.add_parser("monitor", help="Monitor raw BLE notifications")
    p_mon.add_argument("address", help="BLE device address")
    p_mon.add_argument("--uuid", help="Characteristic UUID to subscribe to (default: all notify-capable)")
    p_mon.add_argument("--duration", type=int, default=60, help="Monitor duration in seconds (default: 60)")

    p_parse = sub.add_parser("parse", help="Parse Lithionics battery data")
    p_parse.add_argument("address", help="BLE device address")
    p_parse.add_argument("--uuid", required=True, help="Data characteristic UUID")
    p_parse.add_argument("--duration", type=int, default=60, help="Parse duration in seconds (default: 60)")

    args = parser.parse_args()

    cmd_map = {
        "scan": cmd_scan,
        "enumerate": cmd_enumerate,
        "monitor": cmd_monitor,
        "parse": cmd_parse,
    }

    try:
        asyncio.run(cmd_map[args.command](args))
    except KeyboardInterrupt:
        print("\nInterrupted.")


if __name__ == "__main__":
    main()
