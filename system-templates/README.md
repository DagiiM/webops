# WebOps System Templates

This directory contains all system templates for WebOps deployments. The structure is organized to reduce duplication and improve maintainability.

## Directory Structure

```
system-templates/
├── app/                 # Templates for general applications
│   ├── nginx/
│   │   └── app.conf.j2
│   └── systemd/
│       ├── app.service.j2
│       └── docker.service.j2
├── llm/                 # Templates for LLM services
│   ├── nginx/
│   │   └── llm.conf.j2
│   └── systemd/
│       ├── vllm.service.j2
│       └── vllm_cpu.service.j2
├── control-panel/       # Templates for WebOps control panel
│   ├── nginx/
│   │   └── nginx-ssl-config.conf
│   └── env.j2
├── unified/             # Unified templates with parameterization
│   ├── nginx/
│   │   └── unified.conf.j2
│   └── systemd/
│       └── unified.service.j2
├── base/                # Base templates for inheritance (future use)
│   ├── nginx/
│   │   └── base.conf.j2
│   └── systemd/
│       └── base.service.j2
├── template_registry.py # Registry mapping deployment types to templates
└── README.md
```

## Template Types

### App Templates
- For general web applications (Django, Flask, etc.)
- Handles standard WSGI/ASGI deployments with Gunicorn

### LLM Templates
- For LLM services like vLLM
- Optimized for AI inference with appropriate resource settings

### Control Panel Templates
- For the WebOps control panel itself
- Includes SSL configuration for the main interface

### Unified Templates
- Single parameterized templates that can handle multiple deployment types
- Reduces code duplication by using conditional logic
- Preferred for new deployments

## Template Registry

The `template_registry.py` file defines which template to use for different deployment scenarios. This centralizes the template selection logic and makes it easier to maintain.

## Best Practices

1. Use unified templates when possible to reduce duplication
2. Add new functionality to unified templates rather than creating new specialized ones
3. Update the template registry when adding new template types
4. Keep templates parameterized rather than creating multiple similar templates