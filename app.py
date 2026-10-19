from flask import Flask, render_template, jsonify, request
import requests
import sqlite3
import json
import os
from datetime import datetime

import httpx
from ollama import Client as OllamaClient, ResponseError
from openai import OpenAI, APIStatusError, APIConnectionError

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

# The AI provider can be switched at runtime from the
# AI EdgeHub Control panel on the dashboard:
#   "gemini" -> Google Gemini API (free tier, needs GEMINI_API_KEY)
#   "ollama" -> local Ollama model (works offline)
#   "auto"   -> Gemini first, local Ollama when Gemini is
#               busy, out of free quota or unreachable
# The choice is saved in ai_settings.json so it survives
# restarts. AI_PROVIDER (env var) is only the first default.

AI_PROVIDERS = (
    "gemini",
    "ollama",
    "auto"
)

AI_SETTINGS_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "ai_settings.json"
)

OLLAMA_MODEL = os.environ.get(
    "OLLAMA_MODEL",
    "qwen3:4b"
)

OLLAMA_HOST = os.environ.get(
    "OLLAMA_HOST",
    "http://127.0.0.1:11434"
)

GEMINI_MODEL = os.environ.get(
    "GEMINI_MODEL",
    "gemini-3.8-flash"
)

# Free models tried in order when the main model is
# overloaded (503) or out of free quota (429).
# Each model has its own free daily quota.

GEMINI_FALLBACK_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite"
]

GEMINI_MODELS = [GEMINI_MODEL] + [
    model
    for model in GEMINI_FALLBACK_MODELS
    if model != GEMINI_MODEL
]

GEMINI_RETRY_STATUS_CODES = {
    429,
    500,
    503
}

GEMINI_BASE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/openai/"
)

AI_PROVIDER_INFO = {

    "gemini": {
        "name": "Gemini",
        "label": "Gemini API • Free tier",
        "description": (
            "Runs on Google's Gemini API (free tier). "
            "Needs internet."
        )
    },

    "ollama": {
        "name": "Ollama",
        "label": f"{OLLAMA_MODEL} • Local AI",
        "description": (
            "Runs locally on this PC through Ollama. "
            "Works offline."
        )
    },

    "auto": {
        "name": "Auto",
        "label": "Auto • Gemini → Ollama",
        "description": (
            "Uses Gemini, and switches to local Ollama "
            "when Gemini is busy, out of quota or offline."
        )
    }
}


def load_ai_provider():

    # The choice saved from the dashboard wins,
    # then the AI_PROVIDER env var, then Gemini.

    try:

        with open(AI_SETTINGS_FILE, encoding="utf-8") as file:

            provider = json.load(file).get("provider")

        if provider in AI_PROVIDERS:

            return provider

    except (OSError, ValueError, AttributeError):

        pass


    provider = os.environ.get(
        "AI_PROVIDER",
        "gemini"
    ).strip().lower()

    if provider not in AI_PROVIDERS:

        raise ValueError(
            f"Unknown AI_PROVIDER '{provider}'. "
            f"Use one of: {', '.join(AI_PROVIDERS)}."
        )

    return provider


def save_ai_provider(provider):

    with open(AI_SETTINGS_FILE, "w", encoding="utf-8") as file:

        json.dump(
            {"provider": provider},
            file,
            indent=2
        )


# Current provider. Changed by POST /api/ai/provider.
ai_provider = load_ai_provider()


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
# AI PROVIDERS
# ============================================================

class AIUnavailableError(Exception):

    # No AI model could answer. The message is short and
    # safe to show in the dashboard.

    pass


_gemini_client = None


def gemini_api_key():

    return os.environ.get(
        "GEMINI_API_KEY",
        ""
    ).strip()


def get_gemini_client():

    global _gemini_client

    if _gemini_client is None:

        if not gemini_api_key():

            raise AIUnavailableError(
                "GEMINI_API_KEY is not set. "
                "Set it and restart the app, "
                "or switch the AI to Ollama."
            )

        # No automatic retries: on a busy or out-of-quota
        # model the client would wait up to a minute.
        # first_ai_call moves to the next model instead.

        _gemini_client = OpenAI(
            api_key=gemini_api_key(),
            base_url=GEMINI_BASE_URL,
            max_retries=0,
            timeout=30
        )

    return _gemini_client


def get_ollama_client():

    # Built on use, so the status check and the chat call
    # always talk to the same OLLAMA_HOST.

    return OllamaClient(
        host=OLLAMA_HOST
    )


def gemini_status():

    # Only checks for the key, so the dashboard
    # doesn't use up free quota just by loading.

    if gemini_api_key():

        return {
            "available": True,
            "detail": "API key found"
        }

    return {
        "available": False,
        "detail": "GEMINI_API_KEY is not set"
    }


