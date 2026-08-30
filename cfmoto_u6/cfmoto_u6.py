import hashlib
import json
import os
import random
import string
import time

import requests
import paho.mqtt.client as mqtt


# ============================================================
# CFMOTO configuration
# ============================================================

BASE_URL = "https://tapi-flkf.cfmoto-oversea.com/v1.0"

APP_ID = "rRrIs3ID"

APP_SECRET = (
    "6c1936f85ecb23508c02ceb7a6e3fd0e33eb8bd2"
)

APP_INFO = (
    "MOBILE|Android|16|CFMOTO_INTERNATIONAL_APP|2.2.5"
)

TOKEN_FILE = "/data/cfmoto_token.json"

MQTT_BASE = "cfmoto/u6"
DISCOVERY_PREFIX = "homeassistant"


# ============================================================
# Fields never published
# ============================================================

SENSITIVE_FIELDS = {
    "encryptInfo",
    "btMac",
    "qrInf",
}


# ============================================================
# Human-readable names
# ============================================================

FIELD_NAMES = {
    "bmsSoc": "Battery",
    "hmiRidableMile": "Range",
    "speed": "Speed",
    "fireVoltage": "12V Voltage",
    "gsmRxLev": "GSM Signal",
    "gsmRxLevStr": "GSM Signal Strength",

    "remainingOil": "Remaining Oil",
    "remainingOilStr": "Remaining Oil",
    "remainingOilDisplay": "Remaining Oil Display",

    "vehicleState": "Vehicle State",

    "totalRideMile": "Total Mileage",
    "rideMileageMonth": "Monthly Mileage",
    "ridingTimeMonth": "Monthly Riding Time",
    "avgRideSpeed": "Average Speed",
    "powerUseAvg": "Average Power Use",

    "totalOilNum": "Total Oil Number",

    "oilLockState": "Oil Lock",
    "batteryLockState": "Battery Lock",
    "seatLockState": "Seat Lock",
    "headLockState": "Head Lock",

    "kl": "KL",

    "chargeState": "Charging",
    "chargeCycle": "Charge Cycles",

    "greenContribution": "Green Contribution",

    "isOnline": "Online",
    "deviceState": "Device State",

    "simRemainingDays": "SIM Remaining Days",
    "simExpire": "SIM Expiry",
    "simServiceEnable": "SIM Service",

    "supportRemoteUnlock": "Remote Unlock Supported",

    "rideAnalysisFlag": "Ride Analysis",
    "oilUseAvgFlag": "Oil Use Average",

    "typeOfProduct": "Product Type",
    "energyType": "Energy Type",

    "tboxIsBlank": "T-Box Blank",
    "tboxIsSupportedDisplay": "T-Box Display Supported",
    "tboxIsActive": "T-Box Active",

    "shareStatus": "Share Status",

    "hmiRideMileFunctionSwitch":
        "Range Function Enabled",

    "typeOfVehicle": "Vehicle Type",

    "pinSetState": "PIN Set",

    "isSupport4GupDownPower":
        "4G Power Control Supported",

    "upDownPowerStatus":
        "4G Power Status",

    "motoPlay": "MotoPlay",
    "motoPlayType": "MotoPlay Type",

    "isPop": "Popup",

    "simRemainingDaysV2":
        "SIM Remaining Days V2",

    "vehicleData": "Vehicle Data",

    "ifFirstBind": "First Bind",

    "vehicleDataServiceFlag":
        "Vehicle Data Service",

    "motoplayServiceFlag":
        "MotoPlay Service",

    "startChargingTime":
        "Service Start Charging Time",

    "freeTime": "Free Time",

    "exchangeMileage":
        "Exchange Mileage",

    "ifExchangeMileage":
        "Exchange Mileage Enabled",

    "expiredTimeMotoplay":
        "MotoPlay Expiry",

    "expiredTimeBasedata":
        "Base Data Expiry",

    "ifIntelligentServiceEnable":
        "Intelligent Service Enabled",

    "simExpiredTimeMotoplay":
        "MotoPlay SIM Expiry",

    "simExpiredTimeBasedata":
        "Base Data SIM Expiry",

    "simOperationType":
        "SIM Operation Type",

    "motoplayConnectionFlag":
        "MotoPlay Connection",

    "vehicleSettingDisplayFlag":
        "Vehicle Settings Display",

    "vehicleBrand":
        "Vehicle Brand",
}


