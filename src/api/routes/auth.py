"""Auth Routes — GitHub OAuth via Popup + Server-Side Token Store.

Flujo:
1. Parent: POST /auth/start → recibe {request_id}
2. Parent: abre popup /auth/login?request_id=XXX
3. Popup: redirect a GitHub → usuario autoriza
4. Popup: callback guarda token en _auth_store[request_id]
5. Popup: muestra "Listo, cierra esta ventana"
6. Parent: GET /auth/poll/XXX → detecta token → lo mueve a su sesión
7. Parent: actualiza UI con avatar

No depende de cookies compartidas entre popup y parent.
"""

import os
import time
import secrets

import requests
from flask import Blueprint, jsonify, make_response, redirect, request, session

auth_bp = Blueprint('auth', __name__)

GITHUB_OAUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
OAUTH_SCOPES = "repo,read:user"

# Server-side store: {request_id: {token, user, created_at}}
# Ephemeral: entries expire after 5 minutes
_auth_store: dict = {}
AUTH_STORE_TTL = 300  # 5 minutes


@auth_bp.route('/api/v1/auth/start', methods=['POST'])
def auth_start():
    """Genera un request_id para iniciar el flujo OAuth."""
    request_id = secrets.token_urlsafe(24)
    _auth_store[request_id] = {"status": "pending", "created_at": time.time()}
    _cleanup_expired()
    return jsonify({"request_id": request_id})


@auth_bp.route('/api/v1/auth/login', methods=['GET'])
def github_login():
    """Redirige a GitHub. Recibe request_id como query param."""
    client_id = os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
    if not client_id:
        return jsonify({"error": "GITHUB_OAUTH_CLIENT_ID no configurado"}), 500

    request_id = request.args.get('request_id', '')
    callback_url = os.environ.get("APP_BASE_URL", "http://localhost:5000")

    # Usar request_id como state (CSRF protection + correlation)
    params = (
        f"?client_id={client_id}"
        f"&scope={OAUTH_SCOPES}"
        f"&state={request_id}"
        f"&redirect_uri={callback_url}/api/v1/auth/callback"
    )
    return redirect(GITHUB_OAUTH_URL + params)


@auth_bp.route('/api/v1/auth/callback', methods=['GET'])
def github_callback():
    """Callback de GitHub. Guarda token en _auth_store[request_id]."""
    code = request.args.get('code')
    request_id = request.args.get('state', '')
    error = request.args.get('error')

    if error or not code:
        if request_id and request_id in _auth_store:
            _auth_store[request_id] = {"status": "error", "error": error or "no_code"}
        return _close_page(success=False, error=error or "no_code")

    # Verificar que request_id existe en store
    if request_id not in _auth_store:
        return _close_page(success=False, error="request_id_expired")

    # Intercambiar code por token
    client_id = os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET", "")

    resp = requests.post(GITHUB_TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
    }, headers={"Accept": "application/json"}, timeout=10)

    if resp.status_code != 200:
        _auth_store[request_id] = {"status": "error", "error": "token_exchange_failed"}
        return _close_page(success=False, error="token_exchange_failed")

    access_token = resp.json().get("access_token")
    if not access_token:
        err = resp.json().get("error_description", "no_token")
        _auth_store[request_id] = {"status": "error", "error": err}
        return _close_page(success=False, error=err)

    # Obtener info del usuario
    user_resp = requests.get(GITHUB_USER_URL, headers={
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github.v3+json",
    }, timeout=10)

    user_data = user_resp.json() if user_resp.status_code == 200 else {}
    user_info = {
        "login": user_data.get("login", "unknown"),
        "avatar_url": user_data.get("avatar_url", ""),
        "name": user_data.get("name", ""),
    }

    # Guardar en auth_store (NO en sesión — la sesión es del popup)
    _auth_store[request_id] = {
        "status": "completed",
        "token": access_token,
        "user": user_info,
        "created_at": time.time(),
    }

    return _close_page(success=True, user=user_info["login"])


@auth_bp.route('/api/v1/auth/poll/<request_id>', methods=['GET'])
def auth_poll(request_id: str):
    """Polleado por la ventana principal. Cuando completa, mueve token a sesión."""
    entry = _auth_store.get(request_id)

    if not entry:
        return jsonify({"status": "expired"})

    if entry.get("status") == "pending":
        return jsonify({"status": "pending"})

    if entry.get("status") == "error":
        # Limpiar store
        _auth_store.pop(request_id, None)
        return jsonify({"status": "error", "error": entry.get("error")})

    if entry.get("status") == "completed":
        # Mover token a la sesión de ESTA request (ventana principal)
        session['github_token'] = entry["token"]
        session['github_user'] = entry["user"]
        # Limpiar store (one-time use)
        _auth_store.pop(request_id, None)
        return jsonify({
            "status": "authenticated",
            "user": entry["user"],
        })

    return jsonify({"status": "unknown"})


@auth_bp.route('/api/v1/auth/status', methods=['GET'])
def auth_status():
    """Retorna estado de autenticación de la sesión actual."""
    token = session.get('github_token')
    user = session.get('github_user')
    if token and user:
        return jsonify({"authenticated": True, "user": user})
    return jsonify({"authenticated": False, "user": None})


@auth_bp.route('/api/v1/auth/logout', methods=['POST'])
def logout():
    """Cierra sesión."""
    session.pop('github_token', None)
    session.pop('github_user', None)
    return jsonify({"status": "ok"})


def get_user_github_token() -> str | None:
    """Obtiene el token del usuario autenticado."""
    return session.get('github_token')


def _cleanup_expired():
    """Elimina entries expirados del auth_store."""
    now = time.time()
    expired = [k for k, v in _auth_store.items()
               if now - v.get("created_at", 0) > AUTH_STORE_TTL]
    for k in expired:
        del _auth_store[k]


def _close_page(success: bool, error: str = "", user: str = "") -> str:
    """HTML que muestra resultado y se auto-cierra."""
    if success:
        html = f"""<!DOCTYPE html>
<html><head><title>OmniSpec AI</title>
<style>body{{background:#0d1117;color:#00ff88;font-family:monospace;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0}}
.box{{text-align:center;border:1px solid #00ff88;padding:2rem;border-radius:8px}}</style></head>
<body><div class="box">
<h2>Conectado como {user}</h2>
<p>Puedes cerrar esta ventana.</p>
<script>setTimeout(function(){{window.close()}},2000)</script>
</div></body></html>"""
    else:
        html = f"""<!DOCTYPE html>
<html><head><title>OmniSpec AI — Error</title>
<style>body{{background:#0d1117;color:#ff3b3b;font-family:monospace;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0}}
.box{{text-align:center;border:1px solid #ff3b3b;padding:2rem;border-radius:8px}}</style></head>
<body><div class="box">
<h2>Error de autenticación</h2>
<p>{error}</p>
<p>Cierra esta ventana e intenta de nuevo.</p>
</div></body></html>"""

    response = make_response(html)
    response.headers['Content-Type'] = 'text/html'
    return response
