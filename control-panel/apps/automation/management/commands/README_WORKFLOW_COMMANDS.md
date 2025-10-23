# Workflow Management Commands

This directory contains Django management commands for creating sample workflows in the WebOps automation system.

## Available Commands

### 1. create_sample_workflow

Creates a simple workflow with three nodes:
- **Input**: Webhook node to receive data
- **Processor**: Transform node using JMESPath query
- **Output**: Email node to send transformed data

#### Usage

```bash
# Basic usage with defaults
python manage.py create_sample_workflow

# With custom parameters
python manage.py create_sample_workflow \
    --user-id 2 \
    --email user@example.com \
    --webhook-url /webhook/my-data
```

#### Parameters

- `--user-id`: ID of the user to own the workflow (default: 1)
- `--email`: Email address for the output node (default: admin@example.com)
- `--webhook-url`: Webhook URL endpoint (default: /webhook/sample-data)

#### Workflow Structure

```
Webhook Input → Transform Data → Send Email
```

#### Sample Payload

```json
{
  "user": {
    "name": "John Doe",
    "email": "john@example.com"
  },
  "created_at": "2023-10-20T10:30:00Z"
}
```

#### Transformed Output

```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "timestamp": "2023-10-20T10:30:00Z",
  "processed": true
}
```

---

### 2. create_advanced_workflow

Creates an advanced workflow with conditional logic and error handling:
- **Input**: Webhook node for order data
- **Validation**: Filter node to validate order data
- **Condition**: Conditional node to check order amount
- **Processors**: Two transform nodes for different order types
- **Outputs**: Email for high-value orders, webhook for regular orders
- **Error Handling**: Error handler and notification nodes

#### Usage

```bash
# Basic usage with defaults
python manage.py create_advanced_workflow

# With custom parameters
python manage.py create_advanced_workflow \
    --user-id 2 \
    --email admin@company.com \
    --webhook-url /webhook/orders
```

#### Parameters

- `--user-id`: ID of the user to own the workflow (default: 1)
- `--email`: Email address for notifications (default: admin@example.com)
- `--webhook-url`: Webhook URL endpoint (default: /webhook/order-data)

#### Workflow Structure

```
                      ┌─ Transform High Value ── Email High Value
Order Webhook ── Validate Order ── Check Amount ┤
                      └─ Transform Regular ── Webhook Regular
                            │
                            └─ Error Handler ── Error Email
```

#### Sample Payload

```json
{
  "order_id": "ORD-12345",
  "customer": {
    "name": "Jane Smith",
    "email": "jane@example.com"
  },
  "amount": 1500.00,
  "items": [
    {"sku": "PROD-001", "quantity": 2, "price": 750.00}
  ]
}
```

#### Workflow Logic

1. Receives order data via webhook
2. Validates required fields (order_id, customer, amount, items)
3. Checks if order amount >= $1000
4. **High-value orders (>= $1000)**:
   - Transforms with HIGH priority
   - Sends email notification to multiple recipients
5. **Regular orders (< $1000)**:
   - Transforms with NORMAL priority
   - Sends to external API via webhook
6. **Error handling**:
   - Catches validation errors
   - Notifies technical team via email

---

## Common Workflow Elements

### Node Types

1. **Input Nodes**:
   - `webhook`: Receives data via HTTP webhook
   - `database`: Queries database for data
   - `api`: Makes API requests to external systems
   - `file`: Reads data from files

2. **Processor Nodes**:
   - `transform`: Transforms data using JMESPath, Python code, or other methods
   - `filter`: Filters data based on conditions
   - `llm`: Processes data using Large Language Models
   - `aggregate`: Combines multiple data streams

3. **Output Nodes**:
   - `email`: Sends email notifications
   - `webhook_output`: Sends data to external webhooks
   - `database_output`: Writes data to database
   - `file_output`: Writes data to files
   - `slack`: Sends messages to Slack channels

4. **Control Nodes**:
   - `condition`: Implements conditional logic
   - `loop`: Implements looping logic
   - `delay`: Adds delays in execution
   - `error_handler`: Handles errors in workflow

### Connection Configuration

Connections between nodes can include:
- **Conditions**: Only execute if condition is met
- **Transformations**: Transform data between nodes
- **Error Handling**: Route errors to specific handlers

### Validation Rules

All workflows must pass validation:
- Unique node IDs within workflow
- All nodes must be connected (no isolated nodes)
- Valid node configurations based on type
- No cycles in workflow graph
- Proper trigger configuration

## Best Practices

1. **Node Naming**: Use descriptive, unique node IDs
2. **Error Handling**: Always include error handlers for critical paths
3. **Validation**: Validate input data early in the workflow
4. **Logging**: Add notification nodes for important events
5. **Testing**: Test workflows with sample data before activation
6. **Security**: Never expose sensitive data in logs or notifications
7. **Timeouts**: Set appropriate timeouts for external API calls

## Troubleshooting

### Common Validation Errors

1. **"Workflow has isolated nodes"**
   - Ensure all nodes have at least one connection
   - Check that all node IDs in connections exist

2. **"Node has no [field] configured"**
   - Check node configuration requirements
   - Ensure required fields are present in config

3. **"Invalid cron expression"**
   - Verify cron expression syntax
   - Use online cron expression validators

4. **"Invalid email address"**
   - Check email format in configuration
   - Ensure all recipient emails are valid

### Testing Workflows

1. Create workflow in DRAFT status
2. Validate using the built-in validator
3. Test with sample data
4. Check execution logs
5. Activate only after successful testing

## Example Test Commands

```bash
# Test webhook endpoint
curl -X POST http://localhost:8000/webhook/sample-data \
  -H "Content-Type: application/json" \
  -d '{
    "user": {
      "name": "Test User",
      "email": "test@example.com"
    },
    "created_at": "2023-10-20T10:30:00Z"
  }'

# Test advanced order workflow
curl -X POST http://localhost:8000/webhook/order-data \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": "TEST-001",
    "customer": {
      "name": "Test Customer",
      "email": "customer@example.com"
    },
    "amount": 1200.00,
    "items": [
      {"sku": "ITEM-001", "quantity": 1, "price": 1200.00}
    ]
  }'
```

## Additional Resources

- [JMESPath Tutorial](https://jmespath.org/tutorial.html)
- [Django Management Commands](https://docs.djangoproject.com/en/stable/howto/custom-management-commands/)
- [WebOps Automation Documentation](../../../docs/automation.md)