from django.db import migrations


def migrate_existing_data(apps, schema_editor):
    """
    Migrates all existing DailyTeam, SellerDailyOperation, and
    DailyEmployeePerformance records to use DailyLocation.

    Strategy:
    - All existing records are assigned to 'Ardis' (the first location),
      since we have no way to know which location they originally belonged to.
    - Admins can reassign records if needed after the migration.
    """
    Location = apps.get_model('daily_sessions', 'Location')
    WorkDay = apps.get_model('daily_sessions', 'WorkDay')
    DailyLocation = apps.get_model('daily_sessions', 'DailyLocation')
    DailyTeam = apps.get_model('daily_sessions', 'DailyTeam')
    SellerDailyOperation = apps.get_model('daily_sessions', 'SellerDailyOperation')
    DailyEmployeePerformance = apps.get_model('daily_sessions', 'DailyEmployeePerformance')

    # Get or create the Ardis location as default
    ardis, _ = Location.objects.get_or_create(
        name='Ardis',
        defaults={'icon': '🏬', 'color_hex': '#1565C0'}
    )

    for work_day in WorkDay.objects.all():
        # Get or create a DailyLocation for Ardis for this work day
        daily_loc, _ = DailyLocation.objects.get_or_create(
            work_day=work_day,
            location=ardis,
        )

        # Migrate DailyTeam records
        DailyTeam.objects.filter(work_day=work_day, daily_location__isnull=True).update(
            daily_location=daily_loc
        )

        # Migrate SellerDailyOperation records
        SellerDailyOperation.objects.filter(work_day=work_day, daily_location__isnull=True).update(
            daily_location=daily_loc
        )

        # Migrate DailyEmployeePerformance records
        DailyEmployeePerformance.objects.filter(work_day=work_day, daily_location__isnull=True).update(
            daily_location=daily_loc
        )


def reverse_migrate(apps, schema_editor):
    DailyTeam = apps.get_model('daily_sessions', 'DailyTeam')
    SellerDailyOperation = apps.get_model('daily_sessions', 'SellerDailyOperation')
    DailyEmployeePerformance = apps.get_model('daily_sessions', 'DailyEmployeePerformance')
    DailyLocation = apps.get_model('daily_sessions', 'DailyLocation')

    DailyTeam.objects.all().update(daily_location=None)
    SellerDailyOperation.objects.all().update(daily_location=None)
    DailyEmployeePerformance.objects.all().update(daily_location=None)
    DailyLocation.objects.all().delete()


class Migration(migrations.Migration):
    """
    Data migration: migrates all existing DailyTeam, SellerDailyOperation,
    and DailyEmployeePerformance records to reference a DailyLocation
    (defaulting to Ardis for all historical data).
    """
    dependencies = [
        ('daily_sessions', '0005_seed_locations'),
    ]

    operations = [
        migrations.RunPython(migrate_existing_data, reverse_code=reverse_migrate),
    ]
