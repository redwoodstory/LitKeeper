from flask import Blueprint

highlights = Blueprint('highlights', __name__, url_prefix='/highlights')

from . import routes
