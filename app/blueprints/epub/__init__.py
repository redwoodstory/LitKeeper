from flask import Blueprint

epub = Blueprint('epub', __name__, url_prefix='/epub')

from . import routes
