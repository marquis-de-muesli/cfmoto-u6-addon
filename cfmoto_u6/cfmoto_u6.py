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

TOKEN_FILE = "/data/cfmoto_token.json"


# ============================================================
# MQTT
# ============================================================

MQTT_BASE = "cfmoto/u6"
DISCOVERY_PREFIX = "homeassistant"


# ============================================================
# Fields that must never be published
# ============================================================

SENSITIVE_FIELDS = {
    "encryptInfo",
    "btMac",
    "qrInf",
}


# ============================================================
# HA entities
#
# Only fields in these dictionaries are exposed as HA
# entities. Everything else is still available through
# cfmoto/u6/raw (except sensitive fields).
# ============================================================

SENSOR_FIELDS = {

    "bmsSoc": {
        "name": "Battery",
        "unit": "%",
        "device_class": "battery",
        "state_class": "measurement",
    },

    "hmiRidableMile": {
        "name": "Range",
        "unit": "km",
        "device_class": "distance",
        "state_class": "measurement",
    },

    "speed": {
        "name": "Speed",
        "unit": "km/h",
        "device_class": "speed",
        "state_class": "measurement",
    },

    "totalRideMile": {
        "name": "Total Mileage",
        "unit": "km",
        "device_class": "distance",
        "state_class": "total_increasing",
    },

    "avgRideSpeed": {
        "name": "Average Speed",
        "unit": "km/h",
        "device_class": "speed",
        "state_class": "measurement",
    },

    "powerUseAvg": {
        "name": "Average Power Use",
        "unit": None,
        "device_class": None,
        "state_class": "measurement",
    },

    "chargeCycle": {
        "name": "Charge Cycles",
        "unit": None,
        "device_class": None,
        "state_class": "measurement",
    },

    "fireVoltage": {
        "name": "12V Voltage",
        "unit": "V",
        "device_class": "voltage",
        "state_class": "measurement",
    },

    "gsmRxLev": {
        "name": "GSM Signal",
        "unit": "dBm",
        "device_class": "signal_strength",
        "state_class": "measurement",
    },

    "simRemainingDays": {
        "name": "SIM Remaining Days",
        "unit": "d",
        "device_class": "duration",
        "state_class": "measurement",
    },

    "vehicleState": {
        "name": "Vehicle State",
        "unit": None,
        "device_class": None,
        "state_class": None,
    },

    "deviceState": {
        "name": "Device State",
        "unit": None,
        "device_class": None,
        "state_class": None,
    },
}


BINARY_SENSOR_FIELDS = {

    "chargeState": {
        "name": "Charging",
        "device_class": "battery_charging",
    },

    "isOnline": {
        "name": "Online",
        "device_class": "connectivity",
    },
}


# ============================================================
# Logging
# ============================================================

def log(message):

    print(
        f"[CFMOTO] {message}",
        flush=True
    )


# ============================================================
# CFMOTO helpers
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
# CFMOTO API client
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

        self.user_id = (
            login_data["userId"]
        )

        save_token(
            self.token,
            self.user_id
        )

        log("Login successful.")
        log("Token saved.")

    # --------------------------------------------------------
    # Vehicle list
    # --------------------------------------------------------

    def vehicles(self):

        params = {
            "position": "2"
        }

        url = (
            BASE_URL
            + "/fuel-vehicle/servervehicle/app/"
              "vehicle/mine"
        )

        log(
            "Requesting vehicle list..."
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
                f"Vehicle list HTTP "
                f"{response.status_code}: "
                f"{response.text}"
            )

        result = response.json()

        if result.get("code") != "0":

            raise RuntimeError(
                "Vehicle list API error: "
                + json.dumps(result)
            )

        data = result.get(
            "data",
            []
        )

        if isinstance(data, list):

            return data

        if isinstance(data, dict):

            for key in (
                "list",
                "vehicles",
                "rows",
                "records",
                "data",
            ):

                if isinstance(
                    data.get(key),
                    list
                ):

                    return data[key]

            return [data]

        return []

    # --------------------------------------------------------
    # Vehicle detail
    # --------------------------------------------------------

    def get_vehicle(
        self,
        vehicle_id
    ):

        params = {
            "vehicleId": str(
                vehicle_id
            )
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

        result = response.json()

        if result.get("code") != "0":

            raise RuntimeError(
                "Vehicle API error: "
                + json.dumps(result)
            )

        return result["data"]


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
                "userId": str(user_id),
            },
            f
        )

    os.replace(
        temp_file,
        TOKEN_FILE
    )


