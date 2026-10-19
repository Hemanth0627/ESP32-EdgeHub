// ============================================================
// ESP32 EDGEHUB — 3D BOARD SCENE (Three.js)
// A live 3D model of an ESP32 DevKit in the hero:
//   - blue LED mirrors GPIO 2 (click it to toggle)
//   - Wi-Fi waves from the antenna, stronger with better RSSI
//   - glow turns red when the board is offline
// Gets device state from dashboard.js via "edgehub:status".
// ============================================================

import * as THREE from "three";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";


const stage = document.getElementById("stage");
const canvas = document.getElementById("boardCanvas");

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;


// Board size in scene units (1 unit ≈ 10 mm).
const BOARD_L = 5.6;
const BOARD_W = 2.6;
const BOARD_T = 0.16;
const TOP = BOARD_T / 2;

const PIN_PITCH = 0.259;
const PIN_START_X = -2.35;
const PIN_ROW_Z = 1.1;

const LED_BLUE_POS = new THREE.Vector3(-1.85, TOP + 0.035, -0.28);
const LED_RED_POS = new THREE.Vector3(-1.85, TOP + 0.035, 0.22);
const ANTENNA_POS = new THREE.Vector3(2.45, TOP + 0.1, 0);
const SHIELD_TOP = new THREE.Vector3(1.2, TOP + 0.36, 0.1);

// Pin names from the USB end toward the antenna (30-pin DevKit V1).
const PINS_FRONT = ["VIN", "GND", "D13", "D12", "D14", "D27", "D26", "D25", "D33", "D32", "D35", "D34", "VN", "VP", "EN"];
const PINS_BACK = ["3V3", "GND", "D15", "D2", "D4", "RX2", "TX2", "D5", "D18", "D19", "D21", "RX0", "TX0", "D22", "D23"];

const COLOR_ONLINE = new THREE.Color("#22d3ee");
const COLOR_OFFLINE = new THREE.Color("#f87171");


// ============================================================
// HELPERS
// ============================================================

// Small seeded random generator so the board looks the same every load.
function seededRandom(seed) {

    return function () {
        seed |= 0;
        seed = (seed + 0x6d2b79f5) | 0;
        let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };

}


function makeCanvas(width, height) {

    const element = document.createElement("canvas");
    element.width = width;
    element.height = height;

    return [element, element.getContext("2d")];

}


function canvasTexture(element, renderer) {

    const texture = new THREE.CanvasTexture(element);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = renderer.capabilities.getMaxAnisotropy();

    return texture;

}


function radialTexture(renderer) {

    const [element, ctx] = makeCanvas(256, 256);
    const gradient = ctx.createRadialGradient(128, 128, 0, 128, 128, 128);

    gradient.addColorStop(0, "rgba(255,255,255,1)");
    gradient.addColorStop(0.25, "rgba(255,255,255,0.45)");
    gradient.addColorStop(1, "rgba(255,255,255,0)");

    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 256, 256);

    return canvasTexture(element, renderer);

}


function webglAvailable() {

    try {
        const test = document.createElement("canvas");
        return Boolean(test.getContext("webgl2") || test.getContext("webgl"));
    }
    catch (error) {
        return false;
    }

}


// ============================================================
// PCB TOP TEXTURE — traces, pads and silkscreen
// ============================================================

