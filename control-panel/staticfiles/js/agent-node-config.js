/**
 * Agent Node Configuration Forms
 *
 * Provides specialized configuration interfaces for agent integration nodes.
 */

const AgentNodeConfigurator = {
    /**
     * Get configuration form HTML for an agent node type
     */
    getConfigForm(nodeType, currentConfig = {}) {
        switch (nodeType) {
            case 'AGENT_TASK':
                return this.getAgentTaskForm(currentConfig);
            case 'AGENT_QUERY':
                return this.getAgentQueryForm(currentConfig);
            case 'AGENT_MEMORY':
                return this.getAgentMemoryForm(currentConfig);
            case 'AGENT_DECISION':
                return this.getAgentDecisionForm(currentConfig);
            case 'AGENT_LEARNING':
                return this.getAgentLearningForm(currentConfig);
            default:
                return '<p>No configuration available for this agent node type.</p>';
        }
    },

    /**
     * Agent Task Configuration Form
     */
    getAgentTaskForm(config) {
        return `
            <div class="webops-node-config-form">
                <h4>Agent Task Configuration</h4>

                <div class="webops-form-group">
                    <label for="agent-id">Agent ID</label>
                    <select id="agent-id" name="agent_id" class="webops-form-control" required>
                        <option value="">Select an agent...</option>
                        <option value="primary-agent" ${config.agent_id === 'primary-agent' ? 'selected' : ''}>Primary Agent</option>
                        <option value="research-agent" ${config.agent_id === 'research-agent' ? 'selected' : ''}>Research Agent</option>
                        <option value="planning-agent" ${config.agent_id === 'planning-agent' ? 'selected' : ''}>Planning Agent</option>
                    </select>
                    <small class="webops-form-text">Select the AI agent to execute this task</small>
                </div>

                <div class="webops-form-group">
                    <label for="task-description">Task Description</label>
                    <textarea
                        id="task-description"
                        name="task_description"
                        class="webops-form-control"
                        rows="4"
                        placeholder="Describe the task for the agent... Use {variable} for input data"
                        required
                    >${config.task_description || ''}</textarea>
                    <small class="webops-form-text">Describe what the agent should do. Use {field} syntax to reference input data.</small>
                </div>

                <div class="webops-form-group">
                    <label for="task-params">Task Parameters (JSON)</label>
                    <textarea
                        id="task-params"
                        name="task_params"
                        class="webops-form-control"
                        rows="3"
                        placeholder='{"param1": "value1", "param2": "value2"}'
                    >${JSON.stringify(config.task_params || {}, null, 2)}</textarea>
                    <small class="webops-form-text">Additional parameters in JSON format</small>
                </div>

                <div class="webops-form-group">
                    <label>
                        <input
                            type="checkbox"
                            id="wait-for-completion"
                            name="wait_for_completion"
                            ${config.wait_for_completion !== false ? 'checked' : ''}
                        >
                        Wait for task completion
                    </label>
                    <small class="webops-form-text">If unchecked, workflow continues immediately</small>
                </div>

                <div class="webops-form-group">
                    <label for="timeout-seconds">Timeout (seconds)</label>
                    <input
                        type="number"
                        id="timeout-seconds"
                        name="timeout_seconds"
                        class="webops-form-control"
                        value="${config.timeout_seconds || 300}"
                        min="10"
                        max="3600"
                    >
                </div>
            </div>
        `;
    },

    /**
     * Agent Query Configuration Form
     */
    getAgentQueryForm(config) {
        return `
            <div class="webops-node-config-form">
                <h4>Agent Query Configuration</h4>

                <div class="webops-form-group">
                    <label for="agent-id">Agent ID</label>
                    <select id="agent-id" name="agent_id" class="webops-form-control" required>
                        <option value="">Select an agent...</option>
                        <option value="primary-agent" ${config.agent_id === 'primary-agent' ? 'selected' : ''}>Primary Agent</option>
                        <option value="research-agent" ${config.agent_id === 'research-agent' ? 'selected' : ''}>Research Agent</option>
                        <option value="planning-agent" ${config.agent_id === 'planning-agent' ? 'selected' : ''}>Planning Agent</option>
                    </select>
                </div>

                <div class="webops-form-group">
                    <label for="query-text">Query Text</label>
                    <textarea
                        id="query-text"
                        name="query_text"
                        class="webops-form-control"
                        rows="3"
                        placeholder="What should I ask the agent? Use {variable} for input data"
                        required
                    >${config.query_text || ''}</textarea>
                    <small class="webops-form-text">The question or request to send to the agent</small>
                </div>

                <div class="webops-form-group">
                    <label for="query-context">Query Context (JSON)</label>
                    <textarea
                        id="query-context"
                        name="query_context"
                        class="webops-form-control"
                        rows="3"
                        placeholder='{"background": "...", "constraints": "..."}'
                    >${JSON.stringify(config.query_context || {}, null, 2)}</textarea>
                    <small class="webops-form-text">Additional context for the agent</small>
                </div>

                <div class="webops-form-group">
                    <label for="expected-format">Expected Response Format</label>
                    <select id="expected-format" name="expected_format" class="webops-form-control">
                        <option value="text" ${config.expected_format === 'text' ? 'selected' : ''}>Plain Text</option>
                        <option value="json" ${config.expected_format === 'json' ? 'selected' : ''}>JSON</option>
                        <option value="structured" ${config.expected_format === 'structured' ? 'selected' : ''}>Structured Data</option>
                    </select>
                </div>

                <div class="webops-form-group">
                    <label for="timeout-seconds">Timeout (seconds)</label>
                    <input
                        type="number"
                        id="timeout-seconds"
                        name="timeout_seconds"
                        class="webops-form-control"
                        value="${config.timeout_seconds || 60}"
                        min="10"
                        max="600"
                    >
                </div>
            </div>
        `;
    },

    /**
     * Agent Memory Configuration Form
     */
    getAgentMemoryForm(config) {
        return `
            <div class="webops-node-config-form">
                <h4>Agent Memory Configuration</h4>

                <div class="webops-form-group">
                    <label for="agent-id">Agent ID</label>
                    <select id="agent-id" name="agent_id" class="webops-form-control" required>
                        <option value="">Select an agent...</option>
                        <option value="primary-agent" ${config.agent_id === 'primary-agent' ? 'selected' : ''}>Primary Agent</option>
                        <option value="research-agent" ${config.agent_id === 'research-agent' ? 'selected' : ''}>Research Agent</option>
                        <option value="planning-agent" ${config.agent_id === 'planning-agent' ? 'selected' : ''}>Planning Agent</option>
                    </select>
                </div>

                <div class="webops-form-group">
                    <label for="operation">Operation</label>
                    <select id="operation" name="operation" class="webops-form-control" onchange="AgentNodeConfigurator.toggleMemoryOperation(this.value)">
                        <option value="store" ${config.operation === 'store' ? 'selected' : ''}>Store Memory</option>
                        <option value="retrieve" ${config.operation === 'retrieve' ? 'selected' : ''}>Retrieve Memory</option>
                        <option value="search" ${config.operation === 'search' ? 'selected' : ''}>Search Memory</option>
                    </select>
                </div>

                <div class="webops-form-group">
                    <label for="memory-type">Memory Type</label>
                    <select id="memory-type" name="memory_type" class="webops-form-control">
                        <option value="episodic" ${config.memory_type === 'episodic' ? 'selected' : ''}>Episodic (Events)</option>
                        <option value="semantic" ${config.memory_type === 'semantic' ? 'selected' : ''}>Semantic (Facts)</option>
                        <option value="procedural" ${config.memory_type === 'procedural' ? 'selected' : ''}>Procedural (Skills)</option>
                        <option value="working" ${config.memory_type === 'working' ? 'selected' : ''}>Working (Temporary)</option>
                    </select>
                    <small class="webops-form-text">Type of memory to interact with</small>
                </div>

                <div class="webops-form-group" id="content-group">
                    <label for="content">Content (JSON)</label>
                    <textarea
                        id="content"
                        name="content"
                        class="webops-form-control"
                        rows="4"
                        placeholder='{"key": "value", "data": "..."}'
                    >${JSON.stringify(config.content || {}, null, 2)}</textarea>
                    <small class="webops-form-text">Memory content or search criteria</small>
                </div>
            </div>
        `;
    },

    /**
     * Agent Decision Configuration Form
     */
    getAgentDecisionForm(config) {
        return `
            <div class="webops-node-config-form">
                <h4>Agent Decision Configuration</h4>

                <div class="webops-form-group">
                    <label for="agent-id">Agent ID</label>
                    <select id="agent-id" name="agent_id" class="webops-form-control" required>
                        <option value="">Select an agent...</option>
                        <option value="primary-agent" ${config.agent_id === 'primary-agent' ? 'selected' : ''}>Primary Agent</option>
                        <option value="research-agent" ${config.agent_id === 'research-agent' ? 'selected' : ''}>Research Agent</option>
                        <option value="planning-agent" ${config.agent_id === 'planning-agent' ? 'selected' : ''}>Planning Agent</option>
                    </select>
                </div>

                <div class="webops-form-group">
                    <label for="decision-context">Decision Context (JSON)</label>
                    <textarea
                        id="decision-context"
                        name="decision_context"
                        class="webops-form-control"
                        rows="3"
                        placeholder='{"situation": "...", "constraints": "..."}'
                    >${JSON.stringify(config.decision_context || {}, null, 2)}</textarea>
                    <small class="webops-form-text">Context for the decision</small>
                </div>

                <div class="webops-form-group">
                    <label for="options">Decision Options (JSON Array)</label>
                    <textarea
                        id="options"
                        name="options"
                        class="webops-form-control"
                        rows="4"
                        placeholder='["Option A", "Option B", "Option C"]'
                        required
                    >${JSON.stringify(config.options || [], null, 2)}</textarea>
                    <small class="webops-form-text">List of options for the agent to choose from</small>
                </div>

                <div class="webops-form-group">
                    <label for="criteria">Decision Criteria (JSON Array)</label>
                    <textarea
                        id="criteria"
                        name="criteria"
                        class="webops-form-control"
                        rows="3"
                        placeholder='["cost", "speed", "reliability"]'
                    >${JSON.stringify(config.criteria || [], null, 2)}</textarea>
                    <small class="webops-form-text">Criteria to evaluate options</small>
                </div>

                <div class="webops-form-group">
                    <label for="timeout-seconds">Timeout (seconds)</label>
                    <input
                        type="number"
                        id="timeout-seconds"
                        name="timeout_seconds"
                        class="webops-form-control"
                        value="${config.timeout_seconds || 120}"
                        min="10"
                        max="600"
                    >
                </div>
            </div>
        `;
    },

    /**
     * Agent Learning Configuration Form
     */
    getAgentLearningForm(config) {
        return `
            <div class="webops-node-config-form">
                <h4>Agent Learning Configuration</h4>

                <div class="webops-form-group">
                    <label for="agent-id">Agent ID</label>
                    <select id="agent-id" name="agent_id" class="webops-form-control" required>
                        <option value="">Select an agent...</option>
                        <option value="primary-agent" ${config.agent_id === 'primary-agent' ? 'selected' : ''}>Primary Agent</option>
                        <option value="research-agent" ${config.agent_id === 'research-agent' ? 'selected' : ''}>Research Agent</option>
                        <option value="planning-agent" ${config.agent_id === 'planning-agent' ? 'selected' : ''}>Planning Agent</option>
                    </select>
                </div>

                <div class="webops-form-group">
                    <label for="feedback-type">Feedback Type</label>
                    <select id="feedback-type" name="feedback_type" class="webops-form-control">
                        <option value="outcome" ${config.feedback_type === 'outcome' ? 'selected' : ''}>Outcome Feedback</option>
                        <option value="correction" ${config.feedback_type === 'correction' ? 'selected' : ''}>Correction</option>
                        <option value="reinforcement" ${config.feedback_type === 'reinforcement' ? 'selected' : ''}>Reinforcement</option>
                    </select>
                    <small class="webops-form-text">Type of learning feedback to provide</small>
                </div>

                <div class="webops-form-group">
                    <label for="feedback-data">Feedback Data (JSON)</label>
                    <textarea
                        id="feedback-data"
                        name="feedback_data"
                        class="webops-form-control"
                        rows="5"
                        placeholder='{"action": "...", "result": "...", "expected": "...", "score": 0.8}'
                    >${JSON.stringify(config.feedback_data || {}, null, 2)}</textarea>
                    <small class="webops-form-text">Learning feedback information</small>
                </div>
            </div>
        `;
    },

    /**
     * Toggle memory operation UI elements
     */
    toggleMemoryOperation(operation) {
        const contentGroup = document.getElementById('content-group');
        const contentLabel = contentGroup.querySelector('label');
        const contentTextarea = contentGroup.querySelector('textarea');
        const helpText = contentGroup.querySelector('small');

        if (operation === 'store') {
            contentLabel.textContent = 'Content to Store (JSON)';
            contentTextarea.placeholder = '{"key": "value", "data": "..."}';
            helpText.textContent = 'Data to store in agent memory';
        } else if (operation === 'retrieve') {
            contentLabel.textContent = 'Retrieval Criteria (JSON)';
            contentTextarea.placeholder = '{"memory_id": "...", "tags": ["..."]}';
            helpText.textContent = 'Criteria to find specific memories';
        } else if (operation === 'search') {
            contentLabel.textContent = 'Search Query (JSON)';
            contentTextarea.placeholder = '{"query": "search terms", "filters": {}, "limit": 10}';
            helpText.textContent = 'Search query and filters';
        }
    },

    /**
     * Extract configuration from form
     */
    extractConfig(formElement) {
        const config = {};
        const formData = new FormData(formElement);

        for (const [key, value] of formData.entries()) {
            // Parse JSON fields
            if (['task_params', 'query_context', 'content', 'decision_context', 'options', 'criteria', 'feedback_data'].includes(key)) {
                try {
                    config[key] = value ? JSON.parse(value) : (key === 'options' || key === 'criteria' ? [] : {});
                } catch (e) {
                    console.error(`Failed to parse JSON for ${key}:`, e);
                    config[key] = key === 'options' || key === 'criteria' ? [] : {};
                }
            }
            // Parse boolean fields
            else if (key === 'wait_for_completion') {
                config[key] = formData.get(key) === 'on';
            }
            // Parse number fields
            else if (key === 'timeout_seconds') {
                config[key] = parseInt(value, 10) || 60;
            }
            // String fields
            else {
                config[key] = value;
            }
        }

        return config;
    }
};

// Export for use in workflow canvas
if (typeof window !== 'undefined') {
    window.AgentNodeConfigurator = AgentNodeConfigurator;
}
