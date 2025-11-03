/**
 * LLM Auto-Detection Preview
 * Railway-style detection preview for LLM deployments
 */

(function() {
    'use strict';

    let detectionTimeout = null;
    let lastModelName = '';

    // Initialize detection preview
    function initDetectionPreview() {
        const modelNameInput = document.getElementById('model_name');
        if (!modelNameInput) return;

        // Listen for model name changes
        modelNameInput.addEventListener('input', function(e) {
            const modelName = e.target.value.trim();

            // Clear previous timeout
            if (detectionTimeout) {
                clearTimeout(detectionTimeout);
            }

            // Hide preview if empty
            if (!modelName) {
                hideDetectionPreview();
                return;
            }

            // Show loading state after 500ms of no typing
            detectionTimeout = setTimeout(() => {
                if (modelName !== lastModelName) {
                    lastModelName = modelName;
                    detectModel(modelName);
                }
            }, 800);
        });
    }

    // Detect model configuration
    async function detectModel(modelName) {
        showDetectionLoading();

        try {
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            const formData = new FormData();
            formData.append('model_name', modelName);

            const response = await fetch('/deployments/llm/detect/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                },
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                showDetectionPreview(data);

                // Auto-fill form fields with detected values
                autoFillFormFields(data.recommended_config);
            } else {
                showDetectionError(data.error || 'Failed to detect model');
            }
        } catch (error) {
            console.error('Detection error:', error);
            showDetectionError('Failed to fetch model information. Please check your internet connection.');
        }
    }

    // Show loading state
    function showDetectionLoading() {
        let container = document.getElementById('detection-preview-container');
        if (!container) {
            container = createDetectionContainer();
        }

        container.innerHTML = `
            <div class="webops-detection-preview webops-detection-loading">
                <div class="webops-flex webops-items-center webops-gap-3">
                    <div class="webops-spinner"></div>
                    <div>
                        <h4 class="webops-h4 webops-m-0">Analyzing Model...</h4>
                        <p class="webops-text-sm webops-text-muted webops-m-0">Fetching model information from Hugging Face Hub</p>
                    </div>
                </div>
            </div>
        `;
        container.style.display = 'block';
    }

    // Show detection preview
    function showDetectionPreview(data) {
        let container = document.getElementById('detection-preview-container');
        if (!container) {
            container = createDetectionContainer();
        }

        const modelInfo = data.model_info;
        const config = data.recommended_config;
        const confidence = data.confidence;

        const confidenceColor = confidence >= 90 ? 'success' : confidence >= 70 ? 'warning' : 'info';
        const confidenceIcon = confidence >= 90 ? 'verified' : confidence >= 70 ? 'info' : 'help';

        container.innerHTML = `
            <div class="webops-detection-preview webops-detection-success">
                <!-- Header -->
                <div class="webops-detection-header">
                    <div class="webops-flex webops-items-center webops-gap-3">
                        <span class="material-icons webops-text-${confidenceColor}" style="font-size: 32px;">${confidenceIcon}</span>
                        <div>
                            <h4 class="webops-h4 webops-m-0 webops-flex webops-items-center webops-gap-2">
                                Auto-Detected Configuration
                                <span class="webops-badge webops-badge-${confidenceColor}">${confidence}% Confidence</span>
                            </h4>
                            <p class="webops-text-sm webops-text-muted webops-m-0">Railway-style zero-configuration deployment</p>
                        </div>
                    </div>
                    <button type="button" class="webops-btn webops-btn-sm webops-btn-ghost" onclick="hideDetectionPreview()">
                        <span class="material-icons">close</span>
                    </button>
                </div>

                <!-- Model Info -->
                <div class="webops-detection-section">
                    <h5 class="webops-h5">📊 Model Information</h5>
                    <div class="webops-detection-grid">
                        <div class="webops-detection-item">
                            <span class="webops-text-muted">Type:</span>
                            <span class="webops-font-medium">${modelInfo.type || 'Unknown'}</span>
                        </div>
                        <div class="webops-detection-item">
                            <span class="webops-text-muted">Architecture:</span>
                            <span class="webops-font-medium">${modelInfo.architecture || 'Unknown'}</span>
                        </div>
                        <div class="webops-detection-item">
                            <span class="webops-text-muted">Parameters:</span>
                            <span class="webops-font-medium">${modelInfo.parameters_billions}</span>
                        </div>
                        <div class="webops-detection-item">
                            <span class="webops-text-muted">Model Size:</span>
                            <span class="webops-font-medium">${modelInfo.model_size_gb ? modelInfo.model_size_gb.toFixed(2) + 'GB' : 'Unknown'}</span>
                        </div>
                        <div class="webops-detection-item">
                            <span class="webops-text-muted">Context Length:</span>
                            <span class="webops-font-medium">${modelInfo.context_length ? modelInfo.context_length.toLocaleString() + ' tokens' : 'Unknown'}</span>
                        </div>
                        <div class="webops-detection-item">
                            <span class="webops-text-muted">License:</span>
                            <span class="webops-font-medium">${modelInfo.license || 'Unknown'}</span>
                        </div>
                    </div>

                    ${modelInfo.author ? `
                    <div class="webops-mt-3">
                        <div class="webops-flex webops-items-center webops-gap-4 webops-text-sm">
                            <span><strong>Author:</strong> ${modelInfo.author}</span>
                            ${modelInfo.downloads ? `<span><strong>Downloads:</strong> ${modelInfo.downloads.toLocaleString()}</span>` : ''}
                            ${modelInfo.likes ? `<span><strong>Likes:</strong> ${modelInfo.likes.toLocaleString()}</span>` : ''}
                        </div>
                    </div>
                    ` : ''}
                </div>

                <!-- Recommended Configuration -->
                <div class="webops-detection-section">
                    <h5 class="webops-h5">🎯 Recommended Configuration</h5>
                    <div class="webops-detection-grid">
                        <div class="webops-detection-item">
                            <span class="webops-text-muted">Backend:</span>
                            <span class="webops-font-medium webops-text-primary">${config.backend}</span>
                        </div>
                        <div class="webops-detection-item">
                            <span class="webops-text-muted">Data Type:</span>
                            <span class="webops-font-medium">${config.dtype}</span>
                        </div>
                        <div class="webops-detection-item">
                            <span class="webops-text-muted">Quantization:</span>
                            <span class="webops-font-medium">${config.quantization}</span>
                        </div>
                        <div class="webops-detection-item">
                            <span class="webops-text-muted">Est. Memory:</span>
                            <span class="webops-font-medium webops-text-warning">${config.estimated_memory_gb.toFixed(2)}GB</span>
                        </div>
                        ${config.max_model_len ? `
                        <div class="webops-detection-item">
                            <span class="webops-text-muted">Max Context:</span>
                            <span class="webops-font-medium">${config.max_model_len.toLocaleString()} tokens</span>
                        </div>
                        ` : ''}
                        <div class="webops-detection-item">
                            <span class="webops-text-muted">GPU Required:</span>
                            <span class="webops-font-medium">${config.requires_gpu ? 'Yes' : 'No'}</span>
                        </div>
                    </div>

                    <div class="webops-mt-3 webops-p-3" style="background: rgba(0, 170, 255, 0.1); border-radius: var(--webops-radius-md); border-left: 4px solid var(--webops-color-info);">
                        <div class="webops-flex webops-gap-2" style="align-items: flex-start;">
                            <span class="material-icons webops-text-info" style="font-size: 20px;">lightbulb</span>
                            <div class="webops-text-sm">
                                <strong>${config.backend_confidence}% confident:</strong> ${config.backend_reasoning}
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Warnings -->
                ${data.warnings && data.warnings.length > 0 ? `
                <div class="webops-detection-section">
                    <h5 class="webops-h5">⚠️ Warnings</h5>
                    <ul class="webops-m-0 webops-pl-4">
                        ${data.warnings.map(warning => `<li class="webops-text-warning webops-text-sm">${warning}</li>`).join('')}
                    </ul>
                </div>
                ` : ''}

                <!-- Info Messages -->
                ${data.info_messages && data.info_messages.length > 0 ? `
                <div class="webops-detection-section">
                    <h5 class="webops-h5">💬 Additional Information</h5>
                    <ul class="webops-m-0 webops-pl-4">
                        ${data.info_messages.map(info => `<li class="webops-text-info webops-text-sm">${info}</li>`).join('')}
                    </ul>
                </div>
                ` : ''}

                <!-- Action Note -->
                <div class="webops-detection-footer">
                    <p class="webops-text-sm webops-text-muted webops-m-0">
                        <span class="material-icons" style="font-size: 16px; vertical-align: text-bottom;">info</span>
                        These values have been automatically filled in the form. You can override them if needed.
                    </p>
                </div>
            </div>
        `;
        container.style.display = 'block';
    }

    // Show detection error
    function showDetectionError(error) {
        let container = document.getElementById('detection-preview-container');
        if (!container) {
            container = createDetectionContainer();
        }

        container.innerHTML = `
            <div class="webops-detection-preview webops-detection-error">
                <div class="webops-flex webops-items-center webops-gap-3">
                    <span class="material-icons webops-text-danger" style="font-size: 32px;">error</span>
                    <div>
                        <h4 class="webops-h4 webops-m-0">Detection Failed</h4>
                        <p class="webops-text-sm webops-text-muted webops-m-0">${error}</p>
                    </div>
                    <button type="button" class="webops-btn webops-btn-sm webops-btn-ghost" onclick="hideDetectionPreview()">
                        <span class="material-icons">close</span>
                    </button>
                </div>
            </div>
        `;
        container.style.display = 'block';
    }

    // Hide detection preview
    window.hideDetectionPreview = function() {
        const container = document.getElementById('detection-preview-container');
        if (container) {
            container.style.display = 'none';
        }
    };

    // Create detection container
    function createDetectionContainer() {
        const container = document.createElement('div');
        container.id = 'detection-preview-container';
        container.className = 'webops-detection-container';

        // Insert after model_name input
        const modelNameGroup = document.getElementById('model_name').closest('.webops-form-group');
        modelNameGroup.insertAdjacentElement('afterend', container);

        return container;
    }

    // Auto-fill form fields
    function autoFillFormFields(config) {
        // Fill dtype
        const dtypeSelect = document.getElementById('dtype');
        if (dtypeSelect && config.dtype) {
            dtypeSelect.value = config.dtype;
        }

        // Fill quantization
        const quantizationSelect = document.getElementById('quantization');
        if (quantizationSelect && config.quantization && config.quantization !== 'None') {
            quantizationSelect.value = config.quantization;
        }

        // Fill max context length
        const maxLenInput = document.getElementById('max_model_len');
        if (maxLenInput && config.max_model_len) {
            maxLenInput.value = config.max_model_len;
        }
    }

    // Initialize on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initDetectionPreview);
    } else {
        initDetectionPreview();
    }
})();
