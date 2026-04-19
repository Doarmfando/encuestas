/* Estado global y navegación entre vistas */

let currentProject = null;   // Proyecto actualmente abierto
let config = null;            // Config activa del proyecto
let estructura = null;        // Estructura scrapeada
let preguntasVisible = true;
let currentExecutionId = null;
let iaPreviewData = null;     // Data temporal del preview IA
let manualStructure = null;
let manualTab = "detected";

const MANUAL_BUTTONS = ["Siguiente", "Atrás", "Enviar", "Borrar formulario"];
const MANUAL_TYPES = [
    "informativo",
    "texto",
    "parrafo",
    "numero",
    "opcion_multiple",
    "seleccion_multiple",
    "desplegable",
    "escala_lineal",
    "likert",
    "nps",
    "ranking",
    "matriz",
    "matriz_checkbox",
    "fecha",
    "hora",
    "archivo",
    "seccion",
    "desconocido",
];
const MANUAL_OPTION_TYPES = new Set([
    "opcion_multiple",
    "seleccion_multiple",
    "desplegable",
    "escala_lineal",
    "likert",
    "nps",
    "ranking",
    "matriz",
    "matriz_checkbox",
]);

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
    manualStructure = null;
    manualTab = "detected";
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
        manualStructure = null;
        manualTab = "detected";

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
                await cargarConfigSelector(projectId);
                setStep(4);
            } else {
                await cargarConfigSelector(projectId);
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

async function scrapeProject(overridePlatform) {
    if (!currentProject) return;

    const btn = document.getElementById("btnScrape");
    const btnMs = document.getElementById("btnScrapeMsForms");
    const headless = document.getElementById("scrapeHeadless").checked;
    const manual = document.getElementById("scrapeManual")?.checked;
    if (manual) {
        abrirManualEditor();
        return;
    }

    // Si nos pasaron override, lo usamos; si no, leemos el select.
    // "auto" => detección por URL en el backend (no se envía force_platform).
    const platformSelect = document.getElementById("scrapePlatform");
    const selected = overridePlatform || (platformSelect ? platformSelect.value : "auto");
    const forcePlatform = (selected && selected !== "auto") ? selected : null;
    if (forcePlatform && platformSelect) platformSelect.value = forcePlatform;

    btn.disabled = true;
    if (btnMs) btnMs.disabled = true;
    btn.textContent = "Scrapeando...";
    hideEl("scrapeError");

    try {
        const payload = { headless };
        if (forcePlatform) payload.force_platform = forcePlatform;
        const data = await apiPost(`projects/${currentProject.id}/scrape`, payload);
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
        if (btnMs) btnMs.disabled = false;
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
    // Mantener global sincronizado para editar/eliminar desde la vista detectada
    estructura = { ...(estructura || {}), ...data, paginas };
    manualStructure = { paginas: JSON.parse(JSON.stringify(paginas || [])) };
    let html = "";
    let nGlobal = 0; // numeración continua entre páginas
    paginas.forEach((pag, pIdx) => {
        html += `<div class="page-header">
            Pagina ${pag.numero} <span class="page-buttons">${(pag.botones || []).join(", ") || "sin botones"}</span>
        </div>`;
        (pag.preguntas || []).forEach((p, qIdx) => {
            nGlobal += 1;
            const isMatrix = p.tipo === "matriz" || p.tipo === "matriz_checkbox";
            const tipoClass = p.tipo.includes("escala") ? "likert" :
                              p.tipo.includes("opcion") ? "radio" :
                              p.tipo.includes("seleccion") ? "check" :
                              (p.tipo.includes("texto") || p.tipo === "numero" || p.tipo === "parrafo") ? "text" :
                              p.tipo === "desplegable" ? "drop" : "";
            const opcionesPreview = p.opciones?.length
                ? '<div class="opciones-preview">' +
                    (isMatrix ? 'Columnas: ' : '') +
                    p.opciones.slice(0, 6).join(" | ") +
                    (p.opciones.length > 6 ? ` (+${p.opciones.length - 6})` : '') +
                  '</div>'
                : '';
            const filasPreview = p.filas?.length
                ? '<div class="opciones-preview">' +
                    'Filas: ' +
                    p.filas.slice(0, 4).join(" | ") +
                    (p.filas.length > 4 ? ` (+${p.filas.length - 4})` : '') +
                  '</div>'
                : '';
            html += `<div class="pregunta-item">
                <div class="pregunta-text">
                    <span class="pregunta-num">${nGlobal}.</span>
                    ${p.texto}${p.obligatoria ? '<span class="obligatoria">*</span>' : ''}
                    ${filasPreview}
                    ${opcionesPreview}
                </div>
                <span class="tipo ${tipoClass}">${p.tipo}</span>
                <div class="pregunta-actions flex-gap">
                    <button class="btn btn-outline btn-sm" onclick="editarPreguntaDetectada(${pIdx}, ${qIdx})">Editar</button>
                    <button class="btn btn-danger btn-sm" onclick="eliminarPreguntaDetectada(${pIdx}, ${qIdx})">Eliminar</button>
                </div>
            </div>`;
        });
    });
    document.getElementById("preguntasList").innerHTML = html;
    preguntasVisible = true;
    showManualTab(manualTab);
}

// ═══════════════ EDITAR ESTRUCTURA DETECTADA ═══════════════

function escapeHtmlAttr(s) {
    return String(s == null ? "" : s)
        .replace(/&/g, "&amp;")
        .replace(/"/g, "&quot;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

async function persistirEstructuraDetectada() {
    if (!currentProject || !estructura) return;
    const result = await apiPost(`projects/${currentProject.id}/manual-structure`, {
        paginas: estructura.paginas || [],
    });
    estructura = { ...estructura, ...result };
    currentProject.estructura = { paginas: result.paginas || [] };
    currentProject.total_preguntas = result.total_preguntas;
    currentProject.status = "scrapeado";
    mostrarEstructura(result);
}

function editarPreguntaDetectada(pageIdx, qIdx) {
    const paginas = (estructura && estructura.paginas) || [];
    const pregunta = paginas[pageIdx] && paginas[pageIdx].preguntas && paginas[pageIdx].preguntas[qIdx];
    if (!pregunta) return;

    const opcionesText = (pregunta.opciones || []).join("\n");

    const html = `
        <div class="form-group">
            <label>Texto de la pregunta</label>
            <input type="text" id="editPregTexto" value="${escapeHtmlAttr(pregunta.texto)}">
        </div>
        <div class="form-group">
            <label>Tipo</label>
            <select id="editPregTipo">
                ${MANUAL_TYPES.map(t => `<option value="${t}" ${pregunta.tipo === t ? "selected" : ""}>${t}</option>`).join("")}
            </select>
        </div>
        <div class="form-group">
            <label class="checkbox-label">
                <input type="checkbox" id="editPregObligatoria" ${pregunta.obligatoria ? "checked" : ""}>
                Obligatoria
            </label>
        </div>
        <div class="form-group">
            <label>Opciones (una por linea)</label>
            <textarea id="editPregOpciones" rows="6">${escapeHtmlAttr(opcionesText)}</textarea>
            <div class="help-text">Solo aplica a tipos con opciones (opcion_multiple, seleccion_multiple, desplegable, escala_lineal, likert, nps, ranking, matriz, matriz_checkbox).</div>
        </div>
    `;

    abrirModal("Editar pregunta detectada", html, () => {
        const texto = (document.getElementById("editPregTexto").value || "").trim();
        const tipo = document.getElementById("editPregTipo").value;
        const obligatoria = document.getElementById("editPregObligatoria").checked;
        const opcionesRaw = document.getElementById("editPregOpciones").value;
        const opciones = String(opcionesRaw || "")
            .split("\n").map(t => t.trim()).filter(Boolean);

        if (!texto) {
            alert("El texto es requerido");
            return false;
        }

        pregunta.texto = texto;
        pregunta.tipo = tipo;
        pregunta.obligatoria = obligatoria;
        pregunta.opciones = MANUAL_OPTION_TYPES.has(tipo) ? opciones : [];

        persistirEstructuraDetectada().catch(e => {
            alert("Error guardando: " + (e.message || e));
        });
    });
}

async function eliminarPreguntaDetectada(pageIdx, qIdx) {
    if (!estructura || !estructura.paginas) return;
    const pagina = estructura.paginas[pageIdx];
    if (!pagina || !pagina.preguntas || !pagina.preguntas[qIdx]) return;
    if (!confirm("Eliminar esta pregunta detectada?")) return;

    const backup = JSON.parse(JSON.stringify(estructura.paginas));
    pagina.preguntas.splice(qIdx, 1);

    try {
        await persistirEstructuraDetectada();
    } catch (e) {
        estructura.paginas = backup;
        mostrarEstructura(estructura);
        alert("Error eliminando: " + (e.message || e));
    }
}

function abrirManualEditor() {
    showEl("seccion2");
    setStep(2);
    ensureManualStructure();
    document.getElementById("infoForm").innerHTML =
        `<strong>${currentProject?.nombre || "Sin titulo"}</strong>` +
        `<br>${(manualStructure.paginas || []).length} paginas | ` +
        `${(manualStructure.paginas || []).reduce((acc, p) => acc + (p.preguntas || []).length, 0)} preguntas`;
    showManualTab("form");
}

function ensureManualStructure() {
    if (!manualStructure || !Array.isArray(manualStructure.paginas)) {
        const base = (estructura && Array.isArray(estructura.paginas)) ? estructura.paginas : [];
        manualStructure = { paginas: JSON.parse(JSON.stringify(base)) };
    }
    if (!manualStructure.paginas.length) {
        manualStructure.paginas = [{
            numero: 1,
            botones: ["Siguiente"],
            preguntas: [],
        }];
    }
}

function showManualTab(tabName, btnEl) {
    manualTab = tabName || "detected";
    document.querySelectorAll(".manual-tab-content").forEach(el => el.classList.add("hidden"));
    document.querySelectorAll(".manual-tabs .tab").forEach(el => el.classList.remove("active"));

    const tabIdMap = {
        detected: "manualTabDetected",
        form: "manualTabForm",
        json: "manualTabJson",
    };
    const targetId = tabIdMap[manualTab] || "manualTabDetected";
    document.getElementById(targetId)?.classList.remove("hidden");
    if (btnEl) btnEl.classList.add("active");

    if (manualTab === "form") {
        ensureManualStructure();
        renderManualForm();
    }
    if (manualTab === "json") {
        cargarManualJson(false);
    }
}

function cargarManualDesdeDetectada() {
    manualStructure = { paginas: JSON.parse(JSON.stringify((estructura && estructura.paginas) || [])) };
    ensureManualStructure();
    renderManualForm();
}

function cargarManualJson(force = true) {
    const editor = document.getElementById("manualJsonEditor");
    if (!editor) return;
    if (!force && editor.value && editor.value.trim()) return;
    ensureManualStructure();
    editor.value = JSON.stringify({ paginas: manualStructure.paginas }, null, 2);
}

function agregarManualPagina() {
    ensureManualStructure();
    manualStructure.paginas.push({
        numero: manualStructure.paginas.length + 1,
        botones: ["Siguiente"],
        preguntas: [],
    });
    renderManualForm();
}

function eliminarManualPagina(idx) {
    ensureManualStructure();
    if (manualStructure.paginas.length <= 1) {
        alert("Debe existir al menos una pagina");
        return;
    }
    manualStructure.paginas.splice(idx, 1);
    renderManualForm();
}

function agregarManualPregunta(pageIdx) {
    ensureManualStructure();
    manualStructure.paginas[pageIdx].preguntas.push({
        texto: "",
        tipo: "texto",
        obligatoria: false,
        opciones: [],
    });
    renderManualForm();
}

function eliminarManualPregunta(pageIdx, qIdx) {
    ensureManualStructure();
    manualStructure.paginas[pageIdx].preguntas.splice(qIdx, 1);
    renderManualForm();
}

function actualizarManualPregunta(pageIdx, qIdx, field, value) {
    ensureManualStructure();
    const pregunta = manualStructure.paginas[pageIdx].preguntas[qIdx];
    if (!pregunta) return;
    if (field === "obligatoria") {
        pregunta.obligatoria = Boolean(value);
        return;
    }
    if (field === "tipo") {
        pregunta.tipo = value;
        if (!MANUAL_OPTION_TYPES.has(value)) {
            pregunta.opciones = [];
        }
        renderManualForm();
        return;
    }
    if (field === "texto") {
        pregunta.texto = value;
    }
}

function actualizarOpcionesManual(pageIdx, qIdx, raw) {
    ensureManualStructure();
    const pregunta = manualStructure.paginas[pageIdx].preguntas[qIdx];
    if (!pregunta) return;
    const opciones = String(raw || "")
        .split("\n")
        .map(t => t.trim())
        .filter(Boolean);
    pregunta.opciones = opciones;
}

function toggleManualBoton(pageIdx, boton, checked) {
    ensureManualStructure();
    const botones = manualStructure.paginas[pageIdx].botones || [];
    const next = new Set(botones);
    if (checked) next.add(boton);
    else next.delete(boton);
    manualStructure.paginas[pageIdx].botones = Array.from(next);
}

function renderManualForm() {
    ensureManualStructure();
    const container = document.getElementById("manualFormContainer");
    if (!container) return;
    const paginas = manualStructure.paginas || [];
    let html = "";
    let nGlobal = 0;

    paginas.forEach((pag, pIdx) => {
        html += `<div class="manual-page">
            <div class="manual-page-head">
                <strong>Pagina ${pIdx + 1}</strong>
                <div class="flex-gap">
                    <button class="btn btn-outline btn-sm" onclick="agregarManualPregunta(${pIdx})">+ Pregunta</button>
                    <button class="btn btn-danger btn-sm" onclick="eliminarManualPagina(${pIdx})">Eliminar pagina</button>
                </div>
            </div>
            <div class="manual-badges">
                ${MANUAL_BUTTONS.map(btn => `
                    <label>
                        <input type="checkbox" ${pag.botones?.includes(btn) ? "checked" : ""} onchange="toggleManualBoton(${pIdx}, '${btn}', this.checked)">
                        ${btn}
                    </label>
                `).join("")}
            </div>
        `;

        const preguntas = pag.preguntas || [];
        if (!preguntas.length) {
            html += `<div class="empty-state-sm" style="margin-top:8px">Sin preguntas</div>`;
        }

        preguntas.forEach((preg, qIdx) => {
            nGlobal += 1;
            const opcionesText = (preg.opciones || []).join("\n");
            const needsOptions = MANUAL_OPTION_TYPES.has(preg.tipo);
            html += `<div class="manual-question">
                <div class="row">
                    <span class="pregunta-num">${nGlobal}.</span>
                    <input type="text" placeholder="Texto de la pregunta" value="${(preg.texto || "").replace(/"/g, "&quot;")}"
                        onchange="actualizarManualPregunta(${pIdx}, ${qIdx}, 'texto', this.value)">

                    <select onchange="actualizarManualPregunta(${pIdx}, ${qIdx}, 'tipo', this.value)">
                        ${MANUAL_TYPES.map(t => `<option value="${t}" ${preg.tipo === t ? "selected" : ""}>${t}</option>`).join("")}
                    </select>
                    <label class="checkbox-label">
                        <input type="checkbox" ${preg.obligatoria ? "checked" : ""} onchange="actualizarManualPregunta(${pIdx}, ${qIdx}, 'obligatoria', this.checked)">
                        Obligatoria
                    </label>
                </div>
                <div class="row">
                    <textarea placeholder="Opciones (una por linea)" ${needsOptions ? "" : "disabled"}
                        onchange="actualizarOpcionesManual(${pIdx}, ${qIdx}, this.value)">${opcionesText}</textarea>
                    <div></div>
                    <button class="btn btn-outline btn-sm" onclick="eliminarManualPregunta(${pIdx}, ${qIdx})">Eliminar</button>
                </div>
            </div>`;
        });

        html += `</div>`;
    });

    container.innerHTML = html;
}

async function guardarManualEstructura() {
    if (!currentProject) return;
    ensureManualStructure();
    try {
        const data = await apiPost(`projects/${currentProject.id}/manual-structure`, {
            paginas: manualStructure.paginas,
        });
        estructura = data;
        currentProject.estructura = { paginas: data.paginas || [] };
        currentProject.total_preguntas = data.total_preguntas;
        currentProject.status = "scrapeado";
        mostrarEstructura(data);
        const badge = document.getElementById("platformBadge");
        const plat = data.plataforma || "google_forms";
        badge.innerHTML = `${platformIcon(plat)} ${platformName(plat)}`;
        badge.className = `platform-badge ${plat}`;
        badge.classList.remove("hidden");
        alert("Estructura manual guardada");
    } catch (e) {
        alert(e.message || "Error guardando estructura manual");
    }
}

async function guardarManualJson() {
    if (!currentProject) return;
    const editor = document.getElementById("manualJsonEditor");
    if (!editor) return;
    let data;
    try {
        data = JSON.parse(editor.value || "{}");
    } catch (e) {
        alert("JSON invalido: " + e.message);
        return;
    }
    if (!data || !Array.isArray(data.paginas)) {
        alert("El JSON debe incluir un array 'paginas'");
        return;
    }
    try {
        const result = await apiPost(`projects/${currentProject.id}/manual-structure`, {
            paginas: data.paginas,
        });
        estructura = result;
        currentProject.estructura = { paginas: result.paginas || [] };
        currentProject.total_preguntas = result.total_preguntas;
        currentProject.status = "scrapeado";
        mostrarEstructura(result);
        const badge = document.getElementById("platformBadge");
        const plat = result.plataforma || "google_forms";
        badge.innerHTML = `${platformIcon(plat)} ${platformName(plat)}`;
        badge.className = `platform-badge ${plat}`;
        badge.classList.remove("hidden");
        alert("Estructura manual guardada");
    } catch (e) {
        alert(e.message || "Error guardando estructura manual");
    }
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

async function generarPlantilla() {
    if (!currentProject) return;
    if (!estructura && !currentProject.estructura) {
        alert("Primero scrapea el formulario");
        return;
    }
    try {
        const result = await apiPost(`projects/${currentProject.id}/template-config`, {});
        config = result;
        currentProject.config_activa = result;
        currentProject.status = "configurado";
        mostrarConfiguracion(result);
        await cargarConfigSelector(currentProject.id);
        setStep(3);
        alert("Plantilla generada. Puedes editarla antes de exportar.");
    } catch (e) {
        alert(e.message || "Error generando plantilla");
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
    if (perfiles.length < 3 || perfiles.length > 4) warnings.push("Se necesitan entre 3 y 4 perfiles");
    if (tendencias.length < 3 || tendencias.length > 4) warnings.push("Se necesitan entre 3 y 4 tendencias");
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
        currentProject.config_activa = result;
        currentProject.status = "configurado";
        mostrarConfiguracion(result);
        await cargarConfigSelector(currentProject.id);
        setStep(4);
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
        const summary = document.getElementById("configListSummary");

        if (!configs.length) {
            select.innerHTML = "";
            if (summary) {
                summary.innerHTML = '<div class="empty-state-sm">Sin configuraciones guardadas</div>';
            }
            return configs;
        }

        select.innerHTML = configs.map(c =>
            `<option value="${c.id}" ${c.is_active ? "selected" : ""}>${c.nombre} ${c.is_active ? "(activa)" : ""}</option>`
        ).join("");

        if (summary) {
            summary.innerHTML = configs.map(c => `
                <div class="history-item" onclick="cambiarConfig(${c.id})">
                    <div class="history-title">
                        <span class="config-badge ${c.is_active ? "active" : "inactive"}">${c.is_active ? "Activa" : "Guardada"}</span>
                        ${c.nombre}
                    </div>
                    <div class="history-meta">
                        <span>${c.total_perfiles || 0} perfiles</span>
                        <span>${c.total_tendencias || 0} tendencias</span>
                        <span>${c.total_reglas || 0} reglas</span>
                        <span>${c.ai_provider_used || "manual"}</span>
                        <span>${timeAgo(c.updated_at || c.created_at)}</span>
                    </div>
                </div>
            `).join("");
        }
        return configs;
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
            config = await apiPut(`projects/${currentProject.id}/configs/${configId}`, config);
            currentProject.config_activa = config;
            await cargarConfigSelector(currentProject.id);
        }
    } catch (e) {
        console.error("Error guardando config:", e);
    }
}

// ═══════════════ IMPORT/EXPORT ═══════════════

function importConfigDirect() {
    document.getElementById("fileImportDirect").click();
}

function validarImportacionConfig(data) {
    if (!data.perfiles || data.perfiles.length < 3) {
        throw new Error("El JSON debe tener al menos 3 perfiles");
    }
    if (!data.tendencias_escalas || data.tendencias_escalas.length < 3) {
        throw new Error("El JSON debe tener al menos 3 tendencias");
    }
}

async function importarConfigProyecto(data, fallbackName = "Importado") {
    if (!currentProject) throw new Error("No hay proyecto activo");

    validarImportacionConfig(data);
    const replaceExisting = Boolean(config?.id);
    const result = await apiPost(`projects/${currentProject.id}/configs`, {
        nombre: data.nombre || fallbackName,
        perfiles: data.perfiles,
        reglas_dependencia: data.reglas_dependencia,
        tendencias_escalas: data.tendencias_escalas,
        replace_existing: replaceExisting,
        replace_config_id: replaceExisting ? config.id : null,
    });

    config = result;
    currentProject.config_activa = result;
    currentProject.status = "configurado";
    mostrarConfiguracion(result);
    await cargarConfigSelector(currentProject.id);
    setStep(4);
    showEl("seccion3");
    showEl("seccion4");
    return { result, replaceExisting };
}

async function handleImportDirect(event) {
    const file = event.target.files[0];
    if (!file || !currentProject) return;
    const reader = new FileReader();
    reader.onload = async (e) => {
        try {
            const data = JSON.parse(e.target.result);
            const { replaceExisting } = await importarConfigProyecto(
                data,
                file.name.replace(/\.json$/i, "")
            );
            alert(replaceExisting ? "Config reemplazada correctamente" : "Config importada correctamente");
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
