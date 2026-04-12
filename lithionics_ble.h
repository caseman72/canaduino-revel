#pragma once
#include "esphome/components/sensor/sensor.h"
#include "esphome/components/text_sensor/text_sensor.h"
#include <string>
#include <cstring>
#include <cstdlib>

struct LithionicsSensors {
  esphome::sensor::Sensor *voltage;
  esphome::sensor::Sensor *cell1;
  esphome::sensor::Sensor *cell2;
  esphome::sensor::Sensor *cell3;
  esphome::sensor::Sensor *cell4;
  esphome::sensor::Sensor *bms_temp;
  esphome::sensor::Sensor *batt_temp;
  esphome::sensor::Sensor *current;
  esphome::sensor::Sensor *soc;
  esphome::sensor::Sensor *capacity;
  esphome::sensor::Sensor *power;
  esphome::text_sensor::TextSensor *status_code;
  std::string *last_status_code;
  uint32_t *last_status_publish_ms;
};

// Parse buffered BLE data from Lithionics battery into sensor values.
// Data arrives as ASCII CSV via BLE notifications (20-byte chunks).
// Three record types:
//   Data:    1338,334,336,333,335,64,62,-1,99,000000
//   Status:  &,1,119,006472,0000,0000,FFFF,FFFF
//   Summary: $,14163,0F4C7D,114,29,1011,228,332,ND010622052
inline void lithionics_parse(std::string &buf, const LithionicsSensors &s) {
  // Safety: clear buffer if it grows too large (corrupted data)
  if (buf.size() > 256) {
    buf.clear();
    return;
  }

  size_t pos;
  while ((pos = buf.find('\n')) != std::string::npos) {
    std::string line = buf.substr(0, pos);
    buf.erase(0, pos + 1);
    if (!line.empty() && line.back() == '\r') line.pop_back();
    if (line.empty()) continue;

    if (line[0] == '$') {
      // Summary record — not parsed yet (serial, aging factors, etc.)
    } else if (line[0] == '&') {
      // Status: &,battery_id,capacity_ah,power_raw,err1,err2,can1,can2
      char tmp[80];
      strncpy(tmp, line.c_str(), sizeof(tmp) - 1);
      tmp[sizeof(tmp) - 1] = '\0';
      char *sp;
      strtok_r(tmp, ",", &sp);              // &
      strtok_r(nullptr, ",", &sp);           // battery_id
      char *cap = strtok_r(nullptr, ",", &sp); // capacity
      if (cap && s.capacity) s.capacity->publish_state(atoi(cap));
    } else if (line[0] >= '0' && line[0] <= '9') {
      // Data: pack_v,c1,c2,c3,c4,bms_temp,batt_temp,current,soc,status
      int f[10] = {};
      int n = 0;
      char tmp[80];
      strncpy(tmp, line.c_str(), sizeof(tmp) - 1);
      tmp[sizeof(tmp) - 1] = '\0';
      char *sp;
      char *tok = strtok_r(tmp, ",", &sp);
      while (tok && n < 10) {
        f[n++] = atoi(tok);
        tok = strtok_r(nullptr, ",", &sp);
      }
      if (n >= 9) {
        if (s.voltage) s.voltage->publish_state(f[0] / 100.0f);
        if (s.cell1) s.cell1->publish_state(f[1] / 100.0f);
        if (s.cell2) s.cell2->publish_state(f[2] / 100.0f);
        if (s.cell3) s.cell3->publish_state(f[3] / 100.0f);
        if (s.cell4) s.cell4->publish_state(f[4] / 100.0f);
        if (s.bms_temp) s.bms_temp->publish_state(f[5]);
        if (s.batt_temp) s.batt_temp->publish_state(f[6]);
        if (s.current) s.current->publish_state(f[7]);
        if (s.soc) s.soc->publish_state(f[8]);
        if (s.power) s.power->publish_state(f[0] / 100.0f * f[7]);
        if (n >= 10 && s.status_code && s.last_status_code && s.last_status_publish_ms) {
          std::string code = line.substr(line.rfind(',') + 1);
          uint32_t now = millis();
          bool changed = code != *s.last_status_code;
          bool expired = (now - *s.last_status_publish_ms) >= 60000;
          if (changed || expired) {
            s.status_code->publish_state(code);
            *s.last_status_code = code;
            *s.last_status_publish_ms = now;
          }
        }
      }
    }
  }
}
