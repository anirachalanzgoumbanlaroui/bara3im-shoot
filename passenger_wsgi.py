import os
import sys

sys.path.insert(0, "/home/apqnnbvs/api.bara3im-shoot.com/bara3im-shoot/")

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "config.settings"
)

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()