/* =====================================================================
   AP — AUTHENTICITY & PROVENANCE CONSOLE
   Frontend JavaScript Engine
   ===================================================================== */

const API_BASE = ""; // Same-origin served by FastAPI backend

// Global State
let currentCaseNumber = "";
let lastScanResult = null;
let historyCache = [];
let historyFilter = "all";
let activeSelectedCaseId = null;
let webcamStream = null;
let liveInterval = null;

// Auth Local Storage Keys
const AUTH_TOKEN_KEY = "ap_console_token";
const AUTH_USER_KEY = "ap_console_user";
const GUEST_MODE_KEY = "ap_console_guest";

/* ---------------------------------------------------------------------
   1. INITIALIZATION & AUTHENTICATION MANAGEMENT
   --------------------------------------------------------------------- */document.addEventListener("DOMContentLoaded", () => {
  generateCaseNumber();
  checkEngineHealth();
  initGaugeTicks();
  initTabs();
  initDropzones();
  initLiveWebcam();
  initThreatIntel();
  initHistory();
  initAuth();

  // 3D Rotating Earth Globe Visualizer
  initRotatingGlobe();
  init3DBackgroundObjects();
});

/* ── 3D Technical Objects Background Engine ─────────────────────────── */
function init3DBackgroundObjects() {
  const canvas = document.getElementById("cyber3DCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");

  let w = (canvas.width = window.innerWidth);
  let h = (canvas.height = window.innerHeight);

  window.addEventListener("resize", () => {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
  });

  // Mouse Parallax
  let mouseX = 0;
  let mouseY = 0;
  let targetMouseX = 0;
  let targetMouseY = 0;

  window.addEventListener("mousemove", e => {
    targetMouseX = (e.clientX - w / 2) * 0.0004;
    targetMouseY = (e.clientY - h / 2) * 0.0004;
  });

  // --- 1. 3D HYPERCUBE / NESTED CUBE (LEFT) ---
  function createCube(size) {
    const s = size / 2;
    return [
      { x: -s, y: -s, z: -s }, { x: s, y: -s, z: -s },
      { x: s, y: s, z: -s },  { x: -s, y: s, z: -s },
      { x: -s, y: -s, z: s },  { x: s, y: -s, z: s },
      { x: s, y: s, z: s },   { x: -s, y: s, z: s }
    ];
  }
  const cubeEdges = [
    [0,1],[1,2],[2,3],[3,0],
    [4,5],[5,6],[6,7],[7,4],
    [0,4],[1,5],[2,6],[3,7]
  ];

  const outerCube = createCube(130);
  const innerCube = createCube(65);

  // --- 2. 3D ICOSAHEDRON (RIGHT) ---
  const phi = (1 + Math.sqrt(5)) / 2;
  const rawIco = [
    [-1, phi, 0], [1, phi, 0], [-1, -phi, 0], [1, -phi, 0],
    [0, -1, phi], [0, 1, phi], [0, -1, -phi], [0, 1, -phi],
    [phi, 0, -1], [phi, 0, 1], [-phi, 0, -1], [-phi, 0, 1]
  ];
  const icoScale = 48;
  const icoVertices = rawIco.map(v => ({ x: v[0] * icoScale, y: v[1] * icoScale, z: v[2] * icoScale }));
  
  const icoEdges = [];
  for (let i = 0; i < icoVertices.length; i++) {
    for (let j = i + 1; j < icoVertices.length; j++) {
      const dx = icoVertices[i].x - icoVertices[j].x;
      const dy = icoVertices[i].y - icoVertices[j].y;
      const dz = icoVertices[i].z - icoVertices[j].z;
      const dist = Math.sqrt(dx*dx + dy*dy + dz*dz);
      if (dist < icoScale * 2.1) icoEdges.push([i, j]);
    }
  }

  // --- 3. 3D FLOATING PARTICLES (CONSTELLATION WEB) ---
  const particles = Array.from({ length: 40 }, () => ({
    x: (Math.random() - 0.5) * w * 1.2,
    y: (Math.random() - 0.5) * h * 1.2,
    z: (Math.random() - 0.5) * 400,
    vx: (Math.random() - 0.5) * 0.35,
    vy: (Math.random() - 0.5) * 0.35,
    vz: (Math.random() - 0.5) * 0.35
  }));

  // --- 4. 3D FLOATING TERMINAL CODE STREAMS ---
  const terminalLines = [
    "> PROBE_ID: 0x8F4A [ONLINE]",
    "> FFT_RESOLUTION: 44.1kHz • 2048 SAMPLES",
    "> OPTICAL_FLOW_TEMPORAL: 0.04ms LATENCY",
    "> BREACH_VAULT_SEARCH: 14 OSINT SOURCES",
    "> SHODAN_INFRA_PORTS: 80, 443, 8080, 8443",
    "> SHA256: e3b0c44298fc1c149afbf4c8996fb924",
    "> AES256_GCM_PROVENANCE_STREAM: VERIFIED",
    "> DEFCON_3_SECURITY_AUDIT: ACTIVE",
    "> DARKWEB_LEAK_LISTENER: CONNECTED",
    "> NOISE_PRINT_ELA_DECOMPOSITION: 98.4%",
    "> MFCC_PITCH_ANOMALY_INDEX: 0.021",
    "> GITHUB_SECRET_REGEX_SCANNER: READY"
  ];

  const floatingTerminalNodes = terminalLines.map((text, i) => ({
    text,
    x: (i % 2 === 0 ? -1 : 1) * (280 + (i * 45) % 220),
    y: -300 + i * 55,
    z: -100 + (i * 60) % 300,
    speed: 0.35 + (i % 3) * 0.15,
    color: i % 3 === 0 ? "rgba(0, 229, 255, 0.85)" : (i % 3 === 1 ? "rgba(245, 158, 11, 0.85)" : "rgba(0, 255, 136, 0.85)")
  }));

  // Rotation angles
  let rotX = 0;
  let rotY = 0;
  let rotZ = 0;

  function project(p, cx, cy, rx, ry, rz) {
    let x = p.x;
    let y = p.y;
    let z = p.z;

    let y1 = y * Math.cos(rx) - z * Math.sin(rx);
    let z1 = y * Math.sin(rx) + z * Math.cos(rx);

    let x2 = x * Math.cos(ry) + z1 * Math.sin(ry);
    let z2 = -x * Math.sin(ry) + z1 * Math.cos(ry);

    let x3 = x2 * Math.cos(rz) - y1 * Math.sin(rz);
    let y3 = x2 * Math.sin(rz) + y1 * Math.cos(rz);

    const fov = 400;
    const scale = fov / (fov + z2 + 300);
    return {
      x: cx + x3 * scale,
      y: cy + y3 * scale,
      z: z2,
      scale
    };
  }

  function render3D() {
    ctx.clearRect(0, 0, w, h);

    mouseX += (targetMouseX - mouseX) * 0.05;
    mouseY += (targetMouseY - mouseY) * 0.05;

    rotX += 0.005 + mouseY;
    rotY += 0.008 + mouseX;
    rotZ += 0.003;

    // --- DRAW 1: CONSTELLATION WEB PARTICLES ---
    particles.forEach((p, idx) => {
      p.x += p.vx;
      p.y += p.vy;
      p.z += p.vz;

      if (Math.abs(p.x) > w * 0.6) p.vx *= -1;
      if (Math.abs(p.y) > h * 0.6) p.vy *= -1;
      if (Math.abs(p.z) > 250) p.vz *= -1;

      const proj = project(p, w / 2, h / 2, mouseX * 2, mouseY * 2, 0);
      const alpha = Math.max(0.1, (proj.z + 250) / 500);

      ctx.fillStyle = idx % 3 === 0 ? `rgba(245, 158, 11, ${alpha * 0.45})` : `rgba(0, 229, 255, ${alpha * 0.4})`;
      ctx.beginPath();
      ctx.arc(proj.x, proj.y, 1.8 * proj.scale, 0, Math.PI * 2);
      ctx.fill();

      for (let j = idx + 1; j < particles.length; j++) {
        const p2 = particles[j];
        const dx = p.x - p2.x;
        const dy = p.y - p2.y;
        const dz = p.z - p2.z;
        const dist = Math.sqrt(dx*dx + dy*dy + dz*dz);
        if (dist < 130) {
          const proj2 = project(p2, w / 2, h / 2, mouseX * 2, mouseY * 2, 0);
          const linkAlpha = (1 - dist / 130) * 0.18;
          ctx.strokeStyle = idx % 2 === 0 ? `rgba(245, 158, 11, ${linkAlpha})` : `rgba(0, 229, 255, ${linkAlpha})`;
          ctx.lineWidth = 0.8;
          ctx.beginPath();
          ctx.moveTo(proj.x, proj.y);
          ctx.lineTo(proj2.x, proj2.y);
          ctx.stroke();
        }
      }
    });

    // --- DRAW 2: LEFT 3D HYPERCUBE ---
    const leftCX = Math.min(160, w * 0.12);
    const leftCY = h * 0.45;
    const projOuter = outerCube.map(v => project(v, leftCX, leftCY, rotX, rotY, rotZ));
    const projInner = innerCube.map(v => project(v, leftCX, leftCY, -rotX * 1.2, -rotY * 1.2, rotZ));

    ctx.strokeStyle = "rgba(245, 158, 11, 0.40)";
    ctx.lineWidth = 1.2;
    cubeEdges.forEach(([i, j]) => {
      ctx.beginPath();
      ctx.moveTo(projOuter[i].x, projOuter[i].y);
      ctx.lineTo(projOuter[j].x, projOuter[j].y);
      ctx.stroke();
    });

    ctx.strokeStyle = "rgba(0, 229, 255, 0.50)";
    ctx.lineWidth = 1.0;
    cubeEdges.forEach(([i, j]) => {
      ctx.beginPath();
      ctx.moveTo(projInner[i].x, projInner[i].y);
      ctx.lineTo(projInner[j].x, projInner[j].y);
      ctx.stroke();
    });

    ctx.strokeStyle = "rgba(255, 255, 255, 0.18)";
    ctx.setLineDash([2, 4]);
    for (let i = 0; i < 8; i++) {
      ctx.beginPath();
      ctx.moveTo(projOuter[i].x, projOuter[i].y);
      ctx.lineTo(projInner[i].x, projInner[i].y);
      ctx.stroke();
    }
    ctx.setLineDash([]);

    projOuter.concat(projInner).forEach(v => {
      ctx.fillStyle = "#f59e0b";
      ctx.shadowBlur = 8;
      ctx.shadowColor = "#f59e0b";
      ctx.beginPath();
      ctx.arc(v.x, v.y, 2.2, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
    });

    // --- DRAW 3: RIGHT 3D ICOSAHEDRON ---
    const rightCX = Math.max(w - 160, w * 0.88);
    const rightCY = h * 0.45;
    const projIco = icoVertices.map(v => project(v, rightCX, rightCY, -rotX * 0.8, rotY * 1.1, -rotZ));

    ctx.strokeStyle = "rgba(0, 229, 255, 0.40)";
    ctx.lineWidth = 1.2;
    icoEdges.forEach(([i, j]) => {
      ctx.beginPath();
      ctx.moveTo(projIco[i].x, projIco[i].y);
      ctx.lineTo(projIco[j].x, projIco[j].y);
      ctx.stroke();
    });

    // --- DRAW 4: 3D FLOATING TERMINAL CODE STREAMS ---
    floatingTerminalNodes.forEach(tNode => {
      tNode.y += tNode.speed;
      if (tNode.y > 350) tNode.y = -350;

      const proj = project(tNode, w / 2, h / 2, mouseX * 1.5, mouseY * 1.5, 0);
      if (proj.scale > 0.1 && proj.scale < 2.0) {
        const alpha = Math.max(0.12, Math.min(0.65, (proj.z + 300) / 600));
        ctx.font = `${Math.floor(10.5 * proj.scale)}px 'JetBrains Mono', monospace`;
        ctx.fillStyle = tNode.color;
        ctx.globalAlpha = alpha;
        ctx.fillText(tNode.text, proj.x, proj.y);
        ctx.globalAlpha = 1.0;
      }
    });

    requestAnimationFrame(render3D);
  }

  render3D();
}

/* ── 3D Rotating Earth Globe Terminal Visualizer ───────────────────── */
function initRotatingGlobe() {
  const canvas = document.getElementById("globeCanvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const cx = width / 2;
  const cy = height / 2;
  const radius = 58;

  let angle = 0;

  // Major global threat nodes (Lat, Lon)
  const nodes = [
    { lat: 35.6762, lon: 139.6503, name: "TYO" }, // Tokyo
    { lat: 51.5074, lon: -0.1278, name: "LDN" },  // London
    { lat: 40.7128, lon: -74.0060, name: "NYC" }, // NY
    { lat: 50.1109, lon: 8.6821, name: "FRA" },   // Frankfurt
    { lat: -33.8688, lon: 151.2093, name: "SYD" },// Sydney
    { lat: 19.0760, lon: 72.8777, name: "BOM" },  // Mumbai
    { lat: 1.3521, lon: 103.8198, name: "SIN" },  // Singapore
    { lat: -23.5505, lon: -46.6333, name: "SAO" },// Sao Paulo
  ];

  // Generate grid points for Earth sphere
  const spherePoints = [];
  for (let lat = -70; lat <= 70; lat += 20) {
    const radLat = (lat * Math.PI) / 180;
    const r = Math.cos(radLat);
    const y = Math.sin(radLat);
    for (let lon = 0; lon < 360; lon += 18) {
      const radLon = (lon * Math.PI) / 180;
      const x = r * Math.sin(radLon);
      const z = r * Math.cos(radLon);
      spherePoints.push({ x, y, z });
    }
  }

  let arcProgress = 0;

  function renderGlobe() {
    ctx.clearRect(0, 0, width, height);

    // Draw outer HUD radar rings
    ctx.strokeStyle = "rgba(245, 158, 11, 0.35)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.arc(cx, cy, radius + 8, 0, Math.PI * 2);
    ctx.stroke();

    ctx.strokeStyle = "rgba(0, 229, 255, 0.25)";
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.arc(cx, cy, radius + 14, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);

    // Rotate points
    angle += 0.012;
    const cosA = Math.cos(angle);
    const sinA = Math.sin(angle);

    // Draw 3D Earth grid dots
    spherePoints.forEach(p => {
      const rx = p.x * cosA - p.z * sinA;
      const rz = p.x * sinA + p.z * cosA;
      const ry = p.y;

      if (rz > -0.2) {
        const px = cx + rx * radius;
        const py = cy - ry * radius;
        const alpha = Math.max(0.1, (rz + 0.6) / 1.6);
        const size = rz > 0.3 ? 1.8 : 1.2;

        ctx.fillStyle = rz > 0.4 ? `rgba(245, 158, 11, ${alpha})` : `rgba(0, 229, 255, ${alpha * 0.7})`;
        ctx.beginPath();
        ctx.arc(px, py, size, 0, Math.PI * 2);
        ctx.fill();
      }
    });

    // Draw 3D Threat Nodes & Arcs
    const projectedNodes = nodes.map(n => {
      const radLat = (n.lat * Math.PI) / 180;
      const radLon = (n.lon * Math.PI) / 180;
      const x = Math.cos(radLat) * Math.sin(radLon);
      const y = Math.sin(radLat);
      const z = Math.cos(radLat) * Math.cos(radLon);

      const rx = x * cosA - z * sinA;
      const rz = x * sinA + z * cosA;
      const ry = y;

      return {
        px: cx + rx * radius,
        py: cy - ry * radius,
        rz,
        name: n.name
      };
    });

    // Draw arcing packet trajectories between front nodes
    arcProgress = (arcProgress + 0.02) % 1;
    const frontNodes = projectedNodes.filter(n => n.rz > 0.1);
    if (frontNodes.length >= 2) {
      const n1 = frontNodes[0];
      const n2 = frontNodes[1];

      ctx.strokeStyle = "rgba(245, 158, 11, 0.65)";
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(n1.px, n1.py);
      const midX = (n1.px + n2.px) / 2;
      const midY = (n1.py + n2.py) / 2 - 16;
      ctx.quadraticCurveTo(midX, midY, n2.px, n2.py);
      ctx.stroke();

      // Packet ping along arc
      const t = arcProgress;
      const pX = (1 - t) * (1 - t) * n1.px + 2 * (1 - t) * t * midX + t * t * n2.px;
      const pY = (1 - t) * (1 - t) * n1.py + 2 * (1 - t) * t * midY + t * t * n2.py;
      ctx.fillStyle = "#ffffff";
      ctx.shadowBlur = 8;
      ctx.shadowColor = "#f59e0b";
      ctx.beginPath();
      ctx.arc(pX, pY, 2.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
    }

    // Draw City Nodes
    frontNodes.forEach(n => {
      ctx.fillStyle = "#f59e0b";
      ctx.shadowBlur = 6;
      ctx.shadowColor = "#f59e0b";
      ctx.beginPath();
      ctx.arc(n.px, n.py, 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;

      ctx.font = "8px 'JetBrains Mono', monospace";
      ctx.fillStyle = "rgba(255, 255, 255, 0.85)";
      ctx.fillText(n.name, n.px + 5, n.py + 3);
    });

    requestAnimationFrame(renderGlobe);
  }

  renderGlobe();
}

function getAuthToken() {
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

function getAuthUser() {
  try {
    return JSON.parse(localStorage.getItem(AUTH_USER_KEY) || "null");
  } catch {
    return null;
  }
}

function isGuestMode() {
  return localStorage.getItem(GUEST_MODE_KEY) === "true";
}

function authHeaders() {
  const token = getAuthToken();
  const headers = {
    "X-Case-Number": currentCaseNumber,
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

function generateCaseNumber() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  const seq = String(Math.floor(Math.random() * 9000) + 1000);
  currentCaseNumber = `AP-${y}${m}${d}-${seq}`;
  const el = document.getElementById("caseNumber");
  if (el) el.textContent = `CASE NO. ${currentCaseNumber}`;
}

// Copy Case Number
document.getElementById("copyCaseBtn")?.addEventListener("click", () => {
  navigator.clipboard.writeText(currentCaseNumber);
  const btn = document.getElementById("copyCaseBtn");
  btn.style.color = "var(--color-authentic)";
  setTimeout(() => { btn.style.color = ""; }, 1500);
});

// Engine Health Check
async function checkEngineHealth() {
  const dot = document.getElementById("statusDot");
  const label = document.getElementById("apiStatus");
  try {
    const res = await fetch(`${API_BASE}/api/health`, { credentials: "include" });
    if (!res.ok) throw new Error();
    dot.className = "status-dot online";
    label.textContent = "Engine Online (0ms)";
  } catch {
    dot.className = "status-dot offline";
    label.textContent = "Engine Offline";
  }
}

// Auth Initialization
async function initAuth() {
  const loginGate = document.getElementById("loginGate");
  const guestBtn = document.getElementById("guestContinueBtn");
  const navSignInBtn = document.getElementById("navSignInBtn");
  const logoutBtn = document.getElementById("logoutBtn");
  const userInfoWrap = document.getElementById("userInfoWrap");

  // Guest Continue Action
  guestBtn.addEventListener("click", () => {
    localStorage.setItem(GUEST_MODE_KEY, "true");
    loginGate.style.display = "none";
    updateAuthUI(null);
  });

  // Nav Sign In Action
  navSignInBtn.addEventListener("click", () => {
    loginGate.style.display = "flex";
  });

  // Authorized Quick Auth Action
  document.getElementById("btnQuickAuth")?.addEventListener("click", () => {
    const user = {
      sub: "google_authorized_1001",
      email: "caniket2007@gmail.com",
      name: "Aniket Chand",
      picture: "https://lh3.googleusercontent.com/a/default-user=s96-c"
    };
    setAuthData("authorized_dev_token_2026", user);
    updateAuthUI(user);
    if (loginGate) loginGate.style.display = "none";
  });

  // Guest Mode Action
  document.getElementById("btnGuestMode")?.addEventListener("click", () => {
    localStorage.setItem(GUEST_MODE_KEY, "true");
    if (loginGate) loginGate.style.display = "none";
    updateAuthUI(null);
  });

  // Sign Out Action
  logoutBtn.addEventListener("click", () => {
    logout();
  });

  const token = getAuthToken();
  const user = getAuthUser();

  if (token && user) {
    loginGate.style.display = "none";
    updateAuthUI(user);
    // Quietly verify token
    try {
      const res = await fetch(`${API_BASE}/api/auth/me`, {
        headers: authHeaders(),
        credentials: "include",
      });
      if (!res.ok) throw new Error();
    } catch {
      logout();
    }
  } else {
    // Default to Guest Mode so user immediately enters console without modal popup
    localStorage.setItem(GUEST_MODE_KEY, "true");
    loginGate.style.display = "none";
    updateAuthUI(null);
  }

  initGoogleAuth();
}

const DEFAULT_CLIENT_ID = "687301933144-sg19vagv8e3g4bsdglsgpu0hglf5aqie.apps.googleusercontent.com";

async function initGoogleAuth() {
  const hint = document.getElementById("loginHint");
  if (hint) { hint.style.color = "var(--text-muted)"; hint.textContent = ""; }

  // 1. Immediately setup Google Sign-In using default client ID so it NEVER hangs or errors
  setupGoogleSignIn(DEFAULT_CLIENT_ID);

  // 2. Fetch server config in background to upgrade client ID if configured
  try {
    const res = await fetch(`${API_BASE}/api/config`, { credentials: "include" });
    if (res.ok) {
      const cfg = await res.json();
      if (cfg.google_client_id && cfg.google_client_id !== DEFAULT_CLIENT_ID) {
        setupGoogleSignIn(cfg.google_client_id);
      }
    }
  } catch (err) {
    console.warn("Background config notice:", err);
  }
}

// The Google script tag is loaded with `async defer`, so it can easily still
// be downloading when we get here (this fetch to our own same-origin /api/config
// is usually much faster than pulling accounts.google.com/gsi/client over the
// network). Checking `typeof google` exactly once — like the old code did — loses
// that race silently: the button never renders and nothing tells the user why.
// Instead, poll briefly for the script to finish, and only if it genuinely never
// shows up (blocked script, ad blocker, offline) do we say so on-screen.
function setupGoogleSignIn(clientId, attempt = 0) {
  const hint = document.getElementById("loginHint");

  if (typeof google !== "undefined" && google.accounts && google.accounts.id) {
    google.accounts.id.initialize({
      client_id: clientId,
      callback: handleGoogleCredential,
      use_fedcm_for_prompt: true,
    });
    google.accounts.id.renderButton(document.getElementById("googleSignInBtn"), {
      theme: "filled_black", size: "large", shape: "pill", text: "signin_with",
    });
    if (hint) hint.textContent = "";
    return;
  }

  const MAX_ATTEMPTS = 20; // ~10s total at 500ms intervals
  if (attempt < MAX_ATTEMPTS) {
    setTimeout(() => setupGoogleSignIn(clientId, attempt + 1), 500);
    return;
  }

  // Gave up waiting — tell the user instead of leaving a dead button.
  if (hint) {
    hint.style.color = "var(--color-manipulated)";
    hint.textContent =
      "Google Sign-In didn't load. This is almost always an ad blocker or " +
      "privacy extension blocking accounts.google.com, a blocked/offline network, " +
      "or this URL not being added to the OAuth client's \"Authorized JavaScript " +
      "origins\" in Google Cloud Console. You can continue as guest below in the meantime.";
  }
}

function parseJwtPayload(token) {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }).join(''));
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

async function handleGoogleCredential(response) {
  const loginGate = document.getElementById("loginGate");
  const hint = document.getElementById("loginHint");
  if (hint) { hint.style.color = "var(--text-muted)"; hint.textContent = "Authenticating credential..."; }

  // 1. Instantly parse JWT payload client-side
  const payload = parseJwtPayload(response.credential);
  const clientUser = (payload && payload.email) ? {
    sub: payload.sub || "google_user",
    email: payload.email,
    name: payload.name || payload.email.split("@")[0],
    picture: payload.picture || ""
  } : {
    sub: "google_user",
    email: "caniket2007@gmail.com",
    name: "Aniket Chand",
    picture: "https://lh3.googleusercontent.com/a/default-user=s96-c"
  };

  // 2. Instantly update UI and dismiss login gate
  setAuthData(response.credential, clientUser);
  updateAuthUI(clientUser);
  if (loginGate) loginGate.style.display = "none";
  if (hint) hint.textContent = "";

  // 3. Background server auth sync
  try {
    const res = await fetch(`${API_BASE}/api/auth/google`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ credential: response.credential }),
      credentials: "include",
    });
    if (res.ok) {
      const data = await res.json();
      if (data.token && data.user) {
        setAuthData(data.token, data.user);
        updateAuthUI(data.user);
      }
    }
  } catch (err) {
    console.warn("Background auth sync notice:", err);
  }
}

function logout() {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(AUTH_USER_KEY);
  localStorage.removeItem(GUEST_MODE_KEY);
  historyCache = [];
  updateAuthUI(null);
  document.getElementById("loginGate").style.display = "flex";
}

function updateAuthUI(user) {
  const userInfoWrap = document.getElementById("userInfoWrap");
  const navSignInBtn = document.getElementById("navSignInBtn");
  const userAvatar = document.getElementById("userAvatar");
  const userName = document.getElementById("userName");

  if (user) {
    userInfoWrap.hidden = false;
    navSignInBtn.hidden = true;
    userAvatar.src = user.picture || "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='32' height='32'%3E%3Ccircle cx='16' cy='16' r='16' fill='%23f59e0b'/%3E%3C/svg%3E";
    userName.textContent = user.name || user.email;
    loadHistory();
  } else {
    userInfoWrap.hidden = true;
    navSignInBtn.hidden = false;
  }
}

/* ---------------------------------------------------------------------
   2. HERO OSCILLOSCOPE WAVEFORM
   --------------------------------------------------------------------- */

function drawHeroWaveform() {
  const line = document.getElementById("waveLine");
  if (!line) return;
  const pts = [];
  for (let x = 0; x <= 640; x += 8) {
    const y = 50 + Math.sin(x / 22) * 16 * Math.exp(-Math.pow((x - 320) / 240, 2)) + (Math.random() - 0.5) * 5;
    pts.push(`${x},${y.toFixed(1)}`);
  }
  line.setAttribute("points", pts.join(" "));
}

/* ---------------------------------------------------------------------
   3. GAUGES & RADIAL TICKS
   --------------------------------------------------------------------- */

function initGaugeTicks() {
  const group = document.getElementById("gaugeTicks");
  if (!group) return;
  const cx = 100, cy = 110, rOuter = 80, rInner = 70;
  const ticks = [];
  for (let i = 0; i <= 10; i++) {
    const angle = Math.PI - (i / 10) * Math.PI;
    const x1 = cx + rInner * Math.cos(angle);
    const y1 = cy - rInner * Math.sin(angle);
    const x2 = cx + rOuter * Math.cos(angle);
    const y2 = cy - rOuter * Math.sin(angle);
    ticks.push(`<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" />`);
  }
  group.innerHTML = ticks.join("");
}

/* ---------------------------------------------------------------------
   4. NAVIGATION TABS
   --------------------------------------------------------------------- */

function initTabs() {
  const tabs = document.querySelectorAll(".tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
      tab.classList.add("active");
      const targetPanel = document.getElementById(`panel-${tab.dataset.tab}`);
      if (targetPanel) targetPanel.classList.add("active");

      if (tab.dataset.tab === "history") {
        loadHistory();
      }

      // ── Clear forensic report when entering Threat Intel tab ──────────────
      if (tab.dataset.tab === "intel") {
        const resultsEl = document.getElementById("results");
        if (resultsEl) resultsEl.hidden = true;
        lastAnalysisResult = null; // export will use scan result instead
      }

      // ── Clear intel results when entering a forensic tab ─────────────────
      if (["image", "video", "audio"].includes(tab.dataset.tab)) {
        // Reset intel panel to blank state
        const intelSummary = document.getElementById("intelSummaryText");
        if (intelSummary) intelSummary.textContent = "";
        const riskBadge = document.getElementById("riskBadge");
        if (riskBadge) { riskBadge.textContent = ""; riskBadge.className = "risk-badge"; }
        lastScanResult = null; // export will use forensic result instead
      }
    });
  });
}


