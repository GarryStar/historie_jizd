function token() {
  return localStorage.getItem("token");
}

function authHeaders() {
  return {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${token()}`
  };
}

async function api(url, options = {}) {
  const res = await fetch(url, options);
  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new Error(data.error || "Něco se pokazilo.");
  }

  return data;
}

function logout() {
  localStorage.removeItem("token");
  localStorage.removeItem("email");
  window.location.href = "/";
}

async function requireLogin() {
  if (!token()) {
    window.location.href = "/";
    return null;
  }

  try {
    return await api("/api/me", { headers: authHeaders() });
  } catch (e) {
    logout();
  }
}

function dnesISO() {
  return new Date().toISOString().slice(0, 10);
}

function saveLocal(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function loadLocal(key, fallback = null) {
  const raw = localStorage.getItem(key);
  if (!raw) return fallback;

  try {
    return JSON.parse(raw);
  } catch (e) {
    return fallback;
  }
}

function removeLocal(key) {
  localStorage.removeItem(key);
}

function isOnline() {
  return navigator.onLine;
}

function addPendingTrip(trip) {
  const pending = loadLocal("pendingTrips", []);
  pending.push({
    id: crypto.randomUUID(),
    created_at: new Date().toISOString(),
    trip
  });
  saveLocal("pendingTrips", pending);
}

async function syncPendingTrips() {
  if (!isOnline()) return;

  const pending = loadLocal("pendingTrips", []);
  if (!pending.length) return;

  const stillPending = [];

  for (const item of pending) {
    try {
      await api("/api/trips", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify(item.trip)
      });
    } catch (e) {
      stillPending.push(item);
    }
  }

  saveLocal("pendingTrips", stillPending);
}

window.addEventListener("online", syncPendingTrips);
