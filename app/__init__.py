"""
Screenshot API Application Package.

This package contains all the components of the self-hosted
website screenshot API service.
"""

from app.main import app, create_app

__version__ = "1.0.0"
__all__ = ["app", "create_app"]
