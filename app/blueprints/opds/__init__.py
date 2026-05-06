from flask import Blueprint, Response, abort, request
from werkzeug.security import check_password_hash

opds_bp = Blueprint('opds', __name__, url_prefix='/opds')


@opds_bp.before_request
def check_opds_access():
    from app.models import AppConfig
    opds_cfg = AppConfig.query.filter_by(key='opds_enabled').first()
    if not opds_cfg or not opds_cfg.get_value():
        abort(404)

    auth_cfg = AppConfig.query.filter_by(key='opds_auth_enabled').first()
    if not auth_cfg or not auth_cfg.get_value():
        return

    auth = request.authorization
    if not auth:
        return Response('Authentication required', 401,
                        {'WWW-Authenticate': 'Basic realm="LitKeeper OPDS"'})

    username_cfg = AppConfig.query.filter_by(key='opds_username').first()
    password_hash_cfg = AppConfig.query.filter_by(key='opds_password_hash').first()

    valid_user = username_cfg and username_cfg.value == auth.username
    valid_pass = password_hash_cfg and password_hash_cfg.value and \
        check_password_hash(password_hash_cfg.value, auth.password)

    if not valid_user or not valid_pass:
        return Response('Invalid credentials', 401,
                        {'WWW-Authenticate': 'Basic realm="LitKeeper OPDS"'})


from . import routes
