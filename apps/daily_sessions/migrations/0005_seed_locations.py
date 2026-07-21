from django.db import migrations


def seed_locations(apps, schema_editor):
    """
    Seeds the two permanent work locations: Ardis and Sablette.
    """
    Location = apps.get_model('daily_sessions', 'Location')
    Location.objects.get_or_create(
        name='Ardis',
        defaults={'icon': '🏬', 'color_hex': '#1565C0'}
    )
    Location.objects.get_or_create(
        name='Sablette',
        defaults={'icon': '🏖️', 'color_hex': '#00695C'}
    )


def reverse_seed_locations(apps, schema_editor):
    Location = apps.get_model('daily_sessions', 'Location')
    Location.objects.filter(name__in=['Ardis', 'Sablette']).delete()


class Migration(migrations.Migration):
    """
    Data migration: seeds the two permanent locations (Ardis, Sablette).
    """
    dependencies = [
        ('daily_sessions', '0004_location_dailylocation'),
    ]

    operations = [
        migrations.RunPython(seed_locations, reverse_code=reverse_seed_locations),
    ]
