"""NotebookLM Toolkit — Web-based suite for Google NotebookLM."""

__version__ = "2.0.0"


def main():
    """Entry point: launch the web server and open browser."""
    from .server import start
    start()
