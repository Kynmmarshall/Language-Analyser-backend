# -*- coding: utf-8 -*-
"""
Production entry point for PM2. `python app.py` (Flask's own dev server) is fine for
local testing, but isn't meant to serve real traffic — this runs the same Flask `app`
through waitress, a small pure-Python production WSGI server (no C build step, so it
installs the same way on the Windows dev machine and the Linux VPS).

Run directly:
    python wsgi.py
(PM2 does exactly this — see deploy/ecosystem.config.js.)
"""

import os

from waitress import serve

from app import app

if __name__ == "__main__":
    host = os.environ.get("YO_B_HOST", "127.0.0.1")
    port = int(os.environ.get("YO_B_PORT", 5000))
    print("Serving Yo-B on http://{}:{} (waitress)".format(host, port))
    serve(app, host=host, port=port)
