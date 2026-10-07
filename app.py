from flask import Flask, render_template, jsonify, request
import os
import requests
import sqlite3
import json
from datetime import datetime

from ollama import chat

from ai_tools import (
    get_device_status,
    set_gpio,
    get_history as get_telemetry_history,
    digital_read,
    digital_write,
    digital_write_multiple,
    read_adc,
    set_pwm,
    get_hardware_state
)


# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)

# Maximum firmware upload size: 4 MB
app.config["MAX_CONTENT_LENGTH"] = (
    4 * 1024 * 1024
)


# ============================================================
# ESP32 CONFIGURATION
# ============================================================

ESP32_IP = os.environ.get("ESP32_IP", "192.168.1.50")

ESP32_BASE_URL = (
    f"http://{ESP32_IP}"
)

ESP32_STATUS_URL = (
    f"{ESP32_BASE_URL}/status"
)


# ============================================================
# AI CONFIGURATION
# ============================================================

AI_MODEL = "qwen3:4b"


# ============================================================
# PHASE 8.3 / 8.4 — SAFE DIGITAL GPIO REGISTRY
# ============================================================

SAFE_DIGITAL_GPIOS = [
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
]


# ============================================================
# DATABASE
# ============================================================

def init_database():

    conn = sqlite3.connect(
        "telemetry.db"
    )

    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS telemetry (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            timestamp TEXT,

            uptime INTEGER,

            rssi INTEGER,

            gpio2 INTEGER,

            free_heap INTEGER

        )
        """
    )

    conn.commit()

    conn.close()


# ============================================================
# SAVE TELEMETRY
# ============================================================

def save_telemetry(data):

    conn = sqlite3.connect(
        "telemetry.db"
    )

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO telemetry
        (
            timestamp,
            uptime,
            rssi,
            gpio2,
            free_heap
        )

        VALUES (?, ?, ?, ?, ?)
        """,
        (
            datetime.now().isoformat(
                timespec="seconds"
            ),

            data.get("uptime"),

            data.get("rssi"),

            data.get("gpio2"),

            data.get("free_heap")
        )
    )

    conn.commit()

    conn.close()


# ============================================================
# DEVICE HEALTH ANALYSIS
# ============================================================

def analyze_health(data):

    alerts = []

    health = "GOOD"

    rssi = data.get(
        "rssi"
    )

    free_heap = data.get(
        "free_heap"
    )


    # --------------------------------------------------------
    # WIFI RSSI
    # --------------------------------------------------------

    if rssi is not None:

        if rssi <= -75:

            alerts.append(
                "Wi-Fi signal is very weak"
            )

            health = "CRITICAL"


        elif rssi <= -65:

            alerts.append(
                "Wi-Fi signal is weak"
            )

            if health == "GOOD":

                health = "WARNING"


    # --------------------------------------------------------
    # FREE HEAP
    # --------------------------------------------------------

    if free_heap is not None:

        if free_heap < 50000:

            alerts.append(
                "ESP32 free heap is critically low"
            )

            health = "CRITICAL"


        elif free_heap < 100000:

            alerts.append(
                "ESP32 free heap is getting low"
            )

            if health == "GOOD":

                health = "WARNING"


    return {
        "health": health,
        "alerts": alerts
    }


# ============================================================
# PHASE 8.5 — AI TOOL DEFINITIONS
# ============================================================

