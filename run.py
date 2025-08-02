import socket
import time
import paho.mqtt.client as mqtt
import json

# --- Hardcoded MQTT config (set your values here) ---
MQTT_HOST = "10.80.1.11"
MQTT_PORT = 1883
MQTT_USER = "mqtt_user"
MQTT_PASS = "mqtt_password"
MQTT_PREFIX = "weatherstation"
DISCOVERY_PREFIX = "homeassistant"

# --- Weather station TCP config ---
WS_HOST = "10.80.24.101"
WS_PORT = 502
PACKET_SIZE = 25

# --- MQTT Setup ---
mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)
if MQTT_USER:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

def on_connect(client, userdata, flags, rc):
    print("[INFO] MQTT connected, sending discovery...")
    send_discovery()

mqtt_client.on_connect = on_connect

def mqtt_publish(topic, value, retain=True):
    full_topic = f"{MQTT_PREFIX}/{topic}"
    mqtt_client.publish(full_topic, value, retain=retain)
    print(f"[MQTT] {full_topic} = {value}")

# --- Home Assistant MQTT Discovery ---
def send_discovery():
    # Sensor definitions
    sensors = [
        ("temperature_C", "Temperatur", "°C"),
        ("humidity_percent", "Feuchte", "%"),
        ("wind_direction_deg", "Windrichtung", "°"),
        ("windspeed_mps", "Wind", "m/s"),
        ("gust_speed_mps", "Böe", "m/s"),
        ("uv_uW_cm2", "UV", "uW/cm²"),
        ("light_lux", "Licht", "lx"),
        ("pressure_hpa", "Luftdruck", "hPa"),
        ("rainfall_mm", "Regen", "mm"),
        ("low_battery", "Batterie schwach", None),
    ]
    for sensor_id, name, unit in sensors:
        unique_id = f"wh65lp_{sensor_id}"
        state_topic = f"{MQTT_PREFIX}/{sensor_id}"
        payload = {
            "name": f"WH65LP {name}",
            "state_topic": state_topic,
            "unique_id": unique_id,
            "device": {
                "identifiers": ["wh65lp_rs485"],
                "name": "WH65LP Wetterstation",
                "manufacturer": "Fine Offset",
                "model": "WH65LP"
            }
        }
        if unit:
            payload["unit_of_measurement"] = unit
        # Entity class for battery
        if sensor_id == "low_battery":
            payload["device_class"] = "battery"
        topic = f"{DISCOVERY_PREFIX}/sensor/{unique_id}/config"
        mqtt_client.publish(topic, json.dumps(payload), retain=True)
        print(f"[DISCOVERY] Published discovery for {name} ({topic})")