function pcbTexture(renderer) {

    const width = 2048;
    const height = Math.round(width * (BOARD_W / BOARD_L));
    const [element, ctx] = makeCanvas(width, height);

    const planeL = BOARD_L - 0.12;
    const planeW = BOARD_W - 0.12;

    const toCanvas = (x, z) => [
        ((x + planeL / 2) / planeL) * width,
        ((z + planeW / 2) / planeW) * height
    ];

    const random = seededRandom(32);

    // Solder mask.
    ctx.fillStyle = "#0b1426";
    ctx.fillRect(0, 0, width, height);

    // Copper traces under the mask (dim cyan, 45° routing).
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    for (let i = 0; i < 46; i++) {

        let x = random() * width;
        let y = random() * height;

        ctx.strokeStyle = `rgba(56, 189, 248, ${0.08 + random() * 0.12})`;
        ctx.lineWidth = 3 + random() * 4;
        ctx.beginPath();
        ctx.moveTo(x, y);

        for (let s = 0; s < 4; s++) {

            const length = 60 + random() * 260;
            const direction = Math.floor(random() * 8) * (Math.PI / 4);

            x += Math.cos(direction) * length;
            y += Math.sin(direction) * length;

            ctx.lineTo(x, y);

        }

        ctx.stroke();

        // Via at the end of the trace.
        ctx.fillStyle = "rgba(212, 166, 74, 0.55)";
        ctx.beginPath();
        ctx.arc(x, y, 6, 0, Math.PI * 2);
        ctx.fill();

    }

    // Header pads + pin labels.
    const drawRow = (names, z, labelOffset) => {

        names.forEach((name, index) => {

            const [cx, cy] = toCanvas(PIN_START_X + index * PIN_PITCH, z);

            ctx.fillStyle = "#d4a64a";
            ctx.beginPath();
            ctx.arc(cx, cy, 22, 0, Math.PI * 2);
            ctx.fill();

            ctx.fillStyle = "#0b1426";
            ctx.beginPath();
            ctx.arc(cx, cy, 9, 0, Math.PI * 2);
            ctx.fill();

            ctx.save();
            ctx.translate(cx, cy + labelOffset);
            ctx.rotate(-Math.PI / 2);
            ctx.font = "600 22px Arial";
            ctx.textAlign = labelOffset > 0 ? "right" : "left";
            ctx.textBaseline = "middle";
            ctx.fillStyle = name === "D2" ? "#60a5fa" : "rgba(232, 237, 245, 0.85)";
            ctx.fillText(name, 0, 0);
            ctx.restore();

        });

    };

    drawRow(PINS_FRONT, PIN_ROW_Z, -36);
    drawRow(PINS_BACK, -PIN_ROW_Z, 36);

    // Silkscreen outlines around parts.
    ctx.strokeStyle = "rgba(232, 237, 245, 0.55)";
    ctx.lineWidth = 3;

    const outline = (x, z, w, d) => {
        const [ax, ay] = toCanvas(x - w / 2, z - d / 2);
        const [bx, by] = toCanvas(x + w / 2, z + d / 2);
        ctx.strokeRect(ax, ay, bx - ax, by - ay);
    };

    outline(1.5, 0, 2.7, 1.95);
    outline(-1.6, 0.5, 0.8, 0.5);
    outline(-1.0, -0.25, 0.65, 0.65);

    // Logo text.
    const [logoX, logoY] = toCanvas(-0.85, 0.62);
    ctx.font = "700 46px Arial";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = "rgba(232, 237, 245, 0.9)";
    ctx.fillText("ESP32 EdgeHub", logoX, logoY);

    const [subX, subY] = toCanvas(-0.85, 0.82);
    ctx.font = "500 26px Arial";
    ctx.fillStyle = "rgba(232, 237, 245, 0.6)";
    ctx.fillText("DEVKIT V1 · AI READY", subX, subY);

    // LED labels.
    ctx.font = "600 22px Arial";
    ctx.textAlign = "left";

    const [ledX, ledY] = toCanvas(LED_BLUE_POS.x + 0.14, LED_BLUE_POS.z);
    ctx.fillStyle = "#60a5fa";
    ctx.fillText("IO2", ledX, ledY);

    const [pwrX, pwrY] = toCanvas(LED_RED_POS.x + 0.14, LED_RED_POS.z);
    ctx.fillStyle = "rgba(248, 113, 113, 0.9)";
    ctx.fillText("PWR", pwrX, pwrY);

    return canvasTexture(element, renderer);

}


// ============================================================
// SHIELD (RF CAN) ENGRAVING TEXTURE
// ============================================================