AI_TOOLS = [

    # ========================================================
    # GET DEVICE STATUS
    # ========================================================

    {
        "type": "function",

        "function": {

            "name":
                "get_device_status",

            "description":
                (
                    "Get the current ESP32 EdgeHub status. "
                    "Returns online status, IP address, "
                    "Wi-Fi RSSI, GPIO 2 state, free heap, "
                    "uptime and firmware version."
                ),

            "parameters": {

                "type": "object",

                "properties": {},

                "required": []
            }
        }
    },


    # ========================================================
    # EXISTING PHASE 7 GPIO 2 CONTROL
    # ========================================================

    {
        "type": "function",

        "function": {

            "name":
                "set_gpio",

            "description":
                (
                    "Turn GPIO 2 on or off. "
                    "This is the legacy Phase 7 GPIO tool "
                    "and is restricted to GPIO 2."
                ),

            "parameters": {

                "type": "object",

                "properties": {

                    "pin": {

                        "type": "integer",

                        "enum": [2]

                    },

                    "state": {

                        "type": "string",

                        "enum": [
                            "on",
                            "off"
                        ]
                    }
                },

                "required": [
                    "pin",
                    "state"
                ]
            }
        }
    },


    # ========================================================
    # TELEMETRY HISTORY
    # ========================================================

    {
        "type": "function",

        "function": {

            "name":
                "get_history",

            "description":
                (
                    "Get recent ESP32 telemetry history "
                    "including Wi-Fi RSSI, GPIO 2 state, "
                    "uptime and free heap."
                ),

            "parameters": {

                "type": "object",

                "properties": {

                    "limit": {

                        "type": "integer",

                        "minimum": 1,

                        "maximum": 20
                    }
                },

                "required": []
            }
        }
    },


    # ========================================================
    # PHASE 8.3 — DIGITAL GPIO READ
    # ========================================================

    {
        "type": "function",

        "function": {

            "name":
                "digital_read",

            "description":
                (
                    "Read the current digital HIGH or LOW "
                    "state of an approved ESP32 GPIO. "
                    "Only GPIOs in the safe digital GPIO "
                    "registry may be read."
                ),

            "parameters": {

                "type": "object",

                "properties": {

                    "pin": {

                        "type": "integer",

                        "enum":
                            SAFE_DIGITAL_GPIOS
                    }
                },

                "required": [
                    "pin"
                ]
            }
        }
    },


    # ========================================================
    # PHASE 8.3 — DIGITAL GPIO WRITE
    # ========================================================

    {
        "type": "function",

        "function": {

            "name":
                "digital_write",

            "description":
                (
                    "Set one approved ESP32 digital GPIO "
                    "HIGH or LOW. "
                    "Use 'on' for HIGH and 'off' for LOW. "
                    "Only GPIOs in the safe digital GPIO "
                    "registry may be controlled."
                ),

            "parameters": {

                "type": "object",

                "properties": {

                    "pin": {

                        "type": "integer",

                        "enum":
                            SAFE_DIGITAL_GPIOS
                    },

                    "state": {

                        "type": "string",

                        "enum": [
                            "on",
                            "off"
                        ]
                    }
                },

                "required": [
                    "pin",
                    "state"
                ]
            }
        }
    },


    # ========================================================
    # PHASE 8.4 — MULTIPLE GPIO DIGITAL WRITE
    # ========================================================

    {
        "type": "function",

        "function": {

            "name":
                "digital_write_multiple",

            "description":
                (
                    "Safely control multiple approved ESP32 "
                    "digital GPIOs in one operation. "
                    "The complete request is validated before "
                    "any GPIO is changed. "
                    "Only approved GPIOs are allowed. "
                    "Maximum 8 GPIO operations per request."
                ),

            "parameters": {

                "type": "object",

                "properties": {

                    "commands": {

                        "type": "array",

                        "description":
                            (
                                "List of GPIO operations. "
                                "Each operation must contain "
                                "pin and state."
                            ),

                        "items": {

                            "type": "object",

                            "properties": {

                                "pin": {

                                    "type": "integer",

                                    "enum":
                                        SAFE_DIGITAL_GPIOS
                                },

                                "state": {

                                    "type": "string",

                                    "enum": [
                                        "on",
                                        "off"
                                    ]
                                }
                            },

                            "required": [
                                "pin",
                                "state"
                            ]
                        },

                        "minItems": 1,

                        "maxItems": 8
                    }
                },

                "required": [
                    "commands"
                ]
            }
        }
    },


    # ========================================================
    # PHASE 8.5 — ADC READ
    # ========================================================

    {
        "type": "function",

        "function": {

            "name":
                "read_adc",

            "description":
                (
                    "Read the analog value from an approved "
                    "ESP32 ADC1 GPIO. Returns the raw ADC value "
                    "and calibrated millivolts. "
                    "Only GPIOs 32, 33, 34, 35, 36 and 39 "
                    "are allowed."
                ),

            "parameters": {

                "type": "object",

                "properties": {

                    "pin": {

                        "type": "integer",

                        "enum": [
                            32,
                            33,
                            34,
                            35,
                            36,
                            39
                        ]
                    }
                },

                "required": [
                    "pin"
                ]
            }
        }
    },

    # ========================================================
    # PHASE 8.6 — PWM WRITE
    # ========================================================

    {
        "type": "function",

        "function": {

            "name":
                "set_pwm",

            "description":
                (
                    "Set the PWM duty cycle of an approved "
                    "ESP32 GPIO. PWM uses 5 kHz frequency and "
                    "8-bit resolution. Duty 0 is 0%, 128 is "
                    "about 50%, and 255 is 100%. "
                    "Only GPIOs 4, 16, 17, 18, 19, 21, 22, "
                    "23, 25, 26 and 27 are allowed."
                ),

            "parameters": {

                "type": "object",

                "properties": {

                    "pin": {

                        "type": "integer",

                        "enum": [
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
                        ]
                    },

                    "duty": {

                        "type": "integer",

                        "minimum": 0,

                        "maximum": 255,

                        "description":
                            (
                                "PWM duty cycle from 0 to 255. "
                                "0=0%, 64≈25%, 128≈50%, "
                                "192≈75%, 255=100%."
                            )
                    }
                },

                "required": [
                    "pin",
                    "duty"
                ]
            }
        }
    }
,

    # ========================================================
    # PHASE 8.7 — UNIFIED HARDWARE STATE
    # ========================================================

    {
        "type": "function",

        "function": {

            "name":
                "get_hardware_state",

            "description":
                (
                    "Read the unified current ESP32 hardware state. "
                    "Returns approved digital GPIO states, active PWM "
                    "channels and duty cycles, and the latest ADC "
                    "readings without changing hardware configuration. "
                    "Use this before answering questions about what the "
                    "ESP32 is currently doing."
                ),

            "parameters": {

                "type": "object",

                "properties": {},

                "required": []
            }
        }
    }

]


