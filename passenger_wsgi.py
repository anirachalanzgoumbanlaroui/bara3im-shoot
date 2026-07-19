import os
import sys

BASE_DIR = "/home/apqnnbvs/api.bara3im-shoot.com/bara3im-shoot"

sys.path.insert(0, BASE_DIR)

# Add virtualenv site-packages so Django & dependencies are importable
VENV_PATH = "/home/apqnnbvs/api.bara3im-shoot.com/bara3im-shoot/venv/lib/python3.10/site-packages"
if os.path.exists(VENV_PATH):
    sys.path.insert(0, VENV_PATH)

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings"
)

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()