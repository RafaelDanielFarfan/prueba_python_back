const API_URL = window.API_URL;

const $ = (testId) => document.querySelector(`[data-testid="${testId}"]`);

const STATUS_MESSAGES = {
  401: "Tu sesión no es válida o ha caducado. Inicia sesión de nuevo.",
  404: "No se encontró el recurso solicitado.",
  503: "El servidor está ocupado calculando. Espera unos segundos y vuelve a intentarlo.",
};

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function showError(message) {
  const element = $("error-message");
  element.textContent = message;
  element.hidden = false;
}

function clearError() {
  const element = $("error-message");
  element.textContent = "";
  element.hidden = true;
}

// En un 422 la API devuelve el motivo en `detail`: texto, o una lista de errores de validación.
function validationMessage(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item) => item.msg).join("; ");
  return "La API rechazó la petición por datos no válidos.";
}

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, options);
  } catch {
    throw new ApiError(0, `No se pudo conectar con la API en ${API_URL}.`);
  }
  if (response.ok) return response;

  let detail;
  try {
    detail = (await response.json()).detail;
  } catch {
    detail = undefined;
  }
  const message =
    response.status === 422
      ? validationMessage(detail)
      : STATUS_MESSAGES[response.status] ?? `La API respondió con el error ${response.status}.`;
  throw new ApiError(response.status, message);
}

const TOKEN_KEY = "panel-token";

const getToken = () => {
  try {
    return sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
};

const setToken = (token) => {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // Sin almacenamiento disponible: la sesión dura lo que dure la página.
  }
};

const state = { functions: [], selectedId: null };

function showLogin() {
  document.getElementById("login-section").hidden = false;
  document.getElementById("panel").hidden = true;
}

function showPanel() {
  document.getElementById("login-section").hidden = true;
  document.getElementById("panel").hidden = false;
}

function signOut() {
  setToken(null);
  state.functions = [];
  state.selectedId = null;
  document.getElementById("function-info").hidden = true;
  document.getElementById("volumes").hidden = true;
  document.getElementById("surface").hidden = true;
  document.getElementById("convergence").hidden = true;
  document.getElementById("select-hint").hidden = false;
  showLogin();
}

// Petición con el token de sesión; un 401 cierra la sesión y deja el motivo en el error.
async function authorized(path) {
  try {
    return await request(path, { headers: { Authorization: `Bearer ${getToken()}` } });
  } catch (error) {
    if (error.status === 401) signOut();
    throw error;
  }
}

function renderFunctionList() {
  const list = $("function-list");
  list.replaceChildren();
  if (state.functions.length === 0) {
    const empty = document.createElement("p");
    empty.className = "muted";
    empty.textContent = "Todavía no tienes funciones registradas.";
    list.append(empty);
    return;
  }
  for (const fn of state.functions) {
    const item = document.createElement("button");
    item.type = "button";
    item.dataset.testid = "function-item";
    item.dataset.id = fn.id;
    item.textContent = fn.name;
    item.setAttribute("aria-pressed", String(fn.id === state.selectedId));
    item.addEventListener("click", () => selectFunction(fn.id));
    list.append(item);
  }
}

function renderFunctionInfo(fn) {
  document.getElementById("select-hint").hidden = true;
  document.getElementById("function-info").hidden = false;
  document.getElementById("function-name").textContent = fn.name;
  const fields = document.getElementById("function-fields");
  fields.replaceChildren();
  const rows = [
    ["Expresión", fn.expression],
    ["Dominio", fn.domain.map(([min, max]) => `[${min}, ${max}]`).join(" × ")],
    ["Resolución", fn.resolution],
  ];
  for (const [label, value] of rows) {
    const term = document.createElement("dt");
    const description = document.createElement("dd");
    term.textContent = label;
    description.textContent = value;
    fields.append(term, description);
  }
}

const VOLUME_CELLS = ["volume-mesh", "volume-voxel", "volume-domain", "volume-difference"];

// Seis cifras significativas: el enunciado exige al menos cuatro.
const formatNumber = (value) => value.toPrecision(6);

function requireFinite(value, label) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`La API devolvió un valor que no es un número finito para ${label}.`);
  }
  return value;
}

// 100 · |malla − vóxeles| / |malla|; sin volumen de malla no hay con qué comparar.
function relativeDifference(mesh, voxel) {
  if (mesh === 0) {
    throw new Error("El volumen por malla es cero: no se puede calcular la diferencia relativa.");
  }
  return (100 * Math.abs(mesh - voxel)) / Math.abs(mesh);
}

function setVolumeCells(texts) {
  VOLUME_CELLS.forEach((testId, index) => {
    $(testId).textContent = texts[index];
  });
}

