/* Paso 2-3: Analizar y configurar perfiles, tendencias, reglas */

function mostrarConfiguracion(cfg) {
    showEl("seccion3");
    showEl("seccion4");
    renderPerfiles(cfg.perfiles);
    renderTendencias(cfg.tendencias_escalas);
    renderReglas(cfg.reglas_dependencia);
}

// ==================== PERFILES ====================

function renderPerfiles(perfiles) {
    if (!perfiles || perfiles.length === 0) {
        document.getElementById("perfilesList").innerHTML =
            '<div class="empty-state">No hay perfiles. Agrega uno para empezar.</div>';
        return;
    }

    const totalFreq = perfiles.reduce((s, p) => s + (p.frecuencia || 0), 0);
    let html = `<div class="freq-total ${totalFreq === 100 ? 'ok' : 'warn'}">Total frecuencias: ${totalFreq}%</div>`;

    perfiles.forEach((p, i) => {
        let respHtml = "";
        const entries = Object.entries(p.respuestas || {});
        const shown = entries.slice(0, 4);
        const more = entries.length - shown.length;

        for (const [preg, cfg] of shown) {
            respHtml += `<div><strong>${truncar(preg, 35)}:</strong> ${formatRespuesta(cfg)}</div>`;
        }
        if (more > 0) respHtml += `<div class="more">+${more} respuestas mas</div>`;

        html += `<div class="perfil-card">
            <div class="perfil-header">
                <h3>${p.nombre}</h3>
                <span class="perfil-freq">${p.frecuencia}%</span>
            </div>
            <div class="perfil-desc">${p.descripcion || ''}</div>
            <div class="perfil-respuestas">${respHtml}</div>
            <div class="perfil-actions">
                <button class="btn btn-primary btn-sm" onclick="editarPerfil(${i})">Editar</button>
                <button class="btn btn-outline btn-sm" onclick="duplicarPerfil(${i})">Duplicar</button>
                ${perfiles.length > 3 ? `<button class="btn btn-danger btn-sm" onclick="eliminarPerfil(${i})">Eliminar</button>` : ''}
            </div>
        </div>`;
    });
    document.getElementById("perfilesList").innerHTML = html;
}

function editarPerfil(idx) {
    const p = config.perfiles[idx];
    abrirModal("Editar perfil", `
        <div class="form-group">
            <label>Nombre del perfil</label>
            <input id="mNombre" value="${p.nombre}" placeholder="Ej: Joven estudiante">
        </div>
        <div class="form-group">
            <label>Descripcion</label>
            <input id="mDesc" value="${p.descripcion || ''}" placeholder="Ej: Estudiante universitario 18-25">
        </div>
        <div class="form-group">
            <label>Frecuencia</label>
            <div class="freq-slider">
                <input type="range" id="mFreq" min="1" max="100" value="${p.frecuencia}"
                    oninput="document.getElementById('mFreqVal').textContent = this.value + '%'">
                <span class="freq-value" id="mFreqVal">${p.frecuencia}%</span>
            </div>
        </div>
        <div class="form-group">
            <label>Respuestas (JSON)</label>
            <textarea id="mResp" rows="10">${JSON.stringify(p.respuestas || {}, null, 2)}</textarea>
            <span class="help-text">Tipos: "fijo" (valor), "rango" (min/max), "aleatorio" (opciones con %)</span>
        </div>
    `, () => {
        try {
            config.perfiles[idx] = {
                nombre: document.getElementById("mNombre").value,
                descripcion: document.getElementById("mDesc").value,
                frecuencia: parseInt(document.getElementById("mFreq").value),
                respuestas: JSON.parse(document.getElementById("mResp").value),
            };
            renderPerfiles(config.perfiles);
            guardarConfig();
        } catch (e) {
            alert("JSON invalido: " + e.message);
            return false;
        }
    });
}

function eliminarPerfil(idx) {
    if (config.perfiles.length <= 3) {
        return alert("No se puede eliminar. Minimo 3 perfiles requeridos.");
    }
    if (confirm("Eliminar este perfil?")) {
        config.perfiles.splice(idx, 1);
        renderPerfiles(config.perfiles);
        guardarConfig();
    }
}

