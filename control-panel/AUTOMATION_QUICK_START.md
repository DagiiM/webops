# 🚀 Automation System - Quick Start Guide

## 5-Minute Overview

WebOps Automation lets you build **no-code workflows** with a visual editor. Think **Zapier meets n8n** - but integrated into your deployment platform!

---

## 🎯 Create Your First Workflow

### Step 1: Create Workflow

```bash
# Via Web UI
1. Go to Automation → Create Workflow
2. Name: "Document Summarizer"
3. Trigger: Manual
4. Click "Create"
```

### Step 2: Add Nodes

Drag nodes from the palette onto the canvas:

```
📄 Google Docs Node
   ↓ (connect)
🤖 LLM Processor Node
   ↓ (connect)
📧 Email Output Node
```

### Step 3: Configure Nodes

**Google Docs Node**:
```json
{
  "document_id": "your-doc-id-here"
}
```

**LLM Processor Node**:
```json
{
  "prompt": "Summarize the following document in 3 bullet points:\n\n{content}",
  "max_tokens": 200
}
```

**Email Node**:
```json
{
  "to": "team@example.com",
  "subject": "Document Summary",
  "body": "{summary}"
}
```

### Step 4: Run Workflow

```bash
# Click "Run Workflow" button
# Or trigger via API:
POST /api/workflows/{id}/execute
```

**Result**: Document is fetched, summarized by AI, and emailed to your team!

---

## 📋 Common Workflow Patterns

### Pattern 1: API Monitoring

**Every 5 minutes, check if API is healthy:**

```
⏰ Schedule Trigger (*/5 * * * *)
   ↓
🌐 API Request (GET /health)
   ↓
🔀 Condition (response_time > 1000ms)
   ├─ Yes → 📱 Slack Alert "API is slow!"
   └─ No  → ✅ Log "API healthy"
```

**Configuration**:

```json
// Schedule Node
{"cron": "*/5 * * * *"}

// API Request Node
{
  "url": "https://api.example.com/health",
  "method": "GET"
}

// Condition Node
{
  "type": "comparison",
  "field": "response_time",
  "operator": "gt",
  "value": 1000
}

// Slack Node
{
  "channel": "#ops",
  "message": "⚠️ API response time: {response_time}ms"
}
```

---

### Pattern 2: Data ETL Pipeline

**Extract → Transform → Load:**

```
🗄️  Database Query
   ↓
🔧 Transform (map fields)
   ↓
🔍 Filter (remove nulls)
   ↓
📊 Aggregate (sum, avg)
   ↓
🌐 Webhook Output (analytics)
```

**Configuration**:

```json
// Database Query
{
  "query": "SELECT * FROM deployments WHERE created_at > NOW() - INTERVAL '1 day'"
}

// Transform
{
  "type": "jmespath",
  "query": "items[*].{name: name, status: status, duration: duration_ms}"
}

// Filter
{
  "condition": "duration != null"
}

// Aggregate
{
  "operations": {
    "total": "count",
    "avg_duration": "avg(duration)",
    "success_rate": "count(status == 'success') / count"
  }
}

// Webhook
{
  "url": "https://analytics.example.com/api/metrics",
  "method": "POST"
}
```

---

### Pattern 3: Smart Content Generation

**Webhook → AI Agent → LLM → File:**

```
🔔 Webhook Trigger
   ↓
🤖 Agent Query (get context)
   ↓
🧠 LLM Processor (generate)
   ↓
📁 File Output (save .md)
```

**Webhook Payload**:

```json
{
  "topic": "Kubernetes deployment guide",
  "target_audience": "developers",
  "length": "medium"
}
```

**Agent Query**:

```json
{
  "query": "What are best practices for {topic}?",
  "context": {"audience": "{target_audience}"},
  "expected_format": "bullet_points"
}
```

**LLM Processor**:

```json
{
  "prompt": "Write a {length} guide about {topic} for {target_audience}.\n\nBest practices:\n{agent_response}",
  "max_tokens": 2000
}
```

**File Output**:

```json
{
  "path": "/docs/{topic}.md",
  "format": "markdown"
}
```

---

### Pattern 4: Intelligent Auto-Scaling

**Monitor → Agent Decision → Action:**

```
⏰ Schedule (every hour)
   ↓
🗄️  Database Query (metrics)
   ↓
🤖 Agent Decision (scale action)
   ↓
🔀 Condition (decision = "scale_up")
   ├─ scale_up → 🌐 API Call (increase replicas)
   ├─ scale_down → 🌐 API Call (decrease replicas)
   └─ maintain → ✅ Log "No action needed"
```

**Agent Decision**:

```json
{
  "agent_id": "scaling-agent",
  "context": {
    "cpu_usage": "{avg_cpu}",
    "memory_usage": "{avg_memory}",
    "request_rate": "{requests_per_minute}",
    "current_replicas": "{replica_count}"
  },
  "options": ["scale_up", "scale_down", "maintain"],
  "criteria": [
    "cost_efficiency",
    "performance",
    "availability"
  ]
}
```

