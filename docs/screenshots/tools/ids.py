"""Print the ids capture.js needs, and mark the demo workers as just seen (so they show Online)."""
import json
from django.utils import timezone
from apps.deployments.models import ApplicationDeployment as A, BuildJob as J, LLMDeployment as L, WorkerNode as W

W.objects.filter(name="build-1").update(last_seen=timezone.now())
print(json.dumps({"care": A.objects.get(name="care-platform").pk, "llm": L.objects.first().pk, "job": J.objects.filter(status="succeeded").first().pk}))
