/**
 * ScoreGauge — Indicador circular SVG de Score 0-100.
 *
 * Colores semáforo:
 * - Rojo (<40): Crítico
 * - Naranja (40-70): Medio
 * - Verde (>70): Seguro
 */
const ScoreGauge = (() => {
    let targetElement = null;

    /**
     * Inicializa el gauge en el contenedor indicado.
     * @param {string} elementId - ID del contenedor
     */
    function init(elementId) {
        targetElement = document.getElementById(elementId);
    }

    /**
     * Renderiza el gauge con un score dado.
     * @param {number|null} score - Valor 0-100 o null para N/A
     */
    function render(score) {
        if (!targetElement) return;

        if (score === null || score === undefined) {
            targetElement.innerHTML = renderNA();
            return;
        }

        const clamped = Math.max(0, Math.min(100, Math.round(score)));
        const color = getColor(clamped);
        const label = getLabel(clamped);
        const circumference = 2 * Math.PI * 70;
        const offset = circumference - (clamped / 100) * circumference;

        targetElement.innerHTML = `
            <svg viewBox="0 0 180 180" aria-label="Score: ${clamped}/100">
                <circle cx="90" cy="90" r="70"
                    fill="none" stroke="var(--border-color)" stroke-width="8"/>
                <circle cx="90" cy="90" r="70"
                    fill="none" stroke="${color}" stroke-width="8"
                    stroke-linecap="round"
                    stroke-dasharray="${circumference}"
                    stroke-dashoffset="${offset}"
                    transform="rotate(-90 90 90)"
                    style="transition: stroke-dashoffset 1s ease-in-out;
                           filter: drop-shadow(0 0 6px ${color});"/>
                <text x="90" y="85" text-anchor="middle"
                    class="score-value" fill="${color}"
                    style="font-family: var(--font-mono); font-size: 2.2rem; font-weight: 700;">
                    ${clamped}
                </text>
                <text x="90" y="115" text-anchor="middle"
                    fill="var(--text-secondary)"
                    style="font-family: var(--font-mono); font-size: 0.7rem; text-transform: uppercase;">
                    ${label}
                </text>
            </svg>
            <div class="score-label">${label}</div>
        `;
    }

    /**
     * Renderiza estado N/A (sin archivos analizables).
     * @returns {string}
     */
    function renderNA() {
        return `
            <svg viewBox="0 0 180 180" aria-label="Score: N/A">
                <circle cx="90" cy="90" r="70"
                    fill="none" stroke="var(--border-color)" stroke-width="8"/>
                <text x="90" y="90" text-anchor="middle"
                    fill="var(--text-muted)"
                    style="font-family: var(--font-mono); font-size: 1.5rem;">
                    N/A
                </text>
                <text x="90" y="115" text-anchor="middle"
                    fill="var(--text-muted)"
                    style="font-family: var(--font-mono); font-size: 0.65rem;">
                    Sin datos
                </text>
            </svg>
            <div class="score-label" style="color: var(--text-muted);">Sin archivos analizables</div>
        `;
    }

    /**
     * Retorna el color según el score.
     * @param {number} score
     * @returns {string}
     */
    function getColor(score) {
        if (score < 40) return 'var(--neon-red)';
        if (score <= 70) return 'var(--neon-orange)';
        return 'var(--neon-green)';
    }

    /**
     * Retorna la etiqueta según el score.
     * @param {number} score
     * @returns {string}
     */
    function getLabel(score) {
        if (score < 40) return 'Crítico';
        if (score <= 70) return 'Riesgo Medio';
        return 'Seguro';
    }

    return { init, render };
})();