# ============================================================
# Vehicle discovery
# ============================================================

def get_vehicle_id(vehicle):

    if not isinstance(
        vehicle,
        dict
    ):
        return None

    for key in (
        "vehicleId",
        "id",
        "vehicleID",
        "vehicle_id",
    ):

        value = vehicle.get(key)

        if value is not None:

            return str(value)

    return None


def get_vehicle_name(vehicle):

    if not isinstance(
        vehicle,
        dict
    ):
        return "Unknown"

    for key in (
        "vehicleName",
        "name",
        "vehicleModel",
        "model",
        "vehicleType",
        "typeOfVehicle",
    ):

        value = vehicle.get(key)

        if value:

            return str(value)

    return "Unknown"


def discover_vehicle(
    cf,
    configured_vehicle_id
):

    # --------------------------------------------------------
    # Explicit ID
    # --------------------------------------------------------

    if configured_vehicle_id:

        log(
            f"Using configured vehicle ID: "
            f"{configured_vehicle_id}"
        )

        return str(
            configured_vehicle_id
        )

    # --------------------------------------------------------
    # Automatic discovery
    # --------------------------------------------------------

    vehicles = cf.vehicles()

    if not vehicles:

        raise RuntimeError(
            "No CFMOTO vehicles were found."
        )

    log(
        f"Found {len(vehicles)} "
        f"vehicle(s)."
    )

    discovered = []

    for index, vehicle in enumerate(
        vehicles,
        start=1
    ):

        vehicle_id = get_vehicle_id(
            vehicle
        )

        vehicle_name = get_vehicle_name(
            vehicle
        )

        log(
            f"  {index}: "
            f"{vehicle_name} "
            f"(ID={vehicle_id})"
        )

        if vehicle_id:

            discovered.append(
                (
                    vehicle_id,
                    vehicle_name
                )
            )

    if len(discovered) == 1:

        vehicle_id, vehicle_name = (
            discovered[0]
        )

        log(
            f"Automatically selected "
            f"{vehicle_name} "
            f"(ID={vehicle_id})"
        )

        return vehicle_id

    if len(discovered) > 1:

        lines = [
            "",
            "Multiple CFMOTO vehicles found.",
            "",
            "Please set vehicle_id in the "
            "add-on configuration.",
            "",
            "Available vehicles:",
        ]

        for vehicle_id, vehicle_name in discovered:

            lines.append(
                f"  {vehicle_name}: "
                f"{vehicle_id}"
            )

        raise RuntimeError(
            "\n".join(lines)
        )

    raise RuntimeError(
        "Vehicles were returned by CFMOTO, "
        "but no vehicle IDs could be identified."
    )


# ============================================================
# MQTT publisher
# ============================================================

