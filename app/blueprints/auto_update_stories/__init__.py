from flask import Blueprint

auto_update_stories = Blueprint('auto_update_stories', __name__, url_prefix='/auto-update-stories')

from . import routes
