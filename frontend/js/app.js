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
        initDocTabs();

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

        const btnExport = document.getElementById('btnExport');
        if (btnExport) {
            btnExport.addEventListener('click', handleExport);
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

        // Downloads
        const btnDownloadDiff = document.getElementById('btnDownloadDiff');
        if (btnDownloadDiff) {
            btnDownloadDiff.addEventListener('click', () => downloadFile('omnispec-fix.diff', window._generatedDiff || ''));
        }

        const btnDownloadTests = document.getElementById('btnDownloadTests');
        if (btnDownloadTests) {
            btnDownloadTests.addEventListener('click', () => downloadFile('test_security_patch.py', window._generatedTests || ''));
        }

        // Alert close
        const alertClose = document.getElementById('alertClose');
        if (alertClose) {
            alertClose.addEventListener('click', hideAlert);
        }

        // GitHub logout
        // GitHub login
        const btnGithubLogin = document.getElementById('btnGithubLogin');
        if (btnGithubLogin) {
            btnGithubLogin.addEventListener('click', () => openGitHubAuthPopup());
        }

        // GitHub logout
        const btnLogout = document.getElementById('btnLogout');
        if (btnLogout) {
            btnLogout.addEventListener('click', handleLogout);
        }
    }

    /**
     * Handler: Exportar Pack .kiro (ZIP).
     */
    async function handleExport() {
        const prompt = document.getElementById('sddPrompt').value.trim();
        if (!prompt) {
            showAlert('Genera un SDD primero antes de exportar.', 'warning');
            return;
        }

        const btn = document.getElementById('btnExport');
        btn.disabled = true;
        btn.textContent = 'Exportando...';

        try {
            const response = await fetch(`${API_BASE}/generate/export`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'omnispec-pack.kiro.zip';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            showAlert('Pack .kiro exportado exitosamente.', 'success');
        } catch (err) {
            showAlert(`Error exportando: ${err.message}`, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Exportar .kiro Pack';
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
        clearDocPanels();
        hideProviderBadge();
        const btn = document.getElementById('btnGenerate');
        btn.disabled = true;
        btn.textContent = 'Generando...';

        try {
            const response = await apiFetch('/generate', {
                method: 'POST',
                body: JSON.stringify({ prompt })
            });

            if (response.documents) {
                // Renderizar cada documento en su panel
                renderDocPanel('streamingOutput', response.documents.requirements);
                renderDocPanel('designOutput', response.documents.design);
                renderDocPanel('tasksOutput', response.documents.tasks);
                renderDocPanel('agentsOutput', response.documents.agents);

                // Guardar documentos para export
                window._generatedDocs = response.documents;

                document.getElementById('btnExport').disabled = false;
                showProviderBadge(response.provider, response.latency_ms);
            } else if (response.data) {
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
     * Handler: Auditar repositorio (progressive SSE).
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

        // Reset UI
        const btn = document.getElementById('btnAudit');
        btn.disabled = true;
        btn.textContent = 'Auditando...';
        resetAuditUI();

        try {
            const response = await fetch(`${API_BASE}/audit/stream?repo_url=${encodeURIComponent(repoUrl)}`);
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop();

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const event = JSON.parse(line.slice(6));
                        handleAuditEvent(event);
                    }
                }
            }
        } catch (err) {
            showAlert(`Error: ${err.message}`, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Auditar';
        }
    }

    /**
     * Procesa eventos SSE del auditor progresivo.
     */
    function handleAuditEvent(event) {
        switch (event.type) {
            case 'phase':
                // Mostrar fase activa
                break;

            case 'enumeration':
                showEnumeration(event);
                break;

            case 'file_scanned':
                showFileScanResult(event);
                break;

            case 'complete':
                showAuditVerdict(event);
                break;

            case 'error':
                showAlert(`Error: ${event.message}`, 'error');
                break;
        }
    }

    /**
     * Muestra la fase de enumeración.
     */
    function showEnumeration(data) {
        document.getElementById('auditPlaceholder').hidden = true;
        const phase = document.getElementById('auditEnumeration');
        phase.hidden = false;

        document.getElementById('enumStats').innerHTML = `
            <div class="enum-stat"><span class="stat-value">${data.total}</span> Total</div>
            <div class="enum-stat"><span class="stat-value">${data.analyzable}</span> Analizables</div>
            <div class="enum-stat"><span class="stat-value">${data.skipped}</span> Omitidos</div>
        `;

        const list = document.getElementById('enumFileList');
        list.innerHTML = data.files.map(f =>
            `<div class="file-list-item">${f}</div>`
        ).join('');

        // Mostrar fase de escaneo
        document.getElementById('auditScanning').hidden = false;
    }

    /**
     * Muestra resultado de escaneo por archivo.
     */
    function showFileScanResult(data) {
        const progress = (data.current / data.total) * 100;
        document.getElementById('scanProgressBar').style.width = `${progress}%`;
        document.getElementById('scanProgressText').textContent = `${data.current}/${data.total} archivos`;

        const iconMap = { clean: '✅', findings: '⚠️', critical: '🔴' };
        const statusMap = { clean: 'OK', findings: `${data.findings_count} hallazgo${data.findings_count > 1 ? 's' : ''}`, critical: 'CRITICAL' };

        const item = document.createElement('div');
        item.className = 'scan-item';
        item.innerHTML = `
            <span class="scan-icon scan-icon--${data.status}">${iconMap[data.status]}</span>
            <span class="scan-path">${data.path}</span>
            <span class="scan-status scan-status--${data.status}">${statusMap[data.status]}</span>
        `;

        const results = document.getElementById('scanResults');
        results.appendChild(item);
        results.scrollTop = results.scrollHeight;
    }

    /**
     * Muestra el veredicto final con score y resumen.
     */
    function showAuditVerdict(data) {
        const phase = document.getElementById('auditVerdict');
        phase.hidden = false;

        // Score gauge
        ScoreGauge.init('scoreGauge');
        ScoreGauge.render(data.score);

        // Summary cards
        const summary = data.summary || {};
        document.getElementById('verdictSummary').innerHTML = `
            <div class="verdict-card"><div class="card-value">${summary.analyzed || 0}</div><div class="card-label">Analizados</div></div>
            <div class="verdict-card"><div class="card-value">${summary.clean || 0}</div><div class="card-label">Limpios</div></div>
            <div class="verdict-card"><div class="card-value">${summary.with_findings || 0}</div><div class="card-label">Con Hallazgos</div></div>
            <div class="verdict-card"><div class="card-value">${data.findings_count || 0}</div><div class="card-label">Total Findings</div></div>
        `;

        // Findings details
        const findings = data.findings || {};
        let html = '';
        if (findings.secrets && findings.secrets.length) {
            html += '<h4 class="phase-title" style="color:var(--neon-red)">Secretos Expuestos</h4>';
            findings.secrets.forEach(f => {
                html += `<div class="scan-item"><span class="scan-icon scan-icon--critical">🔴</span><span class="scan-path">${f.description} → ${f.file}:${f.line}</span></div>`;
            });
        }
        if (findings.iac && findings.iac.length) {
            html += '<h4 class="phase-title" style="color:var(--neon-orange)">IaC Insegura</h4>';
            findings.iac.forEach(f => {
                html += `<div class="scan-item"><span class="scan-icon scan-icon--findings">⚠️</span><span class="scan-path">${f.description} → ${f.file}:${f.line}</span></div>`;
            });
        }
        if (findings.governance && findings.governance.length) {
            html += '<h4 class="phase-title" style="color:var(--text-secondary)">Gobierno</h4>';
            findings.governance.forEach(f => {
                html += `<div class="scan-item"><span class="scan-icon">📋</span><span class="scan-path">${f.description}</span></div>`;
            });
        }
        document.getElementById('findingsSection').innerHTML = html;

        // Guardar hallazgos para Auto-Fix Engine
        window._auditFindings = [
            ...(findings.secrets || []),
            ...(findings.iac || []),
        ];
        window._auditRepoUrl = document.getElementById('repoUrl').value.trim();
        populateFixFindings();
    }

    /**
     * Resetea la UI del auditor para un nuevo escaneo.
     */
    function resetAuditUI() {
        document.getElementById('auditPlaceholder').hidden = true;
        document.getElementById('auditEnumeration').hidden = true;
        document.getElementById('auditScanning').hidden = true;
        document.getElementById('auditVerdict').hidden = true;
        document.getElementById('scanResults').innerHTML = '';
        document.getElementById('scanProgressBar').style.width = '0%';
        document.getElementById('scanProgressText').textContent = '0/0 archivos';
        document.getElementById('findingsSection').innerHTML = '';
        document.getElementById('verdictSummary').innerHTML = '';
    }

    /**
     * Handler: Generar fix.
     */
    async function handleGenerateFix() {
        const selected = getSelectedFindings();
        if (selected.length === 0) {
            showAlert('Selecciona al menos un hallazgo para corregir.', 'warning');
            return;
        }

        const btn = document.getElementById('btnGenerateFix');
        btn.disabled = true;
        btn.textContent = 'Generando Fix...';

        try {
            const response = await apiFetch('/fix/generate', {
                method: 'POST',
                body: JSON.stringify({
                    findings: selected,
                    repo_url: window._auditRepoUrl || '',
                })
            });

            if (response.status === 'generated') {
                // Mostrar diff
                DiffViewer.init('diffViewer');
                DiffViewer.render(response.diff);

                // Mostrar tests
                const testViewer = document.getElementById('testViewer');
                if (testViewer && response.tests) {
                    testViewer.innerHTML = `<pre><code>${escapeHtml(response.tests)}</code></pre>`;
                }

                // Habilitar botones
                document.getElementById('btnCreatePR').disabled = false;
                document.getElementById('btnDownloadDiff').disabled = false;
                document.getElementById('btnDownloadTests').disabled = false;

                // Guardar para descarga
                window._generatedDiff = response.diff;
                window._generatedTests = response.tests;
                window._fixId = response.id;

                showProviderBadge(response.provider || 'AI', response.latency_ms || 0);
            } else if (response.status === 'no_fix_needed') {
                showAlert('No se necesita corrección para los hallazgos seleccionados.', 'info');
            } else if (response.status === 'error') {
                showAlert(`Error: ${response.message}`, 'error');
            }
        } catch (err) {
            showAlert(`Error generando fix: ${err.message}`, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Generar Fix';
        }
    }

    /**
     * Popula el checklist de hallazgos en el tab Auto-Fix.
     */
    function populateFixFindings() {
        const container = document.getElementById('fixFindings');
        const findings = window._auditFindings || [];

        if (findings.length === 0) {
            container.innerHTML = '<p class="placeholder-text">Ejecuta una auditoría primero para ver hallazgos...</p>';
            return;
        }

        const html = findings.map((f, i) => {
            const severity = f.severity || 'unknown';
            const colorClass = severity === 'critical' ? 'scan-icon--critical' : 'scan-icon--findings';
            return `
                <label class="finding-checkbox">
                    <input type="checkbox" name="finding" value="${i}" checked>
                    <span class="finding-severity ${colorClass}">[${severity}]</span>
                    <span class="finding-desc">${f.description || 'Unknown'}</span>
                    <span class="finding-file">${f.file || ''}:${f.line || ''}</span>
                </label>
            `;
        }).join('');

        container.innerHTML = html;
        document.getElementById('btnGenerateFix').disabled = false;
    }

    /**
     * Obtiene los hallazgos seleccionados del checklist.
     */
    function getSelectedFindings() {
        const checkboxes = document.querySelectorAll('#fixFindings input[name="finding"]:checked');
        const findings = window._auditFindings || [];
        return Array.from(checkboxes).map(cb => findings[parseInt(cb.value)]).filter(Boolean);
    }

    /**
     * Escapa HTML para inserción segura.
     */
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    /**
     * Handler: Crear Pull Request.
     */
    async function handleCreatePR() {
        // Verificar autenticación — abrir popup si no conectado
        const authStatus = await apiFetch('/auth/status');
        if (!authStatus.authenticated) {
            showAlert('Conectando con GitHub...', 'info');
            const connected = await openGitHubAuthPopup();
            if (!connected) {
                showAlert('Necesitas conectar GitHub para crear Pull Requests.', 'warning');
                return;
            }
        }

        const repoUrl = window._auditRepoUrl || document.getElementById('repoUrl').value.trim();

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
            const response = await apiFetch('/fix/apply', {
                method: 'POST',
                body: JSON.stringify({
                    fix_id: window._fixId,
                    write_permission_granted: true,
                })
            });

            if (response.status === 'pr_created') {
                showAlert(`Pull Request creado: ${response.pr_url}`, 'success');
            } else if (response.status === 'validation_failed') {
                showAlert(`Tests fallaron — PR no creado. ${response.pytest_output || ''}`, 'error');
            } else {
                showAlert(response.message || 'Error creando PR', 'error');
            }
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
     * Renderiza markdown en un panel de documento.
     * @param {string} elementId - ID del contenedor
     * @param {string} markdown - Contenido markdown
     */
    function renderDocPanel(elementId, markdown) {
        const el = document.getElementById(elementId);
        if (!el || !markdown) return;
        if (typeof marked !== 'undefined') {
            el.innerHTML = marked.parse(markdown);
        } else {
            el.textContent = markdown;
        }
        // Auto-render mermaid blocks
        if (typeof MermaidBlock !== 'undefined') {
            MermaidBlock.renderAll(el);
        }
    }

    /**
     * Limpia todos los paneles de documentos.
     */
    function clearDocPanels() {
        const panels = ['streamingOutput', 'designOutput', 'tasksOutput', 'agentsOutput'];
        panels.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.innerHTML = '<p class="placeholder-text">Generando...</p>';
        });
    }

    /**
     * Inicializa las sub-tabs de documentos.
     */
    function initDocTabs() {
        const tabs = document.querySelectorAll('.doc-tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                // Desactivar todos
                document.querySelectorAll('.doc-tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.doc-panel').forEach(p => {
                    p.classList.remove('active');
                    p.hidden = true;
                });
                // Activar seleccionado
                tab.classList.add('active');
                const panel = document.getElementById(`doc-${tab.dataset.doc}`);
                if (panel) {
                    panel.classList.add('active');
                    panel.hidden = false;
                }
            });
        });
    }

    /**
     * Descarga un archivo de texto al navegador.
     * @param {string} filename
     * @param {string} content
     */
    function downloadFile(filename, content) {
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
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

        // Check GitHub auth status
        checkGitHubAuth();
    }

    /**
     * Verifica estado de autenticación de GitHub al iniciar.
     */
    async function checkGitHubAuth() {
        try {
            const data = await apiFetch('/auth/status');
            if (data.authenticated && data.user) {
                showGitHubUser(data.user);
            } else {
                showGitHubLogin();
            }
        } catch {
            showGitHubLogin();
        }
    }

    /**
     * Abre popup de OAuth y pollea /auth/poll/{id} hasta que complete.
     * @returns {Promise<boolean>} true si autenticado exitosamente.
     */
    function openGitHubAuthPopup() {
        return new Promise(async (resolve) => {
            // 1. Pedir request_id al servidor
            let requestId;
            try {
                const startResp = await apiFetch('/auth/start', { method: 'POST' });
                requestId = startResp.request_id;
            } catch (e) {
                showAlert('Error iniciando autenticación.', 'error');
                resolve(false);
                return;
            }

            // 2. Abrir popup con request_id
            const width = 500, height = 600;
            const left = (screen.width - width) / 2;
            const top = (screen.height - height) / 2;
            const popup = window.open(
                `/api/v1/auth/login?request_id=${requestId}`,
                'omnispec-github-auth',
                `width=${width},height=${height},left=${left},top=${top}`
            );

            // 3. Polling: preguntar al servidor si el auth completó
            const poll = setInterval(async () => {
                try {
                    const resp = await fetch(`${API_BASE}/auth/poll/${requestId}`);
                    const data = await resp.json();

                    if (data.status === 'authenticated') {
                        clearInterval(poll);
                        showGitHubUser(data.user);
                        showAlert(`Conectado como ${data.user.login}`, 'success');
                        if (popup && !popup.closed) popup.close();
                        resolve(true);
                    } else if (data.status === 'error') {
                        clearInterval(poll);
                        showAlert(`Error: ${data.error}`, 'error');
                        resolve(false);
                    } else if (data.status === 'expired') {
                        clearInterval(poll);
                        showAlert('Sesión expirada. Intenta de nuevo.', 'warning');
                        resolve(false);
                    }
                } catch { /* ignore network errors during polling */ }

                // Si el popup se cerró sin completar
                if (popup && popup.closed) {
                    // Dar un último intento
                    setTimeout(async () => {
                        try {
                            const resp = await fetch(`${API_BASE}/auth/poll/${requestId}`);
                            const data = await resp.json();
                            if (data.status === 'authenticated') {
                                showGitHubUser(data.user);
                                showAlert(`Conectado como ${data.user.login}`, 'success');
                                resolve(true);
                            } else {
                                resolve(false);
                            }
                        } catch { resolve(false); }
                    }, 1000);
                    clearInterval(poll);
                }
            }, 1500);
        });
    }

    /**
     * Muestra el botón de login de GitHub.
     */
    function showGitHubLogin() {
        document.getElementById('githubAuth').hidden = false;
        document.getElementById('githubUser').hidden = true;
    }

    /**
     * Muestra el usuario autenticado de GitHub.
     */
    function showGitHubUser(user) {
        document.getElementById('githubAuth').hidden = true;
        const userEl = document.getElementById('githubUser');
        userEl.hidden = false;
        document.getElementById('userAvatar').src = user.avatar_url || '';
        document.getElementById('userName').textContent = user.login || 'user';
    }

    /**
     * Handler: Logout de GitHub.
     */
    async function handleLogout() {
        try {
            await apiFetch('/auth/logout', { method: 'POST' });
            showGitHubLogin();
            showAlert('Sesión de GitHub cerrada.', 'info');
        } catch {
            showGitHubLogin();
        }
    }

    return { init, apiFetch, showAlert };
})();

// Boot
document.addEventListener('DOMContentLoaded', () => App.init());