# --- Packet Decoder ---
def decode_packet(data):
    if len(data) != 25:
        raise ValueError("Invalid packet size")

    temperature = {}
    wind = {}
    sun = {}
    rain = {}
    debug = {}

    # Byte 2: Wind Direction
    wind_dir = data[2]
    wind["wind_direction_deg"] = wind_dir if wind_dir <= 359 else None

    # Byte 3: DIR_H + TMP_H
    dir_h = (data[3] >> 4) & 0x0F
    tmp_h = data[3] & 0x0F
    debug["low_battery"] = bool((tmp_h >> 3) & 0x01)
    tmp_10 = (tmp_h >> 2) & 0x01
    tmp_9 = (tmp_h >> 1) & 0x01
    tmp_8 = tmp_h & 0x01

    # Byte 4: TMP_M + TMP_L
    tmp_m = (data[4] >> 4) & 0x0F
    tmp_l = data[4] & 0x0F
    tmp_7 = (tmp_m >> 3) & 0x01
    tmp_6 = (tmp_m >> 2) & 0x01
    tmp_5 = (tmp_m >> 1) & 0x01
    tmp_3 = (tmp_l >> 3) & 0x01
    tmp_2 = (tmp_l >> 2) & 0x01
    tmp_1 = (tmp_l >> 1) & 0x01
    tmp_0 = tmp_l & 0x01
    tmp_raw = (
        (tmp_10 << 10) |
        (tmp_9 << 9) |
        (tmp_8 << 8) |
        (tmp_7 << 7) |
        (tmp_6 << 6) |
        (tmp_5 << 5) |
        (tmp_3 << 3) |
        (tmp_2 << 2) |
        (tmp_1 << 1) |
        (tmp_0 << 0)
    )
    temperature["temperature_C"] = round((tmp_raw - 400) / 10.0, 1)
    debug["TMP_raw"] = tmp_raw

    # Byte 5: Humidity
    hum = data[5]
    temperature["humidity_percent"] = hum if hum != 0xFF else None

    # Byte 6: Windspeed
    wsp_high = (data[6] >> 4) & 0x0F
    wsp_low = data[6] & 0x0F
    wsp_raw = (wsp_high << 4) | wsp_low
    wind["windspeed_mps"] = round(wsp_raw * 0.51 / 8, 2) if wsp_raw != 0x7FF else None
    debug["WSP_raw"] = wsp_raw

    # Byte 7: Gust
    gust = data[7]
    wind["gust_speed_mps"] = round(gust * 0.51, 2) if gust != 0xFF else None

    # Bytes 8–9: Rainfall
    rain_raw = (data[8] << 8) | data[9]
    rain["rainfall_mm"] = round(rain_raw * 0.254, 2)
    debug["rain_raw"] = rain_raw

    # Bytes 10–11: UV
    uv_raw = (data[10] << 8) | data[11]
    sun["uv_uW_cm2"] = uv_raw

    # Bytes 12–14: Light
    light_raw = (data[12] << 16) | (data[13] << 8) | data[14]
    sun["light_lux"] = round(light_raw / 10) if light_raw != 0xFFFFFF else None
    debug["light_raw"] = light_raw

    # Bytes 17–19: Pressure (23-bit, MSB bit is WSP_10)
    pressure_raw = ((data[17] & 0x7F) << 16) | (data[18] << 8) | data[19]
    sun["pressure_hpa"] = round(pressure_raw / 100.0, 2) if pressure_raw != 0x1FFFF else None
    debug["pressure_raw"] = pressure_raw

    # Battery
    debug["low_battery"] = int(bool((tmp_h >> 3) & 0x01))

    return temperature, wind, sun, rain, debug

def publish_all(temperature, wind, sun, rain, debug):
    mqtt_publish("temperature_C", temperature.get("temperature_C"))
    mqtt_publish("humidity_percent", temperature.get("humidity_percent"))
    mqtt_publish("wind_direction_deg", wind.get("wind_direction_deg"))
    mqtt_publish("windspeed_mps", wind.get("windspeed_mps"))
    mqtt_publish("gust_speed_mps", wind.get("gust_speed_mps"))
    mqtt_publish("rainfall_mm", rain.get("rainfall_mm"))
    mqtt_publish("uv_uW_cm2", sun.get("uv_uW_cm2"))
    mqtt_publish("light_lux", sun.get("light_lux"))
    mqtt_publish("pressure_hpa", sun.get("pressure_hpa"))
    mqtt_publish("low_battery", debug.get("low_battery"))
    print("[DEBUG] Published MQTT for all categories.")
    print("------------------------------------------------------------")

# --- Main Loop ---
def main():
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start()
    time.sleep(2)  # Give MQTT time to connect and send discovery

    print(f"[INFO] Connecting to {WS_HOST}:{WS_PORT}...")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((WS_HOST, WS_PORT))
            print("[INFO] Connected. Listening for 25-byte packets...\n")

            while True:
                packet = s.recv(PACKET_SIZE)
                if not packet:
                    print("[!] Connection closed.")
                    break

                if len(packet) < PACKET_SIZE:
                    print(f"[!] Incomplete packet ({len(packet)} bytes). Skipping...")
                    continue

                try:
                    temp, wind, sun, rain, debug = decode_packet(packet)
                    publish_all(temp, wind, sun, rain, debug)
                except Exception as e:
                    print(f"[!] Failed to decode or publish packet: {e}")

                time.sleep(1)

    except Exception as e:
        print(f"[FATAL] {e}")

if __name__ == "__main__":
    main()