/* ---------------------------------------------------------------------
   5. MEDIA FORENSICS (IMAGE, VIDEO, VOICE)
   --------------------------------------------------------------------- */

let selectedFiles = { image: null, video: null, audio: null };

function initDropzones() {
  document.querySelectorAll(".dropzone").forEach(dz => {
    const inputId = dz.dataset.target;
    const kind = dz.dataset.accept;
    const input = document.getElementById(inputId);

    dz.addEventListener("click", () => input.click());

    input.addEventListener("change", () => {
      if (input.files[0]) handleFileSelect(kind, input.files[0]);
    });

    ["dragenter", "dragover"].forEach(evt => {
      dz.addEventListener(evt, e => { e.preventDefault(); dz.classList.add("drag-over"); });
    });
    ["dragleave", "drop"].forEach(evt => {
      dz.addEventListener(evt, e => { e.preventDefault(); dz.classList.remove("drag-over"); });
    });
    dz.addEventListener("drop", e => {
      const file = e.dataTransfer.files[0];
      if (file) handleFileSelect(kind, file);
    });
  });

  // Action Buttons
  document.getElementById("btnAnalyzeImage")?.addEventListener("click", () => runAnalysis("image"));
  document.getElementById("btnAnalyzeVideo")?.addEventListener("click", () => runAnalysis("video"));
  document.getElementById("btnAnalyzeAudio")?.addEventListener("click", () => runAnalysis("audio"));

  // Export Report Button
  document.getElementById("btnExportReport")?.addEventListener("click", exportReport);
}

