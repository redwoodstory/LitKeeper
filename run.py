from app import create_app

# Create the app using the factory function in app/__init__.py
app = create_app()

if __name__ == "__main__":
    # For local development:
    # Run the app directly using Flask's built-in development server
    app.run(host="0.0.0.0", port=5015, debug=True)