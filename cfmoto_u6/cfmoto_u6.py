import hashlib
import json
import os
import random
import string
import time

import requests
import paho.mqtt.client as mqtt


# ============================================================
# CFMOTO
# ============================================================

BASE_URL = (
    "https://tapi-flkf.cfmoto-oversea.com/v1.0"
)

APP_ID = "rRrIs3ID"

APP_SECRET = (
    "6c1936f85ecb23508c02ceb7a6e3fd0e33eb8bd2"
)

APP_INFO = (
    "MOBILE|Android|16|CFMOTO_INTERNATIONAL_APP|2.2.5"
)


# Persistent HA app storage
TOKEN_FILE = "/data/cfmoto_token.json"


# MQTT
MQTT_BASE = "cfmoto/u6"

DISCOVERY_PREFIX = "homeassistant"


# ============================================================
# Logging
# ============================================================

def log(message):

    print(
        f"[CFMOTO] {message}",
        flush=True
    )


# ============================================================
# Nonce
# ============================================================

def make_nonce(length=16):

    chars = (
        string.ascii_letters
        + string.digits
    )

    return "".join(
        random.SystemRandom().choices(
            chars,
            k=length
        )
    )


# ============================================================
# Query serialization
# ============================================================

def serialize_query_params(params):

    items = sorted(
        params.items(),
        key=lambda x: x[0]
    )

    return "&".join(
        f"{key}={value}"
        for key, value in items
    )


# ============================================================
# CFMOTO client
# ============================================================

class CFMoto:

    def __init__(self):

        self.session = requests.Session()

        self.token = None
        self.user_id = None

    # --------------------------------------------------------
    # Signature
    # --------------------------------------------------------

    def make_signature(
        self,
        body="",
        query_params=None
    ):

        nonce = make_nonce()

        timestamp = str(
            int(time.time() * 1000)
        )

        if query_params is not None:

            payload = serialize_query_params(
                query_params
            )

        else:

            payload = body

        params = (
            f"appId={APP_ID}"
            f"&nonce={nonce}"
            f"&timestamp={timestamp}"
        )

        raw = (
            payload
            + params
            + APP_SECRET
        )

        sha1 = hashlib.sha1(
            raw.encode("utf-8")
        ).hexdigest()

        signature = hashlib.md5(
            sha1.encode("utf-8")
        ).hexdigest()

        return {
            "appId": APP_ID,
            "nonce": nonce,
            "timestamp": timestamp,
            "signature": signature,

            "Cfmoto-X-Param": params,
            "Cfmoto-X-Sign": signature,
            "Cfmoto-X-Sign-Type": "0",
        }

    # --------------------------------------------------------
    # Headers
    # --------------------------------------------------------

    def headers(
        self,
        body="",
        query_params=None
    ):

        headers = self.make_signature(
            body=body,
            query_params=query_params
        )

        headers.update({

            "Authorization": (
                f"Bearer {self.token}"
                if self.token
                else ""
            ),

            "user_id": (
                str(self.user_id)
                if self.user_id is not None
                else ""
            ),

            "lang": "en_US",

            "ZoneId": "Europe/Vienna",

            "X-App-Info": APP_INFO,

            "User-Agent": APP_INFO,

            "Content-Type":
                "application/json; charset=UTF-8",

            "Accept":
                "application/json",
        })

        return headers

    # --------------------------------------------------------
    # Login
    # --------------------------------------------------------

    def login(
        self,
        username,
        password
    ):

        log("Logging in to CFMOTO...")

        password_md5 = hashlib.md5(
            password.encode("utf-8")
        ).hexdigest()

        payload = {

            "idcard": username,

            "idcardType": (
                "email"
                if "@" in username
                else "phone"
            ),

            "password": password_md5,

            "thirdpartyId": "",

            "thirdpartyType": "",

            "areaCode": "",

            "areaNo": "AT",

            "emailMarketingAlarm": False,

            "verifyCode": "",
        }

        body = json.dumps(
            payload,
            separators=(",", ":"),
            ensure_ascii=False
        )

        url = (
            BASE_URL
            + "/fuel-user/serveruser/app/auth/user/"
              "login_by_idcard"
        )

        response = self.session.post(
            url,
            headers=self.headers(
                body=body
            ),
            data=body,
            timeout=20
        )

        if response.status_code != 200:

            raise RuntimeError(
                f"Login HTTP "
                f"{response.status_code}: "
                f"{response.text}"
            )

        data = response.json()

        if data.get("code") != "0":

            raise RuntimeError(
                "Login failed: "
                + json.dumps(data)
            )

        login_data = data["data"]

        self.token = (
            login_data
            ["tokenInfo"]
            ["accessToken"]
        )

        self.user_id = login_data[
            "userId"
        ]

        save_token(
            self.token,
            self.user_id
        )

        log("Login successful.")
        log("CFMOTO token saved.")

    # --------------------------------------------------------
    # Vehicle
    # --------------------------------------------------------

    def get_vehicle(
        self,
        vehicle_id
    ):

        params = {
            "vehicleId": str(vehicle_id)
        }

        url = (
            BASE_URL
            + "/fuel-vehicle/servervehicle/app/"
              "vehicle"
        )

        response = self.session.get(
            url,
            params=params,
            headers=self.headers(
                query_params=params
            ),
            timeout=20
        )

        if response.status_code != 200:

            raise RuntimeError(
                f"Vehicle HTTP "
                f"{response.status_code}: "
                f"{response.text}"
            )

        data = response.json()

        if data.get("code") != "0":

            raise RuntimeError(
                "Vehicle API error: "
                + json.dumps(data)
            )

        return data["data"]


