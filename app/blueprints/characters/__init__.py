from flask import Blueprint

characters_bp = Blueprint("characters", __name__, url_prefix="/characters")

from app.blueprints.characters import api, routes  # noqa: E402, F401
