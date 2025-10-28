"""
Template Registry for WebOps
Centralizes template selection logic to reduce duplication and improve maintainability
"""

class TemplateRegistry:
    """
    A registry that maps deployment types to appropriate templates
    """
    
    def __init__(self):
        # Define template mappings for different deployment types
        self.template_mappings = {
            'app': {
                'nginx': 'app/nginx/app.conf.j2',
                'systemd': 'app/systemd/app.service.j2',
                'env': 'control-panel/env.j2'
            },
            'django': {
                'nginx': 'app/nginx/app.conf.j2',  # Uses the same as general app but with django-specific vars
                'systemd': 'app/systemd/app.service.j2',
                'env': 'control-panel/env.j2'
            },
            'vllm_gpu': {
                'nginx': 'llm/nginx/llm.conf.j2',
                'systemd': 'llm/systemd/vllm.service.j2',
            },
            'vllm_cpu': {
                'nginx': 'llm/nginx/llm.conf.j2',
                'systemd': 'llm/systemd/vllm_cpu.service.j2',
            },
            'docker': {
                'systemd': 'app/systemd/docker.service.j2',
            },
            'llm': {
                'nginx': 'llm/nginx/llm.conf.j2',
                'systemd': 'unified/systemd/unified.service.j2',  # Use unified for more flexibility
            }
        }
    
    def get_template_path(self, deployment_type, service_type):
        """
        Get the appropriate template path for a given deployment type and service type.
        Falls back to unified templates if specific templates don't exist.
        """
        # First try to get the specific template
        if deployment_type in self.template_mappings:
            if service_type in self.template_mappings[deployment_type]:
                return self.template_mappings[deployment_type][service_type]
        
        # Fallback mapping to unified templates
        fallback_mapping = {
            ('app', 'nginx'): 'unified/nginx/unified.conf.j2',
            ('app', 'systemd'): 'unified/systemd/unified.service.j2',
            ('django', 'nginx'): 'unified/nginx/unified.conf.j2',
            ('django', 'systemd'): 'unified/systemd/unified.service.j2',
            ('vllm_gpu', 'nginx'): 'unified/nginx/unified.conf.j2',
            ('vllm_gpu', 'systemd'): 'unified/systemd/unified.service.j2',
            ('vllm_cpu', 'nginx'): 'unified/nginx/unified.conf.j2',
            ('vllm_cpu', 'systemd'): 'unified/systemd/unified.service.j2',
            ('docker', 'systemd'): 'unified/systemd/unified.service.j2',
            ('llm', 'nginx'): 'unified/nginx/unified.conf.j2',
            ('llm', 'systemd'): 'unified/systemd/unified.service.j2',
        }
        
        fallback_key = (deployment_type, service_type)
        if fallback_key in fallback_mapping:
            return fallback_mapping[fallback_key]
        
        # If no specific or fallback template found, return None
        return None
    
    def get_available_types(self):
        """
        Get all available deployment types
        """
        return list(self.template_mappings.keys())
    
    def get_available_services(self, deployment_type):
        """
        Get all available service types for a given deployment type
        """
        if deployment_type in self.template_mappings:
            return list(self.template_mappings[deployment_type].keys())
        return []


# Singleton instance
template_registry = TemplateRegistry()