# ============================================================
# PHASE 8.5 — AI SYSTEM PROMPT
# ============================================================

AI_SYSTEM_PROMPT = """

You are the AI controller for ESP32 EdgeHub.

Your job is to help the user monitor and safely control
their ESP32 EdgeHub device.


AVAILABLE CAPABILITIES:

1. Read ESP32 device status.
2. Control GPIO 2 using the legacy set_gpio tool.
3. Read recent telemetry history.
4. Read approved digital GPIOs using digital_read.
5. Control one approved digital GPIO using digital_write.
6. Control multiple approved digital GPIOs using
   digital_write_multiple.
7. Read approved ADC1 analog GPIOs using read_adc.
8. Control approved PWM GPIOs using set_pwm.


PHASE 8 SAFE DIGITAL GPIO REGISTRY:

GPIO 2
GPIO 4
GPIO 16
GPIO 17
GPIO 18
GPIO 19
GPIO 21
GPIO 22
GPIO 23
GPIO 25
GPIO 26
GPIO 27
GPIO 32
GPIO 33


PHASE 8.5 SAFE ADC1 REGISTRY:

GPIO 32
GPIO 33
GPIO 34
GPIO 35
GPIO 36
GPIO 39


IMPORTANT SAFETY RULES:

- Only use digital_read for GPIOs in the approved
  digital GPIO registry.

- Only use digital_write for GPIOs in the approved
  digital GPIO registry.

- Only use digital_write_multiple for GPIOs in the
  approved digital GPIO registry.

- Never attempt to control a GPIO outside the approved
  digital GPIO registry.

- GPIO 34, 35, 36 and 39 are NOT allowed for digital
  output control.

- GPIO 5 is NOT allowed by the Phase 8 digital registry.

- Never invent ESP32 status information.

- Never claim that an action succeeded unless the
  tool result confirms success.

- For Wi-Fi signal questions, use get_device_status.

- For firmware questions, use get_device_status.

- For uptime questions, use get_device_status.

- For general device status questions, use
  get_device_status.

- For GPIO 2 state questions, get_device_status may
  be used.

- For the state of another approved GPIO, use
  digital_read.

- For telemetry/history questions, use get_history.

- For GPIO 2 control, set_gpio may be used.

- For a single approved GPIO operation, use
  digital_write.

- For multiple GPIO operations requested together,
  use digital_write_multiple.

- When using digital_write_multiple, include every
  requested GPIO and its desired state in the commands
  list.

- Never split a multiple-GPIO request into unsafe
  individual operations.

- Never attempt a GPIO operation outside the safe
  registry.

- If a requested GPIO is outside the safe registry,
  explain that it is not available for digital control.

- Never invent a GPIO reading.

- Never claim HIGH or LOW unless the tool confirms it.


PHASE 8.5 ADC RULES:

- Only use read_adc for GPIOs 32, 33, 34, 35, 36 and 39.

- Never use read_adc for GPIO 5 or any GPIO outside
  the approved ADC1 registry.

- Never invent ADC readings.

- Never claim an ADC reading succeeded unless the
  read_adc tool result confirms success.

- When the user asks for an analog reading, ADC value,
  voltage or millivolt value from an approved ADC1 GPIO,
  use read_adc.



PHASE 8.6 PWM RULES:

- Only use set_pwm for GPIOs 4, 16, 17, 18, 19, 21, 22,
  23, 25, 26 and 27.

- PWM duty must always be an integer from 0 to 255.

- PWM mapping is:
  0 = 0%
  64 ≈ 25%
  128 ≈ 50%
  192 ≈ 75%
  255 = 100%

- PWM frequency is 5000 Hz and resolution is 8-bit.

- Never use set_pwm for GPIO 2.

- Never use set_pwm for GPIO 32 or GPIO 33 because those
  pins are reserved as shared ADC-capable pins.

- Never use set_pwm for GPIO 34, 35, 36 or 39 because
  those GPIOs are input-only.

- GPIO 5 is not approved for PWM control.

- If the user asks for a percentage, convert it to the
  nearest 8-bit duty value using:
  duty = round(percentage * 255 / 100).

- Never claim PWM succeeded unless the set_pwm tool result
  confirms success.

- When reporting PWM changes, clearly mention the GPIO,
  duty value and approximate percentage.

- When reporting an ADC reading, clearly mention both
  the raw ADC value and millivolts when available.

- GPIO 34, 35, 36 and 39 are ADC input-only GPIOs and
  must never be treated as digital outputs.

- GPIO 32 and 33 are shared-capability pins. Reading
  them with read_adc configures them for analog input
  operation on the ESP32.

PHASE 8.7 UNIFIED HARDWARE STATE RULES:

- Use get_hardware_state when the user asks what the ESP32 is currently doing, which approved GPIOs are HIGH or LOW, which PWM channels are active, the current PWM duty cycle, firmware phase, or the latest recorded ADC state.

- Treat get_hardware_state as read-only. It must never be described as changing a GPIO, PWM output or ADC configuration.

- Never invent current hardware state. Only report GPIO, PWM or ADC values confirmed by the tool.

- If a PWM GPIO is active, report its PWM duty information rather than claiming it is a normal static HIGH or LOW digital output.

- GPIO 32 and 33 are shared digital/ADC pins. Respect the mode reported by the hardware-state tool and do not claim simultaneous independent digital and ADC operation.

- Latest ADC values may be unavailable until an ADC read has occurred. Say so when the tool reports that no reading is available.

- When the user asks for a complete hardware overview, prefer get_hardware_state over making several separate read-only tool calls.

- Keep responses clear and concise.

"""