function duplicarPerfil(idx) {
    const clon = JSON.parse(JSON.stringify(config.perfiles[idx]));
    clon.nombre += " (copia)";
    clon.frecuencia = 5;
    config.perfiles.push(clon);
    renderPerfiles(config.perfiles);
    guardarConfig();
}

function agregarPerfil() {
    if (!config) config = { perfiles: [], reglas_dependencia: [], tendencias_escalas: [] };
    config.perfiles.push({
        nombre: "Nuevo perfil",
        descripcion: "",
        frecuencia: 10,
        respuestas: {},
    });
    renderPerfiles(config.perfiles);
    editarPerfil(config.perfiles.length - 1);
}

// ==================== TENDENCIAS ====================

function _getDistribuciones(t) {
    if (t.distribuciones && typeof t.distribuciones === "object") return t.distribuciones;
    if (t.distribucion) return { [t.distribucion.length]: t.distribucion };
    return { "5": [20, 20, 20, 20, 20] };
}

function renderTendencias(tendencias) {
    if (!tendencias || tendencias.length === 0) {
        document.getElementById("tendenciasList").innerHTML =
            '<div class="empty-state">No hay tendencias.</div>';
        return;
    }

    const totalFreq = tendencias.reduce((s, t) => s + (t.frecuencia || 0), 0);
    let html = `<div class="freq-total ${totalFreq === 100 ? 'ok' : 'warn'}">Total frecuencias: ${totalFreq}%</div>`;

    tendencias.forEach((t, i) => {
        const dists = _getDistribuciones(t);
        let chartsHtml = "";

        for (const [escala, dist] of Object.entries(dists)) {
            const maxVal = Math.max(...dist, 1);
            const barsHtml = dist.map((v) =>
                `<div class="tendencia-bar" style="height:${Math.max(6, (v / maxVal) * 40)}px" data-val="${v}"></div>`
            ).join("");
            let labelsHtml = '<div class="tendencia-labels">';
            for (let li = 0; li < dist.length; li++) labelsHtml += `<span>${li + 1}</span>`;
            labelsHtml += '</div>';
            chartsHtml += `<div class="dist-chart">
                <div class="dist-chart-label">Escala 1-${escala}</div>
                <div class="tendencia-dist">${barsHtml}</div>
                ${labelsHtml}
            </div>`;
        }

        html += `<div class="tendencia-card">
            <div class="tendencia-header">
                <div>
                    <h4>${t.nombre}</h4>
                    <div class="tendencia-desc">${t.descripcion || ''}</div>
                </div>
                <div class="flex-gap">
                    <span class="tendencia-freq">${t.frecuencia}%</span>
                    <button class="btn btn-primary btn-sm" onclick="editarTendencia(${i})">Editar</button>
                    ${tendencias.length > 3 ? `<button class="btn btn-danger btn-sm" onclick="eliminarTendencia(${i})">X</button>` : ''}
                </div>
            </div>
            <div class="dist-charts">${chartsHtml}</div>
        </div>`;
    });
    document.getElementById("tendenciasList").innerHTML = html;
}

function editarTendencia(idx) {
    const t = config.tendencias_escalas[idx];
    const dists = _getDistribuciones(t);

    let distsHtml = '<div id="distsContainer">';
    for (const [escala, dist] of Object.entries(dists)) {
        distsHtml += `<div class="dist-editor" data-escala="${escala}">
            <div class="dist-editor-header">
                <strong>Escala 1-${escala}</strong>
                <button class="btn btn-danger btn-sm" onclick="this.closest('.dist-editor').remove()">Quitar</button>
            </div>`;
        dist.forEach((v, i) => {
            distsHtml += `<div class="dist-row">
                <span class="dist-label">${i + 1}</span>
                <input type="range" min="0" max="100" value="${v}" class="dist-input"
                    oninput="actualizarDistTotal(this)">
                <span class="dist-val">${v}%</span>
            </div>`;
        });
        distsHtml += `<div class="dist-total">Total: ${dist.reduce((a, b) => a + b, 0)}%</div>`;
        distsHtml += '</div>';
    }
    distsHtml += `<div class="mt-5">
        <button class="btn btn-outline btn-sm" onclick="agregarEscala()">+ Agregar escala</button>
    </div></div>`;

    abrirModal("Editar tendencia", `
        <div class="form-group">
            <label>Nombre</label>
            <input id="mNombre" value="${t.nombre}">
        </div>
        <div class="form-group">
            <label>Descripcion</label>
            <input id="mDesc" value="${t.descripcion || ''}">
        </div>
        <div class="form-group">
            <label>Frecuencia</label>
            <div class="freq-slider">
                <input type="range" id="mFreq" min="1" max="100" value="${t.frecuencia}"
                    oninput="document.getElementById('mFreqVal').textContent = this.value + '%'">
                <span class="freq-value" id="mFreqVal">${t.frecuencia}%</span>
            </div>
        </div>
        <div class="form-group">
            <label>Distribuciones por escala</label>
            ${distsHtml}
        </div>
    `, () => {
        const distribuciones = {};
        document.querySelectorAll("#distsContainer .dist-editor").forEach(editor => {
            const escala = editor.dataset.escala;
            const valores = [];
            editor.querySelectorAll(".dist-input").forEach(input => {
                valores.push(parseInt(input.value));
            });
            if (valores.length > 0) distribuciones[escala] = valores;
        });
        config.tendencias_escalas[idx] = {
            nombre: document.getElementById("mNombre").value,
            descripcion: document.getElementById("mDesc").value,
            frecuencia: parseInt(document.getElementById("mFreq").value),
            distribuciones: distribuciones,
        };
        renderTendencias(config.tendencias_escalas);
        guardarConfig();
    });
}

