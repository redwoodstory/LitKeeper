#!/bin/bash
set -e

DATA_DIR="/litkeeper/app/data"
STORIES_DIR="/litkeeper/app/stories"

mkdir -p "$STORIES_DIR/epubs" "$STORIES_DIR/html" "$STORIES_DIR/covers"

echo "Stories directory ready at $STORIES_DIR"

echo "Running database migrations..."
SKIP_BACKGROUND_WORKERS=true flask db upgrade

SCRIPT="/litkeeper/update_epub_descriptions.py"
if [ -f "$SCRIPT" ]; then
    echo "Injecting missing DC:description into existing EPUBs (one-time)..."
    SKIP_BACKGROUND_WORKERS=true python "$SCRIPT"
    rm "$SCRIPT"
fi

echo "Starting application..."
exec "$@"
