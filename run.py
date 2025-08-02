import socket
import time
import paho.mqtt.client as mqtt

print(">>> WS PARSER ADD-ON STARTING <<<")

# === HARD-CODED CONFIG ===
WS_HOST = "10.80.24.101"
WS_PORT = 502
PACKET_SIZE = 25

MQTT_HOST = "10.80.1.11"
MQTT_PORT = 1883
MQTT_USER = "mqtt_user"
MQTT_PASS = "mqtt_password"
MQTT_PREFIX = "weatherstation"
DEBUG = True

# === MQTT SETUP ===
mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)
if MQTT_USER:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
try:
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start()
    print(f"[INFO] Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
except Exception as e:
    print(f"[MQTT ERROR] Could not connect to MQTT → {e}")

def publish(group, key, value):
    topic = f"{MQTT_PREFIX}/{key}"
    mqtt_client.publish(topic, value, retain=True)
    if DEBUG:
        print(f"[MQTT] {topic} = {value}")

def decode_packet(data):
    if len(data) != 25:
        raise ValueError("Invalid packet size")

    temperature = {}
    wind = {}
    sun = {}
    rain = {}
    debug = {}

    # Byte 0: Family code
    debug["family_code"] = data[0]
    debug["tx_interval"] = "16s" if data[0] == 0x24 else "unknown"

    # Byte 1: ID LSB
    debug["device_id_lsb"] = data[1]

    # Byte 2: Wind Direction
    wind_dir = data[2]
    wind["wind_direction_deg"] = wind_dir if wind_dir <= 359 else None

    # Byte 3: DIR_H + TMP_H
    dir_h = (data[3] >> 4) & 0x0F
    tmp_h = data[3] & 0x0F
    debug["DIR_8"] = (dir_h >> 3) & 0x01
    debug["WSP_FLAG"] = (dir_h >> 2) & 0x01
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

    # Byte 15: CRC1
    debug["crc1"] = data[15]

    # Byte 16: Checksum1
    debug["checksum1"] = data[16]

    # Bytes 17–19: Pressure (23-bit, MSB bit is WSP_10)
    wsp_10 = (data[17] >> 7) & 0x01
    pressure_raw = ((data[17] & 0x7F) << 16) | (data[18] << 8) | data[19]
    sun["pressure_hpa"] = round(pressure_raw / 100.0, 2) if pressure_raw != 0x1FFFF else None
    debug["WSP_10"] = wsp_10
    debug["pressure_raw"] = pressure_raw

    # Byte 20: Pressure checksum
    debug["pressure_checksum"] = data[20]

    # Bytes 21–22: ID_MSB + ID_HSB
    device_id = (data[22] << 16) | (data[21] << 8) | data[1]
    debug["device_id_full"] = f"{device_id:06X}"

    # Byte 23: CRC2
    debug["crc2"] = data[23]

    # Byte 24: Checksum2
    debug["checksum2"] = data[24]

    return temperature, wind, sun, rain, debug

def main():
    print(f"[INFO] Connecting to weather station at {WS_HOST}:{WS_PORT}")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((WS_HOST, WS_PORT))
            print("[INFO] Connected. Listening for 25-byte packets...")

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

                    for k, v in temp.items():
                        publish("temperature", k, v)
                    for k, v in wind.items():
                        publish("wind", k, v)
                    for k, v in sun.items():
                        publish("sun", k, v)
                    for k, v in rain.items():
                        publish("rain", k, v)
                    publish("debug", "low_battery", int(debug.get("low_battery", False)))

                    if DEBUG:
                        print("[DEBUG] Published MQTT for all categories.")
                        print("-" * 60)

                except Exception as e:
                    print(f"[!] Failed to decode packet: {e}")

                time.sleep(1)

    except Exception as e:
        print(f"[FATAL] {e}")
    finally:
        mqtt_client.loop_stop()

if __name__ == "__main__":
    main()
