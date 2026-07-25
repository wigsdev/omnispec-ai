"""Flask app factory — Servidor principal de OmniSpec AI.

Sirve el frontend estático y expone los endpoints REST de la API.
"""

import os

from flask import Flask, jsonify, send_from_directory


def create_app() -> Flask:
    """Crea y configura la aplicación Flask.

    Returns:
        Instancia de Flask configurada con rutas y static files.
    """
    app = Flask(
        __name__,
        static_folder=os.path.join(os.path.dirname(__file__), '../../frontend'),
        static_url_path='/static'
    )

    # Servir index.html en la raíz
    @app.route('/')
    def index():
        """Sirve la interfaz gráfica principal."""
        frontend_dir = os.path.join(os.path.dirname(__file__), '../../frontend')
        return send_from_directory(frontend_dir, 'index.html')

    # Health check endpoint
    @app.route('/api/v1/health')
    def health():
        """Retorna estado de salud de la API."""
        return jsonify({"status": "ok"})

    return app


# Entry point para ejecución directa
if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
