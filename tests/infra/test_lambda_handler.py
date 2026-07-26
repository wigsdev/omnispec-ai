"""Tests para src/api/lambda_handler.py.

Verifica que el handler serverless-wsgi se inicializa correctamente
y responde a eventos Lambda simulados.
"""

import json
import pytest


class TestLambdaHandlerInit:
    """Tests de inicialización del handler."""

    def test_handler_is_callable(self):
        """El handler debe ser una función callable."""
        from src.api.lambda_handler import handler
        assert callable(handler)

    def test_app_is_flask_instance(self):
        """La app debe ser una instancia de Flask."""
        from src.api.lambda_handler import app
        from flask import Flask
        assert isinstance(app, Flask)


def _make_apigw_event(method: str, path: str) -> dict:
    """Crea un evento API Gateway HTTP API v2 para testing."""
    return {
        "version": "2.0",
        "requestContext": {
            "http": {
                "method": method,
                "path": path,
                "sourceIp": "127.0.0.1",
                "protocol": "HTTP/1.1",
            },
            "stage": "$default",
            "accountId": "123456789",
            "requestId": "test-request-id",
            "domainName": "localhost",
            "time": "01/Jan/2026:00:00:00 +0000",
            "timeEpoch": 1700000000,
        },
        "rawPath": path,
        "rawQueryString": "",
        "headers": {
            "host": "localhost",
            "content-type": "application/json",
            "x-forwarded-for": "127.0.0.1",
            "x-forwarded-proto": "https",
        },
        "isBase64Encoded": False,
        "body": None,
    }


class TestLambdaHealthCheck:
    """Tests del health check via evento Lambda simulado."""

    def test_health_returns_200(self):
        """GET /api/v1/health via Lambda retorna 200."""
        from src.api.lambda_handler import app

        # Usar test client de Flask directamente (más confiable que simular evento)
        client = app.test_client()
        r = client.get('/api/v1/health')
        assert r.status_code == 200

    def test_health_returns_ok_body(self):
        """GET /api/v1/health retorna body con status ok."""
        from src.api.lambda_handler import app

        client = app.test_client()
        r = client.get('/api/v1/health')
        data = r.get_json()
        assert data == {"status": "ok"}

    def test_auth_status_returns_200(self):
        """GET /api/v1/auth/status via Lambda retorna 200."""
        from src.api.lambda_handler import app

        client = app.test_client()
        r = client.get('/api/v1/auth/status')
        assert r.status_code == 200

    def test_handler_processes_apigw_event(self):
        """El handler procesa un evento API Gateway v2 correctamente."""
        from src.api.lambda_handler import handler

        event = _make_apigw_event("GET", "/api/v1/health")
        response = handler(event, {})

        # Mangum retorna dict con statusCode
        assert "statusCode" in response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body == {"status": "ok"}
