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

function selectFunction(id) {
  state.selectedId = id;
  clearError();
  renderFunctionList();
  renderFunctionInfo(state.functions.find((fn) => fn.id === id));
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
