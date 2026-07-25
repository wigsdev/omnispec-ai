/**
 * MermaidBlock — Auto-renderizado de diagramas Mermaid.js.
 *
 * Detecta bloques <code class="language-mermaid"> o <pre><code>
 * con contenido mermaid y los renderiza como SVG.
 */
const MermaidBlock = (() => {
    let initialized = false;

    /**
     * Inicializa mermaid.js con tema dark.
     */
    function init() {
        if (typeof mermaid !== 'undefined' && !initialized) {
            mermaid.initialize({
                startOnLoad: false,
                theme: 'dark',
                themeVariables: {
                    primaryColor: '#1c2128',
                    primaryBorderColor: '#00f3ff',
                    primaryTextColor: '#e6edf3',
                    lineColor: '#00f3ff',
                    secondaryColor: '#161b22',
                    tertiaryColor: '#0d1117'
                },
                flowchart: { curve: 'basis' },
                securityLevel: 'strict'
            });
            initialized = true;
        }
    }

    /**
     * Renderiza todos los bloques mermaid dentro de un contenedor.
     * @param {HTMLElement} container - Elemento padre donde buscar bloques
     */
    async function renderAll(container) {
        if (typeof mermaid === 'undefined') return;
        if (!initialized) init();

        const codeBlocks = container.querySelectorAll('code.language-mermaid, code');
        for (const block of codeBlocks) {
            const text = block.textContent.trim();
            if (!isMermaidSyntax(text)) continue;
            if (block.dataset.mermaidRendered === 'true') continue;

            const wrapper = document.createElement('div');
            wrapper.className = 'mermaid-diagram';

            try {
                const id = `mermaid-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
                const { svg } = await mermaid.render(id, text);
                wrapper.innerHTML = svg;
                block.dataset.mermaidRendered = 'true';

                const pre = block.closest('pre');
                if (pre) {
                    pre.replaceWith(wrapper);
                } else {
                    block.replaceWith(wrapper);
                }
            } catch (err) {
                // Si falla el render, dejar el código visible
                console.warn('MermaidBlock: render failed', err.message);
            }
        }
    }

    /**
     * Detecta si un texto es sintaxis mermaid válida.
     * @param {string} text
     * @returns {boolean}
     */
    function isMermaidSyntax(text) {
        const keywords = ['graph ', 'flowchart ', 'sequenceDiagram', 'classDiagram',
                          'stateDiagram', 'erDiagram', 'gantt', 'pie ', 'gitGraph'];
        return keywords.some(kw => text.startsWith(kw));
    }

    return { init, renderAll };
})();