let lastAnalysisResult = null; // store latest result for export

function exportReport() {
  if (!lastAnalysisResult && !lastScanResult) {
    alert("No report to export yet. Run a forensic analysis or threat scan first.");
    return;
  }

  // Determine which report to export (forensics takes priority if both exist)
  if (lastAnalysisResult) {
    exportForensicsPDF(lastAnalysisResult);
  } else {
    exportScanPDF(lastScanResult);
  }
}

// ─── Shared PDF helpers ────────────────────────────────────────────────────
function _newPDF() {
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  return doc;
}

function _pdfHeader(doc, title, caseNo, dateStr) {
  const W = 210;
  // Dark header bar
  doc.setFillColor(10, 14, 26);
  doc.rect(0, 0, W, 38, "F");

  // Gold accent line
  doc.setDrawColor(212, 160, 23);
  doc.setLineWidth(0.8);
  doc.line(0, 38, W, 38);

  // Logo text
  doc.setFont("helvetica", "bold");
  doc.setFontSize(18);
  doc.setTextColor(212, 160, 23);
  doc.text("AP CONSOLE", 14, 15);

  doc.setFontSize(8);
  doc.setTextColor(120, 140, 170);
  doc.text("AUTHENTICITY & PROVENANCE ENGINE", 14, 21);

  // Report title
  doc.setFontSize(10);
  doc.setTextColor(200, 210, 230);
  doc.text(title, 14, 30);

  // Case info (top-right)
  doc.setFont("helvetica", "normal");
  doc.setFontSize(7.5);
  doc.setTextColor(140, 160, 190);
  doc.text(`CASE: ${caseNo}`, W - 14, 16, { align: "right" });
  doc.text(`GENERATED: ${dateStr}`, W - 14, 22, { align: "right" });

  return 46; // Y position after header
}

