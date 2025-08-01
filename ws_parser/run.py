import os
import socket
import time
import paho.mqtt.client as mqtt

print("[DEBUG] WS Parser started")

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

# Load MQTT configuration
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = getenv_int("MQTT_PORT", 1883)
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
MQTT_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "weatherstation")

print("[DEBUG] Environment Variables:")
print(f"MQTT_HOST: '{MQTT_HOST}'")
print(f"MQTT_PORT: {MQTT_PORT}")
print(f"MQTT_USER: '{MQTT_USER}'")
print(f"MQTT_PASS: '{MQTT_PASS}'")
print(f"MQTT_PREFIX: '{MQTT_PREFIX}'")

# Setup MQTT client
try:
    mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)
    if MQTT_USER and MQTT_PASS:
        mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
        print("[DEBUG] MQTT authentication configured")
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start()
    print(f"[INFO] Connected to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
except Exception as e:
    print(f"[MQTT ERROR] Could not connect to MQTT → {e}")

def publish(topic, value):
    full_topic = f"{MQTT_PREFIX}/{topic}"
    if DEBUG:
        print(f"[MQTT] Publishing {full_topic} = {value}")
    mqtt_client.publish(full_topic, value, retain=True)

def decode_packet(data):
    temperature = {}
    wind = {}
    sun = {}
    rain = {}
    debug = {}

    wind_dir = data[2]
    wind["wind_direction_deg"] = wind_dir if wind_dir <= 359 else None

    dir_h = (data[3] >> 4) & 0x0F
    tmp_h = data[3] & 0x0F
    debug["WSP_FLAG"] = (dir_h >> 2) & 0x01
    debug["low_battery"] = bool((tmp_h >> 3) & 0x01)

    tmp_bits = [
        ((tmp_h >> 2) & 0x01) << 10,
        ((tmp_h >> 1) & 0x01) << 9,
        (tmp_h & 0x01) << 8,
        ((data[4] >> 4) & 0x08) << 4,
        ((data[4] >> 4) & 0x04) << 4,
        ((data[4] >> 4) & 0x02) << 4,
        ((data[4] >> 4) & 0x01) << 4,
        ((data[4] & 0x0F) >> 3) << 3,
        ((data[4] & 0x0F) >> 2) << 2,
        ((data[4] & 0x0F) >> 1) << 1,
        (data[4] & 0x01)
    ]
    tmp_raw = sum(tmp_bits)
    temperature["temperature_C"] = round((tmp_raw - 400) / 10.0, 1)
    debug["TMP_raw"] = tmp_raw

    hum = data[5]
    temperature["humidity_percent"] = hum if hum != 0xFF else None

    wsp_high = (data[6] >> 4) & 0x0F
    wsp_low = data[6] & 0x0F
    wsp_raw = (wsp_high << 4) | wsp_low
    wind["windspeed_mps"] = round(wsp_raw * 0.51 / 8, 2) if wsp_raw != 0x7FF else None
    debug["WSP_raw"] = wsp_raw

    gust = data[7]
    wind["gust_speed_mps"] = round(gust * 0.51, 2) if gust != 0xFF else None

    rain_raw = (data[8] << 8) | data[9]
    rain["rainfall_mm"] = round(rain_raw * 0.254, 2)
    debug["rain_raw"] = rain_raw

    uv_raw = (data[10] << 8) | data[11]
    sun["uv_uW/cm²"] = uv_raw

    light_raw = (data[12] << 16) | (data[13] << 8) | data[14]
    sun["light_lux"] = round(light_raw / 10) if light_raw != 0xFFFFFF else None
    debug["light_raw"] = light_raw

    pressure_raw = ((data[17] & 0x7F) << 16) | (data[18] << 8) | data[19]
    sun["pressure_hpa"] = round(pressure_raw / 100.0, 2) if pressure_raw != 0x1FFFF else None
    debug["pressure_raw"] = pressure_raw

    if DEBUG:
        print("[DEBUG] Decoded data:")
        print("  Temp:", temperature)
        print("  Wind:", wind)
        print("  Sun :", sun)
        print("  Rain:", rain)
        print("  Debug:", debug)

    return temperature, wind, sun, rain, debug

def decode_and_publish(packet):
    try:
        temp, wind, sun, rain, debug = decode_packet(packet)
        publish("temperature", temp.get("temperature_C"))
        publish("humidity", temp.get("humidity_percent"))
        publish("wind_direction", wind.get("wind_direction_deg"))
        publish("wind_speed", wind.get("windspeed_mps"))
        publish("wind_gust", wind.get("gust_speed_mps"))
        publish("uv", sun.get("uv_uW/cm²"))
        publish("light", sun.get("light_lux"))
        publish("pressure", sun.get("pressure_hpa"))
        publish("rainfall", rain.get("rainfall_mm"))
        publish("battery_low", int(debug.get("low_battery", False)))
        print("[INFO] Published packet successfully")
    except Exception as e:
        print(f"[ERROR] Packet decode/publish failed: {e}")

def main():
    print(f"[INFO] Connecting to weather station at {HOST}:{PORT}")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            while True:
                data = s.recv(PACKET_SIZE)
                if data and len(data) == PACKET_SIZE:
                    decode_and_publish(data)
                else:
                    print(f"[WARN] Incomplete or empty packet received: {data}")
                time.sleep(1)
    except Exception as e:
        print(f"[FATAL] Could not connect to weather station → {e}")

if __name__ == "__main__":
    main()
