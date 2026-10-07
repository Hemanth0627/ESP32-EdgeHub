# Project phases

This overview follows phase labels and features present in the supplied source and saved snapshots. No separate source snapshot for Phases 8.0–8.2 was found.

## Phase 7 — Basic AI GPIO control

The original AI tool controls GPIO 2 with an `on` or `off` state. It validates the requested pin and state before sending a command to the ESP32.

## Phase 7.5 — Dashboard and telemetry baseline

The Phase 7.5 snapshots show the Flask dashboard and telemetry workflow alongside GPIO 2 control. The app reads ESP32 status, stores telemetry in a local SQLite database, and shows device/network status and history.

## Phase 8.3 — Safe-listed digital GPIO

Digital GPIO read and write support expands beyond GPIO 2. Requested pins are checked against an approved GPIO registry before firmware requests are sent.

## Phase 8.4 — Multiple GPIO writes

A single request can set more than one approved digital GPIO, with pin and state validation still applied.

## Phase 8.5 — ADC input

The app adds analog reads for approved ADC1 pins. Check board-specific voltage limits before wiring sensors.

## Phase 8.6 — PWM output

The app adds PWM output control for approved pins, with validation in the tool implementation.

## Phase 8.7 — Unified hardware state

A read-only operation gathers available device status and GPIO, PWM, and ADC information into one response.

## OTA and firmware

The Flask app includes an OTA upload interface for compatible ESP32 firmware. The supplied project folder contains no firmware source, so firmware endpoints and image format must match firmware provided separately.

The ZIP contains the active app, tools, templates, styles, and manual check scripts. Historical backup copies are omitted because they duplicate earlier implementations.
