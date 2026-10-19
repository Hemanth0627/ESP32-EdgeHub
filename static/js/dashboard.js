// ============================================================
// ESP32 EDGEHUB — DASHBOARD LOGIC
// Data loading, AI panel, provider switch and 3D UI effects.
// The 3D board itself lives in esp32-scene.js and talks to
// this file through window events:
//   "edgehub:status"      this file -> scene (latest device state)
//   "edgehub:toggle-gpio" scene -> this file (LED clicked)
// ============================================================

const PROVIDERS = ["gemini", "ollama", "auto"];

const ESP32_TOTAL_HEAP = 327680; // ~320 KB usable on a classic ESP32

const prefersReducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
).matches;

let wifiChart = null;

let lastOnline = null;

let lastGpio2 = null;

let currentProvider =
    document.getElementById("providerSwitch").dataset.provider;

let providerBusy = false;


// ============================================================
// HELPERS
// ============================================================

function $(id) {

    return document.getElementById(id);

}


function escapeHtml(text) {

    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");

}


// Escape, then allow **bold** (local models like Markdown).
function formatAIText(text) {

    return escapeHtml(text || "")
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

}


function formatUptime(seconds) {

    if (seconds === null || seconds === undefined) {
        return "--";
    }

    seconds = Number(seconds);

    const days = Math.floor(seconds / 86400);
    seconds %= 86400;

    const hours = Math.floor(seconds / 3600);
    seconds %= 3600;

    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);

    return `${days}d ${hours}h ${minutes}m ${secs}s`;

}


// Smoothly counts a number from its previous value to the new one.
function animateNumber(element, to, format) {

    const from = Number(element.dataset.value);

    element.dataset.value = to;

    if (prefersReducedMotion || Number.isNaN(from) || from === to) {
        element.textContent = format(to);
        return;
    }

    const start = performance.now();
    const duration = 600;

    function step(now) {

        const t = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - t, 3);

        element.textContent = format(from + (to - from) * eased);

        if (t < 1) {
            requestAnimationFrame(step);
        }

    }

    requestAnimationFrame(step);

}


// ============================================================
// SYSTEM LOG
// ============================================================

function addLog(message) {

    const log = $("systemLog");

    const entry = document.createElement("div");

    entry.className = "log-entry";

    const time = document.createElement("span");
    time.className = "log-time";
    time.textContent = new Date().toLocaleTimeString();

    entry.append(time, document.createTextNode(message));

    log.appendChild(entry);

    // Keep the log light: last 200 lines only.
    while (log.children.length > 200) {
        log.firstChild.remove();
    }

    log.scrollTop = log.scrollHeight;

}


// ============================================================
// CONNECTION + 3D SCENE STATE
// ============================================================

function setConnection(online) {

    const pill = $("connPill");

    pill.classList.toggle("is-online", online);
    pill.classList.toggle("is-offline", !online);

    $("connText").textContent = online ? "ESP32 online" : "ESP32 offline";

    // Only log changes, not every 3-second poll.
    if (online !== lastOnline) {

        addLog(
            online
                ? "ESP32 connected."
                : "ESP32 is offline or unreachable."
        );

        lastOnline = online;

    }

}


function publishStatus(detail) {

    window.__edgehubStatus = detail;

    window.dispatchEvent(
        new CustomEvent("edgehub:status", { detail })
    );

}


function rssiQuality(rssi) {

    // 0-4 bars, from typical Wi-Fi RSSI ranges.
    if (rssi >= -55) return 4;
    if (rssi >= -67) return 3;
    if (rssi >= -75) return 2;
    if (rssi >= -85) return 1;
    return 0;

}


function setSignalBars(bars) {

    document
        .querySelectorAll("#signalBars i")
        .forEach((bar, index) => bar.classList.toggle("on", index < bars));

}


