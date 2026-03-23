/* Comunicación con el backend v2 */

const API = "http://localhost:5002/api";

async function apiPost(endpoint, body = {}) {
    const res = await fetch(`${API}/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Error del servidor");
    return data;
}

async function apiGet(endpoint) {
    const res = await fetch(`${API}/${endpoint}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Error del servidor");
    return data;
}

async function apiPut(endpoint, body) {
    const res = await fetch(`${API}/${endpoint}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Error del servidor");
    return data;
}

async function apiDelete(endpoint) {
    const res = await fetch(`${API}/${endpoint}`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Error del servidor");
    return data;
}

async function guardarConfig() {
    if (!config) return;
    try {
        await apiPut("configuracion", config);
    } catch (e) {
        console.error("Error guardando config:", e);
    }
}