---

## 🔧 Node Configuration Examples

### Google Docs Node

```json
{
  "document_id": "1ABC-XYZ123",
  "extract_format": "plain_text"  // or "markdown"
}
```

**Output**:

```json
{
  "content": "Document text here...",
  "title": "Meeting Notes",
  "document_url": "https://docs.google.com/document/d/...",
  "last_modified": "2024-01-15T10:30:00Z"
}
```

---

### LLM Processor Node

```json
{
  "model": "gpt-4",  // or deployment name
  "prompt": "Analyze this: {input_text}",
  "temperature": 0.7,
  "max_tokens": 500,
  "system_prompt": "You are a helpful assistant."
}
```

**Output**:

```json
{
  "response": "Analysis result...",
  "model": "gpt-4",
  "tokens_used": 234,
  "finish_reason": "stop"
}
```

---

### Agent Task Node

```json
{
  "agent_id": "webops-agent",
  "task_description": "Deploy the latest version of my-app",
  "task_params": {
    "app_name": "my-app",
    "environment": "production",
    "strategy": "rolling"
  }
}
```

**Output**:

```json
{
  "status": "completed",
  "result": "Deployment successful. Version 1.2.3 is now live.",
  "task_id": "task-abc-123",
  "duration_ms": 45000
}
```

---

### Conditional Node

```json
{
  "condition": {
    "type": "expression",
    "expression": "data['status'] == 'success' and data['duration'] < 5000"
  },
  "true_path": "success_handler",
  "false_path": "error_handler"
}
```

**Expression Examples**:

```python
# Simple comparison
data['status'] == 'success'

# Multiple conditions
data['cpu'] > 80 and data['memory'] > 90

# In operator
'error' in data['message']

# Field access
data['user']['role'] == 'admin'

# Array operations
len(data['items']) > 10
```

---

### Loop Node

```json
{
  "items_field": "deployments",  // Loop over this array
  "item_variable": "deployment",  // Each item accessible as this
  "max_iterations": 100,
  "parallel": false  // Process sequentially
}
```

**Example**: Process each deployment in the array.

---

## 🔗 Data Transformations

### JMESPath Transform

**Input**:

```json
{
  "users": [
    {"name": "Alice", "age": 30, "active": true},
    {"name": "Bob", "age": 25, "active": false},
    {"name": "Charlie", "age": 35, "active": true}
  ]
}
```

**Transform**:

```json
{
  "type": "jmespath",
  "query": "users[?active == `true`].{name: name, age: age}"
}
```

**Output**:

```json
[
  {"name": "Alice", "age": 30},
  {"name": "Charlie", "age": 35}
]
```

---

### JSONPath Transform

**Input**:

```json
{
  "data": {
    "deployments": [
      {"name": "app-1", "status": "running"},
      {"name": "app-2", "status": "failed"}
    ]
  }
}
```

**Transform**:

```json
{
  "type": "jsonpath",
  "query": "$.data.deployments[*].name"
}
```

**Output**:

```json
["app-1", "app-2"]
```

---

### Template Transform

**Input**:

```json
{
  "user": "Alice",
  "action": "deployed",
  "app": "my-app",
  "version": "1.2.3"
}
```

**Transform**:

```json
{
  "type": "template",
  "template": "${user} ${action} ${app} version ${version} successfully!"
}
```

**Output**:

```
"Alice deployed my-app version 1.2.3 successfully!"
```

---

## ⚙️ Trigger Types

### 1. Manual Trigger

```bash
# Run via UI or API
POST /api/workflows/{id}/execute
{
  "input_data": {"key": "value"}
}
```

### 2. Schedule Trigger

```json
{
  "schedule_cron": "*/30 * * * *"  // Every 30 minutes
}
```

**Cron Examples**:

```bash
*/5 * * * *    # Every 5 minutes
0 * * * *      # Every hour
0 0 * * *      # Daily at midnight
0 9 * * 1      # Every Monday at 9 AM
0 0 1 * *      # First day of month
```

### 3. Webhook Trigger

```bash
# Unique webhook URL generated for workflow
POST /api/webhooks/{workflow_uuid}
{
  "payload": {"event": "deployment_complete"}
}
```

### 4. Event Trigger (Future)

```json
{
  "event_type": "deployment.completed",
  "filters": {
    "app_name": "my-app",
    "environment": "production"
  }
}
```

---

## 🛡️ Security Best Practices

### 1. Credential Management

**✅ DO**:

```python
# Store credentials encrypted
credential = DataSourceCredential.objects.create(
    user=request.user,
    provider='google',
    name='My Google Account',
    credentials={
        'access_token': 'token',  # Auto-encrypted
        'refresh_token': 'refresh'  # Auto-encrypted
    }
)

# Use in workflow
node.config = {
    'credential_id': credential.id  # Reference, not raw token!
}
```