async function loadVolumes(id) {
  document.getElementById("volumes").hidden = false;
  setVolumeCells(VOLUME_CELLS.map(() => "Calculando…"));
  try {
    const volume = await (await authorized(`/functions/${id}/volume`)).json();
    if (state.selectedId !== id) return;
    const mesh = requireFinite(volume.mesh_volume, "el volumen por malla");
    const voxel = requireFinite(volume.voxel_volume, "el volumen por vóxeles");
    const domain = requireFinite(volume.domain_volume, "el volumen del dominio");
    const difference = relativeDifference(mesh, voxel);
    setVolumeCells([formatNumber(mesh), formatNumber(voxel), formatNumber(domain), `${formatNumber(difference)} %`]);
  } catch (error) {
    if (state.selectedId !== id) return;
    setVolumeCells(VOLUME_CELLS.map(() => "—"));
    showError(error.message);
  }
}

// Formato binario de la malla (app/volumes/binary.py, versión 3), little-endian:
// "IMSH", versión u16, flags u16, n_vértices u32, n_caras u32, origen 3×f64 (40 bytes),
// vértices n×3×f32 relativos al origen, caras m×3×u32.
const MESH_MAGIC = "IMSH";
const MESH_VERSION = 3;
const MESH_HEADER_BYTES = 40;

function decodeMesh(buffer) {
  if (buffer.byteLength < MESH_HEADER_BYTES) throw new Error("La malla recibida está incompleta.");
  const magic = String.fromCharCode(...new Uint8Array(buffer, 0, 4));
  if (magic !== MESH_MAGIC) throw new Error("La API devolvió un archivo que no es una malla.");
  const view = new DataView(buffer);
  const version = view.getUint16(4, true);
  if (version !== MESH_VERSION) {
    throw new Error(`Versión de malla no soportada (${version}); el panel espera la ${MESH_VERSION}.`);
  }
  const vertexCount = view.getUint32(8, true);
  const faceCount = view.getUint32(12, true);
  if (buffer.byteLength < MESH_HEADER_BYTES + vertexCount * 12 + faceCount * 12) {
    throw new Error("La malla recibida está incompleta.");
  }
  const vertices = new Float32Array(buffer, MESH_HEADER_BYTES, vertexCount * 3);
  const faces = new Uint32Array(buffer, MESH_HEADER_BYTES + vertices.byteLength, faceCount * 3);
  return { vertices, faces };
}

let surface = null;

function setSurfaceMessage(text) {
  document.getElementById("surface-message").textContent = text;
}

// Three.js se carga bajo demanda: si no hay red o WebGL, el resto del panel sigue funcionando.
async function ensureSurface() {
  if (surface) return surface;
  const [THREE, { OrbitControls }] = await Promise.all([
    import("three"),
    import("three/addons/controls/OrbitControls.js"),
  ]);
  const container = $("surface-view");
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio);
  container.append(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x11151c);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x334455, 1.2));
  const sun = new THREE.DirectionalLight(0xffffff, 1.5);
  sun.position.set(3, 5, 4);
  scene.add(sun);

  const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 1000);
  const controls = new OrbitControls(camera, renderer.domElement);

  const resize = () => {
    const { clientWidth: width, clientHeight: height } = container;
    if (width === 0 || height === 0) return;
    renderer.setSize(width, height);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  };
  new ResizeObserver(resize).observe(container);
  renderer.setAnimationLoop(() => {
    controls.update();
    renderer.render(scene, camera);
  });

  surface = { THREE, scene, camera, controls, resize, mesh: null };
  return surface;
}

function clearSurfaceMesh() {
  if (!surface?.mesh) return;
  surface.scene.remove(surface.mesh);
  surface.mesh.geometry.dispose();
  surface.mesh.material.dispose();
  surface.mesh = null;
}

function drawSurface({ vertices, faces }) {
  const { THREE, scene, camera, controls, resize } = surface;
  clearSurfaceMesh();
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(vertices, 3));
  geometry.setIndex(new THREE.BufferAttribute(faces, 1));
  geometry.computeVertexNormals();
  geometry.computeBoundingSphere();

  const material = new THREE.MeshStandardMaterial({
    color: 0x4f9cf9,
    roughness: 0.45,
    metalness: 0.1,
    side: THREE.DoubleSide,
  });
  surface.mesh = new THREE.Mesh(geometry, material);
  scene.add(surface.mesh);

  // Los vértices vienen relativos al origen de la malla, así que el encuadre es local.
  const { center, radius } = geometry.boundingSphere;
  controls.target.copy(center);
  camera.position.copy(center).add(new THREE.Vector3(radius * 1.8, radius * 1.4, radius * 2.2));
  camera.near = radius / 100;
  camera.far = radius * 100;
  resize();
  camera.updateProjectionMatrix();
}

