/* Paneles laterales: Settings y Providers */

function togglePanel(name) {
    const panelMap = {
        settings: "panelSettings",
    };
    const panelId = panelMap[name] || "panelSettings";
    const panel = document.getElementById(panelId);
    const isHidden = panel.classList.contains("hidden");

    document.querySelectorAll(".side-panel").forEach(p => p.classList.add("hidden"));

    if (isHidden) {
        panel.classList.remove("hidden");
        if (name === "settings") {
            loadProviders();
            loadSettings();
        }
    }
}

// ==================== PROVIDERS DE IA ====================

async function loadProviders() {
    try {
        const providers = await apiGet("config/ai-providers");
        const container = document.getElementById("providerList");
        if (!container) return;
        if (!providers.length) {
            container.innerHTML = '<div class="empty-state-sm">Sin proveedores</div>';
            return;
        }
        container.innerHTML = providers.map(p => `
            <div class="provider-item ${p.is_active ? 'active' : ''}" onclick="activateProvider('${p.name}')">
                <span class="provider-name">${p.name}</span>
                <span class="provider-model">${p.model}</span>
                ${p.is_active ? '<span class="provider-badge">Activo</span>' : ''}
            </div>
        `).join("");
    } catch (e) {
        // Server might not be running
    }
}

async function activateProvider(name) {
    try {
        await apiPut(`config/ai-providers/${name}/activate`);
        loadProviders();
    } catch (e) {
        alert("Error: " + e.message);
    }
}

async function addProvider() {
    const name = document.getElementById("newProviderName").value;
    const key = document.getElementById("newProviderKey").value.trim();
    const model = document.getElementById("newProviderModel").value.trim();

    if (!key) return alert("API Key requerida");

    try {
        await apiPost("config/ai-providers", {
            provider_name: name,
            api_key: key,
            model: model || undefined,
        });
        document.getElementById("newProviderKey").value = "";
        document.getElementById("newProviderModel").value = "";
        loadProviders();
        alert("Proveedor agregado");
    } catch (e) {
        alert("Error: " + e.message);
    }
}

// ==================== SETTINGS ====================

async function loadSettings() {
    try {
        const settings = await apiGet("config/settings");
        const container = document.getElementById("settingsInfo");
        if (!container) return;
        container.innerHTML = `
            <div class="settings-grid">
                <div class="setting-item">
                    <span class="setting-label">Idioma browser</span>
                    <span class="setting-value">${settings.browser_locale}</span>
                </div>
                <div class="setting-item">
                    <span class="setting-label">Zona horaria</span>
                    <span class="setting-value">${settings.browser_timezone}</span>
                </div>
                <div class="setting-item">
                    <span class="setting-label">Viewport</span>
                    <span class="setting-value">${settings.browser_viewport?.width}x${settings.browser_viewport?.height}</span>
                </div>
                <div class="setting-item">
                    <span class="setting-label">Max encuestas</span>
                    <span class="setting-value">${settings.max_encuestas}</span>
                </div>
                <div class="setting-item">
                    <span class="setting-label">Pausa entre envios</span>
                    <span class="setting-value">${settings.pausa_min}s - ${settings.pausa_max}s</span>
                </div>
                <div class="setting-item">
                    <span class="setting-label">IA Temperature</span>
                    <span class="setting-value">${settings.ai_temperature}</span>
                </div>
                <div class="setting-item">
                    <span class="setting-label">IA Max tokens</span>
                    <span class="setting-value">${settings.ai_max_tokens}</span>
                </div>
                <div class="setting-item">
                    <span class="setting-label">Proveedor default</span>
                    <span class="setting-value">${settings.default_ai_provider}</span>
                </div>
            </div>
        `;
    } catch (e) {
        const container = document.getElementById("settingsInfo");
        if (container) container.innerHTML = '<div class="empty-state-sm">No se pudo cargar config del servidor</div>';
    }
}