def ollama_status():

    try:

        response = requests.get(
            f"{OLLAMA_HOST}/api/tags",
            timeout=2
        )

        response.raise_for_status()

        installed = {
            model.get("name")
            for model in response.json().get("models", [])
        }

    except (requests.RequestException, ValueError):

        return {
            "available": False,
            "detail": "Ollama is not running. Open the Ollama app."
        }


    if OLLAMA_MODEL not in installed:

        return {
            "available": False,
            "detail": (
                f"{OLLAMA_MODEL} is not downloaded. "
                f"Run: ollama pull {OLLAMA_MODEL}"
            )
        }

    return {
        "available": True,
        "detail": f"{OLLAMA_MODEL} is ready"
    }


def ai_provider_state():

    statuses = {
        "gemini": gemini_status(),
        "ollama": ollama_status()
    }

    return {

        "provider":
            ai_provider,

        "label":
            AI_PROVIDER_INFO[ai_provider]["label"],

        "description":
            AI_PROVIDER_INFO[ai_provider]["description"],

        "providers": {

            "gemini": {
                **statuses["gemini"],
                "models": GEMINI_MODELS
            },

            "ollama": {
                **statuses["ollama"],
                "model": OLLAMA_MODEL
            },

            "auto": {
                "available": (
                    statuses["gemini"]["available"]
                    or statuses["ollama"]["available"]
                ),
                "detail": "Needs Gemini or Ollama"
            }
        }
    }


def ai_candidates(provider):

    # (provider, model) pairs tried in order for the first
    # AI call. Auto skips Gemini when there is no API key.

    gemini = [
        ("gemini", model)
        for model in GEMINI_MODELS
    ]

    ollama = [
        ("ollama", OLLAMA_MODEL)
    ]

    if provider == "gemini":

        return gemini

    if provider == "ollama":

        return ollama

    if not gemini_api_key():

        return ollama

    return gemini + ollama


def can_try_next_model(provider, error):

    # True when the error means "this model can't answer
    # right now", so trying another model makes sense.

    if provider == "gemini":

        return (
            isinstance(error, APIConnectionError)
            or (
                isinstance(error, APIStatusError)
                and error.status_code in GEMINI_RETRY_STATUS_CODES
            )
        )

    return isinstance(
        error,
        (ConnectionError, ResponseError, httpx.HTTPError)
    )


def describe_ai_error(error):

    if isinstance(error, APIStatusError):

        if error.status_code == 429:

            return "free quota used up"

        if error.status_code == 503:

            return "busy (high demand)"

        return f"error {error.status_code}"

    if isinstance(error, APIConnectionError):

        return "can't reach Google, check the internet"

    if isinstance(error, ConnectionError):

        return "Ollama is not running"

    if isinstance(error, ResponseError):

        return f"Ollama error: {error.error}"

    if isinstance(error, httpx.HTTPError):

        return "Ollama did not respond"

    return str(error)


def ai_chat(
    messages,
    tool_mode,
    provider,
    model
):

    # tool_mode "auto" lets the AI request tools,
    # "none" forces a plain text answer.

    if provider == "gemini":

        # Gemini keeps the tool list on every call so it can
        # read the earlier tool calls in the conversation.

        response = get_gemini_client().chat.completions.create(

            model=model,

            messages=messages,

            tools=AI_TOOLS,

            tool_choice=tool_mode
        )

        return response.choices[0].message


    response = get_ollama_client().chat(

        model=model,

        messages=messages,

        tools=(
            AI_TOOLS
            if tool_mode == "auto"
            else None
        )
    )

    return response.message


def first_ai_call(
    messages,
    provider
):

    # Returns (message, provider used, model used).
    # Moves to the next model when one can't answer. This is
    # safe here because no tool has run yet.

    failures = []

    if provider == "auto" and not gemini_api_key():

        failures.append("Gemini: no API key")


    for candidate_provider, model in ai_candidates(provider):

        try:

            return (
                ai_chat(messages, "auto", candidate_provider, model),
                candidate_provider,
                model
            )

        except Exception as error:

            if not can_try_next_model(candidate_provider, error):

                raise

            reason = describe_ai_error(error)

            print(
                f"AI model {model} unavailable ({reason}), "
                "trying next model..."
            )

            failures.append(
                f"{model}: {reason}"
            )


    hint = {
        "gemini": "Try again later, or switch the AI to Ollama or Auto.",
        "ollama": "Start the Ollama app, or switch the AI to Gemini.",
        "auto": "Check the internet connection and that Ollama is running."
    }[provider]

    raise AIUnavailableError(
        "No AI model could answer ("
        + "; ".join(failures)
        + "). "
        + hint
    )