async function loadSurface(id) {
  document.getElementById("surface").hidden = false;
  setSurfaceMessage("Cargando superficie…");
  try {
    const buffer = await (await authorized(`/functions/${id}/mesh.bin`)).arrayBuffer();
    if (state.selectedId !== id) return;
    const mesh = decodeMesh(buffer);
    if (mesh.faces.length === 0) {
      clearSurfaceMesh();
      setSurfaceMessage("Esta función no tiene superficie dentro del dominio.");
      return;
    }
    try {
      await ensureSurface();
    } catch {
      setSurfaceMessage("No se pudo iniciar la vista 3D: comprueba la conexión y que el navegador admita WebGL.");
      return;
    }
    if (state.selectedId !== id) return;
    drawSurface(mesh);
    setSurfaceMessage("");
  } catch (error) {
    if (state.selectedId !== id) return;
    clearSurfaceMesh();
    setSurfaceMessage("No se pudo cargar la superficie.");
    showError(error.message);
  }
}

const CONVERGENCE_RESOLUTIONS = [32, 64, 128, 256];
const BUSY_RETRIES = 2;
const BUSY_WAIT_MS = 2000;

const sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

function buildConvergenceRows() {
  const body = document.getElementById("convergence-body");
  body.replaceChildren();
  for (const n of CONVERGENCE_RESOLUTIONS) {
    const row = document.createElement("tr");
    row.dataset.testid = "convergence-row";
    row.dataset.n = n;
    const cells = [
      [null, String(n)],
      ["convergence-mesh", "…"],
      ["convergence-voxel", "…"],
    ];
    for (const [testId, text] of cells) {
      const cell = document.createElement("td");
      if (testId) cell.dataset.testid = testId;
      cell.textContent = text;
      row.append(cell);
    }
    body.append(row);
  }
}

function setConvergenceRow(n, mesh, voxel) {
  const row = document.querySelector(`[data-testid="convergence-row"][data-n="${n}"]`);
  row.querySelector('[data-testid="convergence-mesh"]').textContent = mesh;
  row.querySelector('[data-testid="convergence-voxel"]').textContent = voxel;
}

// Si la API está ocupada (503) se espera y se reintenta unas pocas veces antes de rendirse.
async function fetchVolumeAt(id, n) {
  for (let attempt = 0; ; attempt += 1) {
    try {
      return await (await authorized(`/functions/${id}/volume?resolution=${n}`)).json();
    } catch (error) {
      if (error.status !== 503 || attempt >= BUSY_RETRIES) throw error;
      await sleep(BUSY_WAIT_MS);
      if (state.selectedId !== id) return null;
    }
  }
}

async function loadConvergence(id) {
  document.getElementById("convergence").hidden = false;
  buildConvergenceRows();
  // En serie y de menor a mayor resolución: la API admite pocos cálculos simultáneos.
  for (const n of CONVERGENCE_RESOLUTIONS) {
    try {
      const volume = await fetchVolumeAt(id, n);
      if (state.selectedId !== id) return;
      const mesh = requireFinite(volume.mesh_volume, `el volumen por malla con n = ${n}`);
      const voxel = requireFinite(volume.voxel_volume, `el volumen por vóxeles con n = ${n}`);
      setConvergenceRow(n, formatNumber(mesh), formatNumber(voxel));
    } catch (error) {
      if (state.selectedId !== id) return;
      setConvergenceRow(n, "—", "—");
      showError(`Convergencia, n = ${n}: ${error.message}`);
      if (error.status === 401) return;
    }
  }
}

async function selectFunction(id) {
  state.selectedId = id;
  clearError();
  renderFunctionList();
  renderFunctionInfo(state.functions.find((fn) => fn.id === id));
  // En serie: la API admite pocos cálculos simultáneos y respondería 503 si se piden a la vez.
  await loadVolumes(id);
  await loadSurface(id);
  await loadConvergence(id);
}

async function openPanel() {
  const response = await authorized("/functions");
  state.functions = await response.json();
  showPanel();
  renderFunctionList();
}

document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearError();
  const form = event.target;
  const submit = $("login-submit");
  submit.disabled = true;
  try {
    const response = await request("/auth/token", { method: "POST", body: new URLSearchParams(new FormData(form)) });
    setToken((await response.json()).access_token);
    form.reset();
    await openPanel();
  } catch (error) {
    showError(error.status === 401 ? "Usuario o contraseña incorrectos." : error.message);
  } finally {
    submit.disabled = false;
  }
});

document.getElementById("logout").addEventListener("click", () => {
  clearError();
  signOut();
});

async function showApiStatus() {
  const status = document.getElementById("api-status");
  try {
    await request("/health");
    status.textContent = `API: ${API_URL}`;
  } catch (error) {
    status.textContent = "";
    showError(error.message);
  }
}

showApiStatus();

if (getToken()) {
  openPanel().catch((error) => showError(error.message));
} else {
  showLogin();
}
