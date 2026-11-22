from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('databases', '0002_database_deleted_at_database_deleted_by_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='database',
            name='created_by',
            field=models.ForeignKey(
                to=settings.AUTH_USER_MODEL, related_name='standalone_databases',
                on_delete=django.db.models.deletion.SET_NULL,
                null=True, blank=True,
            ),
        ),
    ]
