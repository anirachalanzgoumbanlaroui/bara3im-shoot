import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Structural migration: adds Location, DailyLocation models and adds
    nullable daily_location FK to DailyTeam, SellerDailyOperation, and
    DailyEmployeePerformance. Also removes old work_day unique_together
    constraints from DailyTeam and SellerDailyOperation.
    """
    dependencies = [
        ('daily_sessions', '0003_sellerdailyoperation'),
    ]

    operations = [
        # ── 1. Create Location ─────────────────────────────────────────────
        migrations.CreateModel(
            name='Location',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('icon', models.CharField(blank=True, default='📍', max_length=10)),
                ('color_hex', models.CharField(blank=True, default='#1565C0', max_length=7, help_text='Primary accent color for this location (hex).')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),

        # ── 2. Create DailyLocation ────────────────────────────────────────
        migrations.CreateModel(
            name='DailyLocation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('notes', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('work_day', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='daily_locations', to='daily_sessions.workday')),
                ('location', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='daily_locations', to='daily_sessions.location')),
            ],
            options={
                'ordering': ['location__name'],
                'unique_together': {('work_day', 'location')},
            },
        ),

        # ── 3. Add nullable daily_location to DailyTeam ───────────────────
        migrations.AddField(
            model_name='dailyteam',
            name='daily_location',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='teams',
                to='daily_sessions.dailylocation',
            ),
        ),

        # ── 4. Add nullable daily_location to SellerDailyOperation ────────
        migrations.AddField(
            model_name='sellerdailyoperation',
            name='daily_location',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='seller_operations',
                to='daily_sessions.dailylocation',
            ),
        ),

        # ── 5. Add nullable daily_location to DailyEmployeePerformance ────
        migrations.AddField(
            model_name='dailyemployeeperformance',
            name='daily_location',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='performances',
                to='daily_sessions.dailylocation',
            ),
        ),
    ]
