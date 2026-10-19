"""Production WSGI entry point for platforms such as Render.
Set APP_ENV=production, ADMIN_USER, ADMIN_PASS and SESSION_SECRET in the environment.
Use persistent storage for DB_FILE if the database must survive redeploys.
"""
import os
from waitress import serve

if os.environ.get('APP_ENV', '').strip().lower() != 'production':
    raise SystemExit('Set APP_ENV=production before starting this server.')

from app import app

serve(
    app,
    host='0.0.0.0',
    port=int(os.environ.get('PORT', '9000')),
    threads=8,
    connection_limit=1000,
    channel_timeout=30,
)
