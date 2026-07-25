/**
 * DiffViewer — Visor de unified diff con resaltado de líneas.
 *
 * Líneas verdes (+) para adiciones, rojas (-) para eliminaciones,
 * magenta (@@) para headers de sección.
 */
const DiffViewer = (() => {
    let targetElement = null;

    /**
     * Inicializa el visor de diff.
     * @param {string} elementId - ID del contenedor
     */
    function init(elementId) {
        targetElement = document.getElementById(elementId);
    }

    /**
     * Renderiza un unified diff en el contenedor.
     * @param {string} diffText - Texto en formato unified diff
     */
    function render(diffText) {
        if (!targetElement) return;

        if (!diffText || diffText.trim() === '') {
            targetElement.innerHTML = '<p class="placeholder-text">El diff aparecerá aquí...</p>';
            return;
        }

        const lines = diffText.split('\n');
        const html = lines.map(line => {
            const cssClass = getLineClass(line);
            const escaped = escapeHtml(line);
            return `<div class="diff-line ${cssClass}">${escaped}</div>`;
        }).join('');

        targetElement.innerHTML = html;
    }

    /**
     * Determina la clase CSS de una línea de diff.
     * @param {string} line
     * @returns {string}
     */
    function getLineClass(line) {
        if (line.startsWith('@@')) return 'diff-line--header';
        if (line.startsWith('+')) return 'diff-line--added';
        if (line.startsWith('-')) return 'diff-line--removed';
        return 'diff-line--context';
    }

    /**
     * Limpia el visor.
     */
    function clear() {
        if (targetElement) {
            targetElement.innerHTML = '<p class="placeholder-text">El diff aparecerá aquí...</p>';
        }
    }

    /**
     * Retorna el diff actual como texto plano.
     * @returns {string}
     */
    function getRawDiff() {
        if (!targetElement) return '';
        const lines = targetElement.querySelectorAll('.diff-line');
        return Array.from(lines).map(el => el.textContent).join('\n');
    }

    /**
     * Escapa HTML.
     * @param {string} str
     * @returns {string}
     */
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    return { init, render, clear, getRawDiff };
})();
