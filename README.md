# ESP32-EdgeHub

ESP32-EdgeHub is a local Flask dashboard and AI-assisted control app for an ESP32 running compatible EdgeHub firmware. The Phase 8.7 application uses Qwen3 4B through Ollama and supports GPIO, PWM, ADC, OTA firmware uploads, telemetry, and a unified hardware-state view.

## What is included

- `app.py` — Flask application, dashboard/API routes, Ollama integration, and OTA upload interface.
- `ai_tools.py` — ESP32 HTTP helpers, telemetry access, hardware-state reporting, and GPIO/PWM/ADC tools.
- `templates/` and `static/` — dashboard, OTA page, and styles.
- `test_*.py` — existing manual connectivity and tool-check scripts.
- `config.example.ps1` — example for setting your ESP32 IP for the current PowerShell session.
- `firmware/sketch_oct6a/sketch_oct6a.ino` — ESP32 firmware source with Phase 8.7 and OTA endpoints.

The source project folder did not contain ESP32 firmware source. The app expects compatible firmware to already be installed on the board. Firmware endpoints and supported features must match the firmware build you use.

## Requirements

- Windows, macOS, or Linux with Python 3.10 or newer
- An ESP32 running compatible EdgeHub firmware on the same network as the computer
- [Ollama](https://ollama.com/) installed and running locally
- The `qwen3:4b` model available in Ollama

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

4. Download the model in Ollama:

   ```powershell
   ollama pull qwen3:4b
   ```

5. Set the board's current IP address. The example defaults to `192.168.1.50`; replace that with the address shown by your router or ESP32 serial output:

   ```powershell
   $env:ESP32_IP = "192.168.1.50"
   ```

   You can also edit and dot-source `config.example.ps1` after replacing its example address. The setting applies to the current terminal session.

6. Start the app:

   ```powershell
   python app.py
   ```

7. Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

The Flask app creates `telemetry.db` locally when it starts. That runtime database is intentionally excluded from Git.

## Features

- Dashboard status and telemetry history
- AI-assisted commands through Qwen3 4B/Ollama
- Safe-listed digital GPIO read and write, including multi-pin writes
- PWM output and ADC1 reads for supported pins
- Phase 8.7 unified hardware-state reporting
- OTA firmware upload page for compatible firmware
- Local health, status, history, and hardware-state APIs

Supported pins and firmware endpoints are defined in the source. Confirm the board wiring and firmware behavior before controlling hardware.

## Configuration and privacy

`ESP32_IP` is read from the environment. Do not commit your real Wi-Fi credentials, API keys, private IP details, or machine-specific settings. Keep local settings in your terminal session or a private local file. The app talks to Ollama locally and to the ESP32 over your LAN.

The included `.gitignore` excludes virtual environments, local environment files, databases, Python caches, logs, and build artifacts.

## Firmware setup

Open `firmware/sketch_oct6a/sketch_oct6a.ino` with the Arduino IDE or another ESP32-compatible build tool. Set your local Wi-Fi SSID and password in the sketch, select the matching ESP32 board and port, then compile and upload. The source includes the Phase 8.7 hardware-state and OTA routes used by the Flask app.

## GitHub upload

After extracting the ZIP, review the files and upload the project folder to a new GitHub repository. For command-line Git:

```powershell
git init
git add .
git commit -m "Add ESP32-EdgeHub Phase 8.7"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

Replace the remote URL with your repository URL. Never push `.env` files, Wi-Fi passwords, API keys, or local databases.

