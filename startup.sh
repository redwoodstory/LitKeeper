#!/bin/bash
set -e

DATA_DIR="/litkeeper/app/data"
DIRS_TO_CHECK=("epubs" "html" "covers")

echo "Checking for bind mounts..."

for dir_name in "${DIRS_TO_CHECK[@]}"; do
    dir_path="$DATA_DIR/$dir_name"
    marker_file="$dir_path/.mount_marker"

    mkdir -p "$dir_path"

    if [ ! -f "$marker_file" ]; then
        echo "No bind mount detected for $dir_name - clearing directory..."
        rm -rf "$dir_path"/*
        echo "Cleared $dir_path"
    else
        echo "Bind mount detected for $dir_name (marker file exists)"
    fi
done

echo "Starting application..."
exec "$@"