# ============================================================
# Units
# ============================================================

FIELD_UNITS = {
    "bmsSoc": "%",
    "hmiRidableMile": "km",
    "speed": "km/h",
    "fireVoltage": "V",
    "gsmRxLev": "dBm",
    "remainingOil": "%",
    "totalRideMile": "km",
    "rideMileageMonth": "km",
    "ridingTimeMonth": "s",
    "avgRideSpeed": "km/h",
    "simRemainingDays": "d",
    "simRemainingDaysV2": "d",
    "exchangeMileage": "km",
}


# ============================================================
# Device classes
# ============================================================

FIELD_DEVICE_CLASSES = {
    "bmsSoc": "battery",
    "hmiRidableMile": "distance",
    "speed": "speed",
    "fireVoltage": "voltage",
    "totalRideMile": "distance",
    "rideMileageMonth": "distance",
    "avgRideSpeed": "speed",
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

    chars = string.ascii_letters + string.digits

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
    # Vehicle list / discovery
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

        if isinstance(data, dict):

            # Some API versions wrap the list.
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

        if isinstance(data, list):
            return data

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
                "userId": str(user_id)
            },
            f
        )

    os.replace(
        temp_file,
        TOKEN_FILE
    )


# ============================================================
# Vehicle ID extraction
# ============================================================

def get_vehicle_id(vehicle):

    if not isinstance(
        vehicle,
        dict
    ):
        return None

    # Try likely ID field names.

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
    # Explicit vehicle ID
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
# Flatten nested data
# ============================================================

def flatten_dict(
    data,
    prefix=""
):

    result = {}

    if not isinstance(
        data,
        dict
    ):
        return result

    for key, value in data.items():

        if key in SENSITIVE_FIELDS:
            continue

        full_key = (
            f"{prefix}_{key}"
            if prefix
            else key
        )

        if isinstance(
            value,
            dict
        ):

            result.update(
                flatten_dict(
                    value,
                    full_key
                )
            )

        elif isinstance(
            value,
            list
        ):

            result[
                full_key
            ] = json.dumps(
                value,
                ensure_ascii=False
            )

        else:

            result[
                full_key
            ] = value

    return result


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

    def set_availability(
        self,
        state
    ):

        self.publish(
            f"{MQTT_BASE}/availability",
            state
        )

    @staticmethod
    def device_info():

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

            "sw_version":
                "CFMOTO Cloud API",
        }

    # --------------------------------------------------------
    # Sensor discovery
    # --------------------------------------------------------

    def publish_sensor_discovery(
        self,
        field
    ):

        name = FIELD_NAMES.get(
            field,
            field.replace(
                "_",
                " "
            ).title()
        )

        unique_id = (
            "cfmoto_u6_"
            + field.lower()
        )

        config = {

            "name":
                name,

            "unique_id":
                unique_id,

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
                self.device_info(),
        }

        unit = FIELD_UNITS.get(
            field
        )

        if unit:
            config[
                "unit_of_measurement"
            ] = unit

        device_class = FIELD_DEVICE_CLASSES.get(
            field
        )

        if device_class:
            config[
                "device_class"
            ] = device_class

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

    def publish_binary_discovery(
        self,
        field
    ):

        name = FIELD_NAMES.get(
            field,
            field.replace(
                "_",
                " "
            ).title()
        )

        unique_id = (
            "cfmoto_u6_"
            + field.lower()
        )

        config = {

            "name":
                name,

            "unique_id":
                unique_id,

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
                self.device_info(),
        }

        if field == "chargeState":

            config[
                "device_class"
            ] = "battery_charging"

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
                self.device_info(),
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

    def publish_discovery(
        self,
        flattened_data
    ):

        for field, value in (
            flattened_data.items()
        ):

            if isinstance(
                value,
                bool
            ):

                self.publish_binary_discovery(
                    field
                )

            elif isinstance(
                value,
                (dict, list)
            ):

                continue

            else:

                self.publish_sensor_discovery(
                    field
                )

        self.publish_gps_discovery()

        log(
            "MQTT Discovery published."
        )