function shieldTexture(renderer) {

    const [element, ctx] = makeCanvas(512, 468);

    ctx.fillStyle = "#c6ccd5";
    ctx.fillRect(0, 0, 512, 468);

    // Brushed metal streaks.
    const random = seededRandom(7);

    for (let i = 0; i < 220; i++) {
        ctx.fillStyle = `rgba(255, 255, 255, ${random() * 0.12})`;
        ctx.fillRect(0, random() * 468, 512, 1);
    }

    ctx.fillStyle = "rgba(38, 44, 56, 0.85)";
    ctx.textAlign = "left";
    ctx.textBaseline = "top";

    ctx.font = "700 46px Arial";
    ctx.fillText("ESP32-WROOM-32", 36, 40);

    ctx.font = "500 26px Arial";
    ctx.fillText("Wi-Fi + BT + BLE MCU", 36, 104);
    ctx.fillText("FCC ID: 2AC7Z-ESPWROOM32", 36, 146);
    ctx.fillText("EdgeHub firmware", 36, 188);

    // QR-style code block.
    const qr = seededRandom(99);
    const size = 12;

    for (let row = 0; row < 12; row++) {
        for (let col = 0; col < 12; col++) {
            if (qr() > 0.5) {
                ctx.fillRect(330 + col * size, 270 + row * size, size, size);
            }
        }
    }

    ctx.strokeStyle = "rgba(38, 44, 56, 0.85)";
    ctx.lineWidth = 4;
    ctx.strokeRect(36, 270, 140, 140);
    ctx.font = "700 30px Arial";
    ctx.fillText("CE", 70, 322);

    return canvasTexture(element, renderer);

}


// ============================================================
// BUILD THE BOARD
// ============================================================

