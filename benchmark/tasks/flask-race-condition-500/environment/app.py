"""
Flask application factory for the analytics processing service.

Usage
─────
    Development:   flask --app app run
    Production:    gunicorn 'app:create_app()'

The application runs with Flask's default settings, which includes
threaded mode for handling concurrent requests.
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

from flask import Flask, jsonify, request

from config import config


def create_app(testing: bool = False) -> Flask:
    """Create and configure the Flask application instance."""
    app = Flask(__name__)
    app.config["TESTING"] = testing
    app.config["SECRET_KEY"] = config.secret_key
    app.config["MAX_CONTENT_LENGTH"] = config.processing.max_payload_bytes

    _setup_logging(app)
    _register_blueprints(app)
    _register_global_error_handlers(app)
    _register_hooks(app)

    app.logger.info(
        "App created — version=%s debug=%s testing=%s",
        config.version, config.debug, testing,
    )
    return app


# ── Internals ────────────────────────────────────────────────────────────

def _setup_logging(app: Flask) -> None:
    """Configure root logger and silence noisy third-party loggers."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(config.logging.format))
    root = logging.getLogger()
    root.setLevel(getattr(logging, config.logging.level, logging.INFO))
    root.addHandler(handler)

    # Quiet down werkzeug request-log noise in non-debug mode
    if not config.debug:
        logging.getLogger("werkzeug").setLevel(logging.WARNING)


def _register_blueprints(app: Flask) -> None:
    from routes import api
    app.register_blueprint(api)


def _register_global_error_handlers(app: Flask) -> None:
    """Catch-all handlers for errors that escape blueprint handlers."""

    @app.errorhandler(405)
    def method_not_allowed(exc):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(413)
    def payload_too_large(exc):
        limit_kb = config.processing.max_payload_bytes // 1024
        return jsonify({
            "error": "Payload too large",
            "max_kb": limit_kb,
        }), 413

    @app.errorhandler(Exception)
    def unhandled(exc):
        app.logger.exception("Unhandled exception in %s %s", request.method, request.path)
        return jsonify({"error": "Internal server error"}), 500


def _register_hooks(app: Flask) -> None:
    """Before / after request hooks for cross-cutting concerns."""

    @app.before_request
    def reject_non_json_posts():
        if request.method == "POST" and request.path.startswith("/api/"):
            ct = request.content_type or ""
            if "application/json" not in ct:
                return jsonify({"error": "Content-Type must be application/json"}), 415

    @app.after_request
    def add_common_headers(response):
        response.headers["X-Service"] = config.app_name
        response.headers["X-Version"] = config.version
        return response


# ── Standalone entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    application = create_app()
    application.run(
        host=config.host,
        port=config.port,
        debug=config.debug,
        # NOTE: Flask defaults to threaded=True since 1.0
    )
