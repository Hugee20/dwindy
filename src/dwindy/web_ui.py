"""Opt-in source-asset hosting. No repository directory is mounted publicly."""
from pathlib import Path

from starlette.responses import FileResponse, RedirectResponse

from .config import ConfigError


WEB_FILES = (
    "index.html", "standalone.js", "standalone.css", "api-client.js",
    "dwindy-chat.js", "dwindy-chat.css",
)
ASSET_FILES = (
    "branding/dwindy-lockup.png", "branding/dwindy-wordmark.png",
    "chatheads/dwindy-idle.png", "chatheads/dwindy-working.png",
)


def frontend_files(root):
    root = Path(root).expanduser().resolve()
    mapping = {}
    for name in [*("web/" + name for name in WEB_FILES), *("assets/" + name for name in ASSET_FILES)]:
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ConfigError("chat-root must contain the complete web/ and assets/ source bundle without external symlinks.")
        mapping["/dwindy/" + name] = path
    return mapping


def add_frontend(app, files):
    headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
                                   "connect-src http: https:; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
    }

    async def index(request):
        return RedirectResponse("/dwindy/web/index.html", status_code=307, headers=headers)

    app.add_route("/chat/", index, methods=["GET", "HEAD"], include_in_schema=False)
    for url, path in files.items():
        def endpoint_for(asset_path):
            async def serve(request):
                media = "text/javascript" if asset_path.suffix == ".js" else None
                return FileResponse(asset_path, media_type=media, headers=headers)
            return serve
        app.add_route(url, endpoint_for(path), methods=["GET", "HEAD"], include_in_schema=False)