function buildBoard(renderer) {

    const board = new THREE.Group();

    const materials = {

        pcb: new THREE.MeshStandardMaterial({ color: 0x0b1426, roughness: 0.55, metalness: 0.1 }),
        module: new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.5, metalness: 0.2 }),
        metal: new THREE.MeshStandardMaterial({ color: 0xc9ced6, roughness: 0.28, metalness: 1 }),
        gold: new THREE.MeshStandardMaterial({ color: 0xd4a64a, roughness: 0.3, metalness: 1 }),
        black: new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.45, metalness: 0.1 }),
        plastic: new THREE.MeshStandardMaterial({ color: 0x15171c, roughness: 0.7 }),
        antenna: new THREE.MeshStandardMaterial({
            color: 0xd4a64a, roughness: 0.3, metalness: 1,
            emissive: COLOR_ONLINE.clone(), emissiveIntensity: 0
        })
    };

    const add = (geometry, material, x, y, z) => {
        const mesh = new THREE.Mesh(geometry, material);
        mesh.position.set(x, y, z);
        board.add(mesh);
        return mesh;
    };


    // ---- PCB ----

    add(new RoundedBoxGeometry(BOARD_L, BOARD_T, BOARD_W, 4, 0.08), materials.pcb, 0, 0, 0);

    const top = add(
        new THREE.PlaneGeometry(BOARD_L - 0.12, BOARD_W - 0.12),
        new THREE.MeshStandardMaterial({ map: pcbTexture(renderer), roughness: 0.6, metalness: 0.15 }),
        0, TOP + 0.002, 0
    );
    top.rotation.x = -Math.PI / 2;


    // ---- ESP32-WROOM module ----

    add(new THREE.BoxGeometry(2.6, 0.08, 1.84), materials.module, 1.5, TOP + 0.04, 0);

    add(new RoundedBoxGeometry(1.8, 0.26, 1.64, 2, 0.03), materials.metal, 1.2, TOP + 0.21, 0);

    const engraving = add(
        new THREE.PlaneGeometry(1.74, 1.58),
        new THREE.MeshStandardMaterial({ map: shieldTexture(renderer), roughness: 0.32, metalness: 0.9 }),
        1.2, TOP + 0.342, 0
    );
    engraving.rotation.x = -Math.PI / 2;

    // Meandering PCB antenna.
    const traceY = TOP + 0.087;
    const lanes = [2.24, 2.4, 2.56, 2.72];

    lanes.forEach((x, index) => {

        add(new THREE.BoxGeometry(0.045, 0.012, 1.4), materials.antenna, x, traceY, 0);

        if (index < lanes.length - 1) {
            const z = index % 2 === 0 ? 0.68 : -0.68;
            add(new THREE.BoxGeometry(0.2, 0.012, 0.045), materials.antenna, x + 0.08, traceY, z);
        }

    });


    // ---- USB port, buttons, chips ----

    add(new THREE.BoxGeometry(0.55, 0.26, 0.76), materials.metal, -2.68, TOP + 0.13, 0);
    add(new THREE.BoxGeometry(0.06, 0.12, 0.55), materials.black, -2.96, TOP + 0.13, 0);

    for (const z of [0.82, -0.82]) {
        add(new THREE.BoxGeometry(0.42, 0.14, 0.34), materials.metal, -2.45, TOP + 0.07, z);
        add(new THREE.CylinderGeometry(0.09, 0.09, 0.09, 20), materials.black, -2.45, TOP + 0.18, z);
    }

    // AMS1117 regulator (SOT-223).
    add(new THREE.BoxGeometry(0.62, 0.16, 0.34), materials.black, -1.6, TOP + 0.08, 0.5);
    add(new THREE.BoxGeometry(0.62, 0.02, 0.12), materials.metal, -1.6, TOP + 0.01, 0.72);

    // CP2102 USB-UART chip.
    add(new THREE.BoxGeometry(0.5, 0.08, 0.5), materials.black, -1.0, TOP + 0.04, -0.25);


    // ---- small SMD parts (instanced) ----

    const random = seededRandom(5);
    const smd = new THREE.InstancedMesh(
        new THREE.BoxGeometry(0.13, 0.05, 0.07),
        new THREE.MeshStandardMaterial({ roughness: 0.5, metalness: 0.2 }),
        44
    );

    const blocked = [
        [-1.6, 0.5, 0.45, 0.3], [-1.0, -0.25, 0.4, 0.4], [-1.85, -0.03, 0.25, 0.4],
        [-0.85, 0.7, 0.75, 0.22], [-2.45, 0, 0.35, 1.1]
    ];

    const dummy = new THREE.Object3D();
    const smdColors = [new THREE.Color(0x1a1a1a), new THREE.Color(0x8b6b4a), new THREE.Color(0x6b7280)];

    for (let i = 0; i < 44; i++) {

        let x;
        let z;

        do {
            x = -2.2 + random() * 2.2;
            z = -0.82 + random() * 1.25;
        } while (blocked.some(([bx, bz, hw, hd]) => Math.abs(x - bx) < hw && Math.abs(z - bz) < hd));

        dummy.position.set(x, TOP + 0.025, z);
        dummy.rotation.y = random() > 0.5 ? 0 : Math.PI / 2;
        dummy.updateMatrix();

        smd.setMatrixAt(i, dummy.matrix);
        smd.setColorAt(i, smdColors[Math.floor(random() * smdColors.length)]);

    }

    smd.instanceColor.needsUpdate = true;
    board.add(smd);


    // ---- pin headers (under the board) + solder joints ----

    const pinCount = PINS_FRONT.length * 2;
    const pins = new THREE.InstancedMesh(new THREE.BoxGeometry(0.06, 0.9, 0.06), materials.gold, pinCount);
    const joints = new THREE.InstancedMesh(new THREE.CylinderGeometry(0.07, 0.085, 0.05, 14), materials.metal, pinCount);

    let pinIndex = 0;

    for (const z of [PIN_ROW_Z, -PIN_ROW_Z]) {

        const rowCenter = PIN_START_X + ((PINS_FRONT.length - 1) * PIN_PITCH) / 2;

        add(
            new THREE.BoxGeometry(PINS_FRONT.length * PIN_PITCH, 0.25, 0.26),
            materials.plastic,
            rowCenter, -TOP - 0.125, z
        );

        for (let i = 0; i < PINS_FRONT.length; i++) {

            const x = PIN_START_X + i * PIN_PITCH;

            dummy.rotation.set(0, 0, 0);

            dummy.position.set(x, -TOP - 0.45, z);
            dummy.updateMatrix();
            pins.setMatrixAt(pinIndex, dummy.matrix);

            dummy.position.set(x, TOP + 0.025, z);
            dummy.updateMatrix();
            joints.setMatrixAt(pinIndex, dummy.matrix);

            pinIndex++;

        }

    }

    board.add(pins, joints);


    // ---- LEDs ----

    const glowMap = radialTexture(renderer);

    const makeLed = (position, color) => {

        const material = new THREE.MeshStandardMaterial({
            color: color.clone().multiplyScalar(0.35),
            emissive: color.clone(),
            emissiveIntensity: 0,
            roughness: 0.3
        });

        const body = add(new THREE.BoxGeometry(0.16, 0.07, 0.1), material, position.x, position.y, position.z);

        const glow = new THREE.Sprite(new THREE.SpriteMaterial({
            map: glowMap,
            color: color,
            blending: THREE.AdditiveBlending,
            transparent: true,
            depthWrite: false,
            opacity: 0
        }));
        glow.position.copy(position).add(new THREE.Vector3(0, 0.06, 0));
        glow.scale.setScalar(1);
        board.add(glow);

        const light = new THREE.PointLight(color, 0, 2.2, 2);
        light.position.copy(position).add(new THREE.Vector3(0, 0.25, 0));
        board.add(light);

        return { body, material, glow, light, level: 0 };

    };

    const blueLed = makeLed(LED_BLUE_POS, new THREE.Color("#3b82f6"));
    const redLed = makeLed(LED_RED_POS, new THREE.Color("#ef4444"));

    // Bigger invisible box so the small LED is easy to click.
    const ledHitBox = add(
        new THREE.BoxGeometry(0.55, 0.45, 0.4),
        new THREE.MeshBasicMaterial({ visible: false }),
        LED_BLUE_POS.x, LED_BLUE_POS.y + 0.1, LED_BLUE_POS.z
    );


    // ---- Wi-Fi waves from the antenna ----

    const waves = [];

    for (let i = 0; i < 3; i++) {

        const wave = new THREE.Mesh(
            new THREE.RingGeometry(0.92, 1, 96),
            new THREE.MeshBasicMaterial({
                color: COLOR_ONLINE,
                transparent: true,
                opacity: 0,
                blending: THREE.AdditiveBlending,
                depthWrite: false,
                side: THREE.DoubleSide
            })
        );

        wave.rotation.x = -Math.PI / 2;
        wave.position.copy(ANTENNA_POS);
        board.add(wave);
        waves.push(wave);

    }

    return { board, blueLed, redLed, ledHitBox, waves, antenna: materials.antenna };

}


