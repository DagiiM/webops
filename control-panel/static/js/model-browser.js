/**
 * WebOps Model Browser - Enhanced Hugging Face Integration
 * 
 * Features:
 * - Optimized API requests with intelligent caching
 * - Enhanced error handling and user feedback
 * - Improved performance for large model lists
 * - Better loading states and transitions
 * - Keyboard navigation and accessibility
 * - Model comparison functionality
 * - Responsive design for mobile devices
 * 
 * @version 2.0.0
 * @author WebOps Team
 */

'use strict';

class WebOpsModelBrowser {
    constructor() {
        // API Configuration
        this.webopsApiBase = 'https://huggingface.co/api';
        this.webopsCache = new Map();
        this.webopsRequestController = null; // For aborting requests
        
        // State Management
        this.webopsCurrentPage = 1;
        this.webopsSearchTimeout = null;
        this.webopsIsLoading = false;
        this.webopsHasMoreModels = true;
        this.webopsSelectedModels = new Set(); // For comparison
        this.webopsFocusedModelIndex = -1; // For keyboard navigation
        
        // Filter State
        this.webopsCurrentFilters = {
            search: '',
            category: 'all',
            sort: 'trending',
            tags: []
        };
        
        // UI Elements
        this.webopsElements = {};
        
        // Categories with enhanced descriptions
        this.webopsCategories = [
            { 
                value: 'all', 
                label: 'All Models', 
                icon: 'apps',
                description: 'Browse all available models'
            },
            { 
                value: 'testing', 
                label: 'Testing & Small', 
                icon: 'science',
                description: 'Lightweight models for testing and development'
            },
            { 
                value: 'popular', 
                label: 'Popular 7B', 
                icon: 'trending_up',
                description: 'Popular medium-sized models with good performance'
            },
            { 
                value: 'deepseek', 
                label: 'DeepSeek Models', 
                icon: 'psychology',
                description: 'Advanced reasoning and coding models'
            },
            { 
                value: 'quantized', 
                label: 'Quantized Models', 
                icon: 'memory',
                description: 'Memory-efficient quantized models'
            }
        ];
        
        // Enhanced sort options with descriptions
        this.webopsSortOptions = [
            { 
                value: 'trending', 
                label: 'Trending', 
                icon: 'trending_up',
                description: 'Models trending in the community'
            },
            { 
                value: 'downloads', 
                label: 'Most Downloads', 
                icon: 'download',
                description: 'Most downloaded models'
            },
            { 
                value: 'likes', 
                label: 'Most Likes', 
                icon: 'favorite',
                description: 'Most liked models by the community'
            },
            { 
                value: 'modified', 
                label: 'Recently Updated', 
                icon: 'schedule',
                description: 'Recently updated models'
            },
            { 
                value: 'created', 
                label: 'Recently Created', 
                icon: 'fiber_new',
                description: 'Newly added models'
            }
        ];

        // Performance optimization
        this.webopsDebounceTime = 300; // Reduced from 500ms for better UX
        this.webopsPageSize = 20;
        this.webopsMaxCacheSize = 100; // Limit cache size
        
        // Initialize component
        this.init();
    }
    
    init() {
        // Cache DOM elements
        this.cacheElements();
        
        if (!this.webopsElements.container) {
            console.warn('Model browser container not found');
            return;
        }
        
        // Initialize component
        this.bindEvents();
        this.setupKeyboardNavigation();
        this.loadModels();
        
        // Announce to screen readers
        this.announceToScreenReader('Model browser loaded. Use Tab to navigate, Enter to select models.');
    }
    
    cacheElements() {
        this.webopsElements = {
            container: document.getElementById('webops-model-browser'),
            searchInput: document.getElementById('webops-model-search'),
            categorySelect: document.getElementById('webops-model-category'),
            sortSelect: document.getElementById('webops-model-sort'),
            modelsGrid: document.getElementById('webops-models-grid'),
            loadingIndicator: document.getElementById('webops-loading-indicator'),
            errorContainer: document.getElementById('webops-error-container'),
            loadMoreBtn: document.getElementById('webops-load-more'),
            compareBtn: document.getElementById('webops-compare-btn'),
            comparePanel: document.getElementById('webops-compare-panel')
        };
    }
    
