import os
import requests
import sqlite3
from pathlib import Path


# ============================================================
# ESP32 EDGEHUB CONFIGURATION
# ============================================================

ESP32_IP = os.environ.get("ESP32_IP", "192.168.1.50")

ESP32_BASE_URL = f"http://{ESP32_IP}"

ESP32_STATUS_URL = f"{ESP32_BASE_URL}/status"


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

TELEMETRY_DB = BASE_DIR / "telemetry.db"


# ============================================================
# NETWORK CONFIGURATION
# ============================================================

ESP32_TIMEOUT = 5


# ============================================================
# PHASE 7 — EXISTING GPIO SAFETY
# ============================================================

# Existing Phase 7 AI GPIO tool remains restricted
# to GPIO 2 for backward compatibility.

ALLOWED_GPIO_PINS = {
    2
}

ALLOWED_GPIO_STATES = {
    "on",
    "off"
}


# ============================================================
# PHASE 8.3 — SAFE DIGITAL GPIO REGISTRY
# ============================================================

# These GPIOs are approved for Phase 8.3
# digital read/write operations.

SAFE_DIGITAL_GPIOS = {
    2,
    4,
    16,
    17,
    18,
    19,
    21,
    22,
    23,
    25,
    26,
    27,
    32,
    33
}


# ============================================================
# PHASE 8.5 — SAFE ADC1 REGISTRY
# ============================================================

SAFE_ADC_PINS = {
    32,
    33,
    34,
    35,
    36,
    39
}


# ============================================================
# PHASE 8.6 — SAFE PWM REGISTRY
# ============================================================

# Only these GPIOs are approved for AI PWM control.
# GPIO 32/33 are reserved for ADC-capable operation.
# GPIO 34-39 are input-only.
# GPIO 2 remains the legacy GPIO 2 control pin.

SAFE_PWM_PINS = {
    4,
    16,
    17,
    18,
    19,
    21,
    22,
    23,
    25,
    26,
    27
}

PWM_MIN_DUTY = 0
PWM_MAX_DUTY = 255


# ============================================================
# HELPER — ERROR RESPONSE
# ============================================================

def tool_error(error_code, message, status=None):
    """
    Create a consistent error response for AI tools.
    """

    result = {
        "success": False,
        "error_code": error_code,
        "message": message
    }

    if status is not None:
        result["status"] = status

    return result


# ============================================================
# HELPER — VALIDATE GPIO NUMBER
# ============================================================

def validate_gpio_number(pin):
    """
    Validate and normalize a GPIO number.

    Returns:
        (True, gpio_number)
        or
        (False, error_response)
    """

    try:

        # Reject booleans because bool is technically an int
        # in Python.

        if isinstance(pin, bool):
            raise ValueError

        pin = int(pin)

    except (ValueError, TypeError):

        return (
            False,
            tool_error(
                "invalid_gpio",
                "Invalid GPIO number. GPIO must be a valid integer."
            )
        )

    return True, pin


# ============================================================
# GET DEVICE STATUS
# ============================================================

def get_device_status():
    """
    Read the current ESP32 EdgeHub status.

    This tool only reads the fixed ESP32 /status endpoint.
    It cannot access arbitrary URLs.
    """

    try:

        response = requests.get(
            ESP32_STATUS_URL,
            timeout=ESP32_TIMEOUT
        )

        response.raise_for_status()

    except requests.exceptions.Timeout:

        return tool_error(
            "esp32_timeout",
            "ESP32 did not respond within the timeout period.",
            "offline"
        )

    except requests.exceptions.ConnectionError:

        return tool_error(
            "esp32_offline",
            "ESP32 could not be reached. Check that the ESP32 is powered on and connected to Wi-Fi.",
            "offline"
        )

    except requests.exceptions.HTTPError as e:

        return tool_error(
            "esp32_http_error",
            f"ESP32 returned an HTTP error: {e}",
            "offline"
        )

    except requests.exceptions.RequestException as e:

        return tool_error(
            "esp32_request_error",
            f"Could not communicate with the ESP32: {e}",
            "offline"
        )


    # --------------------------------------------------------
    # Validate JSON response
    # --------------------------------------------------------

    try:

        data = response.json()

    except ValueError:

        return tool_error(
            "invalid_esp32_response",
            "ESP32 returned an invalid JSON response."
        )


    if not isinstance(data, dict):

        return tool_error(
            "invalid_esp32_response",
            "ESP32 returned an unexpected response format."
        )


    # --------------------------------------------------------
    # Return safe device information
    # --------------------------------------------------------

    return {
        "success": True,
        "device": data.get(
            "device",
            "ESP32 EdgeHub"
        ),
        "status": data.get("status"),
        "ip": data.get("ip"),
        "ssid": data.get("ssid"),
        "rssi": data.get("rssi"),
        "gpio2": data.get("gpio2"),
        "free_heap": data.get("free_heap"),
        "uptime": data.get("uptime"),
        "firmware": data.get("firmware")
    }


