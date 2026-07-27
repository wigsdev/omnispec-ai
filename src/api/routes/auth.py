"""Auth Routes — GitHub OAuth via Popup + DynamoDB Store + postMessage.

Flujo:
1. Parent: POST /auth/start → DynamoDB: {request_id, status: "pending"}
2. Parent: abre popup /auth/login?request_id=XXX
3. Popup: redirect a GitHub → usuario autoriza
4. Popup: callback → DynamoDB: update {status: "completed", token, user}
5. Popup: postMessage al parent con token + user (canal rápido)
6. Popup: se auto-cierra
7. Parent: recibe postMessage → guarda en localStorage → UI actualizada
8. Parent (fallback): poll → lee de DynamoDB → mismo resultado

No depende de cookies ni de dict en memoria. DynamoDB es compartido
entre todas las instancias Lambda.
"""

import json
import os
import secrets

import requests
from flask import Blueprint, jsonify, make_response, redirect, request, session

from src.api.auth_store import auth_store

auth_bp = Blueprint('auth', __name__)

GITHUB_OAUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
OAUTH_SCOPES = "repo,read:user"


@auth_bp.route('/api/v1/auth/start', methods=['POST'])
def auth_start():
    """Genera un request_id y crea sesión pendiente en DynamoDB."""
    request_id = secrets.token_urlsafe(24)
    auth_store.create_session(request_id)
    return jsonify({"request_id": request_id})


@auth_bp.route('/api/v1/auth/login', methods=['GET'])
def github_login():
    """Redirige a GitHub. Recibe request_id como query param."""
    client_id = os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
    if not client_id:
        return jsonify({"error": "GITHUB_OAUTH_CLIENT_ID no configurado"}), 500

    request_id = request.args.get('request_id', '')
    callback_url = os.environ.get("APP_BASE_URL", "http://localhost:5000")

    params = (
        f"?client_id={client_id}"
        f"&scope={OAUTH_SCOPES}"
        f"&state={request_id}"
        f"&redirect_uri={callback_url}/api/v1/auth/callback"
    )
    return redirect(GITHUB_OAUTH_URL + params)


@auth_bp.route('/api/v1/auth/callback', methods=['GET'])
def github_callback():
    """Callback de GitHub. Guarda token en DynamoDB via auth_store."""
    code = request.args.get('code')
    request_id = request.args.get('state', '')
    error = request.args.get('error')

    if error or not code:
        if request_id and auth_store.exists(request_id):
            auth_store.set_error(request_id, error or "no_code")
        return _close_page(success=False, error=error or "no_code")

    # Verificar que request_id existe en store
    if not auth_store.exists(request_id):
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
        auth_store.set_error(request_id, "token_exchange_failed")
        return _close_page(success=False, error="token_exchange_failed")

    access_token = resp.json().get("access_token")
    if not access_token:
        err = resp.json().get("error_description", "no_token")
        auth_store.set_error(request_id, err)
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

    # Guardar en DynamoDB (compartido entre instancias Lambda)
    auth_store.complete_session(request_id, access_token, user_info)

    return _close_page(
        success=True, user=user_info["login"],
        token=access_token, user_info=user_info
    )


@auth_bp.route('/api/v1/auth/poll/<request_id>', methods=['GET'])
def auth_poll(request_id: str):
    """Polleado por la ventana principal. Lee de DynamoDB (compartido).

    No elimina la entry — DynamoDB TTL se encarga de la limpieza.
    Esto permite reintentos sin race conditions.
    """
    entry = auth_store.get_session(request_id)

    if not entry:
        return jsonify({"status": "expired"})

    status = entry.get("status", "unknown")

    if status == "pending":
        return jsonify({"status": "pending"})

    if status == "error":
        return jsonify({"status": "error", "error": entry.get("error")})

    if status == "completed":
        # Guardar en sesión Flask como backup
        session['github_token'] = entry["token"]
        session['github_user'] = entry["user"]
        return jsonify({
            "status": "authenticated",
            "user": entry["user"],
            "token": entry["token"],
        })

    return jsonify({"status": "unknown"})


@auth_bp.route('/api/v1/auth/status', methods=['GET'])
def auth_status():
    """Retorna estado de autenticación.

    Fuentes (en orden de prioridad):
    1. Header Authorization: Bearer <token> (localStorage del frontend)
    2. Flask session cookie (backup)
    """
    # Fuente primaria: header Authorization
    token = _extract_bearer_token()
    if token:
        user = _validate_github_token(token)
        if user:
            session['github_token'] = token
            session['github_user'] = user
            return jsonify({"authenticated": True, "user": user})
        # Token inválido/revocado
        session.clear()
        return jsonify({"authenticated": False, "user": None})

    # Fallback: sesión Flask
    token = session.get('github_token')
    user = session.get('github_user')
    if token and user:
        return jsonify({"authenticated": True, "user": user})
    return jsonify({"authenticated": False, "user": None})


@auth_bp.route('/api/v1/auth/logout', methods=['POST'])
def logout():
    """Cierra sesión completamente.

    Usa session.clear() + invalida cookie para evitar sesiones zombie.
    """
    session.clear()
    response = make_response(jsonify({"status": "ok"}))
    response.set_cookie('session', '', expires=0, httponly=True, samesite='Lax')
    return response


def get_user_github_token() -> str | None:
    """Obtiene el token del usuario autenticado.

    Fuentes (en orden de prioridad):
    1. Header Authorization: Bearer <token> (enviado desde localStorage)
    2. Flask session cookie (backup)
    """
    token = _extract_bearer_token()
    if token:
        return token
    return session.get('github_token')


def _extract_bearer_token() -> str | None:
    """Extrae token del header Authorization: Bearer <token>."""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer ') and len(auth_header) > 7:
        return auth_header[7:]
    return None


def _validate_github_token(token: str) -> dict | None:
    """Valida un token contra la API de GitHub.

    Args:
        token: GitHub access token.

    Returns:
        Dict con user info si válido, None si expiró/revocado.
    """
    try:
        resp = requests.get(GITHUB_USER_URL, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "login": data.get("login", "unknown"),
                "avatar_url": data.get("avatar_url", ""),
                "name": data.get("name", ""),
            }
    except requests.RequestException:
        pass
    return None


def _close_page(
    success: bool, error: str = "", user: str = "",
    token: str = "", user_info: dict | None = None
) -> str:
    """HTML que envía postMessage al parent y se auto-cierra.

    Usa window.opener.postMessage para comunicar el resultado
    directamente al frontend (canal primario, instantáneo).
    """
    if success:
        user_json = json.dumps(user_info) if user_info else "{}"
        html = f"""<!DOCTYPE html>
<html><head><title>OmniSpec AI</title>
<style>body{{background:#0d1117;color:#00ff88;font-family:monospace;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0}}
.box{{text-align:center;border:1px solid #00ff88;padding:2rem;border-radius:8px}}</style></head>
<body><div class="box">
<h2>Conectado como {user}</h2>
<p>Puedes cerrar esta ventana.</p>
<script>
if (window.opener) {{
    window.opener.postMessage({{
        type: 'omnispec-auth-success',
        token: '{token}',
        user: {user_json}
    }}, '*');
}}
setTimeout(function(){{window.close()}}, 1500);
</script>
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
<script>
if (window.opener) {{
    window.opener.postMessage({{
        type: 'omnispec-auth-error',
        error: '{error}'
    }}, '*');
}}
</script>
</div></body></html>"""

    response = make_response(html)
    response.headers['Content-Type'] = 'text/html'
    return response
