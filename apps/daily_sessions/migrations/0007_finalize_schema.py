import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Final schema migration:
    - Makes daily_location non-nullable on DailyTeam and SellerDailyOperation.
    - Updates unique_together constraints to use daily_location instead of work_day.
    - Removes the old work_day FK from DailyTeam and SellerDailyOperation
      (DailyEmployeePerformance keeps its work_day FK for dashboard performance).
    - daily_location on DailyEmployeePerformance remains nullable.
    """
    dependencies = [
        ('daily_sessions', '0006_migrate_existing_data'),
    ]

    operations = [
        # ── DailyTeam: remove old unique_together ────────────────────────
        migrations.AlterUniqueTogether(
            name='dailyteam',
            unique_together=set(),
        ),

        # ── DailyTeam: make daily_location non-nullable ──────────────────
        migrations.AlterField(
            model_name='dailyteam',
            name='daily_location',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='teams',
                to='daily_sessions.dailylocation',
            ),
        ),

        # ── DailyTeam: remove work_day FK ────────────────────────────────
        migrations.RemoveField(
            model_name='dailyteam',
            name='work_day',
        ),

        # ── DailyTeam: add new unique_together ───────────────────────────
        migrations.AlterUniqueTogether(
            name='dailyteam',
            unique_together={('daily_location', 'photographer'), ('daily_location', 'clown')},
        ),

        # ── SellerDailyOperation: remove old unique_together ─────────────
        migrations.AlterUniqueTogether(
            name='sellerdailyoperation',
            unique_together=set(),
        ),

        # ── SellerDailyOperation: make daily_location non-nullable ───────
        migrations.AlterField(
            model_name='sellerdailyoperation',
            name='daily_location',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='seller_operations',
                to='daily_sessions.dailylocation',
            ),
        ),

        # ── SellerDailyOperation: remove work_day FK ─────────────────────
        migrations.RemoveField(
            model_name='sellerdailyoperation',
            name='work_day',
        ),

        # ── SellerDailyOperation: add new unique_together ────────────────
        migrations.AlterUniqueTogether(
            name='sellerdailyoperation',
            unique_together={('daily_location', 'seller')},
        ),

        # ── Update ordering meta on DailyTeam ───────────────────────────
        migrations.AlterModelOptions(
            name='dailyteam',
            options={'ordering': ['-daily_location__work_day__date', 'team_name']},
        ),

        # ── Update ordering meta on SellerDailyOperation ─────────────────
        migrations.AlterModelOptions(
            name='sellerdailyoperation',
            options={'ordering': ['-daily_location__work_day__date', 'seller__first_name']},
        ),
    ]
