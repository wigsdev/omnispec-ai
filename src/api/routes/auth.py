"""Auth Routes — GitHub OAuth via Popup + Polling.

El flujo:
1. Ventana principal abre popup → /auth/login
2. Popup redirige a GitHub → usuario autoriza
3. GitHub redirige a /auth/callback → guarda token en sesión
4. Callback muestra "Listo, cierra esta ventana"
5. Ventana principal pollea /auth/status cada 1s
6. Detecta authenticated=true → actualiza UI → continúa

No usa postMessage ni localStorage. La cookie de sesión es
compartida entre popup y parent (mismo dominio).
"""

import os
import secrets

import requests
from flask import Blueprint, jsonify, make_response, redirect, request, session

auth_bp = Blueprint('auth', __name__)

GITHUB_OAUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
OAUTH_SCOPES = "repo,read:user"


@auth_bp.route('/api/v1/auth/login', methods=['GET'])
def github_login():
    """Redirige a GitHub para autorización OAuth."""
    client_id = os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
    if not client_id:
        return jsonify({"error": "GITHUB_OAUTH_CLIENT_ID no configurado"}), 500

    state = secrets.token_urlsafe(16)
    session['oauth_state'] = state

    callback_url = os.environ.get("APP_BASE_URL", "http://localhost:5000")
    params = (
        f"?client_id={client_id}"
        f"&scope={OAUTH_SCOPES}"
        f"&state={state}"
        f"&redirect_uri={callback_url}/api/v1/auth/callback"
    )
    return redirect(GITHUB_OAUTH_URL + params)


@auth_bp.route('/api/v1/auth/callback', methods=['GET'])
def github_callback():
    """Callback de GitHub. Guarda token y muestra página de cierre."""
    code = request.args.get('code')
    error = request.args.get('error')

    if error or not code:
        return _close_page(success=False, error=error or "no_code")

    # Intercambiar code por token
    client_id = os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET", "")

    resp = requests.post(GITHUB_TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
    }, headers={"Accept": "application/json"}, timeout=10)

    if resp.status_code != 200:
        return _close_page(success=False, error="token_exchange_failed")

    access_token = resp.json().get("access_token")
    if not access_token:
        return _close_page(success=False, error=resp.json().get("error_description", "no_token"))

    # Obtener info del usuario
    user_resp = requests.get(GITHUB_USER_URL, headers={
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github.v3+json",
    }, timeout=10)

    user_data = user_resp.json() if user_resp.status_code == 200 else {}

    # Guardar en sesión (compartida con la ventana principal via cookie)
    session['github_token'] = access_token
    session['github_user'] = {
        "login": user_data.get("login", "unknown"),
        "avatar_url": user_data.get("avatar_url", ""),
        "name": user_data.get("name", ""),
    }
    session.pop('oauth_state', None)

    return _close_page(success=True, user=session['github_user']['login'])


@auth_bp.route('/api/v1/auth/status', methods=['GET'])
def auth_status():
    """Retorna estado de autenticación. Polleado por el frontend."""
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


def _close_page(success: bool, error: str = "", user: str = "") -> str:
    """HTML que muestra resultado y se puede cerrar."""
    if success:
        html = f"""<!DOCTYPE html>
<html><head><title>OmniSpec AI</title>
<style>body{{background:#0d1117;color:#00ff88;font-family:monospace;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}}
.box{{text-align:center;border:1px solid #00ff88;padding:2rem;border-radius:8px}}</style></head>
<body><div class="box">
<h2>Conectado como {user}</h2>
<p>Puedes cerrar esta ventana.</p>
<script>setTimeout(()=>window.close(),2000)</script>
</div></body></html>"""
    else:
        html = f"""<!DOCTYPE html>
<html><head><title>OmniSpec AI — Error</title>
<style>body{{background:#0d1117;color:#ff3b3b;font-family:monospace;display:flex;align-items:center;justify-content:center;height:100vh;margin:0}}
.box{{text-align:center;border:1px solid #ff3b3b;padding:2rem;border-radius:8px}}</style></head>
<body><div class="box">
<h2>Error de autenticación</h2>
<p>{error}</p>
<p>Cierra esta ventana e intenta de nuevo.</p>
</div></body></html>"""

    response = make_response(html)
    response.headers['Content-Type'] = 'text/html'
    return response
