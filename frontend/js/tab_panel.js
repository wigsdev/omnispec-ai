/**
 * TabPanel — Sistema de pestañas con indicador neón animado.
 *
 * Gestiona la navegación entre los 3 paneles principales:
 * - SDD Generator (generator)
 * - Auditor 3D (auditor)
 * - Auto-Fix Engine (fixer)
 */
const TabPanel = (() => {
    let activeTab = 'generator';

    /**
     * Inicializa el sistema de tabs registrando event listeners.
     */
    function init() {
        const buttons = document.querySelectorAll('.tab-btn[data-tab]');
        buttons.forEach(btn => {
            btn.addEventListener('click', () => switchTab(btn.dataset.tab));
        });
    }

    /**
     * Cambia la pestaña activa.
     * @param {string} tabId - Identificador del tab (generator|auditor|fixer)
     */
    function switchTab(tabId) {
        if (tabId === activeTab) return;

        // Desactivar tabs
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.remove('active');
            btn.setAttribute('aria-selected', 'false');
        });

        // Ocultar paneles
        document.querySelectorAll('.tab-panel').forEach(panel => {
            panel.classList.remove('active');
            panel.hidden = true;
        });

        // Activar tab seleccionado
        const selectedBtn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
        const selectedPanel = document.getElementById(`panel-${tabId}`);

        if (selectedBtn && selectedPanel) {
            selectedBtn.classList.add('active');
            selectedBtn.setAttribute('aria-selected', 'true');
            selectedPanel.classList.add('active');
            selectedPanel.hidden = false;
            activeTab = tabId;
        }
    }

    /**
     * Retorna el tab activo actual.
     * @returns {string}
     */
    function getActiveTab() {
        return activeTab;
    }

    return { init, switchTab, getActiveTab };
})();
