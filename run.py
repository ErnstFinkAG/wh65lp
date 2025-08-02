import paho.mqtt.client as mqtt
import time

print("STARTING MINIMAL MQTT TEST")

MQTT_HOST = "10.80.1.11"
MQTT_PORT = 1883
MQTT_USER = "mqtt_user"
MQTT_PASS = "mqtt_password"
MQTT_TOPIC = "weatherstation/test"

mqtt_client = mqtt.Client(protocol=mqtt.MQTTv311)
if MQTT_USER:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)

try:
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
    mqtt_client.loop_start()
    print("Connected to MQTT broker")
    mqtt_client.publish(MQTT_TOPIC, "mqtt test from python", retain=True)
    print("Published test message to MQTT topic")
except Exception as e:
    print(f"[ERROR] {e}")

time.sleep(5)