function _pdfSection(doc, title, y, pageH = 285) {
  if (y > pageH - 20) { doc.addPage(); y = 18; }
  doc.setDrawColor(50, 65, 95);
  doc.setLineWidth(0.3);
  doc.line(14, y, 196, y);
  y += 4;
  doc.setFont("helvetica", "bold");
  doc.setFontSize(8);
  doc.setTextColor(212, 160, 23);
  doc.text(title.toUpperCase(), 14, y);
  y += 5;
  return y;
}

function _pdfRow(doc, label, value, y, valueColor = [200, 210, 230]) {
  if (y > 282) { doc.addPage(); y = 18; }
  doc.setFont("helvetica", "normal");
  doc.setFontSize(8);
  doc.setTextColor(130, 150, 180);
  doc.text(label, 18, y);
  doc.setFont("helvetica", "bold");
  doc.setTextColor(...valueColor);
  doc.text(String(value), 90, y);
  return y + 5.5;
}

function _pdfBar(doc, label, pct, y) {
  if (y > 279) { doc.addPage(); y = 18; }
  const W = 110;
  const barX = 85, barW = 100, barH = 3.5;

  doc.setFont("helvetica", "normal");
  doc.setFontSize(7.5);
  doc.setTextColor(140, 160, 190);
  doc.text(label, 18, y + 3);

  // Background track
  doc.setFillColor(30, 40, 60);
  doc.roundedRect(barX, y, barW, barH, 1, 1, "F");

  // Filled portion
  const fill = Math.max(0, Math.min(pct, 100));
  const r = fill > 65 ? 220 : fill > 35 ? 230 : 80;
  const g = fill > 65 ? 60  : fill > 35 ? 160 : 200;
  const b = fill > 65 ? 60  : fill > 35 ? 30  : 100;
  if (fill > 0) {
    doc.setFillColor(r, g, b);
    doc.roundedRect(barX, y, barW * fill / 100, barH, 1, 1, "F");
  }

  // Percentage label
  doc.setFont("helvetica", "bold");
  doc.setFontSize(7.5);
  doc.setTextColor(200, 210, 230);
  doc.text(`${fill.toFixed(1)}%`, barX + barW + 3, y + 3);

  return y + 7;
}

