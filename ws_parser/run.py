import os
import socket
import time
import paho.mqtt.client as mqtt
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Weather station connection
HOST = "10.80.24.101"
PORT = 502
PACKET_SIZE = 25

# Helper to safely parse integer env vars
def getenv_int(varname, default):
    value = os.getenv(varname, str(default))
    try:
        return int(value)
    except ValueError:
        print(f"[WARN] Invalid int for {varname}: '{value}', using default: {default}")
        return default

# MQTT configuration
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = getenv_int("MQTT_PORT", 1883)
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
MQTT_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "weatherstation")

# Initialize MQTT client
print(f"[INFO] Connecting to MQTT broker at {MQTT_HOST}:{MQTT_PORT}")
mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)

if MQTT_USER or MQTT_PASS:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

try:
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start()
except Exception as e:
    print(f"[MQTT ERROR] Could not connect to MQTT → {e}")

# Publish function
def publish(topic, value):
    full_topic = f"{MQTT_PREFIX}/{topic}"
    print(f"[MQTT] Publishing {full_topic} = {value}")
    mqtt_client.publish(full_topic, value, retain=True)

# Decode and categorize data
def decode_packet(data):
    temperature = {}
    wind = {}
    sun = {}
    rain = {}
    debug = {}

    # Wind direction
    wind_dir = data[2]
    wind["wind_direction_deg"] = wind_dir if wind_dir <= 359 else None

    # Temp bits + low battery
    dir_h = (data[3] >> 4) & 0x0F
    tmp_h = data[3] & 0x0F
    wsp_flag = (dir_h >> 2) & 0x01
    battery_low = bool((tmp_h >> 3) & 0x01)
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

    temperature["temperature_C"] = round((tmp_raw - 400) / 10.0, 1)
    temperature["humidity_percent"] = data[5] if data[5] != 0xFF else None
    debug["battery_low"] = battery_low

    # Wind speed and gust
    wsp_high = (data[6] >> 4) & 0x0F
    wsp_low = data[6] & 0x0F
    wsp_raw = (wsp_high << 4) | wsp_low
    wind["windspeed_mps"] = round(wsp_raw * 0.51 / 8, 2) if wsp_raw != 0x7FF else None

    gust = data[7]
    wind["gust_speed_mps"] = round(gust * 0.51, 2) if gust != 0xFF else None

    # Rainfall
    rain_raw = (data[8] << 8) | data[9]
    rain["rainfall_mm"] = round(rain_raw * 0.254, 2)

    # UV & Light
    uv_raw = (data[10] << 8) | data[11]
    sun["uv_uW_cm2"] = uv_raw

    light_raw = (data[12] << 16) | (data[13] << 8) | data[14]
    sun["light_lux"] = round(light_raw / 10.0, 1) if light_raw != 0xFFFFFF else None

    # Pressure
    pressure_raw = ((data[17] & 0x7F) << 16) | (data[18] << 8) | data[19]
    sun["pressure_hpa"] = round(pressure_raw / 100.0, 2) if pressure_raw != 0x1FFFF else None

    return temperature, wind, sun, rain, debug

# Decode, publish
def decode_and_publish(packet):
    try:
        temp, wind, sun, rain, debug = decode_packet(packet)

        publish("temperature", temp.get("temperature_C"))
        publish("humidity", temp.get("humidity_percent"))
        publish("wind_direction", wind.get("wind_direction_deg"))
        publish("wind_speed", wind.get("windspeed_mps"))
        publish("wind_gust", wind.get("gust_speed_mps"))
        publish("uv", sun.get("uv_uW_cm2"))
        publish("light", sun.get("light_lux"))
        publish("pressure", sun.get("pressure_hpa"))
        publish("rainfall", rain.get("rainfall_mm"))
        publish("battery_low", int(debug.get("battery_low", False)))

    except Exception as e:
        print(f"[ERROR] Packet decode failed: {e}")

# Main loop
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
        print(f"[FATAL] Could not connect to weather station: {e}")

if __name__ == "__main__":
    main()
