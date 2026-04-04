"""Planex Desktop — native window wrapping the web UI."""

import threading
import time
import sys
import webbrowser
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()
load_dotenv(Path.home() / ".planex" / ".env")


def start_backend():
    """Start FastAPI in a background thread."""
    import uvicorn
    from dashboard.app import app
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


class Api:
    """Exposed to JavaScript via pywebview."""
    def openUrl(self, url: str):
        webbrowser.open(url)


def on_navigation(url: str) -> bool:
    """Intercept navigation — open external URLs in system browser."""
    if url and not url.startswith("http://localhost") and not url.startswith("http://127.0.0.1"):
        webbrowser.open(url)
        return False  # Block navigation in the window
    return True


def _set_dock_icon():
    """Set macOS dock icon before webview starts."""
    try:
        from AppKit import NSApplication, NSImage
        icon_path = str(Path(__file__).parent / "assets" / "icon.png")
        app = NSApplication.sharedApplication()
        icon = NSImage.alloc().initWithContentsOfFile_(icon_path)
        if icon:
            app.setApplicationIconImage_(icon)
    except Exception:
        pass


def main():
    _set_dock_icon()

    import webview

    server = threading.Thread(target=start_backend, daemon=True)
    server.start()
    time.sleep(1)

    window = webview.create_window(
        "Planex — Research Assistant",
        url="http://localhost:8000",
        width=1280,
        height=800,
        min_size=(900, 600),
        js_api=Api(),
    )

    # Intercept external link clicks
    window.events.loaded += lambda: window.evaluate_js("""
        document.addEventListener('click', function(e) {
            var a = e.target.closest('a');
            if (a && a.href && !a.href.startsWith('http://localhost') && !a.href.startsWith('http://127.0.0.1')) {
                e.preventDefault();
                if (window.pywebview && window.pywebview.api) {
                    window.pywebview.api.openUrl(a.href);
                } else {
                    window.open(a.href, '_blank');
                }
            }
        }, true);
    """)

    webview.start(debug=("--debug" in sys.argv))


if __name__ == "__main__":
    main()
