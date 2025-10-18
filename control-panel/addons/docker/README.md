# Docker Addon for WebOps

The Docker addon provides containerization support for WebOps deployments, allowing you to deploy applications in isolated Docker containers.

## Features

- **Automatic Dockerfile Generation**: WebOps can automatically generate optimized Dockerfiles for Django and static site projects
- **Container Management**: Full lifecycle management of Docker containers (build, start, stop, restart)
- **Health Monitoring**: Docker-specific health checks integrated with WebOps monitoring
- **Flexible Configuration**: Support for custom Docker images, environment variables, volumes, and network modes
- **Systemd Integration**: Docker containers are managed via systemd for reliability

## Prerequisites

- Docker Engine 20.10.0 or higher installed on the server
- User must have permissions to run Docker commands
- For production: systemd service support

## Installation

The Docker addon is automatically available in WebOps. To enable it:

1. Ensure Docker is installed on your server:
   ```bash
   docker --version
   ```

2. The addon will be auto-discovered from the `addons/docker` directory

3. Verify the addon is loaded by checking WebOps logs for:
   ```
   Docker addon hooks registered successfully
   ```

## Usage

### Creating a Docker Deployment

When creating a new deployment through the WebOps UI:

1. Fill in the standard deployment fields (name, repository URL, branch, domain)
2. Check the **"Use Docker containerization"** checkbox
3. Configure Docker options:
   - **Auto-generate Dockerfile**: Let WebOps create an optimized Dockerfile
   - **Dockerfile Path**: Specify custom Dockerfile location (default: `Dockerfile`)
   - **Network Mode**: Choose Docker network mode (bridge, host, or none)

### Dockerfile Auto-Generation

If your repository doesn't have a Dockerfile and auto-generation is enabled, WebOps will create one based on your project type:

#### Django Projects
```dockerfile
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput || true

# Run with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "config.wsgi:application"]
```

#### Static Sites
```dockerfile
FROM nginx:alpine
COPY . /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Custom Dockerfiles

You can provide your own Dockerfile in your repository. Make sure it:

1. Exposes the port specified in the deployment (use `$PORT` environment variable)
2. Handles the application startup correctly
3. Is located at the path specified in `dockerfile_path` (default: `Dockerfile`)

Example custom Dockerfile:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Your custom setup
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Use PORT environment variable
EXPOSE $PORT

CMD gunicorn --bind 0.0.0.0:$PORT myapp.wsgi:application
```

## Advanced Configuration

### Environment Variables

Docker deployments support both standard deployment environment variables and Docker-specific ones:

- Standard env vars (from deployment `env_vars` field) are passed to the container
- Docker-specific env vars (from `docker_env_vars` field) are also passed
- `PORT` is automatically set to the allocated port

### Volume Mounts

Configure persistent storage by adding volumes in the deployment model:

```python
deployment.docker_volumes = [
    {"host": "/var/webops/data", "container": "/app/data"},
    {"host": "/var/webops/media", "container": "/app/media"}
]
```

### Additional Port Mappings

Expose additional ports beyond the main application port:

```python
deployment.docker_ports = [
    {"host": 9000, "container": 9000},  # Admin port
    {"host": 9001, "container": 9001}   # Metrics port
]
```

### Network Modes

- **Bridge** (default): Standard Docker networking with port mapping
- **Host**: Container shares host network namespace (no port mapping needed)
- **None**: No networking

## Deployment Workflow

When deploying with Docker enabled:

1. **Pre-deployment Hook**:
   - Checks if Docker is available
   - Generates Dockerfile if needed and auto-generation is enabled
   - Validates Dockerfile exists

2. **Main Deployment**:
   - Repository is cloned
   - Dependencies are prepared (if needed)

3. **Post-deployment Hook**:
   - Builds Docker image (`webops/{deployment-name}:latest`)
   - Creates and starts Docker container (`webops-{deployment-name}`)
   - Updates deployment status

4. **Health Checks**:
   - Monitors container status
   - Checks if container is running
   - Integrates with WebOps health monitoring

## Container Management

Docker containers are managed through:

### Via WebOps UI
- Start/Stop/Restart buttons in deployment details
- Real-time container status
- Container logs accessible through deployment logs

### Via CLI
```bash
# View container status
docker ps | grep webops-{deployment-name}

# View container logs
docker logs webops-{deployment-name}

# Inspect container
docker inspect webops-{deployment-name}
```

### Via Systemd (Production)
```bash
# Start/stop/restart via systemd
sudo systemctl start webops-{deployment-name}
sudo systemctl stop webops-{deployment-name}
sudo systemctl restart webops-{deployment-name}

# Check status
sudo systemctl status webops-{deployment-name}
```

## Troubleshooting

### Container Won't Start

1. Check Docker logs:
   ```bash
   docker logs webops-{deployment-name}
   ```

2. Verify Dockerfile syntax:
   ```bash
   docker build -t test -f Dockerfile .
   ```

3. Check deployment logs in WebOps UI

### Build Failures

- Ensure all dependencies are in `requirements.txt`
- Verify Dockerfile instructions are valid
- Check for sufficient disk space: `docker system df`

### Permission Issues

- Ensure user has Docker permissions: `docker ps`
- Add user to docker group: `sudo usermod -aG docker $USER`

### Port Conflicts

- Check if port is already in use: `netstat -tuln | grep {port}`
- WebOps automatically allocates ports, but custom port mappings may conflict

## Integration with vLLM

Docker is particularly useful for vLLM deployments:

```python
# vLLM deployment with Docker
deployment = Deployment.objects.create(
    name="llama-model",
    project_type="llm",
    use_docker=True,
    model_name="meta-llama/Llama-2-7b-chat-hf",
    docker_env_vars={
        "HUGGING_FACE_HUB_TOKEN": "hf_xxx..."
    },
    docker_volumes=[
        {"host": "/var/cache/huggingface", "container": "/root/.cache/huggingface"}
    ]
)
```

## API Integration

The Docker addon integrates seamlessly with WebOps hooks:

- `pre_deployment`: Validates Docker availability and prepares Dockerfile
- `post_deployment`: Builds image and starts container
- `service_health_check`: Monitors container health

## Best Practices

1. **Use Multi-stage Builds**: Optimize image size with multi-stage Dockerfiles
2. **Pin Versions**: Specify exact versions in `requirements.txt` and base images
3. **Health Checks**: Define Docker HEALTHCHECK in custom Dockerfiles
4. **Resource Limits**: Set memory/CPU limits for containers in production
5. **Logging**: Configure proper logging drivers for production
6. **Security**: Run containers as non-root users when possible

## Security Considerations

- Containers run with `--restart unless-stopped` for reliability
- Network isolation via bridge mode by default
- Environment variables are passed securely
- Volumes should be properly secured with appropriate permissions

## Performance Tips

- Use `.dockerignore` to exclude unnecessary files from build context
- Leverage Docker layer caching by ordering Dockerfile commands properly
- Clean up old images regularly: `docker image prune`
- Monitor container resource usage: `docker stats`

## Future Enhancements

Planned features for the Docker addon:

- Docker Compose support for multi-container deployments
- Custom Docker registry integration
- Container resource limits configuration via UI
- Docker network creation and management
- Image versioning and rollback support

## Support

For issues or questions:
- Check WebOps deployment logs
- Review Docker addon logs in WebOps
- Consult Docker documentation: https://docs.docker.com/
- Report issues to WebOps repository

## Version

Current version: 1.0.0

## License

Part of the WebOps project.
