#!/bin/bash
set -e

DATA_DIR="/litkeeper/app/data"
STORIES_DIR="/litkeeper/app/stories"

mkdir -p "$STORIES_DIR/epubs" "$STORIES_DIR/html" "$STORIES_DIR/covers"

echo "Stories directory ready at $STORIES_DIR"

echo "Running database migrations..."
SKIP_BACKGROUND_WORKERS=true flask db upgrade

echo "Starting application..."
exec "$@"
