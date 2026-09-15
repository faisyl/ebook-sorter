"""Web interface for ebook-sorter (FastAPI backend).

The ASGI entrypoint is the ``create_app`` factory; run it with uvicorn's
``--factory`` flag, e.g. ``uvicorn ebook_sorter.web:create_app --factory``.
Importing this package does not build the app (so importing it in tests is
cheap and side-effect free); the factory is only invoked at server start.
"""

from .app import create_app

__all__ = ["create_app"]
