/* Panel de gestion de prompts */

let promptsData = [];

async function loadPrompts() {
    const container = document.getElementById("promptsList");
    try {
        promptsData = await apiGet("prompts");
        if (!promptsData.length) {
            container.innerHTML = '<div class="empty-state-sm">No hay prompts configurados</div>';
            return;
        }

        let html = "";
        for (const p of promptsData) {
            const customBadge = p.is_default
                ? '<span style="color:var(--text-muted);font-size:11px">default</span>'
                : '<span style="color:var(--accent);font-size:11px">personalizado</span>';
            html += `
                <div class="prompt-item" style="border:1px solid var(--border);border-radius:8px;padding:10px;margin-bottom:8px">
                    <div class="flex-between" style="margin-bottom:5px">
                        <strong style="font-size:13px">${escapeHtml(p.nombre)}</strong>
                        ${customBadge}
                    </div>
                    <p style="font-size:11px;color:var(--text-muted);margin:0 0 8px 0">${escapeHtml(p.descripcion || '')}</p>
                    <div style="display:flex;gap:5px">
                        <button class="btn btn-outline btn-sm" onclick="editPrompt('${p.slug}')" style="font-size:11px">Editar</button>
                        ${!p.is_default ? `<button class="btn btn-outline btn-sm" onclick="resetPrompt('${p.slug}')" style="font-size:11px">Restaurar default</button>` : ''}
                    </div>
                </div>
            `;
        }
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = '<div class="empty-state-sm">Error cargando prompts</div>';
    }
}

async function editPrompt(slug) {
    try {
        const prompt = await apiGet(`prompts/${slug}`);
        const html = `
            <p style="font-size:12px;color:var(--text-muted);margin-bottom:10px">${escapeHtml(prompt.descripcion || '')}</p>
            <textarea id="promptEditArea" style="width:100%;height:400px;font-family:monospace;font-size:12px;
                background:var(--bg-secondary);color:var(--text);border:1px solid var(--border);
                border-radius:6px;padding:10px;resize:vertical">${escapeHtml(prompt.contenido)}</textarea>
        `;

        abrirModal(`Editar: ${prompt.nombre}`, html, () => {
            const contenido = document.getElementById("promptEditArea").value;
            if (contenido) {
                apiPut(`prompts/${slug}`, { contenido })
                    .then(() => loadPrompts())
                    .catch(e => alert("Error guardando: " + e.message));
            }
        });
    } catch (e) {
        alert("Error: " + e.message);
    }
}

async function resetPrompt(slug) {
    if (!confirm("Restaurar este prompt al valor por defecto?")) return;
    try {
        await apiPost(`prompts/${slug}/reset`);
        loadPrompts();
    } catch (e) {
        alert("Error: " + e.message);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
