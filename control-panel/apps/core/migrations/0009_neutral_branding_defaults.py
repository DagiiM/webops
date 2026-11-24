"""Neutral (grayscale) branding defaults.

The old defaults were a blue primary (#3b82f6) and an emerald accent
(#10b981). New installs now start neutral, and a row that still has the old
unmodified defaults is moved to the neutral ones. Customised rows are left
alone.
"""

from django.db import migrations, models

OLD = {
    'primary_hue': 217, 'primary_saturation': 91, 'primary_lightness': 60,
    'primary_color': '#3b82f6', 'secondary_color': '#1e40af', 'accent_color': '#10b981',
}
NEW = {
    'primary_hue': 0, 'primary_saturation': 0, 'primary_lightness': 12,
    'primary_color': '#1f2937', 'secondary_color': '#4b5563', 'accent_color': '#374151',
}


def _swap(apps, source, target):
    BrandingSettings = apps.get_model('core', 'BrandingSettings')
    BrandingSettings.objects.filter(**source).update(**target)


def to_neutral(apps, schema_editor):
    _swap(apps, OLD, NEW)


def to_previous(apps, schema_editor):
    _swap(apps, NEW, OLD)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_alter_securityauditlog_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='brandingsettings',
            name='primary_hue',
            field=models.IntegerField(default=0, help_text='Primary color hue (0-360 degrees)'),
        ),
        migrations.AlterField(
            model_name='brandingsettings',
            name='primary_saturation',
            field=models.IntegerField(default=0, help_text='Primary color saturation (0-100%)'),
        ),
        migrations.AlterField(
            model_name='brandingsettings',
            name='primary_lightness',
            field=models.IntegerField(default=12, help_text='Primary color lightness (0-100%)'),
        ),
        migrations.AlterField(
            model_name='brandingsettings',
            name='primary_color',
            field=models.CharField(default='#1f2937', help_text='Primary brand color (hex format: #RRGGBB) - auto-generated from HSL', max_length=7),
        ),
        migrations.AlterField(
            model_name='brandingsettings',
            name='secondary_color',
            field=models.CharField(default='#4b5563', help_text='Secondary brand color (hex format: #RRGGBB) - auto-generated', max_length=7),
        ),
        migrations.AlterField(
            model_name='brandingsettings',
            name='accent_color',
            field=models.CharField(default='#374151', help_text='Accent color for success states (hex format: #RRGGBB)', max_length=7),
        ),
        migrations.RunPython(to_neutral, to_previous),
    ]
