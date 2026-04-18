/* Paso 4: Ejecutar bot y monitorear progreso */

let intervalo = null;
let lastLogLength = 0;
let turboAllowed = false;

async function ejecutar() {
    if (!currentProject) return alert("No hay proyecto abierto");

    const cantidad = parseInt(document.getElementById("cantidadInput").value);
    const headless = document.getElementById("headlessInput").checked;
    const speedProfile = document.getElementById("speedProfileInput")?.value || "balanced";

    // Guardar config actual antes de ejecutar
    await guardarConfig();

    try {
        if (speedProfile === "turbo" || speedProfile === "turbo_plus") {
            const allowed = await verificarTurbo();
            if (!allowed) {
                alert("Turbo/Turbo+ requiere una ejecucion balanced 100% exitosa previa.");
                return;
            }
        }
        const result = await apiPost(`projects/${currentProject.id}/execute`, {
            cantidad,
            headless,
            speed_profile: speedProfile,
        });
        currentExecutionId = result.execution_id || null;
        lastLogLength = 0;

        document.getElementById("btnEjecutar").disabled = true;
        const turboPlusBtn = document.getElementById("btnEjecutarTurboPlus");
        if (turboPlusBtn) turboPlusBtn.disabled = true;
        hideEl("btnReejecutar");
        showEl("btnDetener");
        showEl("progressSection");
        hideEl("btnExcel");
        document.getElementById("consoleOutput").textContent = "Iniciando ejecucion...\n";
        setStep(4);
        intervalo = setInterval(pollEstado, 1500);
    } catch (e) {
        alert(e.message || "Error conectando al servidor");
    }
}

async function ejecutarConPerfil(profileId) {
    const speedSelect = document.getElementById("speedProfileInput");
    if (speedSelect) speedSelect.value = profileId;
    await ejecutar();
}

async function ejecutarTurboPlus() {
    await ejecutarConPerfil("turbo_plus");
}

async function pollEstado() {
    if (!currentProject) return;

    try {
        let endpoint = `projects/${currentProject.id}/estado`;
        if (currentExecutionId) endpoint += `?execution_id=${currentExecutionId}`;

        const st = await apiGet(endpoint);

        const pct = st.total > 0 ? Math.round((st.progreso / st.total) * 100) : 0;
        const bar = document.getElementById("progressBar");
        bar.style.width = pct + "%";
        bar.textContent = pct + "%";

        document.getElementById("stExitosas").textContent = st.exitosas;
        document.getElementById("stFallidas").textContent = st.fallidas;
        document.getElementById("stProgreso").textContent = `${st.progreso}/${st.total}`;
        document.getElementById("stTiempo").textContent = st.tiempo_transcurrido || "0s";
        document.getElementById("stPromedio").textContent = st.tiempo_por_encuesta || "0s";
        document.getElementById("stMensaje").textContent = st.mensaje;

        if (st.logs && st.logs.length > lastLogLength) {
            const consoleEl = document.getElementById("consoleOutput");
            consoleEl.textContent = st.logs;
            lastLogLength = st.logs.length;
            consoleEl.scrollTop = consoleEl.scrollHeight;
        }

        if (st.progreso > 0) {
            const tasa = st.exitosas / st.progreso;
            if (tasa >= 0.8) bar.style.background = "var(--gradient-success)";
            else if (tasa >= 0.5) bar.style.background = "var(--gradient-primary)";
            else bar.style.background = "var(--gradient-danger)";
        }

        const fase = st.fase || st.status;
        if (fase === "ejecutando") {
            document.getElementById("stMensaje").classList.add("pulse");
        } else if (fase === "completado" || fase === "idle" || fase === "detenido" || fase === "error") {
            document.getElementById("stMensaje").classList.remove("pulse");
            clearInterval(intervalo);
            document.getElementById("btnEjecutar").disabled = false;
            const turboPlusBtn = document.getElementById("btnEjecutarTurboPlus");
            if (turboPlusBtn) turboPlusBtn.disabled = false;
            hideEl("btnDetener");
            showEl("btnReejecutar");
            if (st.excel) showEl("btnExcel");
            bar.style.background = "";
            if (st.logs) {
                document.getElementById("consoleOutput").textContent = st.logs;
            }
            // Recargar historial
            if (currentProject) cargarHistorialEjecuciones(currentProject.id);
        }
    } catch (e) {
        console.error("Error polling:", e);
    }
}

async function detener() {
    if (!currentProject) return;
    try {
        const body = currentExecutionId ? { execution_id: currentExecutionId } : {};
        await apiPost(`projects/${currentProject.id}/stop`, body);
    } catch (e) { /* ignore */ }
    clearInterval(intervalo);
    document.getElementById("btnEjecutar").disabled = false;
    const turboPlusBtn = document.getElementById("btnEjecutarTurboPlus");
    if (turboPlusBtn) turboPlusBtn.disabled = false;
    hideEl("btnDetener");
    showEl("btnReejecutar");
}

function descargar() {
    if (!currentProject) return;
    let endpoint = `projects/${currentProject.id}/download`;
    if (currentExecutionId) endpoint += `?execution_id=${currentExecutionId}`;
    window.open(`${API}/${endpoint}`, "_blank");
}

function clearConsole() {
    document.getElementById("consoleOutput").textContent = "Consola limpia.\n";
    lastLogLength = 0;
}

function applyExecutionSettings(settings = {}) {
    const headlessInput = document.getElementById("headlessInput");
    if (headlessInput && typeof settings.default_headless === "boolean") {
        headlessInput.checked = settings.default_headless;
    }

    const speedSelect = document.getElementById("speedProfileInput");
    if (!speedSelect) return;

    const profiles = Array.isArray(settings.execution_profiles) ? settings.execution_profiles : [];
    if (profiles.length) {
        speedSelect.innerHTML = profiles.map((profile) => `
            <option value="${profile.id}">${profile.label}</option>
        `).join("");
    }

    speedSelect.value = settings.default_execution_profile || "balanced";

    speedSelect.onchange = async () => {
        if (speedSelect.value === "turbo" || speedSelect.value === "turbo_plus") {
            const allowed = await verificarTurbo();
            if (!allowed) {
                alert("Turbo/Turbo+ requiere una ejecucion balanced 100% exitosa previa.");
                speedSelect.value = "balanced";
            }
        }
    };
}

async function verificarTurbo() {
    if (!currentProject) return false;
    try {
        const executions = await apiGet(`projects/${currentProject.id}/executions`);
        const match = (executions || []).find(e => {
            const msg = (e.mensaje || "").toLowerCase();
            return e.status === "completado" && e.total > 0 && e.exitosas === e.total && msg.includes("(balanced)");
        });
        turboAllowed = Boolean(match);
        return turboAllowed;
    } catch (e) {
        return false;
    }
}
