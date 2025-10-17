"""
Add restart policy models.

Generated migration for restart policy support.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('services', '0001_initial'),
        ('deployments', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RestartPolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('policy_type', models.CharField(
                    choices=[
                        ('always', 'Always Restart'),
                        ('on_failure', 'Restart on Failure'),
                        ('never', 'Never Auto-Restart'),
                        ('backoff', 'Exponential Backoff')
                    ],
                    default='on_failure',
                    max_length=20
                )),
                ('enabled', models.BooleanField(default=True)),
                ('max_restarts', models.IntegerField(default=3, help_text='Maximum restart attempts within time window')),
                ('time_window_minutes', models.IntegerField(default=15, help_text='Time window for counting restart attempts')),
                ('initial_delay_seconds', models.IntegerField(default=10, help_text='Initial delay before first restart')),
                ('max_delay_seconds', models.IntegerField(default=300, help_text='Maximum delay between restarts (5 minutes)')),
                ('backoff_multiplier', models.FloatField(default=2.0, help_text='Multiplier for exponential backoff')),
                ('cooldown_minutes', models.IntegerField(default=5, help_text='Cooldown period after max restarts exceeded')),
                ('require_health_check', models.BooleanField(default=True, help_text='Only restart if health check confirms failure')),
                ('health_check_retries', models.IntegerField(default=3, help_text='Number of health check failures before restart')),
                ('notify_on_restart', models.BooleanField(default=True)),
                ('notify_on_max_restarts', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('deployment', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='restart_policy',
                    to='deployments.deployment'
                )),
            ],
            options={
                'verbose_name': 'Restart Policy',
                'verbose_name_plural': 'Restart Policies',
                'db_table': 'restart_policies',
            },
        ),
        migrations.CreateModel(
            name='RestartAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('attempt_number', models.IntegerField()),
                ('delay_seconds', models.IntegerField()),
                ('reason', models.CharField(max_length=255)),
                ('success', models.BooleanField()),
                ('error_message', models.TextField(blank=True)),
                ('started_at', models.DateTimeField()),
                ('completed_at', models.DateTimeField()),
                ('deployment', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='restart_attempts',
                    to='deployments.deployment'
                )),
                ('policy', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='services.restartpolicy'
                )),
            ],
            options={
                'verbose_name': 'Restart Attempt',
                'verbose_name_plural': 'Restart Attempts',
                'db_table': 'restart_attempts',
                'ordering': ['-started_at'],
            },
        ),
        migrations.AddIndex(
            model_name='restartattempt',
            index=models.Index(fields=['deployment', '-started_at'], name='restart_att_deploym_idx'),
        ),
    ]
