"""ASGI entrypoint for uvicorn: `uvicorn app.asgi:app`.

Separate from `main` so that importing the factory has no side effects.
"""

from app.main import create_app

app = create_app()
