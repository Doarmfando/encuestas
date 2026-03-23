/* Paso 4: Ejecutar bot y monitorear progreso */

let intervalo = null;
let lastLogLength = 0;

async function ejecutar() {
    if (!currentProject) return alert("No hay proyecto abierto");

    const cantidad = parseInt(document.getElementById("cantidadInput").value);
    const headless = document.getElementById("headlessInput").checked;

    // Guardar config actual antes de ejecutar
    await guardarConfig();

    try {
        const result = await apiPost(`projects/${currentProject.id}/execute`, { cantidad, headless });
        currentExecutionId = result.execution_id || null;
        lastLogLength = 0;

        document.getElementById("btnEjecutar").disabled = true;
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
            hideEl("btnDetener");
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
    hideEl("btnDetener");
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
