#!/bin/bash

export PYTHONPATH="${PYTHONPATH}:$(pwd)"

if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

gunicorn -c gunicorn.conf.py "app:create_app()"
