"""Lambda Handler — Punto de entrada para AWS Lambda via Mangum.

Adapta la app Flask (WSGI) a eventos Lambda + API Gateway.
Usa asgiref para convertir WSGI→ASGI, luego Mangum adapta ASGI→Lambda.
"""

import os

from dotenv import load_dotenv

# Cargar .env en desarrollo local (en Lambda usa env vars del template)
load_dotenv()

from asgiref.wsgi import WsgiToAsgi
from mangum import Mangum
from src.api.app import create_app

# Crear app Flask (WSGI)
app = create_app()

# Convertir WSGI → ASGI → Lambda handler
asgi_app = WsgiToAsgi(app)
handler = Mangum(asgi_app, lifespan="off")