# ============================================================
# PHASE 8.7 — UNIFIED HARDWARE STATE
# ============================================================

def get_hardware_state():
    """
    Read the unified current hardware state from the ESP32.

    This is a read-only Phase 8.7 tool. It uses only the fixed
    ESP32 /hardware/state endpoint and cannot access arbitrary URLs.
    """

    try:

        response = requests.get(
            f"{ESP32_BASE_URL}/hardware/state",
            timeout=ESP32_TIMEOUT
        )

        response.raise_for_status()

    except requests.exceptions.Timeout:

        return tool_error(
            "esp32_timeout",
            "ESP32 did not respond while reading hardware state.",
            "offline"
        )

    except requests.exceptions.ConnectionError:

        return tool_error(
            "esp32_offline",
            "ESP32 could not be reached while reading hardware state.",
            "offline"
        )

    except requests.exceptions.HTTPError as e:

        return tool_error(
            "esp32_http_error",
            f"ESP32 returned an HTTP error for hardware state: {e}",
            "offline"
        )

    except requests.exceptions.RequestException as e:

        return tool_error(
            "esp32_request_error",
            f"Could not read ESP32 hardware state: {e}",
            "offline"
        )

    try:

        data = response.json()

    except ValueError:

        return tool_error(
            "invalid_esp32_response",
            "ESP32 returned invalid JSON for hardware state."
        )

    if not isinstance(data, dict):

        return tool_error(
            "invalid_esp32_response",
            "ESP32 returned an unexpected hardware-state format."
        )

    if data.get("success") is not True:

        return tool_error(
            "hardware_state_failed",
            data.get(
                "error",
                "ESP32 failed to provide hardware state."
            )
        )

    return {
        "success": True,
        "device": data.get("device", "ESP32 EdgeHub"),
        "firmware": data.get("firmware"),
        "phase": data.get("phase", "8.7"),
        "uptime": data.get("uptime"),
        "digital_gpio": data.get("digital_gpio", []),
        "pwm": data.get("pwm", []),
        "adc": data.get("adc", []),
        "message": (
            "Unified ESP32 hardware state read successfully."
        ),
        "esp32_response": data
    }


# ============================================================
# PHASE 7 — EXISTING SET GPIO
# ============================================================