# ============================================================
# RUN AI COMMAND
# ============================================================

def run_ai_command(
    user_command,
    provider=None
):

    # Read the provider once, so switching it from the
    # dashboard never changes a command halfway through.

    provider = provider or ai_provider

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

    response_message, used_provider, model = first_ai_call(
        messages,
        provider
    )

    print(
        "AI model used:",
        f"{model} ({used_provider})"
    )

    answered_by = {

        "provider":
            used_provider,

        "model":
            model
    }


    # ========================================================
    # NO TOOL REQUIRED
    # ========================================================

    if not response_message.tool_calls:

        return {

            "success":
                True,

            "response":
                response_message.content,

            **answered_by
        }


    # ========================================================
    # ADD AI TOOL REQUEST
    # ========================================================

    if used_provider == "gemini":

        # Send Gemini's message back unchanged, including
        # its thought signature, or the next call fails.

        messages.append(
            response_message.model_dump(
                exclude_none=True
            )
        )

    else:

        messages.append(
            response_message
        )


    # ========================================================
    # EXECUTE EVERY REQUESTED TOOL
    # ========================================================

    tool_results = []

    for tool_call in (
        response_message.tool_calls
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

        tool_results.append({
            "tool": tool_name,
            "result": result
        })


        # ----------------------------------------------------
        # RETURN TOOL RESULT TO AI
        # ----------------------------------------------------

        tool_message = {

            "role":
                "tool",

            "content":
                json.dumps(
                    result,
                    default=str
                )
        }

        if used_provider == "gemini":

            tool_message["tool_call_id"] = (
                tool_call.id
            )

        messages.append(
            tool_message
        )


    # ========================================================
    # SECOND AI CALL
    # ========================================================

    try:

        final_message = ai_chat(
            messages,
            "none",
            used_provider,
            model
        )

    except Exception as error:

        if not can_try_next_model(used_provider, error):

            raise

        # The tools already ran, so don't start over with
        # another model (that would repeat hardware actions).
        # Report the raw tool results instead.

        return {

            "success":
                True,

            "response":
                (
                    "Your command was carried out, but "
                    f"{model} could not write a summary "
                    f"({describe_ai_error(error)}). Results: "
                    + json.dumps(
                        tool_results,
                        default=str
                    )
                ),

            **answered_by
        }


    return {

        "success":
            True,

        "response":
            final_message.content,

        **answered_by
    }


# ============================================================
# MAIN DASHBOARD
# ============================================================

@app.route("/")
def dashboard():

    return render_template(
        "dashboard.html",
        ai_provider=ai_provider,
        ai_provider_info=AI_PROVIDER_INFO
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


    except AIUnavailableError as e:

        print(
            "AI UNAVAILABLE:",
            str(e)
        )


        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 503


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
# AI PROVIDER API
# ============================================================

@app.route(
    "/api/ai/provider",
    methods=["GET"]
)
def get_ai_provider():

    return jsonify(
        ai_provider_state()
    )


@app.route(
    "/api/ai/provider",
    methods=["POST"]
)
def set_ai_provider():

    global ai_provider

    data = request.get_json(
        silent=True
    ) or {}

    provider = str(
        data.get("provider", "")
    ).strip().lower()


    if provider not in AI_PROVIDERS:

        return jsonify({

            "success":
                False,

            "error":
                f"Unknown provider. Use one of: {', '.join(AI_PROVIDERS)}."

        }), 400


    # Refuse a switch that would make every command fail.

    state = ai_provider_state()

    target = state["providers"][provider]

    if not target["available"]:

        return jsonify({

            "success":
                False,

            "error":
                (
                    f"Can't switch to {AI_PROVIDER_INFO[provider]['name']}: "
                    + (
                        target["detail"]
                        if provider != "auto"
                        else "neither Gemini nor Ollama is available"
                    )
                ),

            **state

        }), 409


    ai_provider = provider

    try:

        save_ai_provider(provider)

    except OSError as e:

        # Still switched for this run; only saving failed.

        print(
            "Could not save AI provider:",
            str(e)
        )


    print(
        "AI provider switched to:",
        provider
    )

    return jsonify({

        "success":
            True,

        **ai_provider_state()
    })


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
        "AI provider:",
        AI_PROVIDER_INFO[ai_provider]["label"],
        "(switch it from the dashboard)"
    )

    print(
        "Gemini models:",
        GEMINI_MODELS,
        "| Ollama model:",
        OLLAMA_MODEL
    )

    if (
        ai_provider == "gemini"
        and not gemini_api_key()
    ):

        print(
            "WARNING: GEMINI_API_KEY is not set. "
            "AI commands will fail until it is."
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