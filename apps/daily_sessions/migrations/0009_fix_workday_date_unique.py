"""
Fix: Remove the legacy field-level UNIQUE constraint on WorkDay.date.
The composite (location, date) constraint from 0008 is correct;
this migration drops the leftover single-column unique that was
originally defined via DateField(unique=True).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('daily_sessions', '0008_rebuild_daily_operations'),
    ]

    operations = [
        migrations.AlterField(
            model_name='workday',
            name='date',
            field=models.DateField(),
        ),
    ]