// ============================================================
// SCENE DRESSING — pedestal rings, floor glow, particles
// ============================================================

function buildEnvironment(scene, renderer) {

    const glowMap = radialTexture(renderer);

    const floorGlow = new THREE.Mesh(
        new THREE.PlaneGeometry(11, 11),
        new THREE.MeshBasicMaterial({
            map: glowMap,
            color: COLOR_ONLINE.clone(),
            transparent: true,
            opacity: 0.45,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        })
    );
    floorGlow.rotation.x = -Math.PI / 2;
    floorGlow.position.y = -1.32;
    scene.add(floorGlow);

    const rings = new THREE.Group();
    rings.position.y = -1.3;

    [[3.4, 0x22d3ee, 0.5], [3.95, 0x8b5cf6, 0.35], [4.5, 0x3b82f6, 0.18]].forEach(([radius, color, opacity], index) => {

        const ring = new THREE.Mesh(
            new THREE.RingGeometry(radius, radius + 0.03, 160, 1, 0, Math.PI * (index === 1 ? 1.6 : 2)),
            new THREE.MeshBasicMaterial({
                color,
                transparent: true,
                opacity,
                blending: THREE.AdditiveBlending,
                depthWrite: false,
                side: THREE.DoubleSide
            })
        );

        ring.rotation.x = -Math.PI / 2;
        rings.add(ring);

    });

    scene.add(rings);

    // Floating particles around the board.
    const count = 420;
    const positions = new Float32Array(count * 3);
    const random = seededRandom(11);

    for (let i = 0; i < count; i++) {

        const radius = 4.5 + random() * 5;
        const theta = random() * Math.PI * 2;
        const phi = Math.acos(2 * random() - 1);

        positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
        positions[i * 3 + 1] = radius * Math.cos(phi) * 0.6;
        positions[i * 3 + 2] = radius * Math.sin(phi) * Math.sin(theta);

    }

    const particleGeometry = new THREE.BufferGeometry();
    particleGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));

    const particles = new THREE.Points(
        particleGeometry,
        new THREE.PointsMaterial({
            color: 0x9bdcff,
            size: 0.04,
            transparent: true,
            opacity: 0.75,
            depthWrite: false,
            blending: THREE.AdditiveBlending
        })
    );

    scene.add(particles);

    return { floorGlow, rings, particles };

}