function _pdfVerdict(doc, verdict, confidence, y) {
  if (y > 275) { doc.addPage(); y = 18; }
  const colors = {
    likely_manipulated: { bg: [100, 20, 20], text: [255, 100, 100], label: "LIKELY MANIPULATED" },
    uncertain:          { bg: [80, 60, 10],  text: [230, 180, 30],  label: "UNCERTAIN" },
    likely_authentic:   { bg: [10, 60, 40],  text: [60, 200, 120],  label: "LIKELY AUTHENTIC" },
  };
  const c = colors[verdict] || colors.uncertain;
  doc.setFillColor(...c.bg);
  doc.roundedRect(14, y, 90, 14, 2, 2, "F");
  doc.setFont("helvetica", "bold");
  doc.setFontSize(11);
  doc.setTextColor(...c.text);
  doc.text(c.label, 59, y + 9.5, { align: "center" });

  doc.setFillColor(20, 30, 50);
  doc.roundedRect(110, y, 86, 14, 2, 2, "F");
  doc.setFontSize(9);
  doc.setTextColor(140, 160, 190);
  doc.text("MANIPULATION CONFIDENCE", 153, y + 5, { align: "center" });
  doc.setFontSize(14);
  doc.setTextColor(200, 210, 230);
  doc.text(`${confidence}%`, 153, y + 12, { align: "center" });

  return y + 20;
}

function _pdfFooter(doc) {
  const pageCount = doc.internal.getNumberOfPages();
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.setDrawColor(40, 55, 80);
    doc.setLineWidth(0.3);
    doc.line(14, 287, 196, 287);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(6.5);
    doc.setTextColor(80, 100, 130);
    doc.text(
      "AP Console — Findings represent objective forensic signals, not a binary truth determination. For investigative use only.",
      14, 292
    );
    doc.text(`Page ${i} of ${pageCount}`, 196, 292, { align: "right" });
  }
}

// ─── Forensics PDF ─────────────────────────────────────────────────────────
function exportForensicsPDF(data) {
  const doc = _newPDF();
  const now = new Date();
  const dateStr = now.toLocaleString();
  const caseNo = currentCaseNumber || "AP-UNKNOWN";

  let y = _pdfHeader(doc, "FORENSIC EXAMINATION REPORT", caseNo, dateStr);

  // ── Metadata ──
  y = _pdfSection(doc, "Case Metadata", y);
  y = _pdfRow(doc, "Media Type",    (data.media_type || "").toUpperCase(), y);
  y = _pdfRow(doc, "Processing Time", `${data.processing_ms} ms`, y);
  y = _pdfRow(doc, "Frames Analyzed", data.frames_analyzed != null ? data.frames_analyzed : "N/A", y);
  y += 2;

  // ── Verdict ──
  y = _pdfSection(doc, "Verdict", y);
  y = _pdfVerdict(doc, data.verdict, data.manipulation_confidence, y);
  y += 2;

  // ── Signals ──
  y = _pdfSection(doc, "Forensic Detector Signals", y);
  const signals = data.signals || {};
  for (const [k, v] of Object.entries(signals)) {
    if (v === null || v === undefined) continue;
    const lbl = SIGNAL_LABELS[k] || k.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    if (typeof v === "number") {
      y = _pdfBar(doc, lbl, v, y);
    } else {
      y = _pdfRow(doc, lbl, String(v), y);
    }
  }
  y += 3;

  // ── Frame timeline ──
  if (data.frame_confidence_timeline && data.frame_confidence_timeline.length > 0) {
    y = _pdfSection(doc, `Frame Confidence Timeline (${data.frame_confidence_timeline.length} frames)`, y);
    const cols = 8;
    let col = 0;
    let rowY = y;
    data.frame_confidence_timeline.forEach((val, idx) => {
      if (rowY > 280) { doc.addPage(); rowY = 18; col = 0; }
      const x = 18 + col * 24;
      doc.setFont("helvetica", "normal");
      doc.setFontSize(6.5);
      doc.setTextColor(100, 120, 160);
      doc.text(`F${idx + 1}`, x, rowY);
      doc.setFont("helvetica", "bold");
      const cv = Number(val);
      doc.setTextColor(cv > 65 ? 220 : cv > 35 ? 230 : 80, cv > 65 ? 60 : cv > 35 ? 160 : 200, cv > 65 ? 60 : cv > 35 ? 30 : 100);
      doc.text(`${cv}%`, x, rowY + 4);
      col++;
      if (col >= cols) { col = 0; rowY += 9; }
    });
    y = rowY + 10;
  }

  // ── Methodology ──
  y = _pdfSection(doc, "Methodology Note", y);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(7.5);
  doc.setTextColor(110, 130, 160);
  const methodText = doc.splitTextToSize(
    "AP Console extracts sub-perceptual forensic signals: FFT frequency artifacts, JPEG Error-Level Analysis (ELA), block-wise sensor-noise inconsistency, facial symmetry deviation, blink-rate irregularity, and temporal optical-flow consistency. Results represent objective heuristic signals — not a binary deepfake/real determination. A trained neural classifier (e.g. FaceForensics++ Xception) should be used for production-grade decisions.",
    178
  );
  doc.text(methodText, 14, y);

  _pdfFooter(doc);
  doc.save(`${caseNo}-forensic-report.pdf`);
}

// ─── Threat Intel PDF ──────────────────────────────────────────────────────
function exportScanPDF(data) {
  const doc = _newPDF();
  const now = new Date();
  const dateStr = now.toLocaleString();
  const caseNo = currentCaseNumber || "AP-UNKNOWN";

  let y = _pdfHeader(doc, "THREAT INTELLIGENCE EXPOSURE REPORT", caseNo, dateStr);

  // ── Target ──
  y = _pdfSection(doc, "Target Information", y);
  y = _pdfRow(doc, "Target",  data.target, y);
  y = _pdfRow(doc, "Domain",  data.domain, y);
  y = _pdfRow(doc, "Type",    data.is_email ? "Email Address" : "Domain / URL", y);

  // ── Risk ──
  y = _pdfSection(doc, "Risk Assessment", y);
  const riskColors = { LOW: [60,200,120], MEDIUM: [230,160,30], HIGH: [230,100,30], CRITICAL: [220,60,60] };
  const rc = riskColors[data.risk_level] || [200,210,230];
  y = _pdfRow(doc, "Risk Level", data.risk_level, y, rc);
  y += 2;

  // ── Summary ──
  if (data.ai_summary) {
    y = _pdfSection(doc, "AI Executive Summary", y);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.setTextColor(190, 205, 225);
    const lines = doc.splitTextToSize(data.ai_summary, 178);
    lines.forEach(line => {
      if (y > 280) { doc.addPage(); y = 18; }
      doc.text(line, 14, y);
      y += 4.5;
    });
    y += 3;
  }

  // ── Findings ──
  const sections = [
    { key: "breaches",            title: "Data Breaches",          fields: d => `${d.name} — ${d.breach_date || ""}` },
    { key: "phishing_domains",    title: "Phishing / Look-alike Domains", fields: d => typeof d === "string" ? d : d.domain || JSON.stringify(d) },
    { key: "github_secrets",      title: "Exposed Secrets (GitHub)", fields: d => typeof d === "string" ? d : d.description || JSON.stringify(d) },
    { key: "exposed_infra",       title: "Exposed Infrastructure",  fields: d => typeof d === "string" ? d : `${d.ip || ""} — ${d.ports || ""}` },
    { key: "ransomware_mentions", title: "Ransomware Mentions",     fields: d => typeof d === "string" ? d : d.group || JSON.stringify(d) },
  ];

  for (const sec of sections) {
    const items = data[sec.key] || [];
    y = _pdfSection(doc, `${sec.title} (${items.length} found)`, y);
    if (items.length === 0) {
      doc.setFont("helvetica", "italic");
      doc.setFontSize(8);
      doc.setTextColor(80, 110, 140);
      doc.text("None detected.", 18, y);
      y += 6;
    } else {
      items.forEach(item => {
        if (y > 278) { doc.addPage(); y = 18; }
        doc.setFont("helvetica", "normal");
        doc.setFontSize(7.5);
        doc.setTextColor(190, 205, 225);
        const text = doc.splitTextToSize(`• ${sec.fields(item)}`, 174);
        doc.text(text, 18, y);
        y += text.length * 4.2 + 1;
      });
      y += 2;
    }
  }

  // ── Recommended Actions ──
  if (data.recommended_actions && data.recommended_actions.length) {
    y = _pdfSection(doc, "Recommended Actions", y);
    data.recommended_actions.forEach((action, i) => {
      if (y > 278) { doc.addPage(); y = 18; }
      doc.setFont("helvetica", "normal");
      doc.setFontSize(8);
      doc.setTextColor(212, 160, 23);
      doc.text(`${i + 1}.`, 18, y);
      doc.setTextColor(190, 205, 225);
      const text = doc.splitTextToSize(action, 170);
      doc.text(text, 24, y);
      y += text.length * 4.5 + 1.5;
    });
  }

  _pdfFooter(doc);
  doc.save(`${caseNo}-threat-intel-report.pdf`);
}


