"""Flask app factory — Servidor principal de OmniSpec AI.

Sirve el frontend estático y expone los endpoints REST de la API.
Configura CORS, manejo centralizado de errores y blueprints.
"""

import os

from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env en la raíz del proyecto
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(dotenv_path=env_path)
load_dotenv()  # Fallback por defecto

from flask import Flask, jsonify, send_from_directory


def create_app() -> Flask:
    """Crea y configura la aplicación Flask.

    Returns:
        Instancia de Flask configurada con rutas, CORS y error handlers.
    """
    frontend_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '../../frontend')
    )

    app = Flask(
        __name__,
        static_folder=frontend_dir,
        static_url_path='/static'
    )

    # Session config (for OAuth tokens)
    secret_key = os.environ.get("FLASK_SECRET_KEY")
    if not secret_key:
        import warnings
        warnings.warn("FLASK_SECRET_KEY not set! Sessions won't persist across restarts.")
        import secrets as _s
        secret_key = _s.token_urlsafe(32)
    app.secret_key = secret_key
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # CORS headers
    @app.after_request
    def add_cors_headers(response):
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        return response

    # Error handlers
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "bad_request", "message": str(e)}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not_found", "message": "Recurso no encontrado"}), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "internal_error", "message": "Error interno del servidor"}), 500

    # Servir index.html en la raíz
    @app.route('/')
    def index():
        """Sirve la interfaz gráfica principal."""
        return send_from_directory(frontend_dir, 'index.html')

    # Health check endpoint
    @app.route('/api/v1/health')
    def health():
        """Retorna estado de salud de la API."""
        return jsonify({"status": "ok"})

    # Register blueprints
    from src.api.routes.generator import generator_bp
    from src.api.routes.auditor import auditor_bp
    from src.api.routes.fixer import fixer_bp
    from src.api.routes.auth import auth_bp
    app.register_blueprint(generator_bp)
    app.register_blueprint(auditor_bp)
    app.register_blueprint(fixer_bp)
    app.register_blueprint(auth_bp)

    return app


# Entry point para ejecución directa
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
