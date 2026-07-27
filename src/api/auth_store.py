"""AuthStore — Almacenamiento persistente de sesiones OAuth.

Usa DynamoDB (tabla omnispec-cache) como backend para el flujo
OAuth popup. Resuelve el problema de múltiples instancias Lambda
donde un dict en memoria no es compartido entre invocaciones.

Esquema en DynamoDB:
    pk: "AUTH#{request_id}"
    sk: "session"
    status: "pending" | "completed" | "error"
    token: str (access token de GitHub, solo si completed)
    user: dict (login, avatar_url, name)
    error: str (mensaje de error, solo si error)
    ttl: int (epoch + 300s = 5 minutos de vida)
    created_at: float (timestamp de creación)

En desarrollo local (sin DYNAMODB_CACHE_TABLE), usa un dict en memoria
como fallback para que el servidor funcione sin DynamoDB.
"""

import os
import time
from typing import Any

# TTL: 5 minutos
AUTH_SESSION_TTL = 300


class AuthStore:
    """Interfaz de almacenamiento de sesiones OAuth.

    Usa DynamoDB en producción (Lambda) y un dict en memoria
    en desarrollo local (cuando DYNAMODB_CACHE_TABLE no está definido).
    """

    def __init__(self):
        """Inicializa el store según el entorno."""
        self._table_name = os.environ.get("DYNAMODB_CACHE_TABLE")
        self._table = None
        self._local_store: dict = {}

        if self._table_name:
            try:
                import boto3
                dynamodb = boto3.resource("dynamodb")
                self._table = dynamodb.Table(self._table_name)
            except Exception as e:
                print(f"[AuthStore] Warning: DynamoDB no disponible, usando memoria: {e}")

    @property
    def _is_dynamo(self) -> bool:
        """True si estamos usando DynamoDB."""
        return self._table is not None

    def create_session(self, request_id: str) -> None:
        """Crea una sesión OAuth pendiente.

        Args:
            request_id: Identificador único de la sesión OAuth.
        """
        now = time.time()
        ttl = int(now) + AUTH_SESSION_TTL

        if self._is_dynamo:
            self._table.put_item(Item={
                "pk": f"AUTH#{request_id}",
                "sk": "session",
                "status": "pending",
                "created_at": int(now),
                "ttl": ttl,
            })
        else:
            self._local_store[request_id] = {
                "status": "pending",
                "created_at": now,
            }
            self._cleanup_local()

    def complete_session(self, request_id: str, token: str, user: dict) -> None:
        """Marca la sesión como completada con token y user info.

        Args:
            request_id: Identificador de la sesión.
            token: GitHub access token.
            user: Dict con login, avatar_url, name.
        """
        now = time.time()
        ttl = int(now) + AUTH_SESSION_TTL

        if self._is_dynamo:
            self._table.update_item(
                Key={"pk": f"AUTH#{request_id}", "sk": "session"},
                UpdateExpression="SET #s = :status, #t = :token, #u = :user, #ttl = :ttl",
                ExpressionAttributeNames={
                    "#s": "status",
                    "#t": "token",
                    "#u": "user",
                    "#ttl": "ttl",
                },
                ExpressionAttributeValues={
                    ":status": "completed",
                    ":token": token,
                    ":user": user,
                    ":ttl": ttl,
                },
            )
        else:
            self._local_store[request_id] = {
                "status": "completed",
                "token": token,
                "user": user,
                "created_at": now,
            }

    def set_error(self, request_id: str, error: str) -> None:
        """Marca la sesión como error.

        Args:
            request_id: Identificador de la sesión.
            error: Mensaje de error.
        """
        now = time.time()
        ttl = int(now) + 60  # Errores expiran en 1 minuto

        if self._is_dynamo:
            self._table.update_item(
                Key={"pk": f"AUTH#{request_id}", "sk": "session"},
                UpdateExpression="SET #s = :status, #e = :error, #ttl = :ttl",
                ExpressionAttributeNames={
                    "#s": "status",
                    "#e": "error",
                    "#ttl": "ttl",
                },
                ExpressionAttributeValues={
                    ":status": "error",
                    ":error": error,
                    ":ttl": ttl,
                },
            )
        else:
            self._local_store[request_id] = {
                "status": "error",
                "error": error,
                "created_at": now,
            }

    def get_session(self, request_id: str) -> dict[str, Any] | None:
        """Obtiene una sesión por request_id.

        Args:
            request_id: Identificador de la sesión.

        Returns:
            Dict con status, token, user, error según estado.
            None si la sesión no existe o expiró.
        """
        if self._is_dynamo:
            try:
                resp = self._table.get_item(
                    Key={"pk": f"AUTH#{request_id}", "sk": "session"}
                )
                item = resp.get("Item")
                if not item:
                    return None
                # DynamoDB TTL no elimina inmediatamente — verificar manualmente
                if item.get("ttl", 0) < int(time.time()):
                    return None
                return {
                    "status": item.get("status", "unknown"),
                    "token": item.get("token"),
                    "user": item.get("user"),
                    "error": item.get("error"),
                }
            except Exception as e:
                print(f"[AuthStore] Error reading session: {e}")
                return None
        else:
            entry = self._local_store.get(request_id)
            if not entry:
                return None
            # Verificar TTL local
            if time.time() - entry.get("created_at", 0) > AUTH_SESSION_TTL:
                self._local_store.pop(request_id, None)
                return None
            return entry

    def exists(self, request_id: str) -> bool:
        """Verifica si una sesión existe (no expirada).

        Args:
            request_id: Identificador de la sesión.

        Returns:
            True si existe y no ha expirado.
        """
        return self.get_session(request_id) is not None

    def _cleanup_local(self) -> None:
        """Limpia entries expirados del store local (solo en dev)."""
        if self._is_dynamo:
            return
        now = time.time()
        expired = [k for k, v in self._local_store.items()
                   if now - v.get("created_at", 0) > AUTH_SESSION_TTL]
        for k in expired:
            del self._local_store[k]


# Singleton: una instancia por Lambda container / proceso Flask
auth_store = AuthStore()
