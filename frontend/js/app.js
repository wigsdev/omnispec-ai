/**
 * App — Módulo principal de OmniSpec AI.
 *
 * Gestiona la inicialización de componentes, enrutamiento
 * de pestañas y wrapper de peticiones fetch a la API.
 */
const App = (() => {
    const API_BASE = '/api/v1';

    /**
     * Inicializa todos los componentes de la aplicación.
     */
    function init() {
        // Inicializar componentes
        TabPanel.init();
        PermissionModal.init();
        StreamingPanel.init('streamingOutput');
        MermaidBlock.init();
        DiffViewer.init('diffViewer');
        ScoreGauge.init('scoreGauge');

        // Registrar event listeners principales
        bindEvents();

        // Health check
        checkHealth();

        console.log('[OmniSpec AI] Initialized');
    }

    /**
     * Registra event listeners de la UI.
     */
    function bindEvents() {
        // SDD Generator
        const btnGenerate = document.getElementById('btnGenerate');
        if (btnGenerate) {
            btnGenerate.addEventListener('click', handleGenerate);
        }

        // Auditor
        const btnAudit = document.getElementById('btnAudit');
        if (btnAudit) {
            btnAudit.addEventListener('click', handleAudit);
        }

        // Auto-Fix
        const btnGenerateFix = document.getElementById('btnGenerateFix');
        if (btnGenerateFix) {
            btnGenerateFix.addEventListener('click', handleGenerateFix);
        }

        const btnCreatePR = document.getElementById('btnCreatePR');
        if (btnCreatePR) {
            btnCreatePR.addEventListener('click', handleCreatePR);
        }

        // Alert close
        const alertClose = document.getElementById('alertClose');
        if (alertClose) {
            alertClose.addEventListener('click', hideAlert);
        }
    }

    /**
     * Handler: Generar SDD.
     */
    async function handleGenerate() {
        const prompt = document.getElementById('sddPrompt').value.trim();
        if (!prompt) {
            showAlert('Ingresa una descripción del proyecto.', 'warning');
            return;
        }

        StreamingPanel.clear();
        hideProviderBadge();
        const btn = document.getElementById('btnGenerate');
        btn.disabled = true;
        btn.textContent = 'Generando...';

        try {
            const response = await apiFetch('/generate', {
                method: 'POST',
                body: JSON.stringify({ prompt })
            });

            if (response.data) {
                StreamingPanel.setContent(response.data);
                document.getElementById('btnExport').disabled = false;
                showProviderBadge(response.provider, response.latency_ms);
            }
        } catch (err) {
            showAlert(`Error: ${err.message}`, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Generar SDD';
        }
    }

    /**
     * Handler: Auditar repositorio.
     */
    async function handleAudit() {
        const repoUrl = document.getElementById('repoUrl').value.trim();
        if (!repoUrl) {
            showAlert('Ingresa la URL del repositorio.', 'warning');
            return;
        }

        // Human-in-the-Loop: Permiso de Lectura
        const granted = await PermissionModal.show({
            type: 'read',
            repoUrl: repoUrl,
            scope: 'Lectura de archivos del repositorio'
        });

        if (!granted) {
            showAlert('Auditoría cancelada — No se accedió a ningún dato del repositorio.', 'info');
            return;
        }

        const btn = document.getElementById('btnAudit');
        btn.disabled = true;
        btn.textContent = 'Auditando...';

        try {
            const response = await apiFetch('/audit', {
                method: 'POST',
                body: JSON.stringify({ repo_url: repoUrl, permission_granted: true })
            });

            if (response.score !== undefined) {
                ScoreGauge.render(response.score);
            }
        } catch (err) {
            showAlert(`Error: ${err.message}`, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Auditar';
        }
    }

    /**
     * Handler: Generar fix.
     */
    async function handleGenerateFix() {
        try {
            const response = await apiFetch('/fix/generate', { method: 'POST' });
            if (response.diff) {
                DiffViewer.render(response.diff);
            }
        } catch (err) {
            showAlert(`Error: ${err.message}`, 'error');
        }
    }

    /**
     * Handler: Crear Pull Request.
     */
    async function handleCreatePR() {
        const repoUrl = document.getElementById('repoUrl').value.trim();

        // Human-in-the-Loop: Permiso de Escritura
        const granted = await PermissionModal.show({
            type: 'write',
            repoUrl: repoUrl,
            scope: 'Crear rama fix/omnispec-patch y abrir Pull Request'
        });

        if (!granted) {
            showAlert('PR cancelado — Los archivos generados están disponibles para descarga local.', 'info');
            document.getElementById('btnDownloadDiff').disabled = false;
            document.getElementById('btnDownloadTests').disabled = false;
            return;
        }

        try {
            await apiFetch('/fix/apply', {
                method: 'POST',
                body: JSON.stringify({ write_permission_granted: true })
            });
            showAlert('Pull Request creado exitosamente.', 'success');
        } catch (err) {
            showAlert(`Error: ${err.message}`, 'error');
        }
    }

    /**
     * Wrapper de fetch para llamadas a la API.
     * @param {string} endpoint - Ruta relativa (e.g., '/generate')
     * @param {object} [options] - Opciones de fetch
     * @returns {Promise<object>}
     */
    async function apiFetch(endpoint, options = {}) {
        const url = `${API_BASE}${endpoint}`;
        const config = {
            headers: { 'Content-Type': 'application/json' },
            ...options
        };

        const response = await fetch(url, config);

        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(error.message || `HTTP ${response.status}`);
        }

        return response.json();
    }

    /**
     * Muestra un banner de alerta.
     * @param {string} message
     * @param {string} [type] - 'info' | 'warning' | 'error' | 'success'
     */
    function showAlert(message, type = 'info') {
        const banner = document.getElementById('alertBanner');
        const msgEl = document.getElementById('alertMessage');
        msgEl.textContent = message;
        banner.hidden = false;

        // Auto-hide después de 5s
        setTimeout(() => hideAlert(), 5000);
    }

    /**
     * Oculta el banner de alerta.
     */
    function hideAlert() {
        document.getElementById('alertBanner').hidden = true;
    }

    /**
     * Muestra el badge del proveedor que respondió.
     * @param {string} provider - Nombre del proveedor
     * @param {number} latencyMs - Tiempo de respuesta en ms
     */
    function showProviderBadge(provider, latencyMs) {
        const badge = document.getElementById('providerBadge');
        const text = document.getElementById('providerText');
        if (badge && text && provider) {
            const seconds = (latencyMs / 1000).toFixed(1);
            text.textContent = `Generado con ${provider} (${seconds}s)`;
            badge.hidden = false;
            setTimeout(() => { badge.hidden = true; }, 10000);
        }
    }

    /**
     * Oculta el badge del proveedor.
     */
    function hideProviderBadge() {
        const badge = document.getElementById('providerBadge');
        if (badge) badge.hidden = true;
    }

    /**
     * Health check contra la API.
     */
    async function checkHealth() {
        try {
            const data = await apiFetch('/health');
            if (data.status === 'ok') {
                document.querySelector('.status-text').textContent = 'Connected';
            }
        } catch {
            document.querySelector('.status-indicator').style.background = 'var(--neon-red)';
            document.querySelector('.status-text').textContent = 'Offline';
        }
    }

    return { init, apiFetch, showAlert };
})();

// Boot
document.addEventListener('DOMContentLoaded', () => App.init());