**❌ DON'T**:

```python
# DON'T store raw tokens in node config
node.config = {
    'api_key': 'sk-abc123...'  # Bad! Visible in config
}
```

---

### 2. URL Validation

**✅ DO**:

```json
{
  "url": "https://api.example.com/data"  // External service OK
}
```

**❌ DON'T**:

```json
{
  "url": "http://localhost:8080/admin"  // Blocked! SSRF protection
}

{
  "url": "http://169.254.169.254/metadata"  // Blocked! AWS metadata
}

{
  "url": "http://192.168.1.1/admin"  // Blocked! Private network
}
```

---

### 3. Expression Safety

**✅ DO**:

```python
# Safe expressions (allowed)
data['status'] == 'success'
data['count'] > 100
'error' in data['message']
data.user.role == 'admin'
```

**❌ DON'T** (These won't work):

```python
# Dangerous operations (blocked)
__import__('os').system('rm -rf /')  # No imports!
open('/etc/passwd').read()  # No file access!
eval(user_input)  # No eval!
exec(malicious_code)  # No exec!
```

---

## 📊 Monitoring & Debugging

### Execution Logs

```python
# View execution logs
execution = WorkflowExecution.objects.get(id=123)

print(f"Status: {execution.status}")
print(f"Duration: {execution.duration_ms}ms")

# Per-node logs
for log in execution.node_logs:
    print(f"Node: {log['node_label']}")
    print(f"Status: {log['status']}")
    print(f"Duration: {log['duration_ms']}ms")
    if log.get('error'):
        print(f"Error: {log['error']}")
```

### Statistics

```python
workflow = Workflow.objects.get(id=456)

print(f"Total Executions: {workflow.total_executions}")
print(f"Success Rate: {workflow.successful_executions / workflow.total_executions * 100:.1f}%")
print(f"Average Duration: {workflow.average_duration_ms}ms")
print(f"Last Executed: {workflow.last_executed_at}")
```

---

## 🎓 Tips & Tricks

### Tip 1: Use Templates

Save time with pre-built templates:

```bash
# Start from template
1. Create Workflow → "From Template"
2. Choose: "API Monitoring", "Data ETL", "Content Generation"
3. Customize for your needs
```

---

### Tip 2: Test Nodes Individually

Test nodes before connecting them:

```bash
# Select node → "Test Node" → View output
# Verify configuration before building full workflow
```

---

### Tip 3: Handle Errors Gracefully

Add error handlers:

```
🌐 API Request
   ↓
🔀 Condition (status == 'success')
   ├─ Yes → ✅ Continue workflow
   └─ No  → 🛑 Error Handler → 📧 Alert Team
```

---

### Tip 4: Use Agent Memory

Store context across workflows:

```
Workflow 1:
🤖 Agent Memory (store) → Save user preference

Workflow 2 (later):
🤖 Agent Memory (retrieve) → Load user preference
```

---

### Tip 5: Optimize Performance

- ✅ Enable node caching for slow operations
- ✅ Use parallel execution where possible
- ✅ Set appropriate timeouts
- ✅ Limit loop iterations
- ✅ Filter data early in pipeline

---

## 🚀 Advanced Patterns

### Multi-Path Workflows

```
📥 Input
   ↓
🔀 Condition (priority)
   ├─ HIGH → 🚨 Immediate Alert
   ├─ MEDIUM → ⏰ Schedule for tomorrow
   └─ LOW → 📋 Add to backlog
```

---

### Fan-Out / Fan-In

```
📥 Input
   ↓
🔀 Split (by category)
   ├─ Category A → Process A → ↘
   ├─ Category B → Process B → → 🔗 Merge → 📤 Output
   └─ Category C → Process C → ↗
```

---

### Retry with Backoff

Node configuration:

```json
{
  "retry_on_failure": true,
  "max_retries": 3
}
```

**Behavior**:
- Attempt 1: Immediate
- Attempt 2: Wait 2s (2^1 seconds)
- Attempt 3: Wait 4s (2^2 seconds)
- Attempt 4: Wait 8s (2^3 seconds)

Plus random jitter to prevent thundering herd!

---

## 📚 Resources

- **Full Documentation**: `AUTOMATION_SYSTEM_ANALYSIS.md`
- **API Reference**: `/api/docs#automation`
- **Example Workflows**: `apps/automation/management/commands/create_sample_workflow.py`
- **Community Templates**: Automation → Templates

---

## 🎉 You're Ready!

Start building workflows with:
1. **Visual builder** - Drag & drop
2. **31 node types** - Data sources, processors, outputs
3. **AI agents** - Intelligent automation
4. **Security** - Built-in SSRF protection, encryption
5. **Monitoring** - Complete execution logs

**Build once, automate forever!**

---

*WebOps - Enterprise-Grade Auto-Deployment Platform*