function setGpioVisual(isOn) {

    $("ledOrb").classList.toggle("is-on", isOn === true);

    $("gpioControlStatus").textContent =
        isOn === null ? "GPIO 2: --" : `GPIO 2: ${isOn ? "ON" : "OFF"}`;

}


// ============================================================
// LOAD STATUS
// ============================================================

async function loadStatus() {

    try {

        const response = await fetch("/api/status");

        const data = await response.json();

        if (!response.ok || data.status === "offline") {
            throw new Error(data.error || "ESP32 is offline");
        }


        // ---- metrics ----

        const status = $("deviceStatus");
        status.textContent = "ONLINE";
        status.className = "metric-value depth tone-good";

        $("deviceStatusFoot").textContent = "Polling every 3 s";

        const health = $("deviceHealth");
        health.textContent = data.health || "UNKNOWN";
        health.className = "metric-value depth " + (
            data.health === "GOOD" ? "tone-good"
                : data.health === "WARNING" ? "tone-warn"
                    : "tone-bad"
        );

        animateNumber($("wifiSignal"), Number(data.rssi), v => `${Math.round(v)} dBm`);

        const bars = rssiQuality(Number(data.rssi));
        setSignalBars(bars);
        $("wifiFoot").textContent =
            ["No signal", "Weak", "Fair", "Good", "Excellent"][bars] + " signal";

        animateNumber($("freeHeap"), Number(data.free_heap) / 1024, v => `${v.toFixed(1)} KB`);

        $("heapMeter").style.width =
            Math.min(100, (Number(data.free_heap) / ESP32_TOTAL_HEAP) * 100) + "%";


        // ---- device information ----

        $("deviceName").textContent = data.device || "ESP32 EdgeHub";
        $("ipAddress").textContent = data.ip || "--";
        $("wifiNetwork").textContent = data.ssid || "--";
        $("uptime").textContent = formatUptime(data.uptime);
        $("gpioState").textContent = data.gpio2 ? "ON" : "OFF";
        $("firmware").textContent = data.firmware || "--";

        setGpioVisual(Boolean(data.gpio2));
        lastGpio2 = Boolean(data.gpio2);


        // ---- health ----

        updateHealth(data.health, data.alerts || []);

        setConnection(true);

        publishStatus({
            online: true,
            gpio2: Boolean(data.gpio2),
            rssi: Number(data.rssi),
            health: data.health
        });

    }

    catch (error) {

        const status = $("deviceStatus");
        status.textContent = "OFFLINE";
        status.className = "metric-value depth tone-bad";

        $("deviceStatusFoot").textContent = "Retrying every 3 s";

        const health = $("deviceHealth");
        health.textContent = "CRITICAL";
        health.className = "metric-value depth tone-bad";

        $("wifiSignal").textContent = "--";
        $("wifiSignal").dataset.value = "";
        $("wifiFoot").textContent = "No connection";
        setSignalBars(0);

        $("freeHeap").textContent = "--";
        $("freeHeap").dataset.value = "";
        $("heapMeter").style.width = "0%";

        setGpioVisual(null);
        lastGpio2 = null;

        updateHealth("CRITICAL", ["ESP32 is offline or unreachable."], "ESP32 OFFLINE");

        setConnection(false);

        publishStatus({
            online: false,
            gpio2: false,
            rssi: null,
            health: "CRITICAL"
        });

    }

}


// ============================================================
// HEALTH
// ============================================================

function updateHealth(health, alerts, label) {

    const healthBox = $("healthBox");

    let className = "health-good";

    if (health === "WARNING") {
        className = "health-warning";
    }

    if (health === "CRITICAL") {
        className = "health-critical";
    }

    healthBox.dataset.health = health;

    healthBox.innerHTML = `
        <div class="health-orb"></div>
        <div>
            <div class="health-label ${className}">${escapeHtml(label || health)}</div>
            <div class="health-sub">${alerts.length} active alert${alerts.length === 1 ? "" : "s"}</div>
        </div>
    `;

    const alertsBox = $("alerts");

    if (alerts.length === 0) {

        alertsBox.innerHTML = `<div class="alert is-calm">No active alerts.</div>`;

        return;

    }

    alertsBox.innerHTML = alerts
        .map(alert => `<div class="alert">${escapeHtml(alert)}</div>`)
        .join("");

}


