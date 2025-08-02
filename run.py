import os
import paho.mqtt.client as mqtt

print(">>> WS PARSER RUNNING <<<")
print("[DEBUG] Hardcoded config mode!")

# ----- HARDCODE YOUR SETTINGS HERE -----
MQTT_HOST = "10.80.1.11"
MQTT_PORT = 1883
MQTT_USER = "mqtt_user"         # Use "" if no user
MQTT_PASS = "mqtt_password"     # Use "" if no pass
MQTT_TOPIC = "weatherstation/test"
# ---------------------------------------

print(f"Connecting to MQTT at {MQTT_HOST}:{MQTT_PORT} as user '{MQTT_USER}'")

mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)
if MQTT_USER:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

try:
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start()
    print("Connected, publishing test message...")
    mqtt_client.publish(MQTT_TOPIC, "hello world (hardcoded)", retain=True)
    print("Published! Check your MQTT broker for the test message.")
except Exception as e:
    print(f"[ERROR] Could not connect/publish to MQTT: {e}")

import time
time.sleep(5)
