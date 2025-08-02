import os
import paho.mqtt.client as mqtt

print(">>> WS PARSER RUNNING <<<")

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = os.getenv("MQTT_PORT")
if not MQTT_PORT or not MQTT_PORT.isdigit():
    print(f"[WARN] Invalid MQTT_PORT: '{MQTT_PORT}', defaulting to 1883")
    MQTT_PORT = 1883
else:
    MQTT_PORT = int(MQTT_PORT)

MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
MQTT_TOPIC = os.getenv("MQTT_TOPIC_PREFIX", "weatherstation/test")

print(f"Connecting to MQTT at {MQTT_HOST}:{MQTT_PORT} as user '{MQTT_USER}'")

mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)
if MQTT_USER:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

try:
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start()
    print("Connected, publishing test message...")
    mqtt_client.publish(f"{MQTT_TOPIC}", "hello world", retain=True)
    print("Published! Check your MQTT broker for the test message.")
except Exception as e:
    print(f"[ERROR] Could not connect/publish to MQTT: {e}")

import time
time.sleep(5)
