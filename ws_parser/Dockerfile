FROM python:3.11-slim

WORKDIR /app

COPY run.py .

RUN pip install paho-mqtt

# 👇 These enable HA config values to become environment variables in container
ENV MQTT_HOST=$MQTT_HOST
ENV MQTT_PORT=$MQTT_PORT
ENV MQTT_USER=$MQTT_USER
ENV MQTT_PASS=$MQTT_PASS
ENV MQTT_TOPIC_PREFIX=$MQTT_TOPIC_PREFIX

CMD ["python", "run.py"]