    bindEvents() {
        // Search with debouncing
        if (this.webopsElements.searchInput) {
            this.webopsElements.searchInput.addEventListener('input', (e) => {
                clearTimeout(this.webopsSearchTimeout);
                this.webopsSearchTimeout = setTimeout(() => {
                    this.handleSearchChange(e.target.value);
                }, this.webopsDebounceTime);
            });
            
            // Clear search on Escape key
            this.webopsElements.searchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    e.target.value = '';
                    this.handleSearchChange('');
                }
            });
        }
        
        // Category change
        if (this.webopsElements.categorySelect) {
            this.webopsElements.categorySelect.addEventListener('change', (e) => {
                this.handleFilterChange('category', e.target.value);
            });
        }
        
        // Sort change
        if (this.webopsElements.sortSelect) {
            this.webopsElements.sortSelect.addEventListener('change', (e) => {
                this.handleFilterChange('sort', e.target.value);
            });
        }
        
        // Load more
        if (this.webopsElements.loadMoreBtn) {
            this.webopsElements.loadMoreBtn.addEventListener('click', () => {
                this.loadMoreModels();
            });
        }
        
        // Compare button (if exists)
        if (this.webopsElements.compareBtn) {
            this.webopsElements.compareBtn.addEventListener('click', () => {
                this.toggleComparePanel();
            });
        }
        
        // Close compare panel (if exists)
        if (this.webopsElements.comparePanel) {
            const closeBtn = this.webopsElements.comparePanel.querySelector('.webops-compare-close');
            if (closeBtn) {
                closeBtn.addEventListener('click', () => {
                    this.toggleComparePanel();
                });
            }
        }
    }
    
    setupKeyboardNavigation() {
        // Add keyboard navigation to the models grid
        if (this.webopsElements.modelsGrid) {
            this.webopsElements.modelsGrid.addEventListener('keydown', (e) => {
                this.handleGridKeyNavigation(e);
            });
        }
        
        // Global keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + K to focus search
            if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                if (this.webopsElements.searchInput) {
                    this.webopsElements.searchInput.focus();
                }
            }
        });
    }
    
    handleGridKeyNavigation(e) {
        const modelCards = this.webopsElements.modelsGrid.querySelectorAll('.webops-model-card');
        if (modelCards.length === 0) return;
        
        let newIndex = this.webopsFocusedModelIndex;
        
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                newIndex = Math.min(newIndex + 1, modelCards.length - 1);
                break;
            case 'ArrowUp':
                e.preventDefault();
                newIndex = Math.max(newIndex - 1, 0);
                break;
            case 'Home':
                e.preventDefault();
                newIndex = 0;
                break;
            case 'End':
                e.preventDefault();
                newIndex = modelCards.length - 1;
                break;
            case 'Enter':
            case ' ':
                e.preventDefault();
                if (newIndex >= 0 && newIndex < modelCards.length) {
                    const selectBtn = modelCards[newIndex].querySelector('.webops-model-card__btn');
                    if (selectBtn) selectBtn.click();
                }
                return;
            case 'c':
                if (e.ctrlKey || e.metaKey) {
                    e.preventDefault();
                    if (newIndex >= 0 && newIndex < modelCards.length) {
                        this.toggleModelComparison(modelCards[newIndex].dataset.modelId);
                    }
                }
                return;
            default:
                return;
        }
        
        if (newIndex !== this.webopsFocusedModelIndex) {
            this.webopsFocusedModelIndex = newIndex;
            this.focusModelCard(modelCards[newIndex]);
        }
    }
    
    focusModelCard(card) {
        // Remove focus from all cards
        this.webopsElements.modelsGrid.querySelectorAll('.webops-model-card').forEach(c => {
            c.classList.remove('webops-model-card--focused');
            c.setAttribute('aria-selected', 'false');
        });
        
        // Add focus to the selected card
        card.classList.add('webops-model-card--focused');
        card.setAttribute('aria-selected', 'true');
        card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    
    handleSearchChange(searchTerm) {
        this.webopsCurrentFilters.search = searchTerm;
        this.resetAndLoadModels();
    }
    
    handleFilterChange(filterType, value) {
        this.webopsCurrentFilters[filterType] = value;
        this.resetAndLoadModels();
    }
    
    resetAndLoadModels() {
        // Abort any ongoing request
        if (this.webopsRequestController) {
            this.webopsRequestController.abort();
        }
        
        // Reset state
        this.webopsCurrentPage = 1;
        this.webopsHasMoreModels = true;
        this.webopsFocusedModelIndex = -1;
        
        // Clear cache for new filters
        this.clearCacheForFilters();
        
        // Load models
        this.loadModels();
    }
    
    clearCacheForFilters() {
        // Clear cache entries that don't match current filters
        const currentFilterKey = this.getCacheKey();
        for (const [key, value] of this.webopsCache.entries()) {
            if (!key.startsWith(currentFilterKey.split('-').slice(0, -1).join('-'))) {
                this.webopsCache.delete(key);
            }
        }
        
        // Limit cache size
        if (this.webopsCache.size > this.webopsMaxCacheSize) {
            const entriesToDelete = Array.from(this.webopsCache.keys()).slice(0, this.webopsCache.size - this.webopsMaxCacheSize);
            entriesToDelete.forEach(key => this.webopsCache.delete(key));
        }
    }
    
    getCacheKey() {
        return `${this.webopsCurrentFilters.search}-${this.webopsCurrentFilters.category}-${this.webopsCurrentFilters.sort}-${this.webopsCurrentPage}`;
    }
    
    async loadModels(append = false) {
        if (this.webopsIsLoading) return;
        
        this.webopsIsLoading = true;
        this.showLoading(!append);
        this.hideError();
        
        // Create abort controller for this request
        this.webopsRequestController = new AbortController();
        
        try {
            const cacheKey = this.getCacheKey();
            
            // Check cache first
            if (this.webopsCache.has(cacheKey) && !append) {
                console.log(`Using cached results for: ${cacheKey}`);
                const cachedModels = this.webopsCache.get(cacheKey);
                this.renderModels(cachedModels, append);
                this.updateLoadMoreButton(cachedModels);
                return;
            }
            
            // Fetch from API
            const models = await this.fetchModelsFromAPI();
            
            if (models.length > 0) {
                // Cache the results
                this.webopsCache.set(cacheKey, models);
                
                // Render models
                this.renderModels(models, append);
                this.updateLoadMoreButton(models);
                
                // Update hasMoreModels flag
                this.webopsHasMoreModels = models.length === this.webopsPageSize;
            } else {
                // No models found
                if (!append) {
                    this.showEmptyState();
                }
                this.webopsHasMoreModels = false;
            }
            
        } catch (error) {
            if (error.name !== 'AbortError') {
                console.error('Error loading models:', error);
                this.showError('Failed to load models. Please check your connection and try again.');
            }
        } finally {
            this.webopsIsLoading = false;
            this.hideLoading();
            this.webopsRequestController = null;
        }
    }
    
    async loadMoreModels() {
        if (!this.webopsHasMoreModels || this.webopsIsLoading) return;
        
        this.webopsCurrentPage++;
        await this.loadModels(true);
    }
    
    async fetchModelsFromAPI() {
        const cacheKey = this.getCacheKey();
        
        if (this.webopsCache.has(cacheKey)) {
            console.log(`Using cached results for: ${cacheKey}`);
            return this.webopsCache.get(cacheKey);
        }
        
        console.log(`Fetching from API with filters:`, this.webopsCurrentFilters);
        
        const params = new URLSearchParams({
            limit: this.webopsPageSize.toString(),
            sort: this.mapSortToAPI(this.webopsCurrentFilters.sort)
        });
        
        // Add search parameter if provided
        if (this.webopsCurrentFilters.search.trim()) {
            params.set('search', this.webopsCurrentFilters.search);
        }
        
        // Add category-specific search terms
        if (this.webopsCurrentFilters.category !== 'all' && !this.webopsCurrentFilters.search.trim()) {
            const categorySearchTerms = {
                'testing': 'gpt gpt2 phi tinyllama small test',
                'popular': 'llama mistral gemma falcon codellama',
                'deepseek': 'deepseek',
                'quantized': 'quantized awq gptq ggml'
            };
            
            if (categorySearchTerms[this.webopsCurrentFilters.category]) {
                params.set('search', categorySearchTerms[this.webopsCurrentFilters.category]);
            }
        }
        
        const url = `${this.webopsApiBase}/models?${params}`;
        console.log(`API URL: ${url}`);
        
        try {
            const response = await fetch(url, {
                signal: this.webopsRequestController?.signal
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log(`Received ${data.length} models from API`);
            
            // Transform and enhance models
            const models = data.map(model => this.transformAPIModel(model));
            
            // Filter by category if needed
            let filteredModels = models;
            if (this.webopsCurrentFilters.category !== 'all') {
                filteredModels = this.filterModelsByCategory(models, this.webopsCurrentFilters.category);
                console.log(`Filtered to ${filteredModels.length} models for category: ${this.webopsCurrentFilters.category}`);
            }
            
            // Add model information
            const enhancedModels = filteredModels.map(model => ({
                ...model,
                info: this.getModelInfo(model)
            }));
            
            return enhancedModels;
            
        } catch (error) {
            if (error.name !== 'AbortError') {
                console.error('Failed to fetch from Hugging Face API:', error);
                throw error;
            }
            return [];
        }
    }
    
    mapSortToAPI(sortValue) {
        const sortMapping = {
            'trending': 'downloads',  // Changed from 'trending' to 'downloads' as 'trending' is not a valid API parameter
            'downloads': 'downloads',
            'likes': 'likes',
            'modified': 'modified',
            'created': 'created'
        };
        return sortMapping[sortValue] || 'downloads';
    }
    
    transformAPIModel(apiModel) {
        return {
            id: apiModel.modelId,
            modelId: apiModel.modelId,
            author: apiModel.author || 'Unknown',
            name: apiModel.modelId.split('/')[1] || apiModel.modelId,
            description: apiModel.modelId?.includes('/') ? 
                `Model by ${apiModel.author || 'Unknown'}` : 
                'Model from Hugging Face Hub',
            downloads: apiModel.downloads || 0,
            likes: apiModel.likes || 0,
            tags: apiModel.tags || [],
            category: 'api',
            vram: 'Variable',
            params: 'Unknown',
            lastModified: apiModel.lastModified || null,
            createdAt: apiModel.createdAt || null,
            pipeline_tag: apiModel.pipeline_tag || null,
            library_name: apiModel.library_name || null
        };
    }
    
    filterModelsByCategory(models, category) {
        const categoryKeywords = {
            'testing': ['gpt2', 'phi', 'tinyllama', 'small', 'test', 'mini'],
            'popular': ['llama', 'mistral', 'gemma', 'falcon', 'codellama', '7b', '8b', '9b', '13b'],
            'deepseek': ['deepseek'],
            'quantized': ['quantized', 'awq', 'gptq', 'ggml', 'thebloke']
        };
        
        const keywords = categoryKeywords[category] || [];
        
        return models.filter(model => {
            const searchText = `${model.modelId} ${model.name} ${model.author}`.toLowerCase();
            return keywords.some(keyword => searchText.includes(keyword.toLowerCase()));
        });
    }
    
    getModelInfo(model) {
        const modelId = model.modelId.toLowerCase();
        
        // Enhanced model size detection
        let sizeCategory = 'medium';
        let typicalVRAM = '8GB';
        let description = 'Model size: medium';
        
        // Very large models
        if (modelId.includes('deepseek-v3') || modelId.includes('671b')) {
            sizeCategory = 'very-large';
            typicalVRAM = '80GB+';
            description = 'Very large model - requires significant resources';
        } else if (modelId.includes('deepseek-r1')) {
            sizeCategory = 'very-large';
            typicalVRAM = '80GB+';
            description = 'Advanced reasoning model - requires significant resources';
        } else if (modelId.includes('deepseek-coder-v2')) {
            sizeCategory = 'large';
            typicalVRAM = '40GB';
            description = 'Large coding model - requires substantial resources';
        }
        // Medium models
        else if (modelId.includes('llama-3-8b') || modelId.includes('8b')) {
            sizeCategory = 'medium';
            typicalVRAM = '16GB';
            description = 'Medium model - good balance of performance and resources';
        } else if (modelId.includes('llama-2-7b') || modelId.includes('7b')) {
            sizeCategory = 'medium';
            typicalVRAM = '14GB';
            description = 'Medium model - good balance of performance and resources';
        } else if (modelId.includes('mistral-7b')) {
            sizeCategory = 'medium';
            typicalVRAM = '14GB';
            description = 'Medium model - good balance of performance and resources';
        } else if (modelId.includes('gemma-2-9b')) {
            sizeCategory = 'medium';
            typicalVRAM = '18GB';
            description = 'Medium model - good balance of performance and resources';
        }
        // Small models
        else if (modelId.includes('phi-2')) {
            sizeCategory = 'small';
            typicalVRAM = '6GB';
            description = 'Small model - ideal for testing and development';
        } else if (modelId.includes('gpt2')) {
            sizeCategory = 'small';
            typicalVRAM = '2GB';
            description = 'Small model - ideal for testing and development';
        }
        // Quantized models
        else if (modelId.includes('awq') || modelId.includes('gptq')) {
            sizeCategory = 'medium-quantized';
            typicalVRAM = '7GB (quantized)';
            description = 'Quantized model - memory efficient with good performance';
        }
        
        return {
            sizeCategory,
            typicalVRAM,
            description,
            recommended: sizeCategory === 'small',
            caution: sizeCategory === 'medium' || sizeCategory === 'medium-quantized',
            warning: sizeCategory === 'large' || sizeCategory === 'very-large'
        };
    }
    
    renderModels(models, append = false) {
        if (!this.webopsElements.modelsGrid) return;
        
        if (!append) {
            this.webopsElements.modelsGrid.innerHTML = '';
        }
        
        if (models.length === 0 && !append) {
            this.showEmptyState();
            return;
        }
        
        // Create document fragment for better performance
        const fragment = document.createDocumentFragment();
        
        models.forEach((model, index) => {
            const modelCard = this.createModelCard(model, append ? this.webopsElements.modelsGrid.children.length : index);
            fragment.appendChild(modelCard);
        });
        
        this.webopsElements.modelsGrid.appendChild(fragment);
        
        // Update ARIA attributes
        this.webopsElements.modelsGrid.setAttribute('aria-label', `Models grid: ${models.length} models displayed`);
    }
    
    createModelCard(model, index) {
        const info = model.info || this.getModelInfo(model);
        const isSelected = this.webopsSelectedModels.has(model.modelId);
        
        // Determine card styling based on model size
        let cardClass = 'webops-model-card';
        let badgeHTML = '';
        
        if (info.recommended) {
            cardClass += ' webops-model-card--recommended';
            badgeHTML = `<span class="webops-model-card__badge webops-model-card__badge--success">
                <span class="material-icons webops-model-card__badge-icon">check_circle</span>
                Good Choice
            </span>`;
        } else if (info.caution) {
            cardClass += ' webops-model-card--caution';
            badgeHTML = `<span class="webops-model-card__badge webops-model-card__badge--warning">
                <span class="material-icons webops-model-card__badge-icon">info</span>
                Standard Size
            </span>`;
        } else if (info.warning) {
            cardClass += ' webops-model-card--incompatible';
            badgeHTML = `<span class="webops-model-card__badge webops-model-card__badge--error">
                <span class="material-icons webops-model-card__badge-icon">warning</span>
                Large Model
            </span>`;
        }
        
        if (isSelected) {
            cardClass += ' webops-model-card--selected';
        }
        
        const card = document.createElement('div');
        card.className = cardClass;
        card.dataset.modelId = model.modelId;
        card.setAttribute('role', 'button');
        card.setAttribute('tabindex', index === 0 ? '0' : '-1');
        card.setAttribute('aria-label', `Model: ${model.name} by ${model.author}. ${info.description}. VRAM required: ${info.typicalVRAM}.`);
        
        card.innerHTML = `
            <div class="webops-model-card__header">
                <div class="webops-model-card__title">
                    <h4 class="webops-model-card__name">${this.escapeHtml(model.name)}</h4>
                    <code class="webops-model-card__id">${this.escapeHtml(model.modelId)}</code>
                </div>
                <div class="webops-model-card__author">
                    <span class="material-icons webops-model-card__author-icon">account_circle</span>
                    <span class="webops-model-card__author-text">${this.escapeHtml(model.author)}</span>
                </div>
                ${badgeHTML}
                ${isSelected ? '<div class="webops-model-card__selected-indicator"><span class="material-icons">check_circle</span></div>' : ''}
            </div>
            <div class="webops-model-card__body">
                <p class="webops-model-card__description">${this.escapeHtml(model.description)}</p>
                
                <!-- Model Information -->
                <div class="webops-model-card__info">
                    <div class="webops-model-card__info-header">
                        <span class="material-icons webops-model-card__info-icon">info</span>
                        <span class="webops-model-card__info-text">${this.escapeHtml(info.description)}</span>
                    </div>
                </div>
                
                <div class="webops-model-card__meta">
                    <div class="webops-model-card__meta-item">
                        <span class="material-icons webops-model-card__meta-icon">memory</span>
                        <span class="webops-model-card__meta-text">${this.escapeHtml(info.typicalVRAM)} VRAM</span>
                    </div>
                    <div class="webops-model-card__meta-item">
                        <span class="material-icons webops-model-card__meta-icon">data_usage</span>
                        <span class="webops-model-card__meta-text">${this.escapeHtml(model.params)} params</span>
                    </div>
                    ${model.downloads ? `
                    <div class="webops-model-card__meta-item">
                        <span class="material-icons webops-model-card__meta-icon">download</span>
                        <span class="webops-model-card__meta-text">${this.formatNumber(model.downloads)}</span>
                    </div>
                    ` : ''}
                </div>
                
                ${model.tags && model.tags.length > 0 ? `
                <div class="webops-model-card__tags">
                    ${model.tags.slice(0, 3).map(tag => `<span class="webops-model-card__tag">${this.escapeHtml(tag)}</span>`).join('')}
                    ${model.tags.length > 3 ? `<span class="webops-model-card__tag">+${model.tags.length - 3}</span>` : ''}
                </div>
                ` : ''}
            </div>
            <div class="webops-model-card__footer">
                <button type="button" class="webops-btn webops-btn-sm webops-btn-primary webops-model-card__btn"
                        onclick="window.webopsFillModel('${this.escapeHtml(model.modelId)}', '${this.escapeHtml(model.modelId)}-deployment')"
                        aria-label="Select model ${model.name} for deployment">
                    <span class="material-icons">smart_toy</span>
                    Use This Model
                </button>
                <button type="button" class="webops-btn webops-btn-sm webops-btn-secondary webops-model-card__compare-btn"
                        onclick="window.webopsModelBrowser.toggleModelComparison('${this.escapeHtml(model.modelId)}')"
                        aria-label="Add model ${model.name} to comparison">
                    <span class="material-icons">compare</span>
                    ${isSelected ? 'Remove' : 'Compare'}
                </button>
            </div>
        `;
        
        // Add click handler for the card
        card.addEventListener('click', (e) => {
            if (!e.target.closest('.webops-model-card__btn') && !e.target.closest('.webops-model-card__compare-btn')) {
                // Focus the card when clicked
                this.focusModelCard(card);
                this.webopsFocusedModelIndex = index;
            }
        });
        
        return card;
    }
    
    toggleModelComparison(modelId) {
        if (this.webopsSelectedModels.has(modelId)) {
            this.webopsSelectedModels.delete(modelId);
        } else {
            // Limit to 3 models for comparison
            if (this.webopsSelectedModels.size >= 3) {
                this.showNotification('You can compare up to 3 models at a time', 'warning');
                return;
            }
            this.webopsSelectedModels.add(modelId);
        }
        
        // Update UI
        this.updateCompareButton();
        this.updateModelCards();
        
        // Update compare panel if open
        if (this.webopsElements.comparePanel && this.webopsElements.comparePanel.classList.contains('webops-compare-panel--open')) {
            this.updateComparePanel();
        }
    }
    
    updateCompareButton() {
        if (!this.webopsElements.compareBtn) return;
        
        const count = this.webopsSelectedModels.size;
        if (count > 0) {
            this.webopsElements.compareBtn.textContent = `Compare (${count})`;
            this.webopsElements.compareBtn.style.display = 'block';
        } else {
            this.webopsElements.compareBtn.style.display = 'none';
        }
    }
    
    updateModelCards() {
        const cards = this.webopsElements.modelsGrid.querySelectorAll('.webops-model-card');
        cards.forEach(card => {
            const modelId = card.dataset.modelId;
            const isSelected = this.webopsSelectedModels.has(modelId);
            const compareBtn = card.querySelector('.webops-model-card__compare-btn');
            
            if (isSelected) {
                card.classList.add('webops-model-card--selected');
                if (!card.querySelector('.webops-model-card__selected-indicator')) {
                    card.insertAdjacentHTML('beforeend', '<div class="webops-model-card__selected-indicator"><span class="material-icons">check_circle</span></div>');
                }
                if (compareBtn) {
                    compareBtn.innerHTML = '<span class="material-icons">compare</span>Remove';
                }
            } else {
                card.classList.remove('webops-model-card--selected');
                const indicator = card.querySelector('.webops-model-card__selected-indicator');
                if (indicator) indicator.remove();
                if (compareBtn) {
                    compareBtn.innerHTML = '<span class="material-icons">compare</span>Compare';
                }
            }
        });
    }
    
    toggleComparePanel() {
        if (!this.webopsElements.comparePanel) return;
        
        const isOpen = this.webopsElements.comparePanel.classList.contains('webops-compare-panel--open');
        
        if (isOpen) {
            this.webopsElements.comparePanel.classList.remove('webops-compare-panel--open');
        } else {
            this.updateComparePanel();
            this.webopsElements.comparePanel.classList.add('webops-compare-panel--open');
        }
    }
    
    updateComparePanel() {
        if (!this.webopsElements.comparePanel) return;
        
        const selectedModels = Array.from(this.webopsSelectedModels);
        
        if (selectedModels.length === 0) {
            this.webopsElements.comparePanel.innerHTML = `
                <div class="webops-compare-panel__empty">
                    <p>No models selected for comparison</p>
                </div>
            `;
            return;
        }
        
        // Get model data from cache or current view
        const modelsData = [];
        selectedModels.forEach(modelId => {
            // Find in current cache
            for (const [key, models] of this.webopsCache.entries()) {
                const model = models.find(m => m.modelId === modelId);
                if (model) {
                    modelsData.push(model);
                    break;
                }
            }
        });
        
        this.webopsElements.comparePanel.innerHTML = `
            <div class="webops-compare-panel__header">
                <h3>Model Comparison</h3>
                <button class="webops-compare-close" aria-label="Close comparison panel">
                    <span class="material-icons">close</span>
                </button>
            </div>
            <div class="webops-compare-panel__content">
                <div class="webops-compare-grid">
                    ${modelsData.map(model => this.createCompareCard(model)).join('')}
                </div>
            </div>
            <div class="webops-compare-panel__footer">
                <button class="webops-btn webops-btn-secondary" onclick="window.webopsModelBrowser.clearComparison()">
                    Clear All
                </button>
            </div>
        `;
        
        // Re-bind close button
        const closeBtn = this.webopsElements.comparePanel.querySelector('.webops-compare-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                this.toggleComparePanel();
            });
        }
    }
    
    createCompareCard(model) {
        const info = model.info || this.getModelInfo(model);
        
        return `
            <div class="webops-compare-card">
                <h4 class="webops-compare-card__title">${this.escapeHtml(model.name)}</h4>
                <code class="webops-compare-card__id">${this.escapeHtml(model.modelId)}</code>
                <div class="webops-compare-card__meta">
                    <div class="webops-compare-card__meta-item">
                        <span class="material-icons">account_circle</span>
                        <span>${this.escapeHtml(model.author)}</span>
                    </div>
                    <div class="webops-compare-card__meta-item">
                        <span class="material-icons">memory</span>
                        <span>${this.escapeHtml(info.typicalVRAM)} VRAM</span>
                    </div>
                    ${model.downloads ? `
                    <div class="webops-compare-card__meta-item">
                        <span class="material-icons">download</span>
                        <span>${this.formatNumber(model.downloads)}</span>
                    </div>
                    ` : ''}
                </div>
                <button type="button" class="webops-btn webops-btn-sm webops-btn-primary webops-compare-card__btn"
                        onclick="window.webopsFillModel('${this.escapeHtml(model.modelId)}', '${this.escapeHtml(model.modelId)}-deployment')">
                    <span class="material-icons">smart_toy</span>
                    Use This Model
                </button>
            </div>
        `;
    }
    
    clearComparison() {
        this.webopsSelectedModels.clear();
        this.updateCompareButton();
        this.updateModelCards();
        this.toggleComparePanel();
    }
    
    showEmptyState() {
        if (!this.webopsElements.modelsGrid) return;
        
        const isInitialLoad = !this.webopsCurrentFilters.search.trim() &&
                             this.webopsCurrentFilters.category === 'all' &&
                             this.webopsCurrentFilters.sort === 'trending';
        
        const isSearchNoResults = this.webopsCurrentFilters.search.trim();
        
        let emptyStateHTML = '';
        
        if (isInitialLoad) {
            emptyStateHTML = `
                <div class="webops-model-browser__empty">
                    <div class="webops-model-browser__empty-icon">
                        <span class="material-icons">hub</span>
                    </div>
                    <h3 class="webops-model-browser__empty-title">Loading Models from Hugging Face</h3>
                    <p class="webops-model-browser__empty-text">
                        Connecting to Hugging Face Hub to fetch the latest models...
                    </p>
                    <div class="webops-loading-spinner"></div>
                </div>
            `;
        } else if (isSearchNoResults) {
            emptyStateHTML = `
                <div class="webops-model-browser__empty">
                    <div class="webops-model-browser__empty-icon">
                        <span class="material-icons">search_off</span>
                    </div>
                    <h3 class="webops-model-browser__empty-title">No models match your search</h3>
                    <p class="webops-model-browser__empty-text">
                        Try different keywords or browse all models to discover new options.
                    </p>
                    <button class="webops-btn webops-btn-sm webops-btn-secondary"
                            onclick="document.getElementById('webops-model-search').value=''; document.getElementById('webops-model-category').value='all'; window.webopsModelBrowser.resetAndLoadModels()">
                        <span class="material-icons">refresh</span>
                        Show All Models
                    </button>
                </div>
            `;
        } else {
            emptyStateHTML = `
                <div class="webops-model-browser__empty">
                    <div class="webops-model-browser__empty-icon">
                        <span class="material-icons">filter_list_off</span>
                    </div>
                    <h3 class="webops-model-browser__empty-title">No models in this category</h3>
                    <p class="webops-model-browser__empty-text">
                        Try selecting a different category or search for specific models.
                    </p>
                    <button class="webops-btn webops-btn-sm webops-btn-secondary"
                            onclick="document.getElementById('webops-model-category').value='all'; window.webopsModelBrowser.resetAndLoadModels()">
                        <span class="material-icons">apps</span>
                        Show All Categories
                    </button>
                </div>
            `;
        }
        
        this.webopsElements.modelsGrid.innerHTML = emptyStateHTML;
    }
    
    showLoading(show) {
        if (!this.webopsElements.loadingIndicator) return;
        
        if (show) {
            this.webopsElements.loadingIndicator.style.display = 'flex';
            this.webopsElements.loadingIndicator.setAttribute('aria-hidden', 'false');
        } else {
            this.webopsElements.loadingIndicator.style.display = 'none';
            this.webopsElements.loadingIndicator.setAttribute('aria-hidden', 'true');
        }
    }
    
    hideLoading() {
        this.showLoading(false);
    }
    
    showError(message) {
        if (!this.webopsElements.errorContainer) return;
        
        this.webopsElements.errorContainer.innerHTML = `
            <div class="webops-model-browser__error" role="alert" aria-live="polite">
                <div class="webops-model-browser__error-icon">
                    <span class="material-icons">error_outline</span>
                </div>
                <h3 class="webops-model-browser__error-title">Error Loading Models</h3>
                <p class="webops-model-browser__error-text">${this.escapeHtml(message)}</p>
                <button class="webops-btn webops-btn-sm webops-btn-secondary" onclick="window.webopsModelBrowser.resetAndLoadModels()">
                    <span class="material-icons">refresh</span>
                    Try Again
                </button>
            </div>
        `;
        this.webopsElements.errorContainer.style.display = 'block';
        this.webopsElements.errorContainer.setAttribute('aria-hidden', 'false');
    }
    
    hideError() {
        if (!this.webopsElements.errorContainer) return;
        this.webopsElements.errorContainer.style.display = 'none';
        this.webopsElements.errorContainer.setAttribute('aria-hidden', 'true');
    }
    
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `webops-notification webops-notification--${type}`;
        notification.setAttribute('role', 'alert');
        notification.setAttribute('aria-live', 'polite');
        notification.innerHTML = `
            <span class="material-icons webops-notification__icon">
                ${type === 'success' ? 'check_circle' : type === 'error' ? 'error' : type === 'warning' ? 'warning' : 'info'}
            </span>
            <span class="webops-notification__message">${this.escapeHtml(message)}</span>
            <button class="webops-notification__close" aria-label="Close notification">
                <span class="material-icons">close</span>
            </button>
        `;
        
        // Add to page
        document.body.appendChild(notification);
        
        // Animate in
        setTimeout(() => {
            notification.classList.add('webops-notification--show');
        }, 10);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            notification.classList.remove('webops-notification--show');
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }, 5000);
        
        // Close button handler
        const closeBtn = notification.querySelector('.webops-notification__close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                notification.classList.remove('webops-notification--show');
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.parentNode.removeChild(notification);
                    }
                }, 300);
            });
        }
    }
    
    updateLoadMoreButton(models) {
        if (!this.webopsElements.loadMoreBtn) return;
        
        // Show load more button if we have more models to load
        if (this.webopsHasMoreModels && models.length > 0) {
            this.webopsElements.loadMoreBtn.style.display = 'flex';
            this.webopsElements.loadMoreBtn.disabled = false;
            this.webopsElements.loadMoreBtn.setAttribute('aria-label', 'Load more models');
        } else {
            this.webopsElements.loadMoreBtn.style.display = 'none';
        }
    }
    
    formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    announceToScreenReader(message) {
        const announcement = document.createElement('div');
        announcement.setAttribute('role', 'status');
        announcement.setAttribute('aria-live', 'polite');
        announcement.className = 'webops-sr-only';
        announcement.textContent = message;
        
        document.body.appendChild(announcement);
        
        setTimeout(() => {
            if (announcement.parentNode) {
                announcement.parentNode.removeChild(announcement);
            }
        }, 1000);
    }
    
    // Get basic system info for context
    getBasicSystemInfo() {
        // This could be enhanced to actually detect system capabilities
        return {
            hasGPU: true, // Assume GPU for LLM deployment
            gpuMemory: '16GB', // Default assumption
            systemMemory: '32GB',
            recommendedModels: ['gpt2', 'phi-2', 'tinyllama']
        };
    }
}