class MqttPublisher:

    def __init__(
        self,
        host,
        port,
        username,
        password
    ):

        # Compatible with the older Paho version
        # available in the HA container.

        self.client = mqtt.Client(
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
    # Device
    # --------------------------------------------------------

    @staticmethod
    def device():

        return {

            "identifiers": [
                "cfmoto_u6"
            ],

            "name":
                "CFMOTO U6 EV",

            "manufacturer":
                "CFMOTO",

            "model":
                "U6 EV",

        }

    # --------------------------------------------------------
    # Sensor discovery
    # --------------------------------------------------------

    def publish_sensor(
        self,
        field,
        definition
    ):

        config = {

            "name":
                definition["name"],

            "unique_id":
                f"cfmoto_u6_{field}",

            "state_topic":
                f"{MQTT_BASE}/state",

            "value_template":
                "{{ value_json['"
                + field
                + "'] }}",

            "availability_topic":
                f"{MQTT_BASE}/availability",

            "payload_available":
                "online",

            "payload_not_available":
                "offline",

            "device":
                self.device(),
        }

        if definition.get(
            "unit"
        ):

            config[
                "unit_of_measurement"
            ] = definition["unit"]

        if definition.get(
            "device_class"
        ):

            config[
                "device_class"
            ] = definition[
                "device_class"
            ]

        if definition.get(
            "state_class"
        ):

            config[
                "state_class"
            ] = definition[
                "state_class"
            ]

        topic = (
            f"{DISCOVERY_PREFIX}/"
            f"sensor/"
            f"cfmoto_u6/"
            f"{field}/config"
        )

        self.publish(
            topic,
            json.dumps(config),
            retain=True
        )

    # --------------------------------------------------------
    # Binary sensor discovery
    # --------------------------------------------------------

    def publish_binary_sensor(
        self,
        field,
        definition
    ):

        config = {

            "name":
                definition["name"],

            "unique_id":
                f"cfmoto_u6_{field}",

            "state_topic":
                f"{MQTT_BASE}/state",

            "value_template":
                "{{ 'ON' if value_json['"
                + field
                + "'] else 'OFF' }}",

            "payload_on":
                "ON",

            "payload_off":
                "OFF",

            "availability_topic":
                f"{MQTT_BASE}/availability",

            "payload_available":
                "online",

            "payload_not_available":
                "offline",

            "device":
                self.device(),
        }

        if definition.get(
            "device_class"
        ):

            config[
                "device_class"
            ] = definition[
                "device_class"
            ]

        topic = (
            f"{DISCOVERY_PREFIX}/"
            f"binary_sensor/"
            f"cfmoto_u6/"
            f"{field}/config"
        )

        self.publish(
            topic,
            json.dumps(config),
            retain=True
        )

    # --------------------------------------------------------
    # GPS discovery
    # --------------------------------------------------------

    def publish_gps_discovery(self):

        config = {

            "name":
                "U6 Location",

            "unique_id":
                "cfmoto_u6_location",

            "state_topic":
                f"{MQTT_BASE}/gps",

            "value_template":
                "{{ value_json.state }}",

            "json_attributes_topic":
                f"{MQTT_BASE}/gps",

            "availability_topic":
                f"{MQTT_BASE}/availability",

            "payload_available":
                "online",

            "payload_not_available":
                "offline",

            "source_type":
                "gps",

            "device":
                self.device(),
        }

        topic = (
            f"{DISCOVERY_PREFIX}/"
            f"device_tracker/"
            f"cfmoto_u6/"
            f"location/config"
        )

        self.publish(
            topic,
            json.dumps(config),
            retain=True
        )

    # --------------------------------------------------------
    # Discovery
    # --------------------------------------------------------

    def publish_discovery(self):

        for field, definition in (
            SENSOR_FIELDS.items()
        ):

            self.publish_sensor(
                field,
                definition
            )

        for field, definition in (
            BINARY_SENSOR_FIELDS.items()
        ):

            self.publish_binary_sensor(
                field,
                definition
            )

        self.publish_gps_discovery()

        log(
            f"MQTT Discovery published: "
            f"{len(SENSOR_FIELDS)} sensors + "
            f"{len(BINARY_SENSOR_FIELDS)} binary sensors + GPS"
        )


# ============================================================
# Convert API values
# ============================================================

def convert_value(value):

    if isinstance(
        value,
        bool
    ):
        return value

    if value is None:
        return None

    if isinstance(
        value,
        str
    ):

        stripped = value.strip()

        try:

            if (
                "." in stripped
                or "e" in stripped.lower()
            ):

                return float(stripped)

            return int(stripped)

        except ValueError:

            return value

    return value


# ============================================================
# Remove sensitive fields recursively
# ============================================================

def remove_sensitive(
    data
):

    if isinstance(
        data,
        dict
    ):

        result = {}

        for key, value in data.items():

            if key in SENSITIVE_FIELDS:

                continue

            result[key] = remove_sensitive(
                value
            )

        return result

    if isinstance(
        data,
        list
    ):

        return [
            remove_sensitive(item)
            for item in data
        ]

    return data


# ============================================================
# Main
# ============================================================

def main():

    # --------------------------------------------------------
    # Load configuration
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

    configured_vehicle_id = (
        options.get(
            "vehicle_id",
            ""
        ).strip()
    )

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

    # --------------------------------------------------------
    # Login
    # --------------------------------------------------------

    saved = load_token()

    cf = CFMoto()

    if saved:

        cf.token = saved.get(
            "accessToken"
        )

        cf.user_id = saved.get(
            "userId"
        )

        log(
            "Using saved CFMOTO token."
        )

    else:

        cf.login(
            email,
            password
        )

    # --------------------------------------------------------
    # Vehicle discovery
    # --------------------------------------------------------

    try:

        vehicle_id = discover_vehicle(
            cf,
            configured_vehicle_id
        )

    except Exception as e:

        log(
            f"Vehicle discovery failed: {e}"
        )

        # Try fresh login once.

        log(
            "Performing fresh login..."
        )

        cf = CFMoto()

        cf.login(
            email,
            password
        )

        vehicle_id = discover_vehicle(
            cf,
            configured_vehicle_id
        )

    log(
        f"Monitoring vehicle: "
        f"{vehicle_id}"
    )

    # --------------------------------------------------------
    # Publish Discovery
    # --------------------------------------------------------

    mqtt_pub.publish_discovery()

    mqtt_pub.availability(
        "online"
    )

    # --------------------------------------------------------
    # Main polling loop
    # --------------------------------------------------------

    while True:

        try:

            # ------------------------------------------------
            # Get vehicle
            # ------------------------------------------------

            try:

                vehicle = cf.get_vehicle(
                    vehicle_id
                )

            except Exception as e:

                log(
                    f"Vehicle request failed: "
                    f"{e}"
                )

                log(
                    "Re-authenticating..."
                )

                cf = CFMoto()

                cf.login(
                    email,
                    password
                )

                vehicle = cf.get_vehicle(
                    vehicle_id
                )

            # ------------------------------------------------
            # State payload
            #
            # Only the selected HA fields are published here.
            # ------------------------------------------------

            state = {}

            for field in SENSOR_FIELDS:

                if field in vehicle:

                    state[field] = convert_value(
                        vehicle[field]
                    )

            # CFMOTO reports totalRideMile in meters
            if "totalRideMile" in state:
                state["totalRideMile"] = (
                    state["totalRideMile"] / 1000
                )


            for field in BINARY_SENSOR_FIELDS:

                if field in vehicle:

                    state[field] = bool(
                        vehicle[field]
                    )

            mqtt_pub.publish(
                f"{MQTT_BASE}/state",
                json.dumps(
                    state,
                    ensure_ascii=False
                )
            )

            # ------------------------------------------------
            # Raw API response
            #
            # Everything except sensitive fields.
            # ------------------------------------------------

            raw = remove_sensitive(
                vehicle
            )

            mqtt_pub.publish(
                f"{MQTT_BASE}/raw",
                json.dumps(
                    raw,
                    ensure_ascii=False
                )
            )

            # ------------------------------------------------
            # GPS
            # ------------------------------------------------

            geo = vehicle.get(
                "geoLocation"
            )

            if isinstance(
                geo,
                dict
            ):

                latitude = geo.get(
                    "latitude"
                )

                longitude = geo.get(
                    "longitude"
                )

                altitude = geo.get(
                    "altitude"
                )

                if (
                    latitude is not None
                    and longitude is not None
                ):

                    gps = {

                        "state":
                            "U6",

                        "latitude":
                            float(latitude),

                        "longitude":
                            float(longitude),
                    }

                    if altitude is not None:

                        gps[
                            "altitude"
                        ] = float(
                            altitude
                        )

                    report = geo.get(
                        "report"
                    )

                    if isinstance(
                        report,
                        dict
                    ):

                        report_datetime = (
                            report.get(
                                "datetime"
                            )
                        )

                        if report_datetime:

                            gps[
                                "report_datetime"
                            ] = report_datetime

                    mqtt_pub.publish(
                        f"{MQTT_BASE}/gps",
                        json.dumps(gps)
                    )

            # ------------------------------------------------
            # Availability
            # ------------------------------------------------

            mqtt_pub.availability(
                "online"
            )

            # ------------------------------------------------
            # Logging
            # ------------------------------------------------

            log(
                f"Battery="
                f"{vehicle.get('bmsSoc')}% | "
                f"Range="
                f"{vehicle.get('hmiRidableMile')} km | "
                f"Charging="
                f"{bool(vehicle.get('chargeState'))} | "
                f"Speed="
                f"{vehicle.get('speed')} km/h | "
                f"SIM="
                f"{vehicle.get('simRemainingDays')} days"
            )

        except Exception as e:

            log(
                f"ERROR: {e}"
            )

            try:

                mqtt_pub.availability(
                    "offline"
                )

            except Exception:
                pass

        time.sleep(
            poll_interval
        )


# ============================================================
# Entry point
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        log(
            "Stopped."
        )

    except Exception as e:

        log(
            f"Fatal error: {e}"
        )