import socket
import time
import json
import paho.mqtt.client as mqtt

HOST = '10.80.24.101'
PORT = 502
PACKET_SIZE = 25

MQTT_HOST = '10.80.1.11'
MQTT_PORT = 1883
MQTT_USER = "mqtt_user"         # oder "" falls anonym
MQTT_PASS = "mqtt_password"     # oder "" falls anonym
MQTT_PREFIX = "weatherstation"

SENSOR_DEFS = [
    {"key": "temperature_C", "name": "WH65LP Temperatur", "unit": "°C", "class": "temperature"},
    {"key": "humidity_percent", "name": "WH65LP Feuchte", "unit": "%", "class": "humidity"},
    {"key": "wind_direction_deg", "name": "WH65LP Windrichtung", "unit": "°", "class": None},
    {"key": "windspeed_mps", "name": "WH65LP Wind", "unit": "m/s", "class": "wind_speed"},
    {"key": "gust_speed_mps", "name": "WH65LP Böe", "unit": "m/s", "class": None},
    {"key": "uv_uW_cm2", "name": "WH65LP UV", "unit": "uW/cm²", "class": None},
    {"key": "light_lux", "name": "WH65LP Licht", "unit": "lx", "class": "illuminance"},
    {"key": "pressure_hpa", "name": "WH65LP Luftdruck", "unit": "hPa", "class": "pressure"},
    {"key": "rainfall_mm", "name": "WH65LP Regen", "unit": "mm", "class": None},
    {"key": "low_battery", "name": "WH65LP Batterie schwach", "unit": None, "class": "battery"},
]

def decode_packet(data):
    # ... (deine decode_packet Funktion wie gehabt!)
    # Kopiere deinen bestehenden decode_packet code hier rein
    pass  # <--- ersetzt durch deinen decoder!

def publish_discovery(mqtt_client):
    for s in SENSOR_DEFS:
        uid = f"wh65lp_{s['key']}"
        topic = f"homeassistant/sensor/{uid}/config"
        payload = {
            "name": s["name"],
            "state_topic": f"{MQTT_PREFIX}/{s['key']}",
            "unique_id": uid,
            "device": {
                "identifiers": ["wh65lp_station"],
                "manufacturer": "Fine Offset",
                "model": "WH65LP",
                "name": "WH65LP Wetterstation"
            }
        }
        if s["unit"]: payload["unit_of_measurement"] = s["unit"]
        if s["class"]: payload["device_class"] = s["class"]

        mqtt_client.publish(topic, json.dumps(payload), retain=True)
        print(f"[DISCOVERY] Published discovery for {s['name']} ({topic})")

def publish_mqtt(mqtt_client, data):
    for s in SENSOR_DEFS:
        topic = f"{MQTT_PREFIX}/{s['key']}"
        value = data.get(s['key'], None)
        if value is not None:
            mqtt_client.publish(topic, value, retain=True)
            print(f"[MQTT] {topic} = {value}")

def main():
    mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)
    if MQTT_USER:
        mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start()
    print("[INFO] MQTT connected, sending discovery...")
    time.sleep(1)
    publish_discovery(mqtt_client)

    print(f"[INFO] Connecting to {HOST}:{PORT}...")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.connect((HOST, PORT))
            print("[INFO] Connected. Listening for 25-byte packets...\n")
            while True:
                packet = s.recv(PACKET_SIZE)
                if not packet or len(packet) < PACKET_SIZE:
                    print("[WARN] Invalid/incomplete packet, skipping...")
                    continue

                # Hier muss decode_packet DEINE Daten als Dict liefern:
                temperature, wind, sun, rain, debug = decode_packet(packet)
                # Sammle alle relevanten Werte in einem dict:
                data = {
                    "temperature_C": temperature.get("temperature_C"),
                    "humidity_percent": temperature.get("humidity_percent"),
                    "wind_direction_deg": wind.get("wind_direction_deg"),
                    "windspeed_mps": wind.get("windspeed_mps"),
                    "gust_speed_mps": wind.get("gust_speed_mps"),
                    "uv_uW_cm2": sun.get("uv_uW/cm²"),
                    "light_lux": sun.get("light_lux"),
                    "pressure_hpa": sun.get("pressure_hpa"),
                    "rainfall_mm": rain.get("rainfall_mm"),
                    "low_battery": int(debug.get("low_battery", 0)),
                }
                publish_mqtt(mqtt_client, data)
                print("[DEBUG] Published MQTT for all categories.")
                print("-" * 60)
                time.sleep(1)
    except Exception as e:
        print(f"[FATAL] {e}")

if __name__ == "__main__":
    main()
