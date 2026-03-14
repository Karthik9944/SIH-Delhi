"""Vercel serverless backend entrypoint.

Vercel expects a Python file in `/api` that exports an ASGI/WSGI app named `app`.
This file simply re-exports the FastAPI app from the backend package.
"""

from backend.main import app  # exposes `app` for Vercel's Python runtime