// Global function to fill model form
window.webopsFillModel = function(modelId, deploymentName) {
    const modelInput = document.getElementById('model_name');
    const nameInput = document.getElementById('name');
    
    if (modelInput) {
        modelInput.value = modelId;
        // Trigger change event for any listeners
        modelInput.dispatchEvent(new Event('change', { bubbles: true }));
    }
    
    if (nameInput) {
        nameInput.value = deploymentName;
        // Trigger change event for any listeners
        nameInput.dispatchEvent(new Event('change', { bubbles: true }));
    }
    
    // Show success feedback
    if (window.WebOps && window.WebOps.Toast) {
        window.WebOps.Toast.success(`Selected model: ${modelId}`);
    } else {
        // Fallback notification
        const notification = document.createElement('div');
        notification.className = 'webops-notification webops-notification--success';
        notification.setAttribute('role', 'status');
        notification.setAttribute('aria-live', 'polite');
        notification.innerHTML = `
            <span class="material-icons">check_circle</span>
            <span>Selected model: ${modelId}</span>
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 3000);
    }
    
    // Scroll to form
    const form = document.getElementById('llmForm');
    if (form) {
        form.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
};

// Initialize model browser when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    window.webopsModelBrowser = new WebOpsModelBrowser();
    
    // Add global keyboard shortcut hint
    const searchInput = document.getElementById('webops-model-search');
    if (searchInput) {
        searchInput.setAttribute('title', 'Search models (Ctrl+K)');
    }
});
