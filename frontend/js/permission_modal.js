/**
 * PermissionModal — Modal reutilizable para diálogos Human-in-the-Loop.
 *
 * Soporta dos tipos de permisos:
 * - read: Permiso de Lectura (Auditor 3D)
 * - write: Permiso de Escritura (Auto-Fix / PR)
 */
const PermissionModal = (() => {
    let resolvePromise = null;

    /**
     * Inicializa listeners de los botones del modal.
     */
    function init() {
        const modal = document.getElementById('permissionModal');
        const btnGrant = document.getElementById('modalGrant');
        const btnDeny = document.getElementById('modalDeny');

        btnGrant.addEventListener('click', () => close(true));
        btnDeny.addEventListener('click', () => close(false));

        // Cerrar con Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !modal.hidden) {
                close(false);
            }
        });
    }

    /**
     * Muestra el modal de permisos y retorna una Promise.
     * @param {object} options
     * @param {string} options.type - 'read' o 'write'
     * @param {string} options.repoUrl - URL del repositorio
     * @param {string} [options.scope] - Descripción del scope
     * @returns {Promise<boolean>} true si concedido, false si denegado
     */
    function show({ type, repoUrl, scope }) {
        const modal = document.getElementById('permissionModal');
        const title = document.getElementById('modalTitle');
        const body = document.getElementById('modalBody');
        const btnGrant = document.getElementById('modalGrant');

        const isRead = type === 'read';
        const permLabel = isRead ? 'Lectura' : 'Escritura';
        const permColor = isRead ? 'var(--neon-cyan)' : 'var(--neon-magenta)';

        title.textContent = `Solicitud de Permiso de ${permLabel}`;
        title.style.color = permColor;

        body.innerHTML = `
            <p>${isRead
                ? 'Para auditar este repositorio, OmniSpec AI necesita acceso de lectura a sus archivos.'
                : 'Para crear un Pull Request, OmniSpec AI necesita permiso de escritura en el repositorio.'
            }</p>
            <div class="permission-scope">
                <strong>Repositorio:</strong> ${escapeHtml(repoUrl)}<br>
                <strong>Scope:</strong> ${scope || (isRead ? 'Lectura de archivos del repositorio' : 'Crear rama y Pull Request')}<br>
                <strong>Tipo:</strong> Permiso de ${permLabel}
            </div>
            <p style="color: var(--text-secondary); font-size: 0.8rem;">
                ${isRead
                    ? 'No se modificará ningún archivo del repositorio.'
                    : 'Se creará una rama fix/omnispec-patch y se abrirá un PR.'
                }
            </p>
        `;

        btnGrant.textContent = `Conceder Permiso de ${permLabel}`;
        btnGrant.style.borderColor = permColor;
        btnGrant.style.color = permColor;

        modal.hidden = false;

        return new Promise((resolve) => {
            resolvePromise = resolve;
        });
    }

    /**
     * Cierra el modal y resuelve la Promise.
     * @param {boolean} granted
     */
    function close(granted) {
        const modal = document.getElementById('permissionModal');
        modal.hidden = true;

        if (resolvePromise) {
            resolvePromise(granted);
            resolvePromise = null;
        }
    }

    /**
     * Escapa HTML para prevenir XSS.
     * @param {string} str
     * @returns {string}
     */
    function escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    return { init, show, close };
})();
