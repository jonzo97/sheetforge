import os

from flask import Flask, redirect, url_for

from config import config_map


def create_app(config_name: str | None = None) -> Flask:
    """Application factory."""
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_map[config_name])

    # Fail loudly if SECRET_KEY isn't set in production
    if config_name == "production" and app.config["SECRET_KEY"] == "dev-secret-change-in-prod":
        raise RuntimeError("SECRET_KEY must be set via environment variable in production")

    # Fix Render's postgres:// URL (SQLAlchemy requires postgresql://)
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri and uri.startswith("postgres://"):
        app.config["SQLALCHEMY_DATABASE_URI"] = uri.replace("postgres://", "postgresql://", 1)

    # Initialize extensions
    from app.extensions import db, login_manager, migrate

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Register blueprints
    from app.blueprints.auth import auth_bp
    from app.blueprints.characters import characters_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(characters_bp)

    # Load SRD data
    from app.srd import load_srd_data

    load_srd_data()

    @app.route("/")
    def index():
        return redirect(url_for("characters.character_list"))

    return app
