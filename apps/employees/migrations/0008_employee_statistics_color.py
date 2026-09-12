from django.db import migrations, models

CURATED_PALETTE = [
    '#2563EB',  # Royal Blue
    '#DC2626',  # Crimson Red
    '#16A34A',  # Forest Green
    '#9333EA',  # Deep Purple
    '#EA580C',  # Tangerine Orange
    '#0891B2',  # Deep Cyan
    '#DB2777',  # Rose Pink
    '#D97706',  # Warm Amber
    '#4F46E5',  # Vivid Indigo
    '#0D9488',  # Dark Teal
    '#65A30D',  # Olive Lime
    '#C026D3',  # Bright Fuchsia
    '#0284C7',  # Ocean Sky Blue
    '#E11D48',  # Vibrant Ruby
    '#7C3AED',  # Rich Violet
    '#059669',  # Mint Emerald
    '#B45309',  # Bronze Sienna
    '#475569',  # Steel Slate
    '#F59E0B',  # Sun Gold
    '#10B981',  # Spring Mint
    '#8B5CF6',  # Soft Lavender
    '#F43F5E',  # Vivid Coral
    '#3B82F6',  # Bright Azure
    '#84CC16',  # Bright Lime
    '#A855F7',  # Electric Purple
    '#06B6D4',  # Aqua Turquoise
    '#EC4899',  # Hot Magenta
    '#1E3A8A',  # Midnight Navy
]

def populate_employee_colors(apps, schema_editor):
    Employee = apps.get_model('employees', 'Employee')
    employees = list(Employee.objects.all().order_by('created_at'))
    palette_len = len(CURATED_PALETTE)
    for idx, emp in enumerate(employees):
        emp.statistics_color = CURATED_PALETTE[idx % palette_len]
        emp.save(update_fields=['statistics_color'])

def reverse_employee_colors(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0007_employee_password_changed_at_passwordchangelog'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='statistics_color',
            field=models.CharField(
                default='#2196F3',
                help_text='Hex color code for employee statistics identity',
                max_length=7
            ),
        ),
        migrations.RunPython(populate_employee_colors, reverse_code=reverse_employee_colors),
    ]
