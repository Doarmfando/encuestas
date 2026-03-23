/* Sistema de modales */

let modalCallback = null;

function abrirModal(titulo, contenidoHtml, onGuardar) {
    document.getElementById("modalTitulo").textContent = titulo;
    document.getElementById("modalContenido").innerHTML = contenidoHtml;
    modalCallback = onGuardar;
    showEl("modalOverlay");
    // Focus primer input
    setTimeout(() => {
        const first = document.querySelector("#modalContenido input, #modalContenido select, #modalContenido textarea");
        if (first) first.focus();
    }, 100);
}

function cerrarModal(e) {
    if (e.target === document.getElementById("modalOverlay")) {
        hideEl("modalOverlay");
    }
}

function cerrarModalBtn() {
    hideEl("modalOverlay");
}

function guardarModal() {
    if (modalCallback) {
        const result = modalCallback();
        if (result !== false) {
            hideEl("modalOverlay");
        }
    }
}

document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
        const overlay = document.getElementById("modalOverlay");
        if (overlay && !overlay.classList.contains("hidden")) {
            hideEl("modalOverlay");
        }
    }
});