# ============================================================
# Authentication
# ============================================================

def authenticate(
    email,
    password
):

    cf = CFMoto()

    saved = load_token()

    if saved:

        cf.token = saved.get(
            "accessToken"
        )

        cf.user_id = saved.get(
            "userId"
        )

        log(
            "Trying saved CFMOTO token..."
        )

        return cf

    cf.login(
        email,
        password
    )

    return cf


# ============================================================
# Main
# ============================================================

def main():

    # --------------------------------------------------------
    # Configuration
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
    # Authentication
    # --------------------------------------------------------

    cf = authenticate(
        email,
        password
    )

    # --------------------------------------------------------
    # Determine vehicle
    # --------------------------------------------------------

    try:

        vehicle_id = discover_vehicle(
            cf,
            configured_vehicle_id
        )

    except Exception as e:

        # A saved token may have expired.
        # Retry discovery with a fresh login.

        log(
            f"Vehicle discovery failed: {e}"
        )

        log(
            "Trying fresh login..."
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
        f"Monitoring vehicle ID: "
        f"{vehicle_id}"
    )

    # --------------------------------------------------------
    # Initial vehicle request
    # --------------------------------------------------------

    try:

        vehicle = cf.get_vehicle(
            vehicle_id
        )

    except Exception as e:

        log(
            f"Initial vehicle request failed: "
            f"{e}"
        )

        log(
            "Trying fresh login..."
        )

        cf = CFMoto()

        cf.login(
            email,
            password
        )

        vehicle = cf.get_vehicle(
            vehicle_id
        )

    # --------------------------------------------------------
    # Discovery
    # --------------------------------------------------------

    flattened = flatten_dict(
        vehicle
    )

    flattened = {
        key: convert_value(value)
        for key, value
        in flattened.items()
    }

    mqtt_pub.publish_discovery(
        flattened
    )

    mqtt_pub.set_availability(
        "online"
    )

    # --------------------------------------------------------
    # Polling loop
    # --------------------------------------------------------

    while True:

        try:

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
            # Flatten data
            # ------------------------------------------------

            flattened = flatten_dict(
                vehicle
            )

            flattened = {
                key: convert_value(value)
                for key, value
                in flattened.items()
            }

            # ------------------------------------------------
            # Normal MQTT state
            # ------------------------------------------------

            mqtt_pub.publish(
                f"{MQTT_BASE}/state",
                json.dumps(
                    flattened,
                    ensure_ascii=False
                )
            )

            # ------------------------------------------------
            # Raw non-sensitive API response
            # ------------------------------------------------

            raw_data = dict(
                vehicle
            )

            for sensitive in SENSITIVE_FIELDS:

                raw_data.pop(
                    sensitive,
                    None
                )

            mqtt_pub.publish(
                f"{MQTT_BASE}/raw",
                json.dumps(
                    raw_data,
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

                    gps_payload = {

                        "state":
                            "home",

                        "latitude":
                            float(latitude),

                        "longitude":
                            float(longitude),
                    }

                    if altitude is not None:

                        gps_payload[
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

                        datetime_value = (
                            report.get(
                                "datetime"
                            )
                        )

                        if datetime_value:

                            gps_payload[
                                "report_datetime"
                            ] = datetime_value

                    mqtt_pub.publish(
                        f"{MQTT_BASE}/gps",
                        json.dumps(
                            gps_payload
                        )
                    )

            # ------------------------------------------------
            # Availability
            # ------------------------------------------------

            mqtt_pub.set_availability(
                "online"
            )

            # ------------------------------------------------
            # Logging
            # ------------------------------------------------

            log(
                f"Battery="
                f"{vehicle.get('bmsSoc')}% "
                f"Range="
                f"{vehicle.get('hmiRidableMile')} km "
                f"Charging="
                f"{bool(vehicle.get('chargeState'))} "
                f"Speed="
                f"{vehicle.get('speed')} km/h"
            )

        except Exception as e:

            log(
                f"ERROR: {e}"
            )

            try:

                mqtt_pub.set_availability(
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