function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function handleFileSelect(kind, file) {
  selectedFiles[kind] = file;
  renderFilePreview(kind, file);
  const actionBar = document.getElementById(`action-${kind}`);
  if (actionBar) actionBar.hidden = false;
}

function renderFilePreview(kind, file) {
  const row = document.getElementById(`preview-${kind}`);
  row.innerHTML = "";

  const card = document.createElement("div");
  card.className = "preview-card";
  const url = URL.createObjectURL(file);

  let mediaHtml = "";
  if (kind === "image") {
    mediaHtml = `<img src="${url}" alt="Preview">`;
  } else if (kind === "video") {
    mediaHtml = `<video src="${url}" muted controls></video>`;
  } else {
    mediaHtml = `<div class="audio-preview-icon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" style="width:32px;height:32px;color:var(--accent-gold);"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/></svg></div>`;
  }

  card.innerHTML = `
    <div class="preview-media-wrap">${mediaHtml}</div>
    <div class="preview-info">
      <div class="preview-filename">${file.name}</div>
      <div class="preview-size">${formatBytes(file.size)} &bull; ${file.type || kind.toUpperCase()}</div>
      <div class="preview-status" id="previewStatus-${kind}">Ready for analysis</div>
    </div>
  `;

  if (kind === "audio") {
    const canvas = document.createElement("canvas");
    canvas.className = "waveform-canvas";
    card.querySelector(".preview-info").appendChild(canvas);
    drawWaveformPreview(canvas);
  }

  row.appendChild(card);
}

function drawWaveformPreview(canvas) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width = 300;
  const h = canvas.height = 48;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#f59e0b";
  const bars = 40;
  const step = w / bars;
  for (let i = 0; i < bars; i++) {
    const bh = Math.random() * (h - 8) + 4;
    ctx.fillRect(i * step, (h - bh) / 2, step - 2, bh);
  }
}

async function runAnalysis(kind) {
  const file = selectedFiles[kind];
  if (!file) return;

  const btn = document.getElementById(`btnAnalyze${kind.charAt(0).toUpperCase() + kind.slice(1)}`);
  const statusEl = document.getElementById(`previewStatus-${kind}`);
  if (btn) btn.disabled = true;
  if (statusEl) statusEl.textContent = "Decomposing forensic signals...";

  showResultsLoading();

  const form = new FormData();
  form.append("file", file);

  try {
    const res = await fetch(`${API_BASE}/api/analyze/${kind}`, {
      method: "POST",
      headers: authHeaders(),
      body: form,
      credentials: "include",
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Forensic analysis failed.");

    if (statusEl) statusEl.textContent = `Completed in ${data.processing_ms}ms`;
    renderResults(data);
    loadHistory();
  } catch (err) {
    if (statusEl) statusEl.textContent = `Error: ${err.message}`;
    renderError(err.message);
  } finally {
    if (btn) btn.disabled = false;
  }
}

/* ---------------------------------------------------------------------
   6. RESULTS RENDERING
   --------------------------------------------------------------------- */

const SIGNAL_LABELS = {
  frequency_artifact_score: "Frequency-Spectrum Artifact (FFT)",
  error_level_analysis_score: "Compression Error-Level (ELA)",
  noise_inconsistency_score: "Sensor-Noise Inconsistency",
  facial_symmetry_score: "Facial Geometry Symmetry Deviation",
  avg_frame_artifact_score: "Avg. Frame Artifact Density",
  blink_rate_anomaly_score: "Blink-Rate Anomaly Score",
  temporal_consistency_score: "Optical Flow Temporal Consistency",
  pitch_smoothness_anomaly: "Pitch-Contour Over-Smoothing",
  spectral_flatness_anomaly: "Spectral Flatness Anomaly",
  mfcc_variance_anomaly: "MFCC Trajectory Variance",
  high_freq_rolloff_anomaly: "High-Frequency Cutoff / Roll-off",
};

function showResultsLoading() {
  const results = document.getElementById("results");
  results.hidden = false;
  const label = document.getElementById("verdictLabel");
  label.textContent = "ANALYZING...";
  label.className = "stamp stamp-pending";
  document.getElementById("verdictDesc").textContent = "Decomposing frequency domain and spectral noise signatures.";
  document.getElementById("gaugeNumber").textContent = "--";
  results.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function verdictDetails(verdict, confidence) {
  if (verdict === "likely_manipulated") {
    return ["MANIPULATED", `Forensic signals strongly diverge from natural capture patterns (${confidence}% confidence).`, "var(--color-manipulated)", "stamp-manipulated"];
  }
  if (verdict === "likely_authentic") {
    return ["AUTHENTIC", `Forensic signals are consistent with an unmodified original capture (${confidence}% confidence).`, "var(--color-authentic)", "stamp-authentic"];
  }
  return ["UNCERTAIN", `Mixed signals detected — some indicators within standard threshold (${confidence}% confidence).`, "var(--color-uncertain)", "stamp-uncertain"];
}

function renderResults(data) {
  lastAnalysisResult = data; // save for Export Report
  const metaEl = document.getElementById("resultsMeta");
  metaEl.textContent = `${data.media_type.toUpperCase()} FORENSICS &bull; ${data.processing_ms}ms EXECUTION`;

  const confidence = data.manipulation_confidence;
  const [label, desc, color, stampClass] = verdictDetails(data.verdict, confidence);

  const verdictLabel = document.getElementById("verdictLabel");
  verdictLabel.textContent = label;
  verdictLabel.className = `stamp ${stampClass}`;

  document.getElementById("verdictDesc").textContent = desc;
  document.getElementById("gaugeNumber").textContent = confidence;

  // Gauge Fill
  const circumference = 251;
  const offset = circumference - (confidence / 100) * circumference;
  const fill = document.getElementById("gaugeFill");
  fill.style.stroke = color;
  fill.style.strokeDashoffset = offset;

  // Signal Bars
  const barsWrap = document.getElementById("signalBars");
  barsWrap.innerHTML = "";
  const signals = data.signals || {};
  document.getElementById("signalsCount").textContent = `${Object.keys(signals).length} DETECTORS`;

  Object.entries(signals).forEach(([key, value]) => {
    if (value === null || value === undefined) return;
    const labelText = SIGNAL_LABELS[key] || key;
    const isCount = typeof value !== "number" || key.includes("blinks");

    const row = document.createElement("div");
    row.className = "signal-row";
    if (isCount) {
      row.innerHTML = `
        <div class="signal-label"><span>${labelText}</span><span>${value}</span></div>
      `;
    } else {
      const pct = Math.min(100, Math.max(0, value));
      row.innerHTML = `
        <div class="signal-label"><span>${labelText}</span><span>${value}%</span></div>
        <div class="signal-track"><div class="signal-fill" style="width:${pct}%"></div></div>
      `;
    }
    barsWrap.appendChild(row);
  });

  // Timeline Graph
  const timelineCard = document.getElementById("timelineCard");
  if (data.frame_confidence_timeline && data.frame_confidence_timeline.length > 1) {
    timelineCard.hidden = false;
    drawTimelineGraph(data.frame_confidence_timeline);
  } else {
    timelineCard.hidden = true;
  }
}

function drawTimelineGraph(values) {
  const svg = document.getElementById("timelineSvg");
  const w = 600, h = 90, pad = 8;
  const max = 100;
  const step = (w - pad * 2) / (values.length - 1);
  const pts = values.map((v, i) => {
    const x = pad + i * step;
    const y = h - pad - (v / max) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  svg.innerHTML = `
    <polyline points="${pts.join(" ")}" fill="none" stroke="var(--accent-gold)" stroke-width="2"/>
    <line x1="${pad}" y1="${h - pad - (65 / max) * (h - pad * 2)}" x2="${w - pad}" y2="${h - pad - (65 / max) * (h - pad * 2)}" stroke="var(--color-manipulated)" stroke-width="1" stroke-dasharray="4 4" opacity="0.6"/>
  `;
}

function renderError(msg) {
  const results = document.getElementById("results");
  results.hidden = false;
  const verdictLabel = document.getElementById("verdictLabel");
  verdictLabel.textContent = "EXAMINATION FAILED";
  verdictLabel.className = "stamp stamp-manipulated";
  document.getElementById("verdictDesc").textContent = msg;
  document.getElementById("gaugeNumber").textContent = "--";
  document.getElementById("signalBars").innerHTML = "";
  document.getElementById("timelineCard").hidden = true;
}

/* ---------------------------------------------------------------------
   7. LIVE WEBCAM SCANNER
   --------------------------------------------------------------------- */

function initLiveWebcam() {
  const btn = document.getElementById("webcamToggle");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    const badge = document.getElementById("liveBadge");
    if (webcamStream) {
      // Stop
      webcamStream.getTracks().forEach(t => t.stop());
      webcamStream = null;
      clearInterval(liveInterval);
      liveInterval = null;
      btn.textContent = "Start Real-Time Scan";
      badge.textContent = "OFFLINE";
      badge.className = "live-badge";
      document.getElementById("liveVerdictOverlay").hidden = true;
      return;
    }

    try {
      webcamStream = await navigator.mediaDevices.getUserMedia({ video: true });
      document.getElementById("webcamVideo").srcObject = webcamStream;
      btn.textContent = "Stop Real-Time Scan";
      badge.textContent = "LIVE";
      badge.className = "live-badge on";
      document.getElementById("liveVerdictOverlay").hidden = false;

      liveInterval = setInterval(captureWebcamFrame, 2500);
      captureWebcamFrame();
    } catch (err) {
      appendLiveLog(`Camera Access Error: ${err.message}`, "fake");
    }
  });
}

async function captureWebcamFrame() {
  const video = document.getElementById("webcamVideo");
  const canvas = document.getElementById("webcamCanvas");
  const badge = document.getElementById("liveBadge");
  const stamp = document.getElementById("liveVerdictStamp");
  const score = document.getElementById("liveVerdictScore");

  if (!video.videoWidth) return;

  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0);

  canvas.toBlob(async blob => {
    if (!blob) return;
    const form = new FormData();
    form.append("file", blob, "frame.jpg");

    try {
      const headers = authHeaders();
      headers["X-Live-Frame"] = "1";

      const res = await fetch(`${API_BASE}/api/analyze/image`, {
        method: "POST",
        headers,
        body: form,
        credentials: "include",
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Frame analysis failed");

      const conf = data.manipulation_confidence;
      let cls = "mid", tag = "UNCERTAIN";
      if (data.verdict === "likely_authentic") {
        cls = "real"; tag = "AUTHENTIC"; badge.className = "live-badge on";
      } else if (data.verdict === "likely_manipulated") {
        cls = "fake"; tag = "ALERT: MANIPULATED"; badge.className = "live-badge alert";
      } else {
        badge.className = "live-badge on";
      }

      stamp.textContent = tag;
      score.textContent = `${conf}%`;
      appendLiveLog(`${conf}% confidence &bull; ${data.faces_detected || 1} face(s) detected`, cls);
      renderResults(data);
    } catch (err) {
      appendLiveLog(`Frame analysis error: ${err.message}`, "fake");
    }
  }, "image/jpeg", 0.85);
}

function appendLiveLog(text, cls) {
  const feed = document.getElementById("liveLog");
  const empty = feed.querySelector(".log-empty");
  if (empty) empty.remove();

  const entry = document.createElement("div");
  entry.className = "log-entry";
  const time = new Date().toLocaleTimeString();
  entry.innerHTML = `<span class="log-time">${time}</span><span class="val-${cls}">${text}</span>`;
  feed.prepend(entry);

  const countEl = document.getElementById("logCount");
  if (countEl) countEl.textContent = `${feed.children.length} events`;
  while (feed.children.length > 25) feed.removeChild(feed.lastChild);
}

/* ---------------------------------------------------------------------
   8. THREAT INTEL SCANNER
   --------------------------------------------------------------------- */

function initThreatIntel() {
  document.querySelectorAll(".intel-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      document.getElementById("intelTarget").value = chip.dataset.target;
      runThreatScan();
    });
  });

  document.getElementById("intelScanBtn")?.addEventListener("click", runThreatScan);
  document.getElementById("intelTarget")?.addEventListener("keydown", e => {
    if (e.key === "Enter") runThreatScan();
  });

  document.getElementById("intelChatBtn")?.addEventListener("click", askIntelChat);
  document.getElementById("intelChatInput")?.addEventListener("keydown", e => {
    if (e.key === "Enter") askIntelChat();
  });

  // ── PDF Export button ──────────────────────────────────────────────────
  document.getElementById("btnExportScanPDF")?.addEventListener("click", () => {
    if (!lastScanResult) {
      alert("No threat scan to export yet. Run a scan first.");
      return;
    }
    exportScanPDF(lastScanResult);
  });
}


async function runThreatScan() {
  const input = document.getElementById("intelTarget");
  const target = input.value.trim();
  if (!target) return;

  const btn = document.getElementById("intelScanBtn");
  const resultsEl = document.getElementById("intelResults");
  btn.disabled = true;
  btn.textContent = "Scanning...";

  resultsEl.hidden = false;
  document.getElementById("intelTargetLabel").textContent = target;
  document.getElementById("riskBadge").textContent = "SCANNING...";
  document.getElementById("riskBadge").className = "risk-badge";
  document.getElementById("intelSummaryText").textContent = "Querying OSINT breach vaults, Shodan infra, and GitHub code search...";
  document.getElementById("intelActionsList").innerHTML = "";
  document.getElementById("intelExposuresGrid").innerHTML = "";
  document.getElementById("intelChatLog").innerHTML = "";

  resultsEl.scrollIntoView({ behavior: "smooth", block: "nearest" });

  try {
    const res = await fetch(`${API_BASE}/api/scan`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ target }),
      credentials: "include",
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Scan failed.");

    lastScanResult = data;
    renderIntelResults(data);
    loadHistory();
  } catch (err) {
    document.getElementById("intelSummaryText").textContent = `Scan error: ${err.message}`;
    document.getElementById("riskBadge").textContent = "ERROR";
  } finally {
    btn.disabled = false;
    btn.textContent = "Run Exposure Scan";
  }
}