def set_gpio(pin, state):
    """
    Control GPIO 2.

    SAFETY:
    Only GPIO 2 is allowed by this legacy Phase 7 tool.

    Phase 8.3 uses digital_write() for the expanded
    safe digital GPIO registry.
    """

    # --------------------------------------------------------
    # Validate GPIO
    # --------------------------------------------------------

    valid, result = validate_gpio_number(pin)

    if not valid:
        return result

    pin = result


    # --------------------------------------------------------
    # HARD SAFETY LIMIT
    # --------------------------------------------------------

    if pin not in ALLOWED_GPIO_PINS:

        return tool_error(
            "unsupported_gpio",
            "Only GPIO 2 is supported by the existing set_gpio tool. "
            f"GPIO {pin} cannot be controlled."
        )


    # --------------------------------------------------------
    # Validate GPIO state
    # --------------------------------------------------------

    if state is None:

        return tool_error(
            "invalid_gpio_state",
            "GPIO state is required. Use 'on' or 'off'."
        )


    state = str(state).lower().strip()


    if state not in ALLOWED_GPIO_STATES:

        return tool_error(
            "invalid_gpio_state",
            "GPIO state must be 'on' or 'off'."
        )


    # --------------------------------------------------------
    # Build approved GPIO 2 endpoint
    # --------------------------------------------------------

    gpio_url = (
        f"{ESP32_BASE_URL}/gpio/2/{state}"
    )


    # --------------------------------------------------------
    # Send command to ESP32
    # --------------------------------------------------------

    try:

        response = requests.get(
            gpio_url,
            timeout=ESP32_TIMEOUT
        )

        response.raise_for_status()

    except requests.exceptions.Timeout:

        return tool_error(
            "esp32_timeout",
            "ESP32 did not respond while controlling GPIO 2.",
            "offline"
        )

    except requests.exceptions.ConnectionError:

        return tool_error(
            "esp32_offline",
            "ESP32 could not be reached while controlling GPIO 2.",
            "offline"
        )

    except requests.exceptions.HTTPError as e:

        return tool_error(
            "esp32_http_error",
            f"ESP32 rejected the GPIO command: {e}"
        )

    except requests.exceptions.RequestException as e:

        return tool_error(
            "esp32_request_error",
            f"Could not send the GPIO command to ESP32: {e}",
            "offline"
        )


    # --------------------------------------------------------
    # Validate ESP32 response
    # --------------------------------------------------------

    try:

        esp32_response = response.json()

    except ValueError:

        return tool_error(
            "invalid_esp32_response",
            "ESP32 returned an invalid response after the GPIO command."
        )


    if not isinstance(esp32_response, dict):

        return tool_error(
            "invalid_esp32_response",
            "ESP32 returned an unexpected GPIO response."
        )


    # --------------------------------------------------------
    # Verify ESP32 response
    # --------------------------------------------------------

    response_gpio = esp32_response.get("gpio")

    response_state = str(
        esp32_response.get(
            "state",
            ""
        )
    ).upper()


    if response_gpio != 2:

        return tool_error(
            "gpio_verification_failed",
            "ESP32 did not confirm control of GPIO 2."
        )


    expected_state = state.upper()


    if response_state != expected_state:

        return tool_error(
            "gpio_verification_failed",
            f"ESP32 did not confirm GPIO 2 {expected_state}."
        )


    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    return {
        "success": True,
        "gpio": 2,
        "state": expected_state,
        "message": (
            f"GPIO 2 has been successfully turned "
            f"{expected_state}."
        ),
        "esp32_response": esp32_response
    }


# ============================================================
# PHASE 8.3 — DIGITAL GPIO WRITE
# ============================================================