# ============================================================
# NORMALIZE AI TOOL ARGUMENTS
# ============================================================

def normalize_tool_arguments(arguments):

    # Ollama normally returns a dictionary,
    # but safely handle JSON strings too.

    if isinstance(
        arguments,
        dict
    ):

        return arguments


    if isinstance(
        arguments,
        str
    ):

        try:

            parsed = json.loads(
                arguments
            )

            if isinstance(
                parsed,
                dict
            ):

                return parsed

        except (
            ValueError,
            TypeError
        ):

            pass


    return {}


# ============================================================
# EXECUTE AI TOOL
# ============================================================

def execute_ai_tool(
    tool_name,
    arguments
):

    print()

    print(
        "AI TOOL REQUEST"
    )

    print(
        "Tool:",
        tool_name
    )

    print(
        "Arguments:",
        arguments
    )


    arguments = normalize_tool_arguments(
        arguments
    )


    # ========================================================
    # GET DEVICE STATUS
    # ========================================================

    if tool_name == "get_device_status":

        result = (
            get_device_status()
        )


    # ========================================================
    # LEGACY GPIO 2 CONTROL
    # ========================================================

    elif tool_name == "set_gpio":

        pin = arguments.get(
            "pin"
        )

        state = arguments.get(
            "state"
        )


        result = set_gpio(
            pin,
            state
        )


    # ========================================================
    # TELEMETRY HISTORY
    # ========================================================

    elif tool_name == "get_history":

        limit = arguments.get(
            "limit",
            10
        )


        result = (
            get_telemetry_history(
                limit
            )
        )


    # ========================================================
    # PHASE 8.3 — DIGITAL GPIO READ
    # ========================================================

    elif tool_name == "digital_read":

        pin = arguments.get(
            "pin"
        )


        result = digital_read(
            pin
        )


    # ========================================================
    # PHASE 8.3 — DIGITAL GPIO WRITE
    # ========================================================

    elif tool_name == "digital_write":

        pin = arguments.get(
            "pin"
        )

        state = arguments.get(
            "state"
        )


        result = digital_write(
            pin,
            state
        )


    # ========================================================
    # PHASE 8.5 — ADC READ
    # ========================================================

    elif tool_name == "read_adc":

        pin = arguments.get(
            "pin"
        )

        result = read_adc(
            pin
        )


    # ========================================================
    # PHASE 8.6 — PWM WRITE
    # ========================================================

    elif tool_name == "set_pwm":

        pin = arguments.get(
            "pin"
        )

        duty = arguments.get(
            "duty"
        )

        result = set_pwm(
            pin,
            duty
        )


    # ========================================================
    # PHASE 8.7 — UNIFIED HARDWARE STATE
    # ========================================================

    elif tool_name == "get_hardware_state":

        result = get_hardware_state()


    # ========================================================
    # PHASE 8.4 — MULTIPLE GPIO DIGITAL WRITE
    # ========================================================

    elif tool_name == "digital_write_multiple":

        commands = arguments.get(
            "commands",
            []
        )


        # ----------------------------------------------------
        # Handle JSON string returned by some model responses
        # ----------------------------------------------------

        if isinstance(
            commands,
            str
        ):

            try:

                commands = json.loads(
                    commands
                )

            except (
                ValueError,
                TypeError
            ):

                commands = []


        result = digital_write_multiple(
            commands
        )


    # ========================================================
    # UNKNOWN TOOL
    # ========================================================

    else:

        result = {

            "success":
                False,

            "error_code":
                "unknown_tool",

            "message":
                "Unknown AI tool."
        }


    print(
        "Tool result:",
        result
    )


    return result


