#!/bin/bash
set -e

DATA_DIR="/litkeeper/app/data"
STORIES_DIR="/litkeeper/app/stories"

echo "Checking directory permissions..."

# Validate write access to required directories
if [ ! -w "$DATA_DIR" ]; then
    echo "ERROR: Data directory not writable: $DATA_DIR"
    echo "Ensure volume mounted with correct permissions (UID:GID 1000:1000)"
    exit 1
fi

if [ ! -w "$STORIES_DIR" ]; then
    echo "ERROR: Stories directory not writable: $STORIES_DIR"
    echo "Ensure volume mounted with correct permissions (UID:GID 1000:1000)"
    exit 1
fi

echo "Directory permissions validated"

mkdir -p "$STORIES_DIR/epubs" "$STORIES_DIR/html" "$STORIES_DIR/covers"

echo "Stories directory ready at $STORIES_DIR"

echo "Running database migrations..."
SKIP_BACKGROUND_WORKERS=true flask db upgrade

echo "Starting application..."
exec "$@"