# ============================================================
# Token persistence
# ============================================================

def load_token():

    if not os.path.exists(
        TOKEN_FILE
    ):
        return None

    try:

        with open(
            TOKEN_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception:

        return None


def save_token(
    token,
    user_id
):

    os.makedirs(
        "/data",
        exist_ok=True
    )

    temp_file = (
        TOKEN_FILE
        + ".tmp"
    )

    with open(
        temp_file,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            {
                "accessToken": token,
                "userId": str(user_id)
            },
            f
        )

    os.replace(
        temp_file,
        TOKEN_FILE
    )


# ============================================================
# MQTT
# ============================================================

class MqttPublisher:

    def __init__(
        self,
        host,
        port,
        username,
        password
    ):

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="cfmoto_u6"
        )

        if username:

            self.client.username_pw_set(
                username,
                password
            )

        self.host = host
        self.port = port

    # --------------------------------------------------------
    # Connect
    # --------------------------------------------------------

    def connect(self):

        log(
            f"Connecting to MQTT "
            f"{self.host}:{self.port}..."
        )

        self.client.connect(
            self.host,
            self.port,
            60
        )

        self.client.loop_start()

        log("MQTT connected.")

    # --------------------------------------------------------
    # Publish
    # --------------------------------------------------------

    def publish(
        self,
        topic,
        payload,
        retain=True
    ):

        self.client.publish(
            topic,
            payload,
            qos=1,
            retain=retain
        )

    # --------------------------------------------------------
    # Availability
    # --------------------------------------------------------

    def availability(
        self,
        state
    ):

        self.publish(
            f"{MQTT_BASE}/availability",
            state
        )

    # --------------------------------------------------------
    # Discovery
    # --------------------------------------------------------

    def publish_discovery(self):

        device = {

            "identifiers": [
                "cfmoto_u6"
            ],

            "name": "CFMOTO U6 EV",

            "manufacturer": "CFMOTO",

            "model": "U6 EV",

            "sw_version": "CFMOTO API",

        }

        sensors = [

            {
                "component": "sensor",
                "object_id": "battery",
                "name": "Battery",
                "unique_id": "cfmoto_u6_battery",
                "value": "{{ value_json.battery }}",
                "unit": "%",
                "device_class": "battery",
                "state_class": "measurement",
            },

            {
                "component": "sensor",
                "object_id": "range",
                "name": "Range",
                "unique_id": "cfmoto_u6_range",
                "value": "{{ value_json.range }}",
                "unit": "km",
                "device_class": "distance",
                "state_class": "measurement",
            },

            {
                "component": "sensor",
                "object_id": "speed",
                "name": "Speed",
                "unique_id": "cfmoto_u6_speed",
                "value": "{{ value_json.speed }}",
                "unit": "km/h",
                "icon": "mdi:speedometer",
                "state_class": "measurement",
            },

            {
                "component": "sensor",
                "object_id": "voltage_12v",
                "name": "12V Voltage",
                "unique_id": "cfmoto_u6_12v_voltage",
                "value": "{{ value_json.voltage_12v }}",
                "unit": "V",
                "device_class": "voltage",
                "state_class": "measurement",
            },

            {
                "component": "sensor",
                "object_id": "total_mileage",
                "name": "Total Mileage",
                "unique_id": "cfmoto_u6_total_mileage",
                "value": "{{ value_json.total_mileage }}",
                "unit": "km",
                "device_class": "distance",
                "state_class": "total_increasing",
            },

            {
                "component": "binary_sensor",
                "object_id": "charging",
                "name": "Charging",
                "unique_id": "cfmoto_u6_charging",
                "value": "{{ 'ON' if value_json.charging else 'OFF' }}",
                "payload_on": "ON",
                "payload_off": "OFF",
                "device_class": "battery_charging",
            },

            {
                "component": "binary_sensor",
                "object_id": "online",
                "name": "Online",
                "unique_id": "cfmoto_u6_online",
                "value": "{{ 'ON' if value_json.online else 'OFF' }}",
                "payload_on": "ON",
                "payload_off": "OFF",
                "device_class": "connectivity",
            },
        ]

        state_topic = (
            f"{MQTT_BASE}/state"
        )

        availability_topic = (
            f"{MQTT_BASE}/availability"
        )

        for sensor in sensors:

            component = sensor.pop(
                "component"
            )

            object_id = sensor.pop(
                "object_id"
            )

            config = {

                "name": sensor["name"],

                "unique_id":
                    sensor["unique_id"],

                "state_topic":
                    state_topic,

                "value_template":
                    sensor["value"],

                "availability_topic":
                    availability_topic,

                "payload_available":
                    "online",

                "payload_not_available":
                    "offline",

                "device": device,

            }

            # Optional attributes
            for key in (
                "unit",
                "device_class",
                "state_class",
                "icon",
                "payload_on",
                "payload_off",
            ):

                if key in sensor:

                    config[key] = sensor[key]

            topic = (
                f"{DISCOVERY_PREFIX}/"
                f"{component}/"
                f"cfmoto_u6/"
                f"{object_id}/config"
            )

            self.publish(
                topic,
                json.dumps(config),
                retain=True
            )

        log(
            "MQTT Discovery published."
        )