# ============================================================
# RUN AI COMMAND
# ============================================================

def run_ai_command(
    user_command
):

    messages = [

        {
            "role":
                "system",

            "content":
                AI_SYSTEM_PROMPT
        },

        {
            "role":
                "user",

            "content":
                user_command
        }
    ]


    # ========================================================
    # FIRST AI CALL
    # ========================================================

    response = chat(

        model=AI_MODEL,

        messages=messages,

        tools=AI_TOOLS
    )


    # ========================================================
    # NO TOOL REQUIRED
    # ========================================================

    if not response.message.tool_calls:

        return {

            "success":
                True,

            "response":
                response.message.content
        }


    # ========================================================
    # ADD AI TOOL REQUEST
    # ========================================================

    messages.append(
        response.message
    )


    # ========================================================
    # EXECUTE EVERY REQUESTED TOOL
    # ========================================================

    for tool_call in (
        response.message.tool_calls
    ):

        tool_name = (
            tool_call.function.name
        )

        arguments = (
            tool_call.function.arguments
        )


        result = execute_ai_tool(

            tool_name,

            arguments
        )


        # ----------------------------------------------------
        # RETURN TOOL RESULT TO AI
        # ----------------------------------------------------

        messages.append({

            "role":
                "tool",

            "content":
                json.dumps(
                    result,
                    default=str
                )
        })


    # ========================================================
    # SECOND AI CALL
    # ========================================================

    final_response = chat(

        model=AI_MODEL,

        messages=messages
    )


    return {

        "success":
            True,

        "response":
            final_response.message.content
    }


