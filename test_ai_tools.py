from ollama import chat
from ai_tools import get_device_status, set_gpio


def run_ai_command(user_command):

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_device_status",
                "description": "Get the current status of the ESP32 EdgeHub device.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "set_gpio",
                "description": "Turn GPIO 2 on or off. Only GPIO 2 is allowed.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pin": {
                            "type": "integer",
                            "enum": [2]
                        },
                        "state": {
                            "type": "string",
                            "enum": ["on", "off"]
                        }
                    },
                    "required": ["pin", "state"]
                }
            }
        }
    ]

    messages = [
        {
            "role": "system",
            "content": (
                "You are the ESP32 EdgeHub AI controller. "
                "You can only control GPIO 2 and read ESP32 status. "
                "Never invent device information. "
                "Use the available tools when device information or "
                "GPIO control is required."
            )
        },
        {
            "role": "user",
            "content": user_command
        }
    ]

    # ========================================================
    # FIRST AI REQUEST
    # ========================================================

    try:

        response = chat(
            model="qwen3:4b",
            messages=messages,
            tools=tools
        )

    except Exception as e:

        print()
        print("AI SERVICE ERROR")
        print("----------------------------------------")
        print("Ollama is currently unavailable.")
        print("Please make sure Ollama is running.")
        print(f"Error: {e}")
        print("----------------------------------------")

        return

    # ========================================================
    # CHECK WHETHER AI REQUESTED A TOOL
    # ========================================================

    if response.message.tool_calls:

        for tool_call in response.message.tool_calls:

            name = tool_call.function.name
            arguments = tool_call.function.arguments

            print()
            print("AI requested tool:")
            print("Tool:", name)
            print("Arguments:", arguments)

            # ------------------------------------------------
            # GET DEVICE STATUS
            # ------------------------------------------------

            if name == "get_device_status":

                result = get_device_status()

            # ------------------------------------------------
            # SET GPIO
            # ------------------------------------------------

            elif name == "set_gpio":

                result = set_gpio(
                    arguments["pin"],
                    arguments["state"]
                )

            # ------------------------------------------------
            # UNKNOWN TOOL
            # ------------------------------------------------

            else:

                result = {
                    "success": False,
                    "error": "Unknown tool"
                }

            print()
            print("Tool result:")
            print(result)

            # ------------------------------------------------
            # SEND TOOL RESULT BACK TO AI
            # ------------------------------------------------

            messages.append(response.message)

            messages.append({
                "role": "tool",
                "content": str(result)
            })

        # ====================================================
        # SECOND AI REQUEST
        # Generate final natural-language response
        # ====================================================

        try:

            final_response = chat(
                model="qwen3:4b",
                messages=messages
            )

        except Exception as e:

            print()
            print("AI SERVICE ERROR")
            print("----------------------------------------")
            print("Ollama stopped responding while generating")
            print("the final response.")
            print(f"Error: {e}")
            print("----------------------------------------")

            return

        print()
        print("AI:")
        print(final_response.message.content)

    # ========================================================
    # NO TOOL REQUIRED
    # ========================================================

    else:

        print()
        print("AI:")
        print(response.message.content)


# ============================================================
# PROGRAM START
# ============================================================

print("========================================")
print("ESP32 EdgeHub AI Tool Test")
print("========================================")

command = input("\nEnter your command: ")

run_ai_command(command)