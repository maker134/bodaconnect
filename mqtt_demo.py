"""
BodaConnect MQTT Demo Script
============================
This script simulates:
1. Passenger requesting a ride (Publisher)
2. Driver receiving and accepting the ride (Subscriber + Publisher)
3. Driver sending location updates
4. Ride status updates

Run this script to demonstrate real-time communication:
    python mqtt_demo.py
"""

import paho.mqtt.client as mqtt
import json
import time
import threading

BROKER = 'localhost'
PORT   = 1883

# ── Colors for terminal output ──────────────────────────────
GREEN  = '\033[92m'
BLUE   = '\033[94m'
YELLOW = '\033[93m'
RED    = '\033[91m'
RESET  = '\033[0m'
BOLD   = '\033[1m'

print(f"""
{BOLD}{'='*60}
   BodaConnect MQTT Real-Time Communication Demo
{'='*60}{RESET}
""")

# ── Message received flag ───────────────────────────────────
ride_request_received = threading.Event()
status_received       = threading.Event()

# ── DRIVER CLIENT (Subscriber) ──────────────────────────────
def driver_on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"{GREEN}✅ DRIVER connected to MQTT Broker{RESET}")
        client.subscribe('ride/request')
        client.subscribe('ride/status')
        print(f"{GREEN}📡 DRIVER subscribed to: ride/request, ride/status{RESET}\n")

def driver_on_message(client, userdata, msg):
    data = json.loads(msg.payload.decode())
    print(f"\n{BLUE}{BOLD}{'─'*50}")
    print(f"🏍️  DRIVER received message on: {msg.topic}")
    print(f"{'─'*50}{RESET}")
    print(f"{BLUE}   Passenger: {data.get('pickup', '')} → {data.get('destination', '')}")
    print(f"   Phone: {data.get('phone', '')}")
    print(f"   Time: {data.get('timestamp', '')}{RESET}")

    if msg.topic == 'ride/request':
        ride_request_received.set()
        print(f"\n{YELLOW}⏳ Driver is considering the request...{RESET}")
        time.sleep(2)

        # Driver accepts the ride
        accept_msg = {
            "event":        "ride_status",
            "ride_id":      data.get('ride_id', 1),
            "driver_id":    101,
            "passenger_id": data.get('user_id', 1),
            "status":       "accepted",
            "message":      "Driver is on the way!",
            "timestamp":    time.strftime('%Y-%m-%d %H:%M:%S')
        }
        client.publish('ride/status', json.dumps(accept_msg), qos=1)
        print(f"\n{GREEN}✅ DRIVER accepted the ride and published status!{RESET}")

# ── PASSENGER CLIENT (Publisher + Subscriber) ───────────────
def passenger_on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"{GREEN}✅ PASSENGER connected to MQTT Broker{RESET}")
        client.subscribe('ride/status')
        client.subscribe('driver/location')
        print(f"{GREEN}📡 PASSENGER subscribed to: ride/status, driver/location{RESET}\n")

def passenger_on_message(client, userdata, msg):
    data = json.loads(msg.payload.decode())
    print(f"\n{YELLOW}{BOLD}{'─'*50}")
    print(f"👤 PASSENGER received message on: {msg.topic}")
    print(f"{'─'*50}{RESET}")

    if msg.topic == 'ride/status':
        status = data.get('status', '')
        status_icons = {
            'accepted':  '✅ Ride ACCEPTED',
            'started':   '🚀 Ride STARTED',
            'completed': '🎉 Ride COMPLETED'
        }
        print(f"{YELLOW}   Status: {status_icons.get(status, status)}")
        print(f"   Message: {data.get('message', '')}")
        print(f"   Time: {data.get('timestamp', '')}{RESET}")
        status_received.set()

    elif msg.topic == 'driver/location':
        print(f"{YELLOW}   Driver Location:")
        print(f"   Latitude:  {data.get('latitude')}")
        print(f"   Longitude: {data.get('longitude')}{RESET}")

# ── START DRIVER ────────────────────────────────────────────
driver = mqtt.Client(client_id="boda-driver-001")
driver.on_connect = driver_on_connect
driver.on_message = driver_on_message

