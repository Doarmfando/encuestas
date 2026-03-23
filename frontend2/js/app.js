/* Estado global y navegación entre vistas */

let currentProject = null;   // Proyecto actualmente abierto
let config = null;            // Config activa del proyecto
let estructura = null;        // Estructura scrapeada
let preguntasVisible = true;
let currentExecutionId = null;
let iaPreviewData = null;     // Data temporal del preview IA

// ═══════════════ INICIALIZACIÓN ═══════════════

document.addEventListener("DOMContentLoaded", () => {
    loadProviders();
    loadSettings();
    cargarProyectos();
});

// ═══════════════ NAVEGACIÓN DE VISTAS ═══════════════

function showView(viewName) {
    document.getElementById("vistaProyectos").style.display = "none";
    document.getElementById("vistaProyecto").style.display = "none";
    document.getElementById("vistaDashboard").style.display = "none";
    document.getElementById("btnVolverProyectos").style.display = "none";

    if (viewName === "proyectos") {
        document.getElementById("vistaProyectos").style.display = "";
        document.getElementById("headerTitle").textContent = "Sistema de Encuestas";
        document.getElementById("headerSubtitle").textContent = "Gestiona tus proyectos de encuestas con IA";
    } else if (viewName === "proyecto") {
        document.getElementById("vistaProyecto").style.display = "";
        document.getElementById("btnVolverProyectos").style.display = "";
        document.getElementById("headerTitle").textContent = currentProject?.nombre || "Proyecto";
        document.getElementById("headerSubtitle").textContent = currentProject?.url || "";
    } else if (viewName === "dashboard") {
        document.getElementById("vistaDashboard").style.display = "";
        document.getElementById("btnVolverProyectos").style.display = "";
        document.getElementById("headerTitle").textContent = "Dashboard";
        document.getElementById("headerSubtitle").textContent = "Ejecuciones en tiempo real";
    }
}

function volverAProyectos() {
    // Limpiar estado
    if (intervalo) clearInterval(intervalo);
    currentProject = null;
    config = null;
    estructura = null;
    currentExecutionId = null;
    showView("proyectos");
    cargarProyectos();
}

function showDashboard() {
    showView("dashboard");
    pollDashboard();
}

// ═══════════════ PROYECTOS: CRUD ═══════════════

async function cargarProyectos() {
    const container = document.getElementById("projectsList");
    try {
        const projects = await apiGet("projects");
        if (!projects.length) {
            container.innerHTML = '<div class="empty-state">No hay proyectos. Crea uno para empezar.</div>';
            return;
        }
        container.innerHTML = projects.map(p => `
            <div class="project-card" onclick="abrirProyecto(${p.id})">
                <div class="project-card-header">
                    <span class="platform-dot ${p.plataforma || 'google_forms'}">${platformIcon(p.plataforma)}</span>
                    <h3>${p.nombre}</h3>
                    <span class="project-status status-${p.status}">${p.status}</span>
                </div>
                <div class="project-card-meta">
                    ${p.total_preguntas ? p.total_preguntas + ' preguntas' : 'Sin scrapear'} |
                    ${p.total_configs || 0} configs |
                    ${timeAgo(p.created_at)}
                </div>
                ${p.ultima_ejecucion ? `
                    <div class="project-card-exec">
                        <span class="status-dot" style="background:${statusColor(p.ultima_ejecucion.status)}"></span>
                        ${p.ultima_ejecucion.exitosas}/${p.ultima_ejecucion.total} -
                        ${p.ultima_ejecucion.status}
                    </div>
                ` : ''}
                <div class="project-card-url">${truncar(p.url, 50)}</div>
                <div class="project-card-actions" onclick="event.stopPropagation()">
                    <button class="btn btn-danger btn-sm" onclick="eliminarProyecto(${p.id})">Eliminar</button>
                </div>
            </div>
        `).join("");
    } catch (e) {
        container.innerHTML = '<div class="empty-state">Error: ' + e.message + '</div>';
    }
}

