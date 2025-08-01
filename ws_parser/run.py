import os
import socket
import time
import paho.mqtt.client as mqtt

print("[DEBUG] WS Parser started")

# === Config ===
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

# === Print all environment variables (for deep debug) ===
if DEBUG:
    print("[DEBUG] All environment variables:")
    for k, v in os.environ.items():
        print(f"  {k}={v}")

# === Environment vars for MQTT ===
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = getenv_int("MQTT_PORT", 1883)
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
MQTT_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "weatherstation")

if DEBUG:
    print("[DEBUG] MQTT settings:")
    print(f"  MQTT_HOST: {MQTT_HOST}")
    print(f"  MQTT_PORT: {MQTT_PORT}")
    print(f"  MQTT_USER: {MQTT_USER}")
    print(f"  MQTT_PASS: {'(hidden)' if MQTT_PASS else ''}")
    print(f"  MQTT_PREFIX: {MQTT_PREFIX}")

# === MQTT Setup ===
mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)
if MQTT_USER:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

try:
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start()
    if DEBUG:
        print(f"[INFO] Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
except Exception as e:
    print(f"[MQTT ERROR] Could not connect to MQTT → {e}")

def publish(topic, value):
    full_topic = f"{MQTT_PREFIX}/{topic}"
    mqtt_client.publish(full_topic, value, retain=True)
    if DEBUG:
        print(f"[MQTT] Publishing {full_topic} = {value}")

def decode_packet(data):
    temperature = {}
    wind = {}
    sun = {}
    rain = {}
    debug = {}

    wind_dir = data[2]
    wind["wind_direction"] = wind_dir if wind_dir <= 359 else None

    dir_h = (data[3] >> 4) & 0x0F
    tmp_h = data[3] & 0x0F
    debug["low_battery"] = bool((tmp_h >> 3) & 0x01)

    tmp_m = (data[4] >> 4) & 0x0F
    tmp_l = data[4] & 0x0F
    tmp_raw = (
        ((tmp_h & 0x07) << 8) |
        ((tmp_m & 0x0F) << 4) |
        (tmp_l & 0x0F)
    )
    temperature["temperature"] = round((tmp_raw - 400) / 10.0, 1)
    debug["TMP_raw"] = tmp_raw

    hum = data[5]
    temperature["humidity"] = hum if hum != 0xFF else None

    wsp_raw = data[6]
    wind["wind_speed"] = round((wsp_raw * 0.51) / 8, 2)

    gust = data[7]
    wind["wind_gust"] = round(gust * 0.51, 2) if gust != 0xFF else None

    rain_raw = (data[8] << 8) | data[9]
    rain["rainfall"] = round(rain_raw * 0.254, 2)

    uv_raw = (data[10] << 8) | data[11]
    sun["uv"] = uv_raw

    light_raw = (data[12] << 16) | (data[13] << 8) | data[14]
    sun["light"] = round(light_raw / 10, 1)

    pressure_raw = ((data[17] & 0x7F) << 16) | (data[18] << 8) | data[19]
    sun["pressure"] = round(pressure_raw / 100.0, 2)

    return temperature, wind, sun, rain, debug

def decode_and_publish(data):
    try:
        temperature, wind, sun, rain, debug = decode_packet(data)
        publish("temperature", temperature.get("temperature"))
        publish("humidity", temperature.get("humidity"))
        publish("wind_direction", wind.get("wind_direction"))
        publish("wind_speed", wind.get("wind_speed"))
        publish("wind_gust", wind.get("wind_gust"))
        publish("rainfall", rain.get("rainfall"))
        publish("uv", sun.get("uv"))
        publish("light", sun.get("light"))
        publish("pressure", sun.get("pressure"))
        publish("battery_low", int(debug.get("low_battery", False)))
        if DEBUG:
            print("[DEBUG] Decoded and published one packet.")
    except Exception as e:
        print(f"[ERROR] Failed to decode/publish: {e}")

def main():
    print(f"[INFO] Connecting to weather station at {HOST}:{PORT}")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            while True:
                if DEBUG:
                    print("[DEBUG] Waiting for data...")
                data = s.recv(PACKET_SIZE)
                if data and len(data) == PACKET_SIZE:
                    if DEBUG:
                        print(f"[DEBUG] Packet received: {data.hex()}")
                    decode_and_publish(data)
                else:
                    print(f"[WARN] Incomplete or empty packet received: {data}")
                time.sleep(1)
    except Exception as e:
        print(f"[FATAL] Could not connect to weather station → {e}")
    finally:
        mqtt_client.loop_stop()

if __name__ == "__main__":
    main()
