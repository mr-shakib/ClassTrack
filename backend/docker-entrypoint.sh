#!/bin/sh
# Bring the schema up to date, then hand off to the server.
#
# The application only creates tables itself outside production; production is
# migration-driven so that a schema change is a reviewed, reversible step rather
# than a side effect of a deploy.
set -e

echo "Applying database migrations..."
alembic upgrade head

exec "$@"