function mostrarCrearProyecto() {
    showEl("formCrearProyecto");
    document.getElementById("nuevoNombre").focus();
}

async function crearProyecto() {
    const nombre = document.getElementById("nuevoNombre").value.trim();
    const url = document.getElementById("nuevaUrl").value.trim();
    const desc = document.getElementById("nuevaDesc").value.trim();

    if (!nombre || !url) return alert("Nombre y URL son requeridos");

    try {
        const project = await apiPost("projects", { nombre, url, descripcion: desc });
        hideEl("formCrearProyecto");
        document.getElementById("nuevoNombre").value = "";
        document.getElementById("nuevaUrl").value = "";
        document.getElementById("nuevaDesc").value = "";
        abrirProyecto(project.id);
    } catch (e) {
        alert("Error: " + e.message);
    }
}

async function eliminarProyecto(id) {
    if (!confirm("Eliminar este proyecto y todo su contenido?")) return;
    try {
        await apiDelete(`projects/${id}`);
        cargarProyectos();
    } catch (e) {
        alert("Error: " + e.message);
    }
}

// ═══════════════ ABRIR PROYECTO ═══════════════

async function abrirProyecto(projectId) {
    try {
        const project = await apiGet(`projects/${projectId}`);
        currentProject = project;
        config = null;
        estructura = null;
        currentExecutionId = null;

        showView("proyecto");

        // Mostrar URL
        document.getElementById("projectUrl").textContent = project.url;

        // Determinar paso actual segun status
        if (project.estructura) {
            estructura = { paginas: project.estructura.paginas || [], ...project };
            mostrarEstructura(project);

            if (project.config_activa) {
                config = project.config_activa;
                mostrarConfiguracion(config);
                cargarConfigSelector(projectId);
                setStep(4);
            } else {
                setStep(2);
            }
        } else {
            // Ocultar secciones
            hideEl("seccion2");
            hideEl("seccion3");
            hideEl("seccion4");
            setStep(1);
        }

        // Cargar historial de ejecuciones
        cargarHistorialEjecuciones(projectId);

    } catch (e) {
        alert("Error cargando proyecto: " + e.message);
    }
}

// ═══════════════ SCRAPING ═══════════════

