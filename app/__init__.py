from __future__ import annotations
from flask import Flask
import os
from datetime import datetime
from dotenv import load_dotenv
from typing import Any

load_dotenv()

def create_app() -> Flask:
    app = Flask(__name__)

    secret_key = os.getenv('SECRET_KEY')
    if not secret_key:
        import secrets
        secret_key = secrets.token_hex(32)
        print("WARNING: No SECRET_KEY found in environment. Using temporary key.")
        print("Generate a permanent key with: python -c \"import secrets; print(secrets.token_hex(32))\"")
        print("Add it to your .env file or environment variables.")

    app.config['SECRET_KEY'] = secret_key

    app.config['UPLOAD_FOLDER'] = "app/epub_files"  # Directory to store EPUB files

    # Register template filters
    @app.template_filter('format_date')
    def format_date(value: Any) -> str:
        if not value:
            return ''
        try:
            if isinstance(value, str):
                dt = datetime.fromisoformat(value)
            else:
                dt = value
            return dt.strftime('%b %d, %Y')
        except:
            return value

    @app.template_filter('format_size')
    def format_size(bytes: Any) -> str:
        if not bytes:
            return ''
        try:
            bytes = int(bytes)
            if bytes < 1024:
                return f'{bytes} B'
            elif bytes < 1024 * 1024:
                return f'{bytes / 1024:.1f} KB'
            else:
                return f'{bytes / (1024 * 1024):.1f} MB'
        except:
            return ''

    @app.template_filter('format_word_count')
    def format_word_count(count: Any) -> str:
        if not count:
            return ''
        try:
            count = int(count)
            if count < 1000:
                return f'{count} words'
            else:
                return f'{count / 1000:.1f}k words'
        except:
            return ''

    # Register Blueprints
    from .blueprints import api, library, downloads, errors

    app.register_blueprint(api)
    app.register_blueprint(library)
    app.register_blueprint(downloads)
    app.register_blueprint(errors)

    return app