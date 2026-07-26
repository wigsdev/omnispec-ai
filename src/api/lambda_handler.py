"""Lambda Handler — Punto de entrada para AWS Lambda via Mangum.

Carga secretos desde SSM Parameter Store en runtime (no env vars estáticas).
Adapta Flask (WSGI) → ASGI → Lambda via asgiref + Mangum.
"""

import os

from dotenv import load_dotenv

# Cargar .env en desarrollo local
load_dotenv()


def _load_ssm_secrets():
    """Carga secretos desde SSM Parameter Store en runtime.

    Solo ejecuta si estamos en Lambda (SSM_PREFIX env var presente).
    En dev local, usa .env via dotenv.
    """
    ssm_prefix = os.environ.get("SSM_PREFIX")
    if not ssm_prefix:
        return  # Dev local — usa .env

    # Solo importar boto3 si estamos en Lambda
    import boto3
    ssm = boto3.client('ssm')

    params_to_load = {
        f"{ssm_prefix}/gemini-api-key": "GEMINI_API_KEY",
        f"{ssm_prefix}/groq-api-key": "GROQ_API_KEY",
        f"{ssm_prefix}/github-oauth-client-secret": "GITHUB_OAUTH_CLIENT_SECRET",
        f"{ssm_prefix}/flask-secret-key": "FLASK_SECRET_KEY",
        f"{ssm_prefix}/app-base-url": "APP_BASE_URL",
    }

    try:
        response = ssm.get_parameters(
            Names=list(params_to_load.keys()),
            WithDecryption=True,
        )
        for param in response.get("Parameters", []):
            env_name = params_to_load.get(param["Name"])
            if env_name:
                os.environ[env_name] = param["Value"]
    except Exception as e:
        print(f"[lambda_handler] Warning: could not load SSM params: {e}")


# Cargar secretos antes de crear la app
_load_ssm_secrets()

from asgiref.wsgi import WsgiToAsgi
from mangum import Mangum
from src.api.app import create_app

# Crear app Flask (WSGI) → ASGI → Lambda
app = create_app()
asgi_app = WsgiToAsgi(app)
handler = Mangum(asgi_app, lifespan="off")