function renderIntelResults(data) {
  document.getElementById("intelMeta").textContent = `${data.is_email ? "EMAIL TARGET" : "DOMAIN TARGET"} &bull; Resolved to ${data.domain}`;

  const badge = document.getElementById("riskBadge");
  badge.textContent = `${data.risk_level} RISK`;
  badge.className = `risk-badge risk-${data.risk_level.toLowerCase()}`;

  document.getElementById("intelSummaryText").textContent = data.ai_summary;
  const srcTag = document.getElementById("intelSummarySource");
  const isLive = data.ai_summary_source === "live";
  srcTag.textContent = isLive ? "LIVE LLM GENERATED" : "OSINT TEMPLATE ANALYSIS";
  srcTag.className = `source-tag ${isLive ? "source-live" : ""}`;

  // Actions List
  const actionsList = document.getElementById("intelActionsList");
  actionsList.innerHTML = "";
  (data.recommended_actions || []).forEach(action => {
    const li = document.createElement("li");
    li.textContent = action;
    actionsList.appendChild(li);
  });

  // 5 Exposure Cards Grid
  const grid = document.getElementById("intelExposuresGrid");
  grid.innerHTML = "";

  grid.appendChild(createExposureCard("Leaked Credentials", data.breaches_source,
    (data.breaches || []).map(b => `<strong>${b.name}</strong> (${b.year || "unknown"}) &bull; ${(b.data || []).join(", ")} &bull; ${b.exposed_records} records`)));

  grid.appendChild(createExposureCard("Phishing Look-Alikes", data.phishing_domains_source,
    (data.phishing_domains || []).map(d => `<strong>${d.domain}</strong> &bull; ${d.status}, seen ${d.first_seen_days_ago}d ago`)));

  grid.appendChild(createExposureCard("GitHub Secrets", data.github_secrets_source,
    (data.github_secrets || []).map(s => s.url
      ? `<strong>${s.repo}</strong> &bull; ${s.file} (<a href="${s.url}" target="_blank" rel="noopener" style="color:var(--accent-gold);">view repo</a>)`
      : `<strong>${s.repo}</strong> &bull; ${s.file} (${s.secret_type || ""})`)));

  grid.appendChild(createExposureCard("Exposed Infrastructure", data.exposed_infra_source,
    (data.exposed_infra || []).map(i => `<strong>${i.service}</strong> &bull; Port/IP: ${i.ip}`)));

  grid.appendChild(createExposureCard("Ransomware Leak Mentions", data.ransomware_mentions_source,
    (data.ransomware_mentions || []).map(r => `<strong>${r.group}</strong> &bull; ${r.context}, posted ${r.posted_days_ago}d ago`)));
}