# ── START PASSENGER ─────────────────────────────────────────
passenger = mqtt.Client(client_id="boda-passenger-001")
passenger.on_connect = passenger_on_connect
passenger.on_message = passenger_on_message

try:
    print(f"{BOLD}🔌 Connecting to MQTT Broker at {BROKER}:{PORT}...{RESET}\n")

    driver.connect(BROKER, PORT, 60)
    passenger.connect(BROKER, PORT, 60)

    driver.loop_start()
    passenger.loop_start()

    time.sleep(1)

    # ── STEP 1: Passenger requests a ride ──────────────────
    print(f"\n{BOLD}{'='*50}")
    print(f"STEP 1: Passenger requests a ride")
    print(f"{'='*50}{RESET}")

    ride_request = {
        "event":       "ride_request",
        "ride_id":     1,
        "user_id":     42,
        "pickup":      "UDOM - Block 1",
        "destination": "Dodoma City Center",
        "phone":       "+255712345678",
        "timestamp":   time.strftime('%Y-%m-%d %H:%M:%S'),
        "status":      "pending"
    }

    passenger.publish('ride/request', json.dumps(ride_request), qos=1)
    print(f"{GREEN}🚀 PASSENGER published ride request!{RESET}")
    print(f"   From: {ride_request['pickup']}")
    print(f"   To:   {ride_request['destination']}")

    # ── STEP 2: Wait for driver to accept ──────────────────
    print(f"\n{BOLD}{'='*50}")
    print(f"STEP 2: Waiting for driver to accept...")
    print(f"{'='*50}{RESET}")
    status_received.wait(timeout=10)

    # ── STEP 3: Driver sends location updates ──────────────
    print(f"\n{BOLD}{'='*50}")
    print(f"STEP 3: Driver sending location updates")
    print(f"{'='*50}{RESET}")

    locations = [
        (-6.1720, 35.7380, "Driver heading to pickup"),
        (-6.1725, 35.7385, "Driver nearby"),
        (-6.1730, 35.7395, "Driver arrived at pickup"),
    ]

    for lat, lng, note in locations:
        location_msg = {
            "event":     "location_update",
            "driver_id": 101,
            "latitude":  lat,
            "longitude": lng,
            "note":      note,
            "ride_id":   1,
            "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
        }
        driver.publish('driver/location', json.dumps(location_msg), qos=0)
        print(f"{GREEN}📍 {note}: ({lat}, {lng}){RESET}")
        time.sleep(1)

    # ── STEP 4: Driver updates ride status ─────────────────
    print(f"\n{BOLD}{'='*50}")
    print(f"STEP 4: Ride status updates")
    print(f"{'='*50}{RESET}")

    for status, msg_text in [('started', 'Ride has started!'), ('completed', 'You have arrived!')]:
        time.sleep(2)
        status_msg = {
            "event":        "ride_status",
            "ride_id":      1,
            "driver_id":    101,
            "passenger_id": 42,
            "status":       status,
            "message":      msg_text,
            "timestamp":    time.strftime('%Y-%m-%d %H:%M:%S')
        }
        driver.publish('ride/status', json.dumps(status_msg), qos=1)
        print(f"{GREEN}📢 Driver published status: {status}{RESET}")

    time.sleep(3)

    print(f"\n{BOLD}{GREEN}{'='*50}")
    print(f"✅ MQTT Demo Complete!")
    print(f"{'='*50}{RESET}")
    print(f"""
Summary of messages exchanged:
  📤 Passenger → ride/request    (1 message)
  📤 Driver    → ride/status     (3 messages: accepted, started, completed)
  📤 Driver    → driver/location (3 messages)
  Total: 7 real-time messages exchanged!
    """)

except Exception as e:
    print(f"{RED}❌ Error: {e}")
    print(f"Make sure MQTT broker is running: docker compose up mqtt-broker{RESET}")

finally:
    driver.loop_stop()
    passenger.loop_stop()
    driver.disconnect()
    passenger.disconnect()