from __future__ import annotations
import os
from flask import Blueprint, current_app, render_template

browse_bp = Blueprint('browse', __name__)


@browse_bp.route('/browse')
def browse_page():
    db_path = os.path.join(current_app.root_path, 'data', 'custom_url_dataset.db')
    return render_template('browse.html', custom_list_available=os.path.exists(db_path))
