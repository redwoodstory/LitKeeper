#!/bin/bash
set -e

STORIES_DIR="/litkeeper/app/stories"
MARKER_FILE="$STORIES_DIR/.mount_marker"

echo "Checking for stories bind mount..."

mkdir -p "$STORIES_DIR/epubs" "$STORIES_DIR/html" "$STORIES_DIR/covers"

# Create marker file to indicate mount is configured
touch "$MARKER_FILE" 2>/dev/null || echo "Note: Could not create marker file (read-only mount?)"

echo "Stories directory ready at $STORIES_DIR"

echo "Running database migrations..."
SKIP_BACKGROUND_WORKERS=true flask db upgrade

echo "Starting application..."
exec "$@"
