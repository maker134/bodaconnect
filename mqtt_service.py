"""
BodaConnect MQTT Service
========================
This file handles all real-time communication between:
- Passengers (publishers of ride requests)
- Drivers (subscribers who receive requests)
- Backend (publishes ride status updates)

Topics used:
- ride/request  → Passenger requests a ride
- ride/status   → Driver updates ride status
- driver/location → Driver sends location updates
"""

import paho.mqtt.client as mqtt
import json
import os
import time
import threading

# ── MQTT Configuration ──────────────────────────────────────
MQTT_BROKER = os.environ.get('MQTT_BROKER', 'localhost')
MQTT_PORT   = int(os.environ.get('MQTT_PORT', 1883))

# ── Topics ──────────────────────────────────────────────────
TOPIC_RIDE_REQUEST    = 'ride/request'
TOPIC_RIDE_STATUS     = 'ride/status'
TOPIC_DRIVER_LOCATION = 'driver/location'

# ── Message received storage ────────────────────────────────
received_messages = []

def on_connect(client, userdata, flags, rc):
    """Called when connected to MQTT broker"""
    if rc == 0:
        print(f"✅ Connected to MQTT Broker at {MQTT_BROKER}:{MQTT_PORT}")
        # Subscribe to all topics
        client.subscribe(TOPIC_RIDE_REQUEST)
        client.subscribe(TOPIC_RIDE_STATUS)
        client.subscribe(TOPIC_DRIVER_LOCATION)
        print(f"📡 Subscribed to topics:")
        print(f"   - {TOPIC_RIDE_REQUEST}")
        print(f"   - {TOPIC_RIDE_STATUS}")
        print(f"   - {TOPIC_DRIVER_LOCATION}")
    else:
        print(f"❌ Failed to connect. Code: {rc}")

def on_message(client, userdata, msg):
    """Called when a message is received"""
    try:
        payload = json.loads(msg.payload.decode())
        message = {
            'topic': msg.topic,
            'data': payload,
            'time': time.strftime('%H:%M:%S')
        }
        received_messages.append(message)
        # Keep only last 50 messages
        if len(received_messages) > 50:
            received_messages.pop(0)

        print(f"\n📨 Message received!")
        print(f"   Topic: {msg.topic}")
        print(f"   Data:  {json.dumps(payload, indent=2)}")

    except Exception as e:
        print(f"❌ Error processing message: {e}")

def on_disconnect(client, userdata, rc):
    """Called when disconnected"""
    print(f"⚠️  Disconnected from MQTT Broker (code: {rc})")

def create_mqtt_client():
    """Create and configure MQTT client"""
    client = mqtt.Client(client_id="bodaconnect-backend")
    client.on_connect    = on_connect
    client.on_message    = on_message
    client.on_disconnect = on_disconnect
    return client

def publish_ride_request(client, user_id, pickup, destination, phone):
    """
    Passenger publishes a ride request
    Topic: ride/request
    """
    message = {
        "event":       "ride_request",
        "user_id":     user_id,
        "pickup":      pickup,
        "destination": destination,
        "phone":       phone,
        "timestamp":   time.strftime('%Y-%m-%d %H:%M:%S'),
        "status":      "pending"
    }
    payload = json.dumps(message)
    result  = client.publish(TOPIC_RIDE_REQUEST, payload, qos=1)
    print(f"\n🚀 Ride request published!")
    print(f"   Topic: {TOPIC_RIDE_REQUEST}")
    print(f"   Data:  {json.dumps(message, indent=2)}")
    return result

def publish_ride_status(client, ride_id, driver_id, status, passenger_id):
    """
    Driver publishes ride status update
    Topic: ride/status
    Status can be: accepted, started, completed
    """
    message = {
        "event":        "ride_status",
        "ride_id":      ride_id,
        "driver_id":    driver_id,
        "passenger_id": passenger_id,
        "status":       status,
        "timestamp":    time.strftime('%Y-%m-%d %H:%M:%S')
    }
    payload = json.dumps(message)
    result  = client.publish(TOPIC_RIDE_STATUS, payload, qos=1)
    print(f"\n📢 Ride status published!")
    print(f"   Topic: {TOPIC_RIDE_STATUS}")
    print(f"   Data:  {json.dumps(message, indent=2)}")
    return result

def publish_driver_location(client, driver_id, latitude, longitude, ride_id=None):
    """
    Driver publishes location update
    Topic: driver/location
    """
    message = {
        "event":     "location_update",
        "driver_id": driver_id,
        "latitude":  latitude,
        "longitude": longitude,
        "ride_id":   ride_id,
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
    }
    payload = json.dumps(message)
    result  = client.publish(TOPIC_DRIVER_LOCATION, payload, qos=0)
    print(f"\n📍 Location published!")
    print(f"   Topic: {TOPIC_DRIVER_LOCATION}")
    print(f"   Data:  {json.dumps(message, indent=2)}")
    return result

def start_mqtt_background(app):
    """Start MQTT client in background thread"""
    def run():
        client = create_mqtt_client()
        app.mqtt_client = client
        retry = 0
        while True:
            try:
                print(f"🔄 Connecting to MQTT Broker ({MQTT_BROKER}:{MQTT_PORT})...")
                client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
                client.loop_forever()
            except Exception as e:
                retry += 1
                wait = min(retry * 5, 30)
                print(f"❌ MQTT Error: {e}. Retrying in {wait}s...")
                time.sleep(wait)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    print("🚀 MQTT background service started!")