async function scrapeProject() {
    if (!currentProject) return;

    const btn = document.getElementById("btnScrape");
    const headless = document.getElementById("scrapeHeadless").checked;
    btn.disabled = true;
    btn.textContent = "Scrapeando...";
    hideEl("scrapeError");

    try {
        const data = await apiPost(`projects/${currentProject.id}/scrape`, { headless });
        estructura = data;
        currentProject.estructura = { paginas: data.paginas || [] };
        currentProject.total_preguntas = data.total_preguntas;
        currentProject.status = "scrapeado";
        mostrarEstructura(data);
        setStep(2);

        // Actualizar badge
        const badge = document.getElementById("platformBadge");
        const plat = data.plataforma || "google_forms";
        badge.innerHTML = `${platformIcon(plat)} ${platformName(plat)}`;
        badge.className = `platform-badge ${plat}`;
        badge.classList.remove("hidden");

    } catch (e) {
        showError("scrapeError", e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = "Scrapear";
    }
}

function mostrarEstructura(data) {
    showEl("seccion2");

    document.getElementById("infoForm").innerHTML =
        `<strong>${data.titulo || data.nombre || "Sin titulo"}</strong>` +
        (data.descripcion ? `<br><span style="font-size:12px">${truncar(data.descripcion, 100)}</span>` : "") +
        `<br>${(data.paginas || data.estructura?.paginas || []).length} paginas | ${data.total_preguntas || 0} preguntas`;

    const paginas = data.paginas || data.estructura?.paginas || [];
    let html = "";
    paginas.forEach((pag) => {
        html += `<div class="page-header">
            Pagina ${pag.numero} <span class="page-buttons">${(pag.botones || []).join(", ") || "sin botones"}</span>
        </div>`;
        (pag.preguntas || []).forEach((p) => {
            const tipoClass = p.tipo.includes("escala") ? "likert" :
                              p.tipo.includes("opcion") ? "radio" :
                              p.tipo.includes("seleccion") ? "check" :
                              (p.tipo.includes("texto") || p.tipo === "numero" || p.tipo === "parrafo") ? "text" :
                              p.tipo === "desplegable" ? "drop" : "";
            html += `<div class="pregunta-item">
                <div class="pregunta-text">
                    ${p.texto}${p.obligatoria ? '<span class="obligatoria">*</span>' : ''}
                    ${p.opciones?.length ? '<div class="opciones-preview">' + p.opciones.slice(0, 6).join(" | ") + (p.opciones.length > 6 ? ` (+${p.opciones.length - 6})` : '') + '</div>' : ''}
                </div>
                <span class="tipo ${tipoClass}">${p.tipo}</span>
            </div>`;
        });
    });
    document.getElementById("preguntasList").innerHTML = html;
    preguntasVisible = true;
}

// ═══════════════ ANÁLISIS IA (con preview) ═══════════════

async function analizarConIA() {
    if (!currentProject) return;

    const btn = document.getElementById("btnAnalizar");
    btn.disabled = true;
    btn.textContent = "Analizando con IA...";

    try {
        // Preguntar instrucciones opcionales
        const instrucciones = prompt("Instrucciones adicionales para la IA (opcional, dejar vacio si no):", "");

        const data = await apiPost(`projects/${currentProject.id}/analyze`, {
            instrucciones: instrucciones || "",
        });

        // Mostrar preview modal
        iaPreviewData = data;
        mostrarIAPreview(data);

    } catch (e) {
        alert(e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = "Analizar con IA";
    }
}

function mostrarIAPreview(data) {
    const perfiles = data.perfiles || [];
    const tendencias = data.tendencias_escalas || [];
    const reglas = data.reglas_dependencia || [];

    let html = '<div class="ia-preview-summary">';
    html += `<div class="ia-preview-stat"><strong>${perfiles.length}</strong> perfiles</div>`;
    html += `<div class="ia-preview-stat"><strong>${tendencias.length}</strong> tendencias</div>`;
    html += `<div class="ia-preview-stat"><strong>${reglas.length}</strong> reglas</div>`;
    html += '</div>';

    // Perfiles resumen
    html += '<h3>Perfiles</h3>';
    perfiles.forEach(p => {
        const respCount = Object.keys(p.respuestas || {}).length;
        html += `<div class="ia-preview-item">
            <strong>${p.nombre}</strong> (${p.frecuencia}%)
            <span class="hint"> - ${p.descripcion || ''} | ${respCount} respuestas</span>
        </div>`;
    });

    // Tendencias resumen
    html += '<h3>Tendencias</h3>';
    tendencias.forEach(t => {
        html += `<div class="ia-preview-item">
            <strong>${t.nombre}</strong> (${t.frecuencia}%)
            <span class="hint"> - ${t.descripcion || ''}</span>
        </div>`;
    });

    // Reglas resumen
    html += '<h3>Reglas</h3>';
    reglas.forEach(r => {
        html += `<div class="ia-preview-item">
            SI "${truncar(r.si_pregunta, 30)}" ${r.operador} "${r.si_valor}"
            → ${truncar(r.entonces_pregunta, 30)}
        </div>`;
    });

    // Validaciones
    const warnings = [];
    if (perfiles.length < 3) warnings.push("Se necesitan minimo 3 perfiles");
    if (tendencias.length < 3) warnings.push("Se necesitan minimo 3 tendencias");
    if (reglas.length < 1) warnings.push("Se necesita minimo 1 regla");

    const totalFreqP = perfiles.reduce((s, p) => s + (p.frecuencia || 0), 0);
    const totalFreqT = tendencias.reduce((s, t) => s + (t.frecuencia || 0), 0);
    if (totalFreqP !== 100) warnings.push(`Frecuencia perfiles suma ${totalFreqP}% (debe ser 100%)`);
    if (totalFreqT !== 100) warnings.push(`Frecuencia tendencias suma ${totalFreqT}% (debe ser 100%)`);

    if (warnings.length) {
        html += '<div class="alert alert-error mt-10">' + warnings.join('<br>') + '</div>';
    }

    // Campo de nombre
    html += `<div class="form-group mt-10">
        <label>Nombre de la config</label>
        <input type="text" id="iaConfigNombre" value="IA - ${new Date().toLocaleDateString('es-PE')}" placeholder="Nombre para esta configuracion">
    </div>`;

    document.getElementById("iaPreviewContent").innerHTML = html;
    showEl("iaPreviewOverlay");
}

function cerrarIAPreview(e) {
    if (e.target === document.getElementById("iaPreviewOverlay")) {
        hideEl("iaPreviewOverlay");
        iaPreviewData = null;
    }
}

function cerrarIAPreviewBtn() {
    hideEl("iaPreviewOverlay");
    iaPreviewData = null;
}

async function aplicarConfigIA() {
    if (!iaPreviewData || !currentProject) return;

    const nombre = document.getElementById("iaConfigNombre")?.value || "IA Config";

    try {
        const result = await apiPost(`projects/${currentProject.id}/apply-config`, {
            nombre,
            perfiles: iaPreviewData.perfiles,
            reglas_dependencia: iaPreviewData.reglas_dependencia,
            tendencias_escalas: iaPreviewData.tendencias_escalas,
        });

        config = result;
        mostrarConfiguracion(result);
        cargarConfigSelector(currentProject.id);
        setStep(3);
        hideEl("iaPreviewOverlay");
        iaPreviewData = null;

    } catch (e) {
        alert("Error aplicando config: " + e.message);
    }
}

// ═══════════════ CONFIG SELECTOR ═══════════════

async function cargarConfigSelector(projectId) {
    try {
        const configs = await apiGet(`projects/${projectId}/configs`);
        const select = document.getElementById("configSelector");
        select.innerHTML = configs.map(c =>
            `<option value="${c.id}" ${c.is_active ? 'selected' : ''}>${c.nombre} ${c.is_active ? '(activa)' : ''}</option>`
        ).join("");
    } catch (e) { /* ignore */ }
}

async function cambiarConfig(configId) {
    if (!currentProject || !configId) return;
    try {
        await apiPut(`projects/${currentProject.id}/configs/${configId}/activate`);
        // Recargar proyecto
        abrirProyecto(currentProject.id);
    } catch (e) {
        alert("Error: " + e.message);
    }
}

// ═══════════════ GUARDAR CONFIG ═══════════════

async function guardarConfig() {
    if (!config || !currentProject) return;
    try {
        const configId = config.id;
        if (configId) {
            await apiPut(`projects/${currentProject.id}/configs/${configId}`, config);
        }
    } catch (e) {
        console.error("Error guardando config:", e);
    }
}

// ═══════════════ IMPORT/EXPORT ═══════════════

function importConfigDirect() {
    document.getElementById("fileImportDirect").click();
}

async function handleImportDirect(event) {
    const file = event.target.files[0];
    if (!file || !currentProject) return;
    const reader = new FileReader();
    reader.onload = async (e) => {
        try {
            const data = JSON.parse(e.target.result);
            if (!data.perfiles || data.perfiles.length < 3) {
                alert("El JSON debe tener al menos 3 perfiles");
                return;
            }
            if (!data.tendencias_escalas || data.tendencias_escalas.length < 3) {
                alert("El JSON debe tener al menos 3 tendencias");
                return;
            }
            if (!data.reglas_dependencia || data.reglas_dependencia.length < 1) {
                alert("El JSON debe tener al menos 1 regla");
                return;
            }

            const result = await apiPost(`projects/${currentProject.id}/configs`, {
                nombre: data.nombre || file.name.replace('.json', ''),
                perfiles: data.perfiles,
                reglas_dependencia: data.reglas_dependencia,
                tendencias_escalas: data.tendencias_escalas,
            });

            config = result;
            mostrarConfiguracion(result);
            cargarConfigSelector(currentProject.id);
            setStep(3);
            showEl("seccion3");
            showEl("seccion4");
            alert("Config importada correctamente");
        } catch (err) {
            alert("Error: " + err.message);
        }
    };
    reader.readAsText(file);
    event.target.value = "";
}

// ═══════════════ HISTORIAL EJECUCIONES ═══════════════

async function cargarHistorialEjecuciones(projectId) {
    const container = document.getElementById("projectExecHistory");
    if (!container) return;
    try {
        const execs = await apiGet(`projects/${projectId}/executions`);
        if (!execs.length) {
            container.innerHTML = '<div class="empty-state-sm">Sin ejecuciones previas</div>';
            return;
        }
        container.innerHTML = execs.map(e => `
            <div class="history-item exec-item">
                <div class="history-title">
                    <span class="status-dot" style="background:${statusColor(e.status)}"></span>
                    ${e.exitosas || 0}/${e.total || 0} exitosas
                </div>
                <div class="history-meta">
                    ${e.tiempo_transcurrido || '?'} | ${e.status} | ${timeAgo(e.created_at)}
                    ${e.excel ? `<a href="${API}/projects/${projectId}/download?execution_id=${e.id}" class="download-link">Excel</a>` : ''}
                </div>
            </div>
        `).join("");
    } catch (e) {
        if (container) container.innerHTML = '<div class="empty-state-sm">Error</div>';
    }
}

// ═══════════════ DASHBOARD ═══════════════

let dashboardInterval = null;

async function pollDashboard() {
    if (dashboardInterval) clearInterval(dashboardInterval);

    async function update() {
        try {
            const data = await apiGet("dashboard");
            const container = document.getElementById("dashboardContent");

            if (!data.activos) {
                container.innerHTML = '<div class="empty-state">No hay ejecuciones activas</div>';
                return;
            }

            container.innerHTML = data.proyectos.map(item => {
                const p = item.project;
                const e = item.execution;
                const pct = e.total > 0 ? Math.round((e.progreso / e.total) * 100) : 0;

                return `<div class="dashboard-card">
                    <div class="dashboard-card-header">
                        <h3>${p.nombre}</h3>
                        <span class="project-status status-ejecutando">Ejecutando</span>
                    </div>
                    <div class="progress-bar-bg">
                        <div class="progress-bar-fill" style="width:${pct}%">${pct}%</div>
                    </div>
                    <div class="stats mini">
                        <div class="stat ok"><div class="num">${e.exitosas}</div><div class="lbl">OK</div></div>
                        <div class="stat fail"><div class="num">${e.fallidas}</div><div class="lbl">Fail</div></div>
                        <div class="stat prog"><div class="num">${e.progreso}/${e.total}</div><div class="lbl">Progreso</div></div>
                    </div>
                    <div class="mensaje">${e.mensaje}</div>
                    <button class="btn btn-danger btn-sm mt-10" onclick="detenerDesde(${p.id})">Detener</button>
                </div>`;
            }).join("");
        } catch (e) {
            document.getElementById("dashboardContent").innerHTML =
                '<div class="empty-state">Error conectando al servidor</div>';
        }
    }

    await update();
    dashboardInterval = setInterval(update, 2000);
}

async function detenerDesde(projectId) {
    try {
        await apiPost(`projects/${projectId}/stop`);
    } catch (e) { /* ignore */ }
}