# ============================================================
# Main
# ============================================================

def main():

    # --------------------------------------------------------
    # Read configuration
    # --------------------------------------------------------

    with open(
        "/data/options.json",
        "r",
        encoding="utf-8"
    ) as f:

        options = json.load(f)

    email = options[
        "cfmoto_email"
    ]

    password = options[
        "cfmoto_password"
    ]

    vehicle_id = options[
        "vehicle_id"
    ]

    mqtt_host = options[
        "mqtt_host"
    ]

    mqtt_port = int(
        options[
            "mqtt_port"
        ]
    )

    mqtt_username = options[
        "mqtt_username"
    ]

    mqtt_password = options[
        "mqtt_password"
    ]

    poll_interval = int(
        options[
            "poll_interval"
        ]
    )

    if not email:

        raise RuntimeError(
            "CFMOTO email is not configured."
        )

    if not password:

        raise RuntimeError(
            "CFMOTO password is not configured."
        )

    # --------------------------------------------------------
    # MQTT
    # --------------------------------------------------------

    mqtt_pub = MqttPublisher(
        mqtt_host,
        mqtt_port,
        mqtt_username,
        mqtt_password
    )

    mqtt_pub.connect()

    mqtt_pub.publish_discovery()

    mqtt_pub.availability(
        "online"
    )

    # --------------------------------------------------------
    # Main polling loop
    # --------------------------------------------------------

    while True:

        try:

            cf = CFMoto()

            saved = load_token()

            # ------------------------------------------------
            # Try saved token
            # ------------------------------------------------

            if saved:

                cf.token = saved.get(
                    "accessToken"
                )

                cf.user_id = saved.get(
                    "userId"
                )

                try:

                    vehicle = cf.get_vehicle(
                        vehicle_id
                    )

                except Exception as e:

                    log(
                        f"Saved token rejected: {e}"
                    )

                    log(
                        "Performing fresh login."
                    )

                    cf.login(
                        email,
                        password
                    )

                    vehicle = cf.get_vehicle(
                        vehicle_id
                    )

            # ------------------------------------------------
            # First run
            # ------------------------------------------------

            else:

                cf.login(
                    email,
                    password
                )

                vehicle = cf.get_vehicle(
                    vehicle_id
                )

            # ------------------------------------------------
            # Extract values
            # ------------------------------------------------

            battery = vehicle.get(
                "bmsSoc"
            )

            range_km = vehicle.get(
                "hmiRidableMile"
            )

            speed = vehicle.get(
                "speed"
            )

            charging = bool(
                vehicle.get(
                    "chargeState"
                )
            )

            device_state = vehicle.get(
                "deviceState"
            )

            online = (
                device_state == "ONLINE"
            )

            voltage_12v = vehicle.get(
                "fireVoltage"
            )

            total_mileage = vehicle.get(
                "totalRideMile"
            )

            # ------------------------------------------------
            # MQTT payload
            # ------------------------------------------------

            payload = {

                "battery": battery,

                "range": range_km,

                "speed": speed,

                "charging": charging,

                "online": online,

                "device_state":
                    device_state,

                "voltage_12v":
                    voltage_12v,

                "total_mileage":
                    total_mileage,

                "timestamp":
                    int(time.time()),
            }

            mqtt_pub.publish(
                f"{MQTT_BASE}/state",
                json.dumps(payload)
            )

            mqtt_pub.availability(
                "online"
            )

            log(
                f"Battery={battery}% "
                f"Range={range_km} km "
                f"Charging={charging} "
                f"Speed={speed} km/h"
            )

        except Exception as e:

            log(
                f"ERROR: {e}"
            )

            # Don't publish fake values.
            # Mark the CFMOTO device unavailable.

            try:

                mqtt_pub.availability(
                    "offline"
                )

            except Exception:
                pass

        time.sleep(
            poll_interval
        )


if __name__ == "__main__":

    main()