# ============================================================
# MAIN DASHBOARD
# ============================================================

@app.route("/")
def dashboard():

    return render_template(
        "dashboard.html"
    )


# ============================================================
# AI COMMAND API
# ============================================================

@app.route(
    "/api/ai",
    methods=["POST"]
)
def ai_command():

    try:

        data = request.get_json(
            silent=True
        )


        if not data:

            return jsonify({

                "success":
                    False,

                "error":
                    "Request body is required."

            }), 400


        command = str(

            data.get(
                "command",
                ""
            )

        ).strip()


        if not command:

            return jsonify({

                "success":
                    False,

                "error":
                    "Command cannot be empty."

            }), 400


        # ----------------------------------------------------
        # Safety limit
        # ----------------------------------------------------

        if len(command) > 500:

            return jsonify({

                "success":
                    False,

                "error":
                    (
                        "Command is too long. "
                        "Maximum 500 characters."
                    )

            }), 400


        print()

        print(
            "============================================================"
        )

        print(
            "AI COMMAND"
        )

        print(
            command
        )

        print(
            "============================================================"
        )


        result = run_ai_command(
            command
        )


        return jsonify(
            result
        )


    except Exception as e:

        print(
            "AI ERROR:",
            str(e)
        )


        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# ============================================================
# ESP32 STATUS API
# ============================================================

@app.route(
    "/api/status"
)
def get_status():

    try:

        response = requests.get(

            ESP32_STATUS_URL,

            timeout=2
        )


        response.raise_for_status()


        data = response.json()


        # ----------------------------------------------------
        # Save telemetry
        # ----------------------------------------------------

        save_telemetry(
            data
        )


        # ----------------------------------------------------
        # Health analysis
        # ----------------------------------------------------

        health = analyze_health(
            data
        )


        data["health"] = (
            health["health"]
        )

        data["alerts"] = (
            health["alerts"]
        )


        return jsonify(
            data
        )


    except requests.exceptions.RequestException as e:

        return jsonify({

            "device":
                "ESP32 EdgeHub",

            "status":
                "offline",

            "health":
                "CRITICAL",

            "alerts": [

                "ESP32 is offline or unreachable"

            ],

            "error":
                str(e)

        }), 503


# ============================================================
# PHASE 8.7 — UNIFIED HARDWARE STATE API
# ============================================================

@app.route(
    "/api/hardware/state"
)
def hardware_state_api():

    try:

        response = requests.get(
            f"{ESP32_BASE_URL}/hardware/state",
            timeout=2
        )

        response.raise_for_status()

        return jsonify(
            response.json()
        )

    except requests.exceptions.RequestException as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e),

            "status":
                "offline"

        }), 503


