#!/usr/bin/env bash
set -o errexit
python manage.py migrate --noinput
python manage.py generate_demo
python manage.py sync_flamingo_international || echo "Flamingo international sync skipped; keeping last successful catalogue."
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-10000}"
