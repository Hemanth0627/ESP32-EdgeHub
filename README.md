# ESP32-EdgeHub

ESP32-EdgeHub is a local Flask dashboard and AI-assisted control app for an ESP32 running compatible EdgeHub firmware. You can control the board in plain English through Google Gemini (free tier) or a local Qwen3 4B model in Ollama, and switch between them on the dashboard at any time. It supports GPIO, PWM, ADC, OTA firmware uploads, telemetry and a unified hardware-state view. The dashboard has a live 3D model of the board.

## What is included

- `app.py` — Flask application, dashboard/API routes, Gemini and Ollama integration with a runtime provider switch, and OTA upload interface.
- `ai_tools.py` — ESP32 HTTP helpers, telemetry access, hardware-state reporting, and GPIO/PWM/ADC tools.
- `templates/` and `static/` — 3D dashboard (Three.js), OTA page, styles and scripts.
- `test_*.py` — manual connectivity and tool-check scripts (`test_gemini.py` checks the Gemini setup).
- `config.example.ps1` — example for setting your ESP32 IP and optional AI settings for the current PowerShell session.
- `firmware/sketch_oct6a/sketch_oct6a.ino` — ESP32 firmware source with Phase and OTA endpoints.

Flash the included firmware (or a compatible build) to the board. Firmware endpoints and supported features must match the firmware build you use.

## Requirements

- Windows, macOS, or Linux with Python 3.10 or newer
- An ESP32 running compatible EdgeHub firmware on the same network as the computer
- At least one AI provider:
  - **Gemini:** a free API key from [Google AI Studio](https://aistudio.google.com), and an internet connection
  - **Ollama:** [Ollama](https://ollama.com/) installed and running locally, with the `qwen3:4b` model
- Internet access in the browser for the dashboard's 3D view, chart and fonts (the rest of the dashboard works without it)

## Setup

1. Clone or extract this project and open a terminal in the `ESP32-EdgeHub` folder.
2. Create and activate a Python virtual environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   On macOS/Linux, use `python3 -m venv .venv` and `source .venv/bin/activate`.

3. Install the Python packages:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Set up one or both AI providers.

   **Gemini:** create a free API key in Google AI Studio and save it as a user environment variable named `GEMINI_API_KEY` (on Windows: Start → "Edit environment variables for your account" → New). Restart your terminal afterwards. Never put the key in the code.

   **Ollama:** download the model:

   ```powershell
   ollama pull qwen3:4b
   ```

5. Set the board's current IP address. The example defaults to `192.168.1.50`; replace that with the address shown by your router or ESP32 serial output:

   ```powershell
   $env:ESP32_IP = "192.168.1.50"
   ```

   You can also edit and dot-source `config.example.ps1` after replacing its example address. The setting applies to the current terminal session. To keep it, save `ESP32_IP` as a user environment variable the same way as the Gemini key.

6. Start the app:

   ```powershell
   python app.py
   ```

7. Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

The Flask app creates `telemetry.db` locally when it starts. That runtime database is intentionally excluded from Git.

## Choosing the AI provider

The **AI EdgeHub Control** panel has a switch with three options:

- **Gemini** — Google's Gemini API (free tier). If the main model is busy or out of free quota, the app tries the next free model automatically.
- **Ollama** — the local `qwen3:4b` model. Works offline, but slower.
- **Auto** — Gemini first, then local Ollama when no Gemini model can answer.

Green and red dots show which options are available right now. Your choice is saved in `ai_settings.json` (not committed), so it stays after a restart. Each answer shows which model replied and how long it took.

Optional environment variables: `AI_PROVIDER` (starting choice before you pick one on the dashboard), `GEMINI_MODEL`, `OLLAMA_MODEL` and `OLLAMA_HOST`.

## Features

- 3D dashboard: live ESP32 model that mirrors GPIO 2 (click its LED to toggle) and shows Wi-Fi signal waves, plus tilt cards and live metrics
- Dashboard status and telemetry history
- AI-assisted commands through Gemini or Qwen3 4B/Ollama, switchable at runtime
- Safe-listed digital GPIO read and write, including multi-pin writes
- PWM output and ADC1 reads for supported pins
- Phase unified hardware-state reporting
- OTA firmware upload page for compatible firmware
- Local health, status, history, hardware-state and AI-provider APIs

Supported pins and firmware endpoints are defined in the source. Confirm the board wiring and firmware behavior before controlling hardware.

## Configuration and privacy

`ESP32_IP` and `GEMINI_API_KEY` are read from the environment. Do not commit your real Wi-Fi credentials, API keys, private IP details, or machine-specific settings. Keep local settings in your terminal session, your user environment variables, or a private local file. Never push `.env` files, Wi-Fi passwords, API keys, or local databases.

With Ollama, AI commands stay on your computer. With Gemini, your commands and the board's status are sent to Google; on the free tier Google may use them to improve its products. The app talks to the ESP32 over your LAN.

The included `.gitignore` excludes virtual environments, local environment files, databases, `ai_settings.json`, local backup copies, Python caches, logs, and build artifacts.

## Firmware setup

Open `firmware/sketch_oct6a/sketch_oct6a.ino` with the Arduino IDE or another ESP32-compatible build tool. Set your local Wi-Fi SSID and password in the sketch, select the matching ESP32 board and port, then compile and upload.