function actualizarDistTotal(inputEl) {
    const editor = inputEl.closest(".dist-editor");
    inputEl.nextElementSibling.textContent = inputEl.value + "%";
    let sum = 0;
    editor.querySelectorAll(".dist-input").forEach(el => sum += parseInt(el.value));
    const totalEl = editor.querySelector(".dist-total");
    totalEl.textContent = `Total: ${sum}%`;
    totalEl.className = sum === 100 ? "dist-total" : "dist-total warn";
}

function agregarEscala() {
    const size = prompt("Tamaño de la escala (ej: 5, 7, 10):");
    if (!size || isNaN(size) || size < 2) return;
    const n = parseInt(size);
    const container = document.getElementById("distsContainer");
    const base = Math.floor(100 / n);
    const valores = Array(n).fill(base);
    valores[Math.floor(n / 2)] += 100 - base * n;

    let html = `<div class="dist-editor" data-escala="${n}">
        <div class="dist-editor-header">
            <strong>Escala 1-${n}</strong>
            <button class="btn btn-danger btn-sm" onclick="this.closest('.dist-editor').remove()">Quitar</button>
        </div>`;
    valores.forEach((v, i) => {
        html += `<div class="dist-row">
            <span class="dist-label">${i + 1}</span>
            <input type="range" min="0" max="100" value="${v}" class="dist-input"
                oninput="actualizarDistTotal(this)">
            <span class="dist-val">${v}%</span>
        </div>`;
    });
    html += `<div class="dist-total">Total: 100%</div></div>`;
    container.querySelector(".mt-5").insertAdjacentHTML("beforebegin", html);
}

function eliminarTendencia(idx) {
    if (config.tendencias_escalas.length <= 3) {
        return alert("No se puede eliminar. Minimo 3 tendencias requeridas.");
    }
    if (confirm("Eliminar esta tendencia?")) {
        config.tendencias_escalas.splice(idx, 1);
        renderTendencias(config.tendencias_escalas);
        guardarConfig();
    }
}

function agregarTendencia() {
    if (!config) config = { perfiles: [], reglas_dependencia: [], tendencias_escalas: [] };
    config.tendencias_escalas.push({
        nombre: "Nueva tendencia",
        descripcion: "",
        frecuencia: 10,
        distribuciones: {
            "5": [20, 20, 20, 20, 20],
            "7": [14, 14, 15, 14, 15, 14, 14],
        },
    });
    renderTendencias(config.tendencias_escalas);
    editarTendencia(config.tendencias_escalas.length - 1);
}

// ==================== REGLAS ====================

