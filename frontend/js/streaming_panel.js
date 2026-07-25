/**
 * StreamingPanel — Renderizado incremental de Markdown con marked.js.
 *
 * Recibe chunks de texto y los renderiza progresivamente
 * en el panel de output usando marked.js.
 */
const StreamingPanel = (() => {
    let accumulated = '';
    let targetElement = null;

    /**
     * Inicializa el panel de streaming.
     * @param {string} elementId - ID del elemento contenedor
     */
    function init(elementId) {
        targetElement = document.getElementById(elementId);
        if (typeof marked !== 'undefined') {
            marked.setOptions({
                breaks: true,
                gfm: true,
                headerIds: false,
                mangle: false
            });
        }
    }

    /**
     * Agrega un chunk de contenido y re-renderiza.
     * @param {string} chunk - Texto markdown parcial
     */
    function appendChunk(chunk) {
        accumulated += chunk;
        render();
    }

    /**
     * Renderiza el contenido acumulado como markdown.
     */
    function render() {
        if (!targetElement) return;

        if (typeof marked !== 'undefined') {
            targetElement.innerHTML = marked.parse(accumulated);
        } else {
            targetElement.textContent = accumulated;
        }

        // Auto-renderizar bloques mermaid si MermaidBlock está disponible
        if (typeof MermaidBlock !== 'undefined') {
            MermaidBlock.renderAll(targetElement);
        }

        // Scroll al fondo
        targetElement.scrollTop = targetElement.scrollHeight;
    }

    /**
     * Limpia el contenido acumulado.
     */
    function clear() {
        accumulated = '';
        if (targetElement) {
            targetElement.innerHTML = '<p class="placeholder-text">El resultado aparecerá aquí...</p>';
        }
    }

    /**
     * Retorna el contenido acumulado en raw markdown.
     * @returns {string}
     */
    function getContent() {
        return accumulated;
    }

    /**
     * Establece contenido completo de una vez.
     * @param {string} content - Markdown completo
     */
    function setContent(content) {
        accumulated = content;
        render();
    }

    return { init, appendChunk, render, clear, getContent, setContent };
})();