def digital_write(pin, state):
    """
    Safely turn an approved digital GPIO ON or OFF.

    Approved GPIOs are defined in SAFE_DIGITAL_GPIOS.
    """

    # --------------------------------------------------------
    # Validate GPIO
    # --------------------------------------------------------

    valid, result = validate_gpio_number(pin)

    if not valid:
        return result

    pin = result


    # --------------------------------------------------------
    # PHASE 8.3 SAFETY CHECK
    # --------------------------------------------------------

    if pin not in SAFE_DIGITAL_GPIOS:

        return tool_error(
            "unsupported_gpio",
            (
                f"GPIO {pin} is not allowed. "
                "It is outside the safe digital GPIO registry."
            )
        )


    # --------------------------------------------------------
    # Validate state
    # --------------------------------------------------------

    if state is None:

        return tool_error(
            "invalid_gpio_state",
            "GPIO state is required. Use 'on' or 'off'."
        )


    state = str(state).lower().strip()


    if state not in ALLOWED_GPIO_STATES:

        return tool_error(
            "invalid_gpio_state",
            "GPIO state must be 'on' or 'off'."
        )


    # --------------------------------------------------------
    # Send request to ESP32
    # --------------------------------------------------------

    try:

        response = requests.get(
            f"{ESP32_BASE_URL}/gpio/write",
            params={
                "pin": pin,
                "state": state
            },
            timeout=ESP32_TIMEOUT
        )

        response.raise_for_status()

    except requests.exceptions.Timeout:

        return tool_error(
            "esp32_timeout",
            f"ESP32 did not respond while controlling GPIO {pin}.",
            "offline"
        )

    except requests.exceptions.ConnectionError:

        return tool_error(
            "esp32_offline",
            f"ESP32 could not be reached while controlling GPIO {pin}.",
            "offline"
        )

    except requests.exceptions.HTTPError as e:

        return tool_error(
            "esp32_http_error",
            f"ESP32 rejected the GPIO {pin} command: {e}"
        )

    except requests.exceptions.RequestException as e:

        return tool_error(
            "esp32_request_error",
            f"Could not send GPIO {pin} command to ESP32: {e}",
            "offline"
        )


    # --------------------------------------------------------
    # Validate ESP32 response
    # --------------------------------------------------------

    try:

        esp32_response = response.json()

    except ValueError:

        return tool_error(
            "invalid_esp32_response",
            "ESP32 returned an invalid response after the GPIO command."
        )


    if not isinstance(esp32_response, dict):

        return tool_error(
            "invalid_esp32_response",
            "ESP32 returned an unexpected GPIO response."
        )


    # --------------------------------------------------------
    # Verify GPIO
    # --------------------------------------------------------

    response_gpio = esp32_response.get("gpio")

    if response_gpio != pin:

        return tool_error(
            "gpio_verification_failed",
            (
                f"ESP32 did not confirm control of GPIO {pin}."
            )
        )


    # --------------------------------------------------------
    # Verify state
    # --------------------------------------------------------

    expected_state = state.upper()

    response_state = str(
        esp32_response.get(
            "state",
            ""
        )
    ).upper()


    if response_state != expected_state:

        return tool_error(
            "gpio_verification_failed",
            (
                f"ESP32 did not confirm GPIO {pin} "
                f"{expected_state}."
            )
        )


    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    return {
        "success": True,
        "gpio": pin,
        "state": expected_state,
        "value": esp32_response.get("value"),
        "message": (
            f"GPIO {pin} has been successfully turned "
            f"{expected_state}."
        ),
        "esp32_response": esp32_response
    }


# ============================================================
# PHASE 8.3 — DIGITAL GPIO READ
# ============================================================

def digital_read(pin):
    """
    Safely read an approved digital GPIO.

    Approved GPIOs are defined in SAFE_DIGITAL_GPIOS.
    """

    # --------------------------------------------------------
    # Validate GPIO
    # --------------------------------------------------------

    valid, result = validate_gpio_number(pin)

    if not valid:
        return result

    pin = result


    # --------------------------------------------------------
    # PHASE 8.3 SAFETY CHECK
    # --------------------------------------------------------

    if pin not in SAFE_DIGITAL_GPIOS:

        return tool_error(
            "unsupported_gpio",
            (
                f"GPIO {pin} is not allowed. "
                "It is outside the safe digital GPIO registry."
            )
        )


    # --------------------------------------------------------
    # Send request to ESP32
    # --------------------------------------------------------

    try:

        response = requests.get(
            f"{ESP32_BASE_URL}/gpio/read",
            params={
                "pin": pin
            },
            timeout=ESP32_TIMEOUT
        )

        response.raise_for_status()

    except requests.exceptions.Timeout:

        return tool_error(
            "esp32_timeout",
            f"ESP32 did not respond while reading GPIO {pin}.",
            "offline"
        )

    except requests.exceptions.ConnectionError:

        return tool_error(
            "esp32_offline",
            f"ESP32 could not be reached while reading GPIO {pin}.",
            "offline"
        )

    except requests.exceptions.HTTPError as e:

        return tool_error(
            "esp32_http_error",
            f"ESP32 rejected the GPIO read request: {e}"
        )

    except requests.exceptions.RequestException as e:

        return tool_error(
            "esp32_request_error",
            f"Could not read GPIO {pin} from ESP32: {e}",
            "offline"
        )


    # --------------------------------------------------------
    # Validate ESP32 response
    # --------------------------------------------------------

    try:

        esp32_response = response.json()

    except ValueError:

        return tool_error(
            "invalid_esp32_response",
            "ESP32 returned an invalid response while reading GPIO."
        )


    if not isinstance(esp32_response, dict):

        return tool_error(
            "invalid_esp32_response",
            "ESP32 returned an unexpected GPIO read response."
        )


    # --------------------------------------------------------
    # Verify GPIO
    # --------------------------------------------------------

    response_gpio = esp32_response.get("gpio")

    if response_gpio != pin:

        return tool_error(
            "gpio_verification_failed",
            (
                f"ESP32 did not confirm that GPIO {pin} "
                "was read."
            )
        )


    # --------------------------------------------------------
    # Validate value
    # --------------------------------------------------------

    value = esp32_response.get("value")

    if value not in [0, 1]:

        return tool_error(
            "invalid_gpio_response",
            (
                f"ESP32 returned an invalid digital value "
                f"for GPIO {pin}."
            )
        )


    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    state = (
        "HIGH"
        if value == 1
        else "LOW"
    )


    return {
        "success": True,
        "gpio": pin,
        "value": value,
        "state": state,
        "message": (
            f"GPIO {pin} is currently {state}."
        ),
        "esp32_response": esp32_response
    }


