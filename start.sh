#!/usr/bin/env bash
set -o errexit
python manage.py migrate --noinput
python manage.py check_sms_delivery
python manage.py generate_demo
python manage.py import_flamingo_domestic_private --min-records 60
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-10000}"
