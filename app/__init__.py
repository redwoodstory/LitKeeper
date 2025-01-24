from flask import Flask
import os

def create_app():
    app = Flask(__name__)

    # Generate a random secret key at startup
    app.config['SECRET_KEY'] = os.urandom(24)

    app.config['UPLOAD_FOLDER'] = "app/epub_files"  # Directory to store EPUB files

    # Register Blueprints
    from .routes import main
    app.register_blueprint(main)

    return app