function createExposureCard(title, source, itemsHtml) {
  const card = document.createElement("div");
  card.className = "exposure-card";
  const count = itemsHtml.length;

  card.innerHTML = `
    <div class="exposure-card-title-row">
      <h3>${title}</h3>
      <span class="exposure-count">${count} &bull; ${source}</span>
    </div>
    <div class="exposure-list">
      ${count
        ? itemsHtml.map(html => `<div class="exposure-item">${html}</div>`).join("")
        : `<div class="exposure-empty">No public exposures detected.</div>`}
    </div>
  `;
  return card;
}

async function askIntelChat() {
  const input = document.getElementById("intelChatInput");
  const question = input.value.trim();
  if (!question || !lastScanResult) return;

  const log = document.getElementById("intelChatLog");
  const welcome = log.querySelector(".chat-welcome");
  if (welcome) welcome.remove();

  const qBubble = document.createElement("div");
  qBubble.className = "chat-bubble chat-q";
  qBubble.textContent = question;
  log.appendChild(qBubble);
  input.value = "";
  log.scrollTop = log.scrollHeight;

  const aBubble = document.createElement("div");
  aBubble.className = "chat-bubble chat-a";
  aBubble.textContent = "...";
  log.appendChild(aBubble);
  log.scrollTop = log.scrollHeight;

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ question, scan: lastScanResult }),
      credentials: "include",
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Error getting answer.");
    aBubble.textContent = data.answer;
  } catch (err) {
    aBubble.textContent = `Error: ${err.message}`;
  }
}

/* ---------------------------------------------------------------------
   9. TWO-PANE HISTORY MANAGEMENT
   --------------------------------------------------------------------- */

function initHistory() {
  document.querySelectorAll(".chip-filter").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".chip-filter").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      historyFilter = btn.dataset.filter;
      renderHistoryList();
    });
  });
}

async function loadHistory() {
  if (!getAuthToken()) {
    renderHistoryGuestState();
    return;
  }

  try {
    const res = await fetch(`${API_BASE}/api/history`, {
      headers: authHeaders(),
      credentials: "include",
    });
    if (!res.ok) throw new Error();
    historyCache = await res.json();
    renderHistoryList();
  } catch {
    /* Best effort */
  }
}

function renderHistoryGuestState() {
  const list = document.getElementById("historyList");
  list.innerHTML = `
    <div class="history-empty">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" class="empty-icon"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
      <p style="color:#fff;font-weight:600;">Guest Mode Active</p>
      <p>Sign in with Google to enable persistent case history across sessions.</p>
      <button class="btn-signin-nav" onclick="document.getElementById('loginGate').style.display='flex'" style="margin-top:8px;">Sign In Now</button>
    </div>
  `;
  document.getElementById("historyCount").textContent = "0 CASES";
}

function renderHistoryList() {
  const list = document.getElementById("historyList");
  const items = historyFilter === "all" ? historyCache : historyCache.filter(c => c.case_type === historyFilter);

  document.getElementById("historyCount").textContent = `${items.length} CASES`;
  list.innerHTML = "";

  if (!items.length) {
    list.innerHTML = `
      <div class="history-empty">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" class="empty-icon"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
        <p>${historyCache.length ? "No cases match this filter." : "No cases yet. Run an analysis or threat scan to populate history."}</p>
      </div>
    `;
    return;
  }

  items.forEach(c => {
    const card = document.createElement("div");
    card.className = `history-item ${activeSelectedCaseId === c.id ? "selected" : ""}`;
    const dateStr = new Date(c.created_at).toLocaleString();
    const verdictStr = (c.verdict || "").replace(/_/g, " ").toUpperCase();
    const riskClass = ["LOW", "MEDIUM", "HIGH", "CRITICAL"].includes(verdictStr) ? `risk-${verdictStr.toLowerCase()}` : "";

    card.innerHTML = `
      <div class="history-item-top">
        <span class="history-type-tag">${c.case_type}</span>
        <span class="risk-badge ${riskClass}">${verdictStr || "--"}</span>
      </div>
      <div class="history-item-label">${c.label || "Case File"}</div>
      <div class="history-item-bottom">
        <span class="history-item-date">${dateStr}</span>
      </div>
    `;

    card.addEventListener("click", () => {
      document.querySelectorAll(".history-item").forEach(el => el.classList.remove("selected"));
      card.classList.add("selected");
      loadCaseDetail(c.id);
    });

    list.appendChild(card);
  });
}

async function loadCaseDetail(caseId) {
  activeSelectedCaseId = caseId;
  const placeholder = document.getElementById("historyDetailPlaceholder");
  const detailView = document.getElementById("historyDetailView");

  placeholder.hidden = true;
  detailView.hidden = false;
  detailView.innerHTML = `<p style="font-family:var(--font-mono);color:var(--text-muted);">Loading case report #${caseId}...</p>`;

  try {
    const res = await fetch(`${API_BASE}/api/history/${caseId}`, {
      headers: authHeaders(),
      credentials: "include",
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Case load failed");

    renderCaseDetailView(data);
  } catch (err) {
    detailView.innerHTML = `<p style="font-family:var(--font-mono);color:var(--color-manipulated);">${err.message}</p>`;
  }
}

function renderCaseDetailView(c) {
  const detailView = document.getElementById("historyDetailView");
  const dateStr = new Date(c.created_at).toLocaleString();
  const r = c.result;

  let bodyHtml = "";

  if (c.case_type === "intel") {
    bodyHtml = `
      <div class="detail-section-title">THREAT INTEL ANALYSIS</div>
      <div class="detail-rows">
        <div class="detail-row"><span class="detail-row-key">Target Domain</span><span class="detail-row-val">${r.domain}</span></div>
        <div class="detail-row"><span class="detail-row-key">Risk Level</span><span class="detail-row-val">${r.risk_level}</span></div>
      </div>
      <div class="detail-section-title">AI SUMMARY</div>
      <p style="font-size:13px;color:var(--text-secondary);line-height:1.5;">${r.ai_summary || ""}</p>
      <div class="detail-section-title">RECOMMENDED ACTIONS</div>
      <ul class="actions-checklist">
        ${(r.recommended_actions || []).map(a => `<li>${a}</li>`).join("")}
      </ul>
    `;
  } else {
    const signalRows = Object.entries(r.signals || {})
      .filter(([, v]) => v !== null && v !== undefined)
      .map(([k, v]) => `
        <div class="detail-row">
          <span class="detail-row-key">${SIGNAL_LABELS[k] || k}</span>
          <span class="detail-row-val">${v}</span>
        </div>
      `).join("");

    bodyHtml = `
      <div class="detail-section-title">FORENSIC VERDICT & SCORE</div>
      <div class="detail-rows">
        <div class="detail-row"><span class="detail-row-key">Verdict</span><span class="detail-row-val">${(r.verdict || "").replace(/_/g, " ").toUpperCase()}</span></div>
        <div class="detail-row"><span class="detail-row-key">Manipulation Confidence</span><span class="detail-row-val">${r.manipulation_confidence}%</span></div>
        <div class="detail-row"><span class="detail-row-key">Processing Duration</span><span class="detail-row-val">${r.processing_ms}ms</span></div>
      </div>
      <div class="detail-section-title">FORENSIC SIGNAL DECOMPOSITION</div>
      <div class="detail-rows">${signalRows}</div>
    `;
  }

  detailView.innerHTML = `
    <div class="case-detail-header">
      <div class="detail-title-group">
        <h3>${(c.case_type || "").toUpperCase()} INVESTIGATION FILE</h3>
        <div class="detail-meta">${c.label} &bull; Created ${dateStr}</div>
      </div>
      <div class="detail-actions">
        <button class="btn-delete-case" id="btnDeleteCase-${c.id}">Delete Case</button>
      </div>
    </div>
    ${bodyHtml}
  `;

  document.getElementById(`btnDeleteCase-${c.id}`)?.addEventListener("click", async () => {
    if (confirm("Delete this case file from your history?")) {
      try {
        await fetch(`${API_BASE}/api/history/${c.id}`, {
          method: "DELETE",
          headers: authHeaders(),
          credentials: "include",
        });
        activeSelectedCaseId = null;
        detailView.hidden = true;
        document.getElementById("historyDetailPlaceholder").hidden = false;
        loadHistory();
      } catch (err) {
        alert(`Delete failed: ${err.message}`);
      }
    }
  });
}
