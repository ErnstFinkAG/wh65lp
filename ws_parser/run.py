import os
import socket
import time
import paho.mqtt.client as mqtt

HOST = "10.80.24.101"
PORT = 502
PACKET_SIZE = 25

MQTT_HOST = os.getenv("MQTT_HOST", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
MQTT_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "weatherstation")

mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
mqtt_client.loop_start()

def publish(topic, value):
    mqtt_client.publish(f"{MQTT_PREFIX}/{topic}", value, retain=True)

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
        print("✅ Published to MQTT")
    except Exception as e:
        print(f"[ERROR] {e}")

def main():
    print(f"[INFO] Connecting to {HOST}:{PORT}")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            while True:
                data = s.recv(PACKET_SIZE)
                if data and len(data) == PACKET_SIZE:
                    decode_and_publish(data)
                time.sleep(1)
    except Exception as e:
        print(f"[FATAL] {e}")

if __name__ == "__main__":
    main()