# ============================================================
# TELEMETRY HISTORY
# ============================================================

def get_history(limit=10):
    """
    Read recent telemetry records from SQLite.

    Safety:
    - Limit is converted to an integer.
    - Maximum of 20 records can be requested.
    - Database path is fixed to the project directory.
    """

    # --------------------------------------------------------
    # Validate limit
    # --------------------------------------------------------

    try:

        if isinstance(limit, bool):
            raise ValueError

        limit = int(limit)

    except (ValueError, TypeError):

        limit = 10


    # --------------------------------------------------------
    # Safety limit
    # --------------------------------------------------------

    limit = max(
        1,
        min(limit, 20)
    )


    # --------------------------------------------------------
    # Read SQLite database
    # --------------------------------------------------------

    try:

        with sqlite3.connect(
            TELEMETRY_DB,
            timeout=5
        ) as conn:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    timestamp,
                    uptime,
                    rssi,
                    gpio2,
                    free_heap
                FROM telemetry
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,)
            )

            rows = cursor.fetchall()


    except sqlite3.Error as e:

        return tool_error(
            "database_error",
            f"Could not read telemetry history: {e}"
        )


    # --------------------------------------------------------
    # Convert oldest → newest
    # --------------------------------------------------------

    rows.reverse()


    history = []


    for row in rows:

        history.append({

            "timestamp": row[0],

            "uptime": row[1],

            "rssi": row[2],

            "gpio2": row[3],

            "free_heap": row[4]

        })


    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    return {
        "success": True,
        "records": history,
        "count": len(history)
    }


# ============================================================
# PHASE 8.4 — MULTIPLE GPIO DIGITAL WRITE
# ============================================================