// ============================================================
// GPIO CONTROL
// ============================================================

async function controlGPIO(action) {

    try {

        const response = await fetch(`/api/gpio/2/${action}`);

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "GPIO operation failed");
        }

        const state = action === "on" ? "ON" : "OFF";

        setGpioVisual(action === "on");

        addLog(`GPIO 2 turned ${state}.`);

        await loadStatus();

    }

    catch (error) {

        addLog("GPIO error: " + error.message);

    }

}


// The blue LED on the 3D board was clicked.
window.addEventListener("edgehub:toggle-gpio", () => {

    if (lastOnline === false) {
        addLog("Can't toggle GPIO 2: the ESP32 is offline.");
        return;
    }

    controlGPIO(lastGpio2 ? "off" : "on");

});


// ============================================================
// WI-FI HISTORY CHART
// ============================================================

async function loadHistory() {

    try {

        const response = await fetch("/api/history");

        const history = await response.json();

        updateChart(history);

    }

    catch (error) {

        addLog("History loading failed.");

    }

}


function updateChart(history) {

    const canvas = $("wifiChart");

    if (!canvas || typeof Chart === "undefined") {
        return;
    }

    const labels = history.map(
        item => new Date(item.timestamp).toLocaleTimeString()
    );

    const values = history.map(item => item.rssi);

    // Update in place so the chart doesn't flash every refresh.
    if (wifiChart) {

        wifiChart.data.labels = labels;
        wifiChart.data.datasets[0].data = values;
        wifiChart.update("none");

        return;

    }

    const context = canvas.getContext("2d");

    const fill = context.createLinearGradient(0, 0, 0, 320);
    fill.addColorStop(0, "rgba(34, 211, 238, 0.35)");
    fill.addColorStop(1, "rgba(139, 92, 246, 0)");

    Chart.defaults.color = "#8f98bd";
    Chart.defaults.font.family = "Inter, Segoe UI, sans-serif";

    wifiChart = new Chart(canvas, {

        type: "line",

        data: {
            labels: labels,
            datasets: [
                {
                    label: "Wi-Fi RSSI (dBm)",
                    data: values,
                    tension: 0.35,
                    fill: true,
                    backgroundColor: fill,
                    borderColor: "#22d3ee",
                    borderWidth: 2,
                    pointRadius: 0,
                    pointHoverRadius: 5,
                    pointHoverBackgroundColor: "#22d3ee"
                }
            ]
        },

        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: "index",
                intersect: false
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: "rgba(5, 8, 22, 0.92)",
                    borderColor: "rgba(148, 163, 255, 0.3)",
                    borderWidth: 1,
                    padding: 10
                }
            },
            scales: {
                x: {
                    grid: {
                        color: "rgba(148, 163, 255, 0.06)"
                    },
                    ticks: {
                        maxTicksLimit: 8
                    }
                },
                y: {
                    grid: {
                        color: "rgba(148, 163, 255, 0.08)"
                    },
                    title: {
                        display: true,
                        text: "RSSI (dBm)"
                    }
                }
            }
        }

    });

}


// ============================================================
// AI PROVIDER SWITCH
// ============================================================

function setProviderUI(state) {

    currentProvider = state.provider;

    const switcher = $("providerSwitch");

    switcher.dataset.provider = state.provider;
    switcher.style.setProperty("--index", PROVIDERS.indexOf(state.provider));

    switcher.querySelectorAll(".provider-option").forEach(option => {

        const selected = option.dataset.provider === state.provider;

        option.setAttribute("aria-checked", String(selected));
        option.tabIndex = selected ? 0 : -1;

    });

    $("aiStatus").textContent = state.label;

    $("providerDetail").textContent = state.description;

    // Availability dots + tooltips.
    for (const [key, info] of Object.entries(state.providers || {})) {

        const dot = document.querySelector(`[data-provider-dot="${key}"]`);

        if (dot) {
            dot.dataset.available = String(info.available);
        }

        const option = switcher.querySelector(`[data-provider="${key}"]`);

        if (option) {
            option.title = info.available
                ? info.detail
                : `Unavailable: ${info.detail}`;
        }

    }

}


