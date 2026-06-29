#!/bin/sh
set -e

if [ "$#" -eq 0 ]; then
    echo "job-entrypoint.sh: missing command" >&2
    echo "Example: job-entrypoint.sh python cli.py pipeline sync-chapters --limit 1" >&2
    exit 1
fi

. /start-xvfb.sh
exec "$@"