# ============================================================
# DEVICE HEALTH API
# ============================================================

@app.route(
    "/api/health"
)
def get_health():

    try:

        response = requests.get(

            ESP32_STATUS_URL,

            timeout=2
        )


        response.raise_for_status()


        data = response.json()


        health = analyze_health(
            data
        )


        return jsonify({

            "device":
                "ESP32 EdgeHub",

            "status":
                "online",

            "health":
                health["health"],

            "alerts":
                health["alerts"],

            "rssi":
                data.get("rssi"),

            "free_heap":
                data.get("free_heap"),

            "uptime":
                data.get("uptime"),

            "gpio2":
                data.get("gpio2"),

            "ip":
                data.get("ip"),

            "ssid":
                data.get("ssid"),

            "firmware":
                data.get("firmware")

        })


    except requests.exceptions.RequestException as e:

        return jsonify({

            "device":
                "ESP32 EdgeHub",

            "status":
                "offline",

            "health":
                "CRITICAL",

            "alerts": [

                "ESP32 is offline or unreachable"

            ],

            "error":
                str(e)

        }), 503


# ============================================================
# TELEMETRY HISTORY API
# ============================================================

@app.route(
    "/api/history"
)
def telemetry_history_api():

    conn = sqlite3.connect(
        "telemetry.db"
    )


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

        LIMIT 100
        """
    )


    rows = cursor.fetchall()


    conn.close()


    history = []


    for row in rows:

        history.append({

            "timestamp":
                row[0],

            "uptime":
                row[1],

            "rssi":
                row[2],

            "gpio2":
                row[3],

            "free_heap":
                row[4]

        })


    history.reverse()


    return jsonify(
        history
    )


# ============================================================
# EXISTING GPIO 2 DASHBOARD CONTROL API
# ============================================================

@app.route(
    "/api/gpio/<int:pin>/<action>"
)
def control_gpio(
    pin,
    action
):

    # --------------------------------------------------------
    # HARD SAFETY LIMIT
    # --------------------------------------------------------

    if pin != 2:

        return jsonify({

            "success":
                False,

            "error":
                "Only GPIO 2 is enabled."

        }), 400


    # --------------------------------------------------------
    # VALIDATE ACTION
    # --------------------------------------------------------

    if action not in [
        "on",
        "off"
    ]:

        return jsonify({

            "success":
                False,

            "error":
                "Invalid action."

        }), 400


    try:

        response = requests.get(

            f"{ESP32_BASE_URL}"
            f"/gpio/{pin}/{action}",

            timeout=2
        )


        response.raise_for_status()


        return jsonify(
            response.json()
        )


    except requests.exceptions.RequestException as e:

        return jsonify({

            "success":
                False,

            "error":
                str(e),

            "status":
                "offline"

        }), 503


# ============================================================
# OTA FIRMWARE UPDATE PAGE
# ============================================================

@app.route(
    "/update"
)
def update_page():

    return render_template(
        "ota.html"
    )


# ============================================================
# OTA FIRMWARE UPDATE API
# ============================================================

@app.route(
    "/api/ota",
    methods=["POST"]
)
def ota_update():

    # --------------------------------------------------------
    # CHECK FILE
    # --------------------------------------------------------

    if "firmware" not in request.files:

        return jsonify({

            "success":
                False,

            "error":
                "No firmware file uploaded."

        }), 400


    firmware = request.files[
        "firmware"
    ]


    if firmware.filename == "":

        return jsonify({

            "success":
                False,

            "error":
                "No firmware file selected."

        }), 400


    # --------------------------------------------------------
    # CHECK EXTENSION
    # --------------------------------------------------------

    if not firmware.filename.lower().endswith(
        ".bin"
    ):

        return jsonify({

            "success":
                False,

            "error":
                "Only .bin firmware files are allowed."

        }), 400


    try:

        print()

        print(
            "========================================"
        )

        print(
            "Starting OTA firmware update"
        )

        print(
            "Firmware:",
            firmware.filename
        )

        print(
            "ESP32:",
            ESP32_IP
        )

        print(
            "========================================"
        )


        response = requests.post(

            f"{ESP32_BASE_URL}/update",

            files={

                "firmware": (

                    firmware.filename,

                    firmware.stream,

                    "application/octet-stream"

                )
            },

            timeout=30
        )


        response.raise_for_status()


        print(
            "OTA update request completed."
        )


        return jsonify({

            "success":
                True,

            "message":
                "Firmware uploaded successfully.",

            "esp32_response":
                response.text

        })


    except requests.exceptions.RequestException as e:

        print(
            "OTA update failed:",
            e
        )


        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 503


# ============================================================
# OTA STATUS
# ============================================================

@app.route(
    "/api/ota/status"
)
def ota_status():

    try:

        response = requests.get(

            ESP32_STATUS_URL,

            timeout=2
        )


        response.raise_for_status()


        data = response.json()


        return jsonify({

            "online":
                True,

            "device":
                data.get(
                    "device",
                    "ESP32 EdgeHub"
                ),

            "firmware":
                data.get(
                    "firmware",
                    "unknown"
                ),

            "ip":
                data.get("ip"),

            "uptime":
                data.get("uptime")

        })


    except requests.exceptions.RequestException as e:

        return jsonify({

            "online":
                False,

            "error":
                str(e)

        }), 503


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(413)
def file_too_large(error):

    return jsonify({

        "success":
            False,

        "error":
            (
                "Firmware file is too large. "
                "Maximum size is 4 MB."
            )

    }), 413


# ============================================================
# SERVER START
# ============================================================

if __name__ == "__main__":

    init_database()


    print()

    print(
        "========================================"
    )

    print(
        "        ESP32 EdgeHub Dashboard"
    )

    print(
        "========================================"
    )

    print()


    print(
        "Telemetry database initialized."
    )

    print(
        "Health monitoring enabled."
    )

    print(
        "GPIO control enabled."
    )

    print(
        "OTA firmware update enabled."
    )

    print(
        "AI control enabled."
    )

    print(
        "AI model:",
        AI_MODEL
    )

    print(
        "Phase 8.6 PWM AI integration enabled."
    )

    print(
        "Phase 8.7 unified hardware state enabled."
    )

    print(
        "Hardware State API:"
    )

    print(
        "http://127.0.0.1:5000/api/hardware/state"
    )


    print(
        "Safe PWM GPIOs:",
        [4, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27]
    )

    print(
        "PWM: 5000 Hz, 8-bit (0-255)"
    )

    print(
        "Phase 8.5 ADC AI integration enabled."
    )

    print(
        "Phase 8.4 multiple GPIO AI control enabled."
    )

    print(
        "Safe ADC1 GPIOs: [32, 33, 34, 35, 36, 39]"
    )

    print(
        "Safe digital GPIOs:",
        SAFE_DIGITAL_GPIOS
    )


    print()

    print(
        "Dashboard:"
    )

    print(
        "http://127.0.0.1:5000"
    )


    print()

    print(
        "AI API:"
    )

    print(
        "POST http://127.0.0.1:5000/api/ai"
    )


    print()

    print(
        "OTA Web Interface:"
    )

    print(
        "http://127.0.0.1:5000/update"
    )


    print()

    print(
        "Status API:"
    )

    print(
        "http://127.0.0.1:5000/api/status"
    )


    print()

    print(
        "Health API:"
    )

    print(
        "http://127.0.0.1:5000/api/health"
    )


    print()

    print(
        "History API:"
    )

    print(
        "http://127.0.0.1:5000/api/history"
    )


    print()

    print(
        "========================================"
    )


    app.run(

        host="127.0.0.1",

        port=5000,

        debug=True
    )