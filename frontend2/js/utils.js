/* Utilidades generales */

function showEl(id) {
    document.getElementById(id)?.classList.remove("hidden");
}

function hideEl(id) {
    document.getElementById(id)?.classList.add("hidden");
}

function showError(id, msg) {
    const el = document.getElementById(id);
    if (el) {
        el.textContent = msg;
        el.classList.remove("hidden");
    }
}

function setStep(n) {
    for (let i = 1; i <= 4; i++) {
        const el = document.getElementById(`step${i}`);
        if (!el) continue;
        el.classList.remove("active", "done");
        if (i < n) el.classList.add("done");
        if (i === n) el.classList.add("active");
    }
}

function formatRespuesta(cfg) {
    if (!cfg) return "";
    if (cfg.tipo === "fijo") return `"${cfg.valor}"`;
    if (cfg.tipo === "rango") return `${cfg.min} - ${cfg.max}`;
    if (cfg.tipo === "aleatorio" && cfg.opciones) {
        return Object.entries(cfg.opciones)
            .map(([k, v]) => `${k} (${v}%)`)
            .join(", ");
    }
    return JSON.stringify(cfg);
}

function truncar(texto, max = 45) {
    if (!texto) return "";
    return texto.length > max ? texto.substring(0, max) + "..." : texto;
}

function timeAgo(dateStr) {
    if (!dateStr) return "";
    const date = new Date(dateStr);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000);
    if (diff < 60) return "hace un momento";
    if (diff < 3600) return `hace ${Math.floor(diff / 60)}m`;
    if (diff < 86400) return `hace ${Math.floor(diff / 3600)}h`;
    return `hace ${Math.floor(diff / 86400)}d`;
}

function platformIcon(plataforma) {
    const icons = {
        google_forms: "G",
        microsoft_forms: "M",
        typeform: "T",
        generic: "?",
    };
    return icons[plataforma] || "?";
}

function platformName(plataforma) {
    const names = {
        google_forms: "Google Forms",
        microsoft_forms: "Microsoft Forms",
        typeform: "Typeform",
        generic: "Generico",
    };
    return names[plataforma] || plataforma || "Desconocido";
}

function statusColor(status) {
    const colors = {
        ejecutando: "var(--accent)",
        completado: "var(--success)",
        error: "var(--danger)",
        detenido: "var(--warning)",
        idle: "var(--text-muted)",
    };
    return colors[status] || "var(--text-muted)";
}

function showConfigTab(tabName, btnEl) {
    document.querySelectorAll(".config-tab-content").forEach(el => el.classList.add("hidden"));
    document.querySelectorAll(".config-tabs .tab").forEach(el => el.classList.remove("active"));
    document.getElementById("tab" + tabName.charAt(0).toUpperCase() + tabName.slice(1)).classList.remove("hidden");
    if (btnEl) btnEl.classList.add("active");
}

function togglePreguntas() {
    const el = document.getElementById("preguntasList");
    preguntasVisible = !preguntasVisible;
    el.style.display = preguntasVisible ? "" : "none";
}

function exportConfig() {
    if (!config) return alert("No hay configuracion para exportar");
    const exportData = {
        perfiles: config.perfiles,
        reglas_dependencia: config.reglas_dependencia,
        tendencias_escalas: config.tendencias_escalas,
    };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const name = currentProject ? currentProject.nombre.replace(/\s+/g, '_') : "config";
    a.download = `config_${name}.json`;
    a.click();
    URL.revokeObjectURL(url);
}

function importConfig() {
    document.getElementById("fileImport").click();
}

function handleImport(event) {
    const file = event.target.files[0];
    if (!file || !currentProject) return;
    const reader = new FileReader();
    reader.onload = async (e) => {
        try {
            const data = JSON.parse(e.target.result);
            if (data.perfiles || data.reglas_dependencia || data.tendencias_escalas) {
                const { replaceExisting } = await importarConfigProyecto(
                    data,
                    file.name.replace(/\.json$/i, "")
                );
                alert(replaceExisting ? "Configuracion reemplazada correctamente" : "Configuracion importada correctamente");
            } else {
                alert("JSON no tiene formato de configuracion valido");
            }
        } catch (err) {
            alert("Error: " + err.message);
        }
    };
    reader.readAsText(file);
    event.target.value = "";
}
