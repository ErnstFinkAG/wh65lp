import os
import socket
import time
import paho.mqtt.client as mqtt

HOST = "10.80.24.101"
PORT = 502
PACKET_SIZE = 25

DEBUG = os.getenv("DEBUG", "false").lower() == "true"

def getenv_int(varname, default):
    value = os.getenv(varname, str(default))
    try:
        return int(value)
    except ValueError:
        print(f"[WARN] Invalid int for {varname}: '{value}', using default: {default}")
        return default

print("[DEBUG] Reading environment variables:")
print(f"MQTT_HOST: {os.getenv('MQTT_HOST')}")
print(f"MQTT_PORT: {os.getenv('MQTT_PORT')}")
print(f"MQTT_USER: {os.getenv('MQTT_USER')}")
print(f"MQTT_PASS: {os.getenv('MQTT_PASS')}")
print(f"MQTT_TOPIC_PREFIX: {os.getenv('MQTT_TOPIC_PREFIX')}")


MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = getenv_int("MQTT_PORT", 1883)
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
MQTT_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "weatherstation")

print(f"[INFO] MQTT_HOST={MQTT_HOST}")
print(f"[INFO] MQTT_PORT={MQTT_PORT}")
print(f"[INFO] MQTT_USER={'(empty)' if not MQTT_USER else MQTT_USER}")
print(f"[INFO] MQTT_TOPIC_PREFIX={MQTT_PREFIX}")
print(f"[INFO] DEBUG mode: {'enabled' if DEBUG else 'disabled'}")

mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)
if MQTT_USER:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

try:
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start()
except Exception as e:
    print(f"[MQTT ERROR] Could not connect to MQTT → {e}")

def publish(topic, value):
    full_topic = f"{MQTT_PREFIX}/{topic}"
    if DEBUG:
        print(f"[MQTT] Publishing {full_topic} = {value}")
    mqtt_client.publish(full_topic, value, retain=True)

def decode_packet(data):
    temperature, wind, sun, rain, debug = {}, {}, {}, {}, {}

    if DEBUG:
        print(f"[DEBUG] Raw packet: {data.hex().upper()}")

    wind_dir = data[2]
    wind["wind_direction"] = wind_dir if wind_dir <= 359 else None

    dir_h = (data[3] >> 4) & 0x0F
    tmp_h = data[3] & 0x0F
    wsp_flag = (dir_h >> 2) & 0x01
    low_batt = (tmp_h >> 3) & 0x01
    tmp_10 = (tmp_h >> 2) & 0x01
    tmp_9 = (tmp_h >> 1) & 0x01
    tmp_8 = tmp_h & 0x01

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
        (tmp_10 << 10) | (tmp_9 << 9) | (tmp_8 << 8) |
        (tmp_7 << 7) | (tmp_6 << 6) | (tmp_5 << 5) |
        (tmp_3 << 3) | (tmp_2 << 2) | (tmp_1 << 1) | tmp_0
    )
    temperature["temperature"] = round((tmp_raw - 400) / 10.0, 1)
    temperature["humidity"] = data[5] if data[5] != 0xFF else None
    wind["windspeed"] = round(((data[6] >> 4) << 4 | (data[6] & 0x0F)) * 0.51 / 8, 2)
    wind["gust"] = round(data[7] * 0.51, 2) if data[7] != 0xFF else None
    rain["rainfall"] = round(((data[8] << 8) | data[9]) * 0.254, 2)
    sun["uv"] = (data[10] << 8) | data[11]
    sun["light"] = round(((data[12] << 16) | (data[13] << 8) | data[14]) / 10)
    sun["pressure"] = round((((data[17] & 0x7F) << 16) | (data[18] << 8) | data[19]) / 100.0, 2)
    debug["low_battery"] = bool(low_batt)
    debug["wsp_flag"] = wsp_flag

    if DEBUG:
        print(f"[DECODED] TEMP: {temperature}")
        print(f"[DECODED] WIND: {wind}")
        print(f"[DECODED] SUN: {sun}")
        print(f"[DECODED] RAIN: {rain}")
        print(f"[DECODED] DEBUG: {debug}")

    return temperature, wind, sun, rain, debug

def decode_and_publish(packet):
    try:
        temp, wind, sun, rain, debug = decode_packet(packet)
        publish("temperature", temp.get("temperature"))
        publish("humidity", temp.get("humidity"))
        publish("wind_direction", wind.get("wind_direction"))
        publish("wind_speed", wind.get("windspeed"))
        publish("wind_gust", wind.get("gust"))
        publish("uv", sun.get("uv"))
        publish("light", sun.get("light"))
        publish("pressure", sun.get("pressure"))
        publish("rainfall", rain.get("rainfall"))
        publish("battery_low", int(debug.get("low_battery", False)))
    except Exception as e:
        print(f"[ERROR] decode_and_publish failed → {e}")

def main():
    print(f"[INFO] Connecting to weather station at {HOST}:{PORT}")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            while True:
                data = s.recv(PACKET_SIZE)
                if data and len(data) == PACKET_SIZE:
                    decode_and_publish(data)
                time.sleep(1)
    except Exception as e:
        print(f"[FATAL] Socket connection failed → {e}")

if __name__ == "__main__":
    main()
