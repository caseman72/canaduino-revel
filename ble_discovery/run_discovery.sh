#!/bin/bash
# BLE Discovery script for Lithionics batteries
# Run from the laptop in the van
set -e

cd "$(dirname "$0")"
source .venv/bin/activate

BATT1="CE08CA63-5ADC-8C80-2AB1-550307894C1E"
BATT2="65DB0DFA-12C8-B795-E245-0BBE37E0792A"
BATT3="2F7914EE-9960-F6FB-F899-A565BA64E035"

echo "=== Step 1: Enumerate Battery 1 (Li3-010622052) ==="
python lithionics_scanner.py enumerate "$BATT1"

echo ""
echo "=== Step 2: Monitor Battery 1 notifications (30s) ==="
python lithionics_scanner.py monitor "$BATT1" --duration 30

echo ""
echo "=== Step 3: Enumerate Battery 3 (Li3-032124086, different firmware) ==="
python lithionics_scanner.py enumerate "$BATT3"

echo ""
echo "Done! Results in gatt_services.json and raw_data.log"
