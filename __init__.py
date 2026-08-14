"""Total Director — ComfyUI integration package.

Registers the backend routes and the frontend panel (WEB_DIRECTORY).
"""

from .server import routes as _routes

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = "./js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]


def _register():
    try:
        import server as _comfy_server

        _routes.register(_comfy_server.PromptServer.instance.routes)
        print("[TotalDirector] routes registered (panel available at /api/director/*)")
    except Exception as e:  # pragma: no cover
        print(f"[TotalDirector] route registration skipped: {e}")


_register()