function renderReglas(reglas) {
    if (!reglas || reglas.length === 0) {
        document.getElementById("reglasList").innerHTML =
            '<div class="empty-state">No hay reglas de dependencia.</div>';
        return;
    }

    let html = "";
    reglas.forEach((r, i) => {
        const forzarText = r.entonces_forzar ? `= "${r.entonces_forzar}"` : '';
        const excluirText = r.entonces_excluir?.length ? `excluir: ${r.entonces_excluir.join(', ')}` : '';

        html += `<div class="regla-item">
            <div class="regla-content">
                <span class="si">SI</span>
                ${truncar(r.si_pregunta, 35)} <strong>${r.operador}</strong> "${r.si_valor}"
                <br>
                <span class="entonces">ENTONCES</span>
                ${truncar(r.entonces_pregunta, 35)} ${forzarText} ${excluirText}
            </div>
            <div class="regla-actions">
                <button class="btn btn-primary btn-sm" onclick="editarRegla(${i})">Editar</button>
                <button class="btn btn-danger btn-sm" onclick="eliminarRegla(${i})">X</button>
            </div>
        </div>`;
    });
    document.getElementById("reglasList").innerHTML = html;
}

function editarRegla(idx) {
    const r = config.reglas_dependencia[idx];

    let preguntasOptions = '<option value="">-- Seleccionar --</option>';
    if (estructura) {
        const paginas = estructura.paginas || estructura.estructura?.paginas || [];
        paginas.forEach((pag) => {
            (pag.preguntas || []).forEach((p) => {
                if (p.tipo !== "informativo") {
                    const escaped = p.texto.replace(/"/g, '&quot;');
                    preguntasOptions += `<option value="${escaped}">${truncar(p.texto, 60)}</option>`;
                }
            });
        });
    }

    abrirModal("Editar regla", `
        <div class="form-group">
            <label>SI esta pregunta...</label>
            <select id="mSiPregunta">${preguntasOptions}</select>
        </div>
        <div class="form-group">
            <label>Tiene este valor</label>
            <input id="mSiValor" value="${r.si_valor || ''}">
        </div>
        <div class="form-group">
            <label>Condicion</label>
            <select id="mOperador">
                <option value="igual" ${r.operador === 'igual' ? 'selected' : ''}>Igual (=)</option>
                <option value="diferente" ${r.operador === 'diferente' ? 'selected' : ''}>Diferente (!=)</option>
                <option value="menor" ${r.operador === 'menor' ? 'selected' : ''}>Menor (&lt;)</option>
                <option value="mayor" ${r.operador === 'mayor' ? 'selected' : ''}>Mayor (&gt;)</option>
            </select>
        </div>
        <div class="form-group">
            <label>ENTONCES en esta pregunta...</label>
            <select id="mEntPregunta">${preguntasOptions}</select>
        </div>
        <div class="form-group">
            <label>Forzar valor (opcional)</label>
            <input id="mEntForzar" value="${r.entonces_forzar || ''}">
        </div>
        <div class="form-group">
            <label>Excluir opciones (separadas por coma)</label>
            <input id="mEntExcluir" value="${(r.entonces_excluir || []).join(', ')}">
        </div>
    `, () => {
        config.reglas_dependencia[idx] = {
            si_pregunta: document.getElementById("mSiPregunta").value,
            si_valor: document.getElementById("mSiValor").value,
            operador: document.getElementById("mOperador").value,
            entonces_pregunta: document.getElementById("mEntPregunta").value,
            entonces_forzar: document.getElementById("mEntForzar").value.trim() || null,
            entonces_excluir: document.getElementById("mEntExcluir").value.trim()
                ? document.getElementById("mEntExcluir").value.split(",").map(s => s.trim())
                : [],
        };
        renderReglas(config.reglas_dependencia);
        guardarConfig();
    });

    setTimeout(() => {
        const siEl = document.getElementById("mSiPregunta");
        const entEl = document.getElementById("mEntPregunta");
        if (siEl) siEl.value = r.si_pregunta || '';
        if (entEl) entEl.value = r.entonces_pregunta || '';
    }, 50);
}

function eliminarRegla(idx) {
    if (confirm("Eliminar esta regla?")) {
        config.reglas_dependencia.splice(idx, 1);
        renderReglas(config.reglas_dependencia);
        guardarConfig();
    }
}

function agregarRegla() {
    if (!config) config = { perfiles: [], reglas_dependencia: [], tendencias_escalas: [] };
    config.reglas_dependencia.push({
        si_pregunta: "",
        si_valor: "",
        operador: "igual",
        entonces_pregunta: "",
        entonces_forzar: null,
        entonces_excluir: [],
    });
    renderReglas(config.reglas_dependencia);
    editarRegla(config.reglas_dependencia.length - 1);
}
