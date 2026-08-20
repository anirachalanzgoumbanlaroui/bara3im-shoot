import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.daily_sessions.models import WorkDay
from apps.daily_sessions.serializers import WorkDaySerializer

try:
    wd = WorkDay.objects.prefetch_related(
        'teams', 'seller_operations', 'teams__performances',
        'teams__photographer', 'teams__clown', 'seller_operations__seller'
    ).filter(date='2026-08-18').first()

    print("Found WorkDay:", wd)
    if wd:
        serializer = WorkDaySerializer(wd)
        print("Data keys:", serializer.data.keys())
        print("Teams serialized:", len(serializer.data['teams']))
        print("Seller operations serialized:", len(serializer.data['seller_operations']))
except Exception as e:
    import traceback
    traceback.print_exc()