def digital_write_multiple(commands):
    """
    Safely control multiple approved ESP32 digital GPIOs.

    Example:
    [
        {"pin": 4, "state": "on"},
        {"pin": 16, "state": "off"}
    ]

    Safety:
    - Entire request is validated before any GPIO is changed.
    - Only GPIOs in SAFE_DIGITAL_GPIOS are allowed.
    - Only ON/OFF states are allowed.
    - Duplicate GPIOs are rejected.
    - Maximum 8 GPIO operations per request.
    """

    # --------------------------------------------------------
    # Validate input type
    # --------------------------------------------------------

    if not isinstance(commands, list):

        return {
            "success": False,
            "error_code": "invalid_commands",
            "message": "GPIO commands must be provided as a list."
        }


    # --------------------------------------------------------
    # Validate number of commands
    # --------------------------------------------------------

    if len(commands) == 0:

        return {
            "success": False,
            "error_code": "empty_commands",
            "message": "At least one GPIO command is required."
        }


    if len(commands) > 8:

        return {
            "success": False,
            "error_code": "too_many_commands",
            "message": "Maximum 8 GPIO operations are allowed in one request."
        }


    # --------------------------------------------------------
    # FIRST PASS — validate EVERYTHING
    # --------------------------------------------------------

    validated_commands = []

    seen_pins = set()


    for index, command in enumerate(commands):

        if not isinstance(command, dict):

            return {
                "success": False,
                "error_code": "invalid_command",
                "message": (
                    f"Command {index + 1} must be an object "
                    "containing pin and state."
                )
            }


        # ----------------------------------------------------
        # GPIO PIN
        # ----------------------------------------------------

        try:

            pin = int(
                command.get("pin")
            )

        except (ValueError, TypeError):

            return {
                "success": False,
                "error_code": "invalid_gpio",
                "message": (
                    f"Command {index + 1} contains "
                    "an invalid GPIO number."
                )
            }


        # ----------------------------------------------------
        # SAFETY CHECK
        # ----------------------------------------------------

        if pin not in SAFE_DIGITAL_GPIOS:

            return {
                "success": False,
                "error_code": "unsafe_gpio",
                "message": (
                    f"GPIO {pin} is not allowed. "
                    "The entire multiple-GPIO request "
                    "was rejected before any GPIO was changed."
                ),
                "gpio": pin
            }


        # ----------------------------------------------------
        # DUPLICATE CHECK
        # ----------------------------------------------------

        if pin in seen_pins:

            return {
                "success": False,
                "error_code": "duplicate_gpio",
                "message": (
                    f"GPIO {pin} appears more than once "
                    "in the same request."
                ),
                "gpio": pin
            }


        seen_pins.add(pin)


        # ----------------------------------------------------
        # STATE
        # ----------------------------------------------------

        state = str(
            command.get("state", "")
        ).lower().strip()


        if state not in {
            "on",
            "off"
        }:

            return {
                "success": False,
                "error_code": "invalid_gpio_state",
                "message": (
                    f"GPIO {pin} state must be "
                    "'on' or 'off'."
                ),
                "gpio": pin
            }


        validated_commands.append({

            "pin": pin,

            "state": state

        })


    # --------------------------------------------------------
    # SECOND PASS — EXECUTE ONLY AFTER FULL VALIDATION
    # --------------------------------------------------------

    results = []

    all_success = True


    for command in validated_commands:

        result = digital_write(

            command["pin"],

            command["state"]

        )


        results.append({

            "gpio": command["pin"],

            "requested_state":
                command["state"].upper(),

            "result": result

        })


        if not result.get(
            "success",
            False
        ):

            all_success = False


    # --------------------------------------------------------
    # FINAL RESULT
    # --------------------------------------------------------

    return {

        "success": all_success,

        "operation": "multiple_gpio_write",

        "count": len(results),

        "results": results

    }


# ============================================================
# PHASE 8.5 — ADC READ
# ============================================================

def read_adc(pin):
    """
    Safely read an approved ESP32 ADC1 GPIO.

    Only GPIOs in SAFE_ADC_PINS are allowed.
    """

    # --------------------------------------------------------
    # Validate GPIO
    # --------------------------------------------------------

    valid, result = validate_gpio_number(pin)

    if not valid:
        return result

    pin = result


    # --------------------------------------------------------
    # PHASE 8.5 SAFETY CHECK
    # --------------------------------------------------------

    if pin not in SAFE_ADC_PINS:

        return tool_error(
            "unsupported_adc_gpio",
            (
                f"GPIO {pin} is not allowed. "
                "It is outside the safe ADC1 registry."
            )
        )


    # --------------------------------------------------------
    # Send request to ESP32
    # --------------------------------------------------------

    try:

        response = requests.get(
            f"{ESP32_BASE_URL}/adc/read",
            params={
                "pin": pin
            },
            timeout=ESP32_TIMEOUT
        )

        response.raise_for_status()

    except requests.exceptions.Timeout:

        return tool_error(
            "esp32_timeout",
            f"ESP32 did not respond while reading ADC GPIO {pin}.",
            "offline"
        )

    except requests.exceptions.ConnectionError:

        return tool_error(
            "esp32_offline",
            f"ESP32 could not be reached while reading ADC GPIO {pin}.",
            "offline"
        )

    except requests.exceptions.HTTPError as e:

        return tool_error(
            "esp32_http_error",
            f"ESP32 rejected the ADC GPIO {pin} request: {e}"
        )

    except requests.exceptions.RequestException as e:

        return tool_error(
            "esp32_request_error",
            f"Could not read ADC GPIO {pin} from ESP32: {e}",
            "offline"
        )


    # --------------------------------------------------------
    # Validate ESP32 JSON response
    # --------------------------------------------------------

    try:

        esp32_response = response.json()

    except ValueError:

        return tool_error(
            "invalid_esp32_response",
            "ESP32 returned invalid JSON while reading ADC."
        )


    if not isinstance(esp32_response, dict):

        return tool_error(
            "invalid_esp32_response",
            "ESP32 returned an unexpected ADC response."
        )


    # --------------------------------------------------------
    # Verify ESP32 operation succeeded
    # --------------------------------------------------------

    if esp32_response.get("success") is not True:

        return tool_error(
            "adc_read_failed",
            esp32_response.get(
                "error",
                "ESP32 failed to read the ADC."
            )
        )


    # --------------------------------------------------------
    # Verify GPIO
    # --------------------------------------------------------

    response_gpio = esp32_response.get("gpio")

    if response_gpio != pin:

        return tool_error(
            "adc_verification_failed",
            f"ESP32 did not confirm that ADC GPIO {pin} was read."
        )


    # --------------------------------------------------------
    # Validate RAW ADC value
    # --------------------------------------------------------

    raw = esp32_response.get("raw")

    if not isinstance(raw, int) or isinstance(raw, bool):

        return tool_error(
            "invalid_adc_response",
            f"ESP32 returned an invalid raw ADC value for GPIO {pin}."
        )


    if raw < 0 or raw > 4095:

        return tool_error(
            "invalid_adc_response",
            f"ESP32 returned an out-of-range raw ADC value for GPIO {pin}."
        )


    # --------------------------------------------------------
    # Validate MILLIVOLT value
    # --------------------------------------------------------

    millivolts = esp32_response.get("millivolts")

    if not isinstance(millivolts, int) or isinstance(millivolts, bool):

        return tool_error(
            "invalid_adc_response",
            f"ESP32 returned an invalid millivolt value for GPIO {pin}."
        )


    if millivolts < 0:

        return tool_error(
            "invalid_adc_response",
            f"ESP32 returned a negative millivolt value for GPIO {pin}."
        )


    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    return {
        "success": True,
        "gpio": pin,
        "raw": raw,
        "millivolts": millivolts,
        "resolution_bits": esp32_response.get(
            "resolution_bits",
            12
        ),
        "adc": esp32_response.get(
            "adc",
            "ADC1"
        ),
        "attenuation": esp32_response.get(
            "attenuation",
            "11dB"
        ),
        "message": (
            f"ADC GPIO {pin} read successfully: "
            f"{raw} raw, {millivolts} mV."
        ),
        "esp32_response": esp32_response
    }

# ============================================================
# PHASE 8.6 — PWM WRITE
# ============================================================

