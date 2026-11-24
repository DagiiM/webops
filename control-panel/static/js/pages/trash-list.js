/* Moved from templates/trash/list.html (ui-skill rule 17: no inline <script>). */
// Ultra-Sleek Trash Interface JavaScript
class WebOpsTrashManager {
    constructor() {
        this.selectedItems = new Set();
        this.searchTimeout = null;
        this.isLoading = false;

        this.initializeEventListeners();
        this.loadSearchState();
    }

    initializeEventListeners() {
        // Search functionality with debouncing
        const searchInput = document.getElementById('trashSearch');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                clearTimeout(this.searchTimeout);
                this.searchTimeout = setTimeout(() => {
                    this.performSearch(e.target.value);
                }, 300);
            });
        }

        // Filter changes
        ['typeFilter', 'dateFromFilter', 'dateToFilter'].forEach(filterId => {
            const filter = document.getElementById(filterId);
            if (filter) {
                filter.addEventListener('change', () => this.applyFilters());
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboardShortcuts(e));

        // Click outside to deselect
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.webops-trash-item-card')) {
                this.clearSelection();
            }
        });
    }

    handleKeyboardShortcuts(e) {
        // Select all (Ctrl+A)
        if (e.ctrlKey && e.key === 'a') {
            e.preventDefault();
            this.selectAllItems();
        }

        // Delete selected (Delete key)
        if (e.key === 'Delete' && this.selectedItems.size > 0) {
            e.preventDefault();
            if (confirm(`Permanently delete ${this.selectedItems.size} selected items?`)) {
                this.bulkDelete();
            }
        }

        // Escape to clear selection
        if (e.key === 'Escape') {
            this.clearSelection();
        }
    }

    selectItem(cardElement, event) {
        // Don't select if clicking on checkbox or action buttons
        if (event.target.type === 'checkbox' ||
            event.target.closest('.webops-trash-item-actions') ||
            event.target.tagName === 'BUTTON') {
            return;
        }

        const itemId = parseInt(cardElement.dataset.itemId);
        const checkbox = cardElement.querySelector('.webops-trash-item-checkbox');

        if (event.ctrlKey || event.metaKey) {
            // Multi-select with Ctrl/Cmd
            this.toggleItemSelection(itemId, checkbox, cardElement);
        } else {
            // Single select - clear others first
            if (this.selectedItems.size === 1 && this.selectedItems.has(itemId)) {
                // Already selected, do nothing
                return;
            }

            this.clearSelection();
            this.selectItemDirect(itemId, checkbox, cardElement);
        }
    }

    toggleItemSelection(itemId, checkbox, cardElement) {
        if (this.selectedItems.has(itemId)) {
            this.selectedItems.delete(itemId);
            checkbox.checked = false;
            cardElement.classList.remove('selected');
        } else {
            this.selectedItems.add(itemId);
            checkbox.checked = true;
            cardElement.classList.add('selected');
        }
        this.updateBulkActions();
    }

    selectItemDirect(itemId, checkbox, cardElement) {
        this.selectedItems.add(itemId);
        checkbox.checked = true;
        cardElement.classList.add('selected');
        this.updateBulkActions();
    }

    selectAllItems() {
        const itemCards = document.querySelectorAll('.webops-trash-item-card');
        itemCards.forEach(card => {
            const itemId = parseInt(card.dataset.itemId);
            const checkbox = card.querySelector('.webops-trash-item-checkbox');

            this.selectedItems.add(itemId);
            checkbox.checked = true;
            card.classList.add('selected');
        });
        this.updateBulkActions();
    }

    clearSelection() {
        this.selectedItems.clear();
        document.querySelectorAll('.webops-trash-item-card').forEach(card => {
            card.classList.remove('selected');
            const checkbox = card.querySelector('.webops-trash-item-checkbox');
            if (checkbox) checkbox.checked = false;
        });
        this.updateBulkActions();
    }

    updateBulkActions() {
        const bulkActions = document.getElementById('bulkActions');
        const selectedCount = document.getElementById('selectedCount');

        if (this.selectedItems.size > 0) {
            selectedCount.textContent = this.selectedItems.size;
            bulkActions.classList.add('active');
        } else {
            bulkActions.classList.remove('active');
        }
    }

    async performSearch(query) {
        if (this.isLoading) return;

        this.isLoading = true;
        const loadingState = document.getElementById('loadingState');
        const trashItems = document.getElementById('trashItems');

        try {
            loadingState.style.display = 'flex';
            trashItems.style.opacity = '0.5';

            const response = await fetch(`/trash/api/search/?q=${encodeURIComponent(query)}`, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                }
            });

            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    // Update results with smooth transition
                    trashItems.style.opacity = '0';
                    setTimeout(() => {
                        trashItems.innerHTML = data.html;
                        trashItems.style.opacity = '1';
                    }, 150);
                }
            }
        } catch (error) {
            console.error('Search failed:', error);
        } finally {
            this.isLoading = false;
            loadingState.style.display = 'none';
            trashItems.style.opacity = '1';
        }
    }

    applyFilters() {
        const typeFilter = document.getElementById('typeFilter').value;
        const dateFromFilter = document.getElementById('dateFromFilter').value;
        const dateToFilter = document.getElementById('dateToFilter').value;

        // Build URL with current filters
        const params = new URLSearchParams(window.location.search);

        if (typeFilter) {
            params.set('type', typeFilter);
        } else {
            params.delete('type');
        }

        if (dateFromFilter) {
            params.set('date_from', dateFromFilter);
        } else {
            params.delete('date_from');
        }

        if (dateToFilter) {
            params.set('date_to', dateToFilter);
        } else {
            params.delete('date_to');
        }

        // Preserve search if exists
        const searchInput = document.getElementById('trashSearch');
        if (searchInput && searchInput.value) {
            params.set('search', searchInput.value);
        }

        // Navigate to filtered view
        window.location.href = `${window.location.pathname}?${params.toString()}`;
    }

    loadSearchState() {
        // Restore search state from URL parameters
        const urlParams = new URLSearchParams(window.location.search);
        const searchValue = urlParams.get('search');

        if (searchValue) {
            const searchInput = document.getElementById('trashSearch');
            if (searchInput) {
                searchInput.value = searchValue;
            }
        }
    }

    // Global functions for onclick handlers
    async restoreItem(itemId, event) {
        event.stopPropagation();

        if (!confirm('Are you sure you want to restore this item?')) {
            return;
        }

        try {
            const formData = new FormData();
            formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);

            const response = await fetch(`/trash/${itemId}/restore/`, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                }
            });

            if (response.ok) {
                // Remove item from UI with animation
                const itemCard = document.querySelector(`[data-item-id="${itemId}"]`);
                if (itemCard) {
                    itemCard.style.transform = 'scale(0.95)';
                    itemCard.style.opacity = '0';
                    setTimeout(() => {
                        itemCard.remove();
                        this.updateStatsAfterAction();
                    }, 300);
                }
            } else {
                throw new Error('Restore failed');
            }
        } catch (error) {
            console.error('Restore failed:', error);
            alert('Failed to restore item. Please try again.');
        }
    }

    async deleteItem(itemId, event) {
        event.stopPropagation();

        if (!confirm('Are you sure you want to permanently delete this item? This action cannot be undone.')) {
            return;
        }

        try {
            const formData = new FormData();
            formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);

            const response = await fetch(`/trash/${itemId}/delete/`, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                }
            });

            if (response.ok) {
                // Remove item from UI with animation
                const itemCard = document.querySelector(`[data-item-id="${itemId}"]`);
                if (itemCard) {
                    itemCard.style.transform = 'scale(0.95)';
                    itemCard.style.opacity = '0';
                    setTimeout(() => {
                        itemCard.remove();
                        this.updateStatsAfterAction();
                    }, 300);
                }
            } else {
                throw new Error('Delete failed');
            }
        } catch (error) {
            console.error('Delete failed:', error);
            alert('Failed to delete item. Please try again.');
        }
    }

    async bulkRestore() {
        if (this.selectedItems.size === 0) return;

        if (!confirm(`Restore ${this.selectedItems.size} selected items?`)) {
            return;
        }

        await this.performBulkAction('restore');
    }

    async bulkDelete() {
        if (this.selectedItems.size === 0) return;

        if (!confirm(`Permanently delete ${this.selectedItems.size} selected items? This action cannot be undone.`)) {
            return;
        }

        await this.performBulkAction('delete');
    }

    async performBulkAction(action) {
        const itemIds = Array.from(this.selectedItems);
        const endpoint = action === 'restore' ? 'bulk/restore/' : 'bulk/delete/';

        try {
            const formData = new FormData();
            formData.append('csrfmiddlewaretoken', document.querySelector('[name=csrfmiddlewaretoken]').value);
            itemIds.forEach(id => formData.append('item_ids', id));

            const response = await fetch(`/trash/${endpoint}`, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                }
            });

            if (response.ok) {
                // Remove selected items from UI
                itemIds.forEach(itemId => {
                    const itemCard = document.querySelector(`[data-item-id="${itemId}"]`);
                    if (itemCard) {
                        itemCard.style.transform = 'scale(0.95)';
                        itemCard.style.opacity = '0';
                    }
                });

                setTimeout(() => {
                    itemIds.forEach(itemId => {
                        const itemCard = document.querySelector(`[data-item-id="${itemId}"]`);
                        if (itemCard) itemCard.remove();
                    });
                    this.clearSelection();
                    this.updateStatsAfterAction();
                }, 300);
            } else {
                throw new Error('Bulk action failed');
            }
        } catch (error) {
            console.error('Bulk action failed:', error);
            alert(`Failed to ${action} items. Please try again.`);
        }
    }

    async updateStatsAfterAction() {
        try {
            const response = await fetch('/trash/api/stats/', {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                }
            });

            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    // Update stats cards with animation
                    const statsCards = document.querySelectorAll('.webops-trash-stat-value');
                    statsCards.forEach((card, index) => {
                        const keys = Object.keys(data.stats);
                        if (keys[index]) {
                            const newValue = data.stats[keys[index]];
                            this.animateValue(card, newValue);
                        }
                    });
                }
            }
        } catch (error) {
            console.error('Failed to update stats:', error);
        }
    }

    animateValue(element, newValue) {
        const currentValue = parseInt(element.textContent.replace(/[^\d]/g, '')) || 0;
        const difference = newValue - currentValue;

        if (difference === 0) return;

        const duration = 500; // Animation duration in ms
        const steps = 20;
        const stepValue = difference / steps;
        let currentStep = 0;

        const animate = () => {
            currentStep++;
            const progress = currentStep / steps;
            const current = Math.round(currentValue + (difference * this.easeOutCubic(progress)));

            // Format the value based on its type
            if (element.textContent.includes('KB') || element.textContent.includes('MB') || element.textContent.includes('GB')) {
                element.textContent = this.formatFileSize(current);
            } else {
                element.textContent = current;
            }

            if (currentStep < steps) {
                requestAnimationFrame(animate);
            }
        };

        requestAnimationFrame(animate);
    }

    easeOutCubic(t) {
        return 1 - Math.pow(1 - t, 3);
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }
}

// Initialize the trash manager when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.trashManager = new WebOpsTrashManager();

    // Make functions globally available for onclick handlers
    window.selectItem = (card, event) => window.trashManager.selectItem(card, event);
    window.restoreItem = (id, event) => window.trashManager.restoreItem(id, event);
    window.deleteItem = (id, event) => window.trashManager.deleteItem(id, event);
    window.bulkRestore = () => window.trashManager.bulkRestore();
    window.bulkDelete = () => window.trashManager.bulkDelete();
    window.clearSelection = () => window.trashManager.clearSelection();
});

// Utility function for global access
function selectItem(cardElement, event) {
    window.trashManager.selectItem(cardElement, event);
}

function restoreItem(itemId, event) {
    window.trashManager.restoreItem(itemId, event);
}

function deleteItem(itemId, event) {
    window.trashManager.deleteItem(itemId, event);
}

function bulkRestore() {
    window.trashManager.bulkRestore();
}

function bulkDelete() {
    window.trashManager.bulkDelete();
}

function clearSelection() {
    window.trashManager.clearSelection();
}