async function loadProviderState() {

    try {

        const response = await fetch("/api/ai/provider");

        if (response.ok) {
            setProviderUI(await response.json());
        }

    }

    catch (error) {
        // The panel keeps the server-rendered state.
    }

}


async function switchProvider(provider) {

    if (providerBusy || provider === currentProvider) {
        return;
    }

    providerBusy = true;

    const switcher = $("providerSwitch");
    const previous = currentProvider;

    // Move the thumb right away; roll back if the server refuses.
    switcher.style.setProperty("--index", PROVIDERS.indexOf(provider));
    switcher.querySelectorAll(".provider-option").forEach(option => option.disabled = true);
    $("providerDetail").textContent = "Switching…";

    try {

        const response = await fetch("/api/ai/provider", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ provider })
        });

        const data = await response.json();

        if (!response.ok || !data.success) {

            if (data.providers) {
                setProviderUI(data);
            }

            throw new Error(data.error || "Could not switch the AI provider.");

        }

        setProviderUI(data);

        addLog(`AI switched to ${data.label}.`);

    }

    catch (error) {

        switcher.style.setProperty("--index", PROVIDERS.indexOf(previous));

        const detail = $("providerDetail");
        detail.innerHTML = `<span class="ai-error">${escapeHtml(error.message)}</span>`;

        addLog("AI switch failed: " + error.message);

    }

    finally {

        switcher.querySelectorAll(".provider-option").forEach(option => option.disabled = false);

        providerBusy = false;

    }

}


function initProviderSwitch() {

    const switcher = $("providerSwitch");

    switcher.style.setProperty("--index", PROVIDERS.indexOf(currentProvider));

    switcher.addEventListener("click", event => {

        const option = event.target.closest(".provider-option");

        if (option) {
            switchProvider(option.dataset.provider);
        }

    });

    // Arrow keys move between options, like a radio group.
    switcher.addEventListener("keydown", event => {

        const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[event.key];

        if (!step) {
            return;
        }

        event.preventDefault();

        const next = PROVIDERS[
            (PROVIDERS.indexOf(currentProvider) + step + PROVIDERS.length) % PROVIDERS.length
        ];

        switcher.querySelector(`[data-provider="${next}"]`).focus();

        switchProvider(next);

    });

    loadProviderState();

    // Keep the availability dots fresh (e.g. Ollama started later).
    setInterval(loadProviderState, 30000);

    window.addEventListener("focus", loadProviderState);

}


// ============================================================
// AI COMMAND
// ============================================================

function setAICommand(command) {

    const input = $("aiCommand");

    input.value = command;

    input.focus();

}


// Reveals the answer progressively, like it's being typed.
function typeOut(element, html) {

    if (prefersReducedMotion) {
        element.innerHTML = html;
        return;
    }

    const holder = document.createElement("div");
    holder.innerHTML = html;
    const fullText = holder.textContent;

    const duration = Math.min(1200, fullText.length * 12);
    const start = performance.now();

    function step(now) {

        const t = Math.min(1, (now - start) / duration);

        if (t >= 1) {
            element.innerHTML = html;
            return;
        }

        element.textContent = fullText.slice(0, Math.floor(fullText.length * t)) + "▍";

        requestAnimationFrame(step);

    }

    requestAnimationFrame(step);

}


