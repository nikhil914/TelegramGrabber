"""
TeleLink — Entry Point

Launches the Streamlit app inside a native desktop window
using streamlit-desktop-app.
"""
import os
import sys
from pathlib import Path


def run():
    """Launch TeleLink as a desktop application."""
    app_path = str(Path(__file__).resolve().parent / "ui" / "app.py")

    try:
        from streamlit_desktop_app import main as desktop_main
        desktop_main(
            app_path=app_path,
            title="TeleLink — Telegram Link Extractor",
            width=1280,
            height=860,
        )
    except ImportError:
        # Fallback: launch via streamlit CLI directly
        import subprocess
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", app_path,
             "--server.headless", "true",
             "--browser.gatherUsageStats", "false"],
            cwd=str(Path(__file__).resolve().parent),
        )
    except Exception:
        # Final fallback — plain streamlit run
        import subprocess
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", app_path],
            cwd=str(Path(__file__).resolve().parent),
        )


if __name__ == "__main__":
    run()
