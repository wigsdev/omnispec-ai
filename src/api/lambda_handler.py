"""Lambda Handler — Punto de entrada para AWS Lambda.

Usa serverless-wsgi para adaptar Flask (WSGI) a eventos Lambda.
Compatible con API Gateway HTTP API v2.
"""

import os

from dotenv import load_dotenv

# Cargar .env en desarrollo local (en Lambda usa env vars del template)
load_dotenv()

import serverless_wsgi
from src.api.app import create_app

# Crear app Flask
app = create_app()


def handler(event, context):
    """Lambda handler — convierte evento API GW → WSGI → Flask."""
    return serverless_wsgi.handle_request(app, event, context)
