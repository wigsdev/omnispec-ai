"""Auth Routes — GitHub OAuth Authentication Flow.

Implementa el flujo OAuth 2.0 de GitHub para obtener tokens
de acceso del usuario. El token se almacena en sesión y se
usa para crear PRs en nombre del usuario.

Endpoints:
    GET  /api/v1/auth/login    — Redirige a GitHub para login
    GET  /api/v1/auth/callback — Callback de GitHub con code
    GET  /api/v1/auth/status   — Estado de autenticación actual
    POST /api/v1/auth/logout   — Elimina el token de sesión
"""

import os
import secrets

import requests
from flask import Blueprint, jsonify, redirect, request, session

auth_bp = Blueprint('auth', __name__)

GITHUB_OAUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"

# Scopes requeridos: repo (para crear PRs) + read:user (para perfil)
OAUTH_SCOPES = "repo,read:user"


@auth_bp.route('/api/v1/auth/login', methods=['GET'])
def github_login():
    """Inicia el flujo OAuth redirigiendo a GitHub.

    Genera un state token para prevenir CSRF y redirige
    al usuario a la página de autorización de GitHub.
    """
    client_id = os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
    if not client_id:
        return jsonify({
            "error": "config_error",
            "message": "GITHUB_OAUTH_CLIENT_ID no configurado"
        }), 500

    # Generar state para CSRF protection
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state

    # Construir URL de autorización
    params = (
        f"?client_id={client_id}"
        f"&scope={OAUTH_SCOPES}"
        f"&state={state}"
        f"&redirect_uri={_get_callback_url()}"
    )

    return redirect(GITHUB_OAUTH_URL + params)


@auth_bp.route('/api/v1/auth/callback', methods=['GET'])
def github_callback():
    """Callback de GitHub OAuth.

    Intercambia el code por un access_token y almacena
    el token + info del usuario en sesión.
    """
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')

    if error:
        return _redirect_to_app(f"?auth_error={error}")

    # Validar state (CSRF protection)
    if state != session.get('oauth_state'):
        return _redirect_to_app("?auth_error=invalid_state")

    # Intercambiar code por access_token
    client_id = os.environ.get("GITHUB_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("GITHUB_OAUTH_CLIENT_SECRET", "")

    token_response = requests.post(
        GITHUB_TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
        },
        headers={"Accept": "application/json"},
        timeout=10,
    )

    if token_response.status_code != 200:
        return _redirect_to_app("?auth_error=token_exchange_failed")

    token_data = token_response.json()
    access_token = token_data.get("access_token")

    if not access_token:
        error_desc = token_data.get("error_description", "Unknown error")
        return _redirect_to_app(f"?auth_error={error_desc}")

    # Obtener info del usuario
    user_response = requests.get(
        GITHUB_USER_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json",
        },
        timeout=10,
    )

    user_data = {}
    if user_response.status_code == 200:
        user_data = user_response.json()

    # Guardar en sesión
    session['github_token'] = access_token
    session['github_user'] = {
        "login": user_data.get("login", "unknown"),
        "avatar_url": user_data.get("avatar_url", ""),
        "name": user_data.get("name", ""),
    }

    return _redirect_to_app("?auth_success=true")


@auth_bp.route('/api/v1/auth/status', methods=['GET'])
def auth_status():
    """Retorna el estado de autenticación del usuario."""
    token = session.get('github_token')
    user = session.get('github_user')

    if token and user:
        return jsonify({
            "authenticated": True,
            "user": user,
        })

    return jsonify({
        "authenticated": False,
        "user": None,
    })


@auth_bp.route('/api/v1/auth/logout', methods=['POST'])
def logout():
    """Elimina el token y datos de sesión."""
    session.pop('github_token', None)
    session.pop('github_user', None)
    session.pop('oauth_state', None)
    return jsonify({"status": "ok", "message": "Sesión cerrada"})


def get_user_github_token() -> str | None:
    """Obtiene el token GitHub del usuario actual desde la sesión.

    Usado por PRCreator para crear PRs en nombre del usuario.

    Returns:
        Token de acceso o None si no autenticado.
    """
    return session.get('github_token')


def _get_callback_url() -> str:
    """Construye la URL de callback basada en el host actual."""
    base_url = os.environ.get(
        "APP_BASE_URL", "http://localhost:5000"
    )
    return f"{base_url}/api/v1/auth/callback"


def _redirect_to_app(query: str = "") -> str:
    """Redirige al frontend de la app."""
    base_url = os.environ.get("APP_BASE_URL", "http://localhost:5000")
    return redirect(f"{base_url}/{query}")
