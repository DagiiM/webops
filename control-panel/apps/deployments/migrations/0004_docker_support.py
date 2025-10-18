# Generated migration for Docker support

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('deployments', '0003_deployment_dtype_deployment_gpu_memory_utilization_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='deployment',
            name='use_docker',
            field=models.BooleanField(default=False, help_text='Deploy using Docker containerization'),
        ),
        migrations.AddField(
            model_name='deployment',
            name='dockerfile_path',
            field=models.CharField(blank=True, default='Dockerfile', help_text='Path to Dockerfile relative to repository root', max_length=255),
        ),
        migrations.AddField(
            model_name='deployment',
            name='docker_compose_path',
            field=models.CharField(blank=True, default='docker-compose.yml', help_text='Path to docker-compose.yml relative to repository root', max_length=255),
        ),
        migrations.AddField(
            model_name='deployment',
            name='docker_image_name',
            field=models.CharField(blank=True, help_text='Custom Docker image name (auto-generated if empty)', max_length=255),
        ),
        migrations.AddField(
            model_name='deployment',
            name='docker_build_args',
            field=models.JSONField(blank=True, default=dict, help_text='Docker build arguments as key-value pairs'),
        ),
        migrations.AddField(
            model_name='deployment',
            name='docker_env_vars',
            field=models.JSONField(blank=True, default=dict, help_text='Docker container environment variables'),
        ),
        migrations.AddField(
            model_name='deployment',
            name='docker_volumes',
            field=models.JSONField(blank=True, default=list, help_text='Docker volume mounts as list of {"host": "path", "container": "path"}'),
        ),
        migrations.AddField(
            model_name='deployment',
            name='docker_ports',
            field=models.JSONField(blank=True, default=list, help_text='Additional Docker port mappings as list of {"host": port, "container": port}'),
        ),
        migrations.AddField(
            model_name='deployment',
            name='docker_network_mode',
            field=models.CharField(blank=True, choices=[('bridge', 'Bridge'), ('host', 'Host'), ('none', 'None')], default='bridge', help_text='Docker network mode', max_length=50),
        ),
        migrations.AddField(
            model_name='deployment',
            name='auto_generate_dockerfile',
            field=models.BooleanField(default=False, help_text='Automatically generate Dockerfile if not present in repository'),
        ),
    ]
