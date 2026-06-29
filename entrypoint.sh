#!/bin/sh
set -e

. /start-xvfb.sh
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