// ============================================================
// MAIN
// ============================================================

function init() {

    const renderer = new THREE.WebGLRenderer({
        canvas,
        antialias: true,
        alpha: true,
        powerPreference: "high-performance"
    });

    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;

    const scene = new THREE.Scene();

    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(renderer), 0.04).texture;

    const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
    const cameraBase = new THREE.Vector3(0, 4.6, 9.6);


    // ---- lights ----

    scene.add(new THREE.HemisphereLight(0x9bdcff, 0x0a0f2a, 0.6));

    const key = new THREE.DirectionalLight(0xffffff, 1.8);
    key.position.set(4, 7, 5);
    scene.add(key);

    const rim = new THREE.PointLight(0x8b5cf6, 40, 20, 2);
    rim.position.set(-5, 2.5, -4);
    scene.add(rim);

    const fill = new THREE.PointLight(0x22d3ee, 25, 20, 2);
    fill.position.set(5, 1, -3);
    scene.add(fill);


    // ---- objects ----

    const model = buildBoard(renderer);
    const pivot = new THREE.Group();
    pivot.add(model.board);
    scene.add(pivot);

    const environment = buildEnvironment(scene, renderer);


    // ---- device state (from dashboard.js) ----

    const state = {
        online: false,
        gpio2: false,
        rssi: null,
        known: false
    };

    const glowColor = COLOR_OFFLINE.clone();

    const hotspots = {
        wifi: document.getElementById("hotspotWifi"),
        led: document.getElementById("hotspotLed"),
        chip: document.getElementById("hotspotChip")
    };

    function applyStatus(detail) {

        if (!detail) {
            return;
        }

        state.online = Boolean(detail.online);
        state.gpio2 = Boolean(detail.gpio2);
        state.rssi = detail.rssi;
        state.known = true;

        const setLabel = (hotspot, text, tone) => {
            hotspot.querySelector(".hotspot-label").textContent = text;
            hotspot.dataset.tone = tone;
        };

        setLabel(
            hotspots.wifi,
            state.online ? `Wi-Fi · ${state.rssi} dBm` : "Wi-Fi · offline",
            state.online ? "" : "bad"
        );

        setLabel(
            hotspots.led,
            state.online ? `GPIO 2 · ${state.gpio2 ? "ON" : "OFF"}` : "GPIO 2 · --",
            state.gpio2 ? "led-on" : "off"
        );

    }

    applyStatus(window.__edgehubStatus);

    window.addEventListener("edgehub:status", event => applyStatus(event.detail));


    // ---- interaction: drag to rotate, click the LED ----

    const rotation = { x: 0, y: -0.55, targetX: 0, targetY: -0.55, velocityY: 0 };
    const pointer = new THREE.Vector2(0, 0);
    const parallax = new THREE.Vector2(0, 0);
    const raycaster = new THREE.Raycaster();

    let dragging = false;
    let dragStart = null;
    let lastPointer = null;
    let lastInteraction = -Infinity;
    let pressedLed = 0;

    function ndcFromEvent(event) {

        const rect = canvas.getBoundingClientRect();

        pointer.set(
            ((event.clientX - rect.left) / rect.width) * 2 - 1,
            -((event.clientY - rect.top) / rect.height) * 2 + 1
        );

        return pointer;

    }

    function ledUnderPointer(event) {

        raycaster.setFromCamera(ndcFromEvent(event), camera);

        return raycaster.intersectObject(model.ledHitBox, false).length > 0;

    }

    canvas.addEventListener("pointerdown", event => {

        dragging = true;
        dragStart = { x: event.clientX, y: event.clientY, time: performance.now() };
        lastPointer = { x: event.clientX, y: event.clientY };
        canvas.classList.add("is-dragging");

        try {
            canvas.setPointerCapture(event.pointerId);
        }
        catch (error) {
            // Capture isn't essential; dragging still works without it.
        }

    });

    canvas.addEventListener("pointermove", event => {

        const rect = canvas.getBoundingClientRect();

        parallax.set(
            ((event.clientX - rect.left) / rect.width) * 2 - 1,
            ((event.clientY - rect.top) / rect.height) * 2 - 1
        );

        if (dragging) {

            const dx = event.clientX - lastPointer.x;
            const dy = event.clientY - lastPointer.y;

            rotation.targetY += dx * 0.008;
            rotation.targetX = THREE.MathUtils.clamp(rotation.targetX + dy * 0.005, -0.45, 0.7);
            rotation.velocityY = dx * 0.008;

            lastPointer = { x: event.clientX, y: event.clientY };
            lastInteraction = performance.now();

            return;

        }

        canvas.classList.toggle("is-hovering-led", ledUnderPointer(event));

    });

    const endDrag = event => {

        if (!dragging) {
            return;
        }

        dragging = false;
        canvas.classList.remove("is-dragging");

        const moved = Math.hypot(event.clientX - dragStart.x, event.clientY - dragStart.y);
        const quick = performance.now() - dragStart.time < 450;

        // A click (not a drag) on the LED toggles GPIO 2.
        if (event.type === "pointerup" && moved < 6 && quick && ledUnderPointer(event)) {

            pressedLed = 1;

            window.dispatchEvent(new CustomEvent("edgehub:toggle-gpio"));

        }

    };

    canvas.addEventListener("pointerup", endDrag);
    canvas.addEventListener("pointercancel", endDrag);

    canvas.addEventListener("pointerleave", () => {
        parallax.set(0, 0);
        canvas.classList.remove("is-hovering-led");
    });


    // ---- sizing ----

    function resize() {

        const width = stage.clientWidth;
        const height = stage.clientHeight;

        renderer.setSize(width, height, false);

        camera.aspect = width / height;

        // Pull the camera back on narrow screens so the board fits.
        const distanceScale = camera.aspect < 1.35 ? 1 + (1.35 - camera.aspect) * 0.85 : 1;
        cameraBase.set(0, 4.6 * distanceScale, 9.6 * distanceScale);

        camera.updateProjectionMatrix();

    }

    new ResizeObserver(resize).observe(stage);
    resize();


    // ---- hotspot labels follow 3D points ----

    const anchors = {
        wifi: ANTENNA_POS.clone().add(new THREE.Vector3(0, 0.15, 0)),
        led: LED_BLUE_POS.clone().add(new THREE.Vector3(0, 0.08, 0)),
        chip: SHIELD_TOP.clone()
    };

    const projected = new THREE.Vector3();

    function placeHotspots(visibility) {

        const width = stage.clientWidth;
        const height = stage.clientHeight;

        for (const [name, anchor] of Object.entries(anchors)) {

            projected.copy(anchor);
            model.board.localToWorld(projected);
            projected.project(camera);

            const x = (projected.x + 1) / 2 * width;
            const y = (1 - projected.y) / 2 * height;

            const label = hotspots[name];
            label.style.transform = `translate(${x}px, ${y}px)`;
            label.style.opacity = String(visibility);

            // Flip a side label to the other side if it would leave the stage.
            const preferred = label.dataset.prefer || (label.dataset.prefer = label.dataset.side);

            if (preferred !== "up") {

                const labelWidth = label.firstElementChild.offsetWidth + 30;

                let side = preferred;

                if (side === "right" && x + labelWidth > width - 8) side = "left";
                if (side === "left" && x - labelWidth < 8) side = "right";

                if (label.dataset.side !== side) {
                    label.dataset.side = side;
                }

            }

        }

    }


    // ---- animation loop ----

    const clock = new THREE.Clock();
    const introStart = performance.now();
    const introDuration = reducedMotion ? 0 : 1600;

    function frame() {

        // getDelta first: getElapsedTime would reset the delta.
        const delta = Math.min(clock.getDelta(), 0.05);
        const time = clock.elapsedTime;

        // Intro: board flies in and settles.
        const introT = introDuration ? Math.min(1, (performance.now() - introStart) / introDuration) : 1;
        const eased = 1 - Math.pow(1 - introT, 3);

        // Idle sway after 2.5 s without dragging.
        const idle = performance.now() - lastInteraction > 2500;

        if (!dragging) {

            rotation.targetY += rotation.velocityY;
            rotation.velocityY *= 0.92;

            if (idle && !reducedMotion) {
                rotation.targetY += ((-0.55 + Math.sin(time * 0.35) * 0.45) - rotation.targetY) * 0.01;
                rotation.targetX += (0 - rotation.targetX) * 0.02;
            }

        }

        rotation.x += (rotation.targetX - rotation.x) * 0.12;
        rotation.y += (rotation.targetY - rotation.y) * 0.12;

        pivot.rotation.x = rotation.x;
        pivot.rotation.y = rotation.y + (1 - eased) * -2.4;
        pivot.scale.setScalar(0.62 + 0.38 * eased);
        model.board.position.y = reducedMotion ? 0 : Math.sin(time * 1.2) * 0.06 - (1 - eased) * 1.2;

        // Camera parallax toward the pointer.
        camera.position.x += (cameraBase.x + parallax.x * 0.7 - camera.position.x) * 0.05;
        camera.position.y += (cameraBase.y - parallax.y * 0.35 - camera.position.y) * 0.05;
        camera.position.z += (cameraBase.z - camera.position.z) * 0.05;
        camera.lookAt(0, -0.1, 0);


        // ---- LEDs ----

        const blueTarget = state.online && state.gpio2 ? 1 : 0;
        const redTarget = state.online ? 1 : 0;

        model.blueLed.level += (blueTarget - model.blueLed.level) * 0.15;
        model.redLed.level += (redTarget - model.redLed.level) * 0.15;

        pressedLed *= 0.9;

        for (const led of [model.blueLed, model.redLed]) {
            led.material.emissiveIntensity = led.level * 4;
            led.glow.material.opacity = led.level * 0.95;
            led.glow.scale.setScalar(0.7 + led.level * 0.5);
            led.light.intensity = led.level * 2.5;
        }

        model.blueLed.glow.scale.multiplyScalar(1 + pressedLed * 0.8);


        // ---- Wi-Fi waves + antenna glow ----

        const strength = state.online && state.rssi !== null
            ? THREE.MathUtils.clamp((state.rssi + 95) / 50, 0.15, 1)
            : 0;

        model.waves.forEach((wave, index) => {

            const phase = (time * (0.35 + strength * 0.35) + index / 3) % 1;

            wave.scale.setScalar(0.25 + phase * 3.2);
            wave.material.opacity = (1 - phase) * 0.6 * strength;

        });

        model.antenna.emissiveIntensity = strength * (0.6 + Math.sin(time * 3) * 0.3);


        // ---- status glow, pedestal, particles ----

        glowColor.lerp(state.online ? COLOR_ONLINE : COLOR_OFFLINE, 0.04);

        environment.floorGlow.material.color.copy(glowColor);
        environment.floorGlow.material.opacity = 0.35 + Math.sin(time * 1.5) * 0.06;

        environment.rings.children[0].material.color.copy(glowColor);

        if (!reducedMotion) {
            environment.rings.rotation.y += delta * 0.15;
            environment.rings.children[1].rotation.z -= delta * 0.3;
            environment.particles.rotation.y += delta * 0.03;
        }

        renderer.render(scene, camera);

        placeHotspots(state.known && introT >= 1 ? 1 : 0);

    }


    // Only render while the stage is on screen and the tab is visible.
    let onScreen = true;

    const updateLoop = () => {
        renderer.setAnimationLoop(onScreen && !document.hidden ? frame : null);
    };

    new IntersectionObserver(entries => {
        onScreen = entries[0].isIntersecting;
        updateLoop();
    }).observe(stage);

    document.addEventListener("visibilitychange", updateLoop);

    updateLoop();

    window.edgeScene = { ready: true };

}


if (webglAvailable()) {

    try {
        init();
    }
    catch (error) {
        console.error("3D scene failed:", error);
        stage.classList.add("no-webgl");
    }

}
else {

    stage.classList.add("no-webgl");

}
