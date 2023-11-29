from __future__ import annotations

import os

#####
# GUNICORN CONFIG FOLLOWS
#####

errorlog = "-"
loglevel = "info"
accesslog = "-"
workers = int(os.getenv("GUNICORN_WORKERS", "4"))

if "GUNICORN_TIMEOUT" in os.environ:
    timeout = int(os.environ["GUNICORN_TIMEOUT"])