async function sendAICommand() {

    const input = $("aiCommand");
    const button = $("aiSendButton");
    const responseBox = $("aiResponse");
    const meta = $("aiMeta");

    const command = input.value.trim();

    if (!command) {

        responseBox.innerHTML = `<span class="ai-error">Please enter a command.</span>`;

        return;

    }


    // ---- loading ----

    button.disabled = true;
    button.textContent = "THINKING...";
    meta.textContent = "";

    // One line: the response box keeps whitespace (pre-wrap).
    responseBox.innerHTML =
        `<span class="ai-thinking"><span class="thinking-dots"><i></i><i></i><i></i></span>The AI is processing your command...</span>`;

    const started = performance.now();

    try {

        const response = await fetch("/api/ai", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ command })
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
            throw new Error(data.error || "AI request failed.");
        }

        const seconds = ((performance.now() - started) / 1000).toFixed(1);

        typeOut(responseBox, formatAIText(data.response));

        if (data.model) {
            const where = data.provider === "ollama" ? "Ollama (local)" : "Gemini API";
            meta.textContent = `Answered by ${data.model} · ${where} · ${seconds} s`;
        }

        addLog("AI: " + data.response);

        // Refresh actual ESP32 values.
        await loadStatus();
        await loadHistory();

    }

    catch (error) {

        console.error("AI Error:", error);

        responseBox.innerHTML = `<span class="ai-error">AI Error: ${escapeHtml(error.message)}</span>`;

        addLog("AI Error: " + error.message);

    }

    finally {

        button.disabled = false;
        button.textContent = "SEND";

    }

}


$("aiCommand").addEventListener("keydown", event => {

    if (event.key === "Enter") {

        event.preventDefault();

        sendAICommand();

    }

});


// ============================================================
// 3D TILT CARDS
// ============================================================

function initTilt() {

    const canHover = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

    if (!canHover || prefersReducedMotion) {
        return;
    }

    const maxTilt = 8;

    document.querySelectorAll("[data-tilt]").forEach(card => {

        card.addEventListener("pointermove", event => {

            const rect = card.getBoundingClientRect();
            const x = (event.clientX - rect.left) / rect.width;
            const y = (event.clientY - rect.top) / rect.height;

            card.classList.add("is-tilting");
            card.style.setProperty("--ry", `${(x - 0.5) * 2 * maxTilt}deg`);
            card.style.setProperty("--rx", `${(0.5 - y) * 2 * maxTilt}deg`);
            card.style.setProperty("--gx", `${x * 100}%`);
            card.style.setProperty("--gy", `${y * 100}%`);
            card.style.setProperty("--glare", "1");

        });

        card.addEventListener("pointerleave", () => {

            card.classList.remove("is-tilting");
            card.style.setProperty("--rx", "0deg");
            card.style.setProperty("--ry", "0deg");
            card.style.setProperty("--glare", "0");

        });

    });

}


// ============================================================
// SCROLL REVEAL
// ============================================================

function initReveal() {

    const items = document.querySelectorAll(".reveal");

    if (!("IntersectionObserver" in window) || prefersReducedMotion) {
        items.forEach(item => item.classList.add("is-visible"));
        return;
    }

    const observer = new IntersectionObserver(entries => {

        entries.forEach(entry => {

            if (entry.isIntersecting) {
                entry.target.classList.add("is-visible");
                observer.unobserve(entry.target);
            }

        });

    }, { threshold: 0.12 });

    items.forEach((item, index) => {
        item.style.transitionDelay = `${(index % 4) * 70}ms`;
        observer.observe(item);
    });

}


// ============================================================
// 3D SCENE FALLBACK
// ============================================================

// If Three.js can't load (offline, no WebGL), show a message
// in the stage instead of an empty box.
setTimeout(() => {

    if (!window.edgeScene) {
        $("stage").classList.add("no-webgl");
    }

}, 8000);


// ============================================================
// INITIAL LOAD + AUTO REFRESH
// ============================================================

initReveal();
initTilt();
initProviderSwitch();

loadStatus();
loadHistory();

setInterval(loadStatus, 3000);
setInterval(loadHistory, 10000);