def set_pwm(pin, duty):
    """
    Safely set PWM duty cycle on an approved ESP32 GPIO.

    PWM configuration on the ESP32:
    - Frequency: 5000 Hz
    - Resolution: 8-bit
    - Duty range: 0-255

    Examples:
        0   = 0%
        64  = ~25%
        128 = ~50%
        192 = ~75%
        255 = 100%
    """

    # --------------------------------------------------------
    # Validate GPIO number
    # --------------------------------------------------------

    valid, result = validate_gpio_number(pin)

    if not valid:
        return result

    pin = result

    # --------------------------------------------------------
    # PHASE 8.6 SAFETY CHECK
    # --------------------------------------------------------

    if pin not in SAFE_PWM_PINS:

        return tool_error(
            "unsupported_pwm_gpio",
            (
                f"GPIO {pin} is not allowed for PWM. "
                "It is outside the safe PWM GPIO registry."
            )
        )

    # --------------------------------------------------------
    # Validate duty cycle
    # --------------------------------------------------------

    try:

        if isinstance(duty, bool):
            raise ValueError

        duty = int(duty)

    except (ValueError, TypeError):

        return tool_error(
            "invalid_pwm_duty",
            "PWM duty must be an integer between 0 and 255."
        )

    if duty < PWM_MIN_DUTY or duty > PWM_MAX_DUTY:

        return tool_error(
            "invalid_pwm_duty",
            "PWM duty must be between 0 and 255."
        )

    # --------------------------------------------------------
    # Send request to ESP32
    # --------------------------------------------------------

    try:

        response = requests.get(
            f"{ESP32_BASE_URL}/pwm/write",
            params={
                "pin": pin,
                "duty": duty
            },
            timeout=ESP32_TIMEOUT
        )

        response.raise_for_status()

    except requests.exceptions.Timeout:

        return tool_error(
            "esp32_timeout",
            f"ESP32 did not respond while setting PWM on GPIO {pin}.",
            "offline"
        )

    except requests.exceptions.ConnectionError:

        return tool_error(
            "esp32_offline",
            f"ESP32 could not be reached while setting PWM on GPIO {pin}.",
            "offline"
        )

    except requests.exceptions.HTTPError as e:

        return tool_error(
            "esp32_http_error",
            f"ESP32 rejected the PWM command for GPIO {pin}: {e}"
        )

    except requests.exceptions.RequestException as e:

        return tool_error(
            "esp32_request_error",
            f"Could not send PWM command to ESP32: {e}",
            "offline"
        )

    # --------------------------------------------------------
    # Validate ESP32 JSON response
    # --------------------------------------------------------

    try:

        esp32_response = response.json()

    except ValueError:

        return tool_error(
            "invalid_esp32_response",
            "ESP32 returned invalid JSON after the PWM command."
        )

    if not isinstance(esp32_response, dict):

        return tool_error(
            "invalid_esp32_response",
            "ESP32 returned an unexpected PWM response."
        )

    # --------------------------------------------------------
    # Verify operation succeeded
    # --------------------------------------------------------

    if esp32_response.get("success") is not True:

        return tool_error(
            "pwm_write_failed",
            esp32_response.get(
                "error",
                "ESP32 failed to apply the PWM command."
            )
        )

    # --------------------------------------------------------
    # Verify GPIO
    # --------------------------------------------------------

    response_gpio = esp32_response.get("gpio")

    if response_gpio != pin:

        return tool_error(
            "pwm_verification_failed",
            f"ESP32 did not confirm PWM control of GPIO {pin}."
        )

    # --------------------------------------------------------
    # Verify duty
    # --------------------------------------------------------

    response_duty = esp32_response.get("duty")

    if response_duty != duty:

        return tool_error(
            "pwm_verification_failed",
            (
                f"ESP32 did not confirm PWM duty {duty} "
                f"on GPIO {pin}."
            )
        )

    # --------------------------------------------------------
    # Validate percentage
    # --------------------------------------------------------

    duty_percent = esp32_response.get("duty_percent")

    if duty_percent is None:

        duty_percent = round(
            (duty / 255.0) * 100.0,
            1
        )

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    return {
        "success": True,
        "gpio": pin,
        "duty": duty,
        "duty_percent": duty_percent,
        "frequency_hz": esp32_response.get(
            "frequency_hz",
            5000
        ),
        "resolution_bits": esp32_response.get(
            "resolution_bits",
            8
        ),
        "message": (
            f"GPIO {pin} PWM set to duty {duty} "
            f"({duty_percent}%)."
        ),
        "esp32_response": esp32_response
    }
