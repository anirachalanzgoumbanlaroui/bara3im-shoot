"""
Rebuild Daily Operations schema:

Goal: Each WorkDay belongs to exactly one Location.
      Ardis and Sablette have completely independent daily histories.
      DailyLocation pivot table is eliminated.

Steps:
1. Add location FK to WorkDay (nullable initially)
2. Populate location from existing DailyLocation relationships
3. Make location non-nullable, update unique constraint
4. Migrate DailyTeam: daily_location FK -> work_day FK
5. Migrate SellerDailyOperation: daily_location FK -> work_day FK
6. Remove daily_location from DailyEmployeePerformance
7. Drop DailyLocation table
"""
from django.db import migrations, models
import django.db.models.deletion


def forwards_workday_location(apps, schema_editor):
    """Populate WorkDay.location from its DailyLocation children."""
    WorkDay = apps.get_model('daily_sessions', 'WorkDay')
    DailyLocation = apps.get_model('daily_sessions', 'DailyLocation')

    for dl in DailyLocation.objects.select_related('work_day', 'location').all():
        wd = dl.work_day
        if wd.location_id is None:
            wd.location_id = dl.location_id
            wd.save(update_fields=['location_id'])


def forwards_dailyteam_workday(apps, schema_editor):
    """Populate DailyTeam.work_day from daily_location.work_day."""
    DailyTeam = apps.get_model('daily_sessions', 'DailyTeam')

    for team in DailyTeam.objects.select_related('daily_location').all():
        if team.work_day_id is None and team.daily_location_id is not None:
            team.work_day_id = team.daily_location.work_day_id
            team.save(update_fields=['work_day_id'])


def forwards_seller_workday(apps, schema_editor):
    """Populate SellerDailyOperation.work_day from daily_location.work_day."""
    SellerOp = apps.get_model('daily_sessions', 'SellerDailyOperation')

    for op in SellerOp.objects.select_related('daily_location').all():
        if op.work_day_id is None and op.daily_location_id is not None:
            op.work_day_id = op.daily_location.work_day_id
            op.save(update_fields=['work_day_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('daily_sessions', '0007_finalize_schema'),
    ]

    operations = [
        # ════════════════════════════════════════════════════════════════
        # PHASE 1: Add location + status to WorkDay
        # ════════════════════════════════════════════════════════════════

        # 1a. Add location FK (nullable initially)
        migrations.AddField(
            model_name='workday',
            name='location',
            field=models.ForeignKey(
                to='daily_sessions.location',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='work_days',
                null=True,
            ),
        ),

        # 1b. Add status field
        migrations.AddField(
            model_name='workday',
            name='status',
            field=models.CharField(
                max_length=10,
                choices=[('open', 'Open'), ('closed', 'Closed')],
                default='open',
            ),
        ),

        # 1c. Add closed_at field
        migrations.AddField(
            model_name='workday',
            name='closed_at',
            field=models.DateTimeField(null=True, blank=True),
        ),

        # ════════════════════════════════════════════════════════════════
        # PHASE 2: Populate WorkDay.location from DailyLocation
        # ════════════════════════════════════════════════════════════════

        migrations.RunPython(
            forwards_workday_location,
            reverse_code=migrations.RunPython.noop,
        ),

        # ════════════════════════════════════════════════════════════════
        # PHASE 3: Make WorkDay.location non-nullable, update constraints
        # ════════════════════════════════════════════════════════════════

        # 3a. Make location non-nullable
        migrations.AlterField(
            model_name='workday',
            name='location',
            field=models.ForeignKey(
                to='daily_sessions.location',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='work_days',
            ),
        ),

        # 3b. Remove old unique constraint on date alone
        migrations.AlterUniqueTogether(
            name='workday',
            unique_together=set(),
        ),

        # 3c. Add new unique constraint: (location, date)
        migrations.AlterUniqueTogether(
            name='workday',
            unique_together={('location', 'date')},
        ),

        # ════════════════════════════════════════════════════════════════
        # PHASE 4: Migrate DailyTeam — daily_location FK -> work_day FK
        # ════════════════════════════════════════════════════════════════

        # 4a. Add work_day FK (nullable initially)
        migrations.AddField(
            model_name='dailyteam',
            name='work_day',
            field=models.ForeignKey(
                to='daily_sessions.workday',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='teams',
                null=True,
            ),
        ),

        # 4b. Populate work_day from daily_location.work_day
        migrations.RunPython(
            forwards_dailyteam_workday,
            reverse_code=migrations.RunPython.noop,
        ),

        # 4c. Make work_day non-nullable
        migrations.AlterField(
            model_name='dailyteam',
            name='work_day',
            field=models.ForeignKey(
                to='daily_sessions.workday',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='teams',
            ),
        ),

        # 4d. Clear old unique_together (daily_location-based)
        migrations.AlterUniqueTogether(
            name='dailyteam',
            unique_together=set(),
        ),

        # 4e. Remove daily_location FK from DailyTeam
        migrations.RemoveField(
            model_name='dailyteam',
            name='daily_location',
        ),

        # 4f. Add new unique_together: (work_day, photographer), (work_day, clown)
        migrations.AlterUniqueTogether(
            name='dailyteam',
            unique_together={('work_day', 'photographer'), ('work_day', 'clown')},
        ),

        # 4g. Update DailyTeam ordering
        migrations.AlterModelOptions(
            name='dailyteam',
            options={'ordering': ['-work_day__date', 'team_name']},
        ),

        # ════════════════════════════════════════════════════════════════
        # PHASE 5: Migrate SellerDailyOperation — daily_location -> work_day
        # ════════════════════════════════════════════════════════════════

        # 5a. Add work_day FK (nullable initially)
        migrations.AddField(
            model_name='sellerdailyoperation',
            name='work_day',
            field=models.ForeignKey(
                to='daily_sessions.workday',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='seller_operations',
                null=True,
            ),
        ),

        # 5b. Populate work_day from daily_location.work_day
        migrations.RunPython(
            forwards_seller_workday,
            reverse_code=migrations.RunPython.noop,
        ),

        # 5c. Make work_day non-nullable
        migrations.AlterField(
            model_name='sellerdailyoperation',
            name='work_day',
            field=models.ForeignKey(
                to='daily_sessions.workday',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='seller_operations',
            ),
        ),

        # 5d. Clear old unique_together (daily_location-based)
        migrations.AlterUniqueTogether(
            name='sellerdailyoperation',
            unique_together=set(),
        ),

        # 5e. Remove daily_location FK from SellerDailyOperation
        migrations.RemoveField(
            model_name='sellerdailyoperation',
            name='daily_location',
        ),

        # 5f. Add new unique_together: (work_day, seller)
        migrations.AlterUniqueTogether(
            name='sellerdailyoperation',
            unique_together={('work_day', 'seller')},
        ),

        # 5g. Update SellerDailyOperation ordering
        migrations.AlterModelOptions(
            name='sellerdailyoperation',
            options={'ordering': ['-work_day__date', 'seller__first_name']},
        ),

        # ════════════════════════════════════════════════════════════════
        # PHASE 6: Clean up DailyEmployeePerformance
        # ════════════════════════════════════════════════════════════════

        # 6a. Remove daily_location FK from DailyEmployeePerformance
        migrations.RemoveField(
            model_name='dailyemployeeperformance',
            name='daily_location',
        ),

        # ════════════════════════════════════════════════════════════════
        # PHASE 7: Drop DailyLocation table
        # ════════════════════════════════════════════════════════════════

        migrations.DeleteModel(
            name='DailyLocation',
        ),
    ]
