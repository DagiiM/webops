/* Moved from templates/automation/template_list.html (ui-skill rule 17: no inline <script>). */
document.addEventListener('DOMContentLoaded', function() {
    const searchInput = document.getElementById('template-search');
    const filterBtns = document.querySelectorAll('.webops-template-list__filter-btn');
    const templatesGrid = document.getElementById('templates-grid');
    const previewModal = document.getElementById('template-preview-modal');
    const previewBtns = document.querySelectorAll('.webops-template-card__preview-btn');

    let currentFilters = {
        category: 'all',
        search: ''
    };

    // Search functionality
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            currentFilters.search = this.value.toLowerCase();
            filterTemplates();
        });
    }

    // Filter buttons
    filterBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const filterValue = this.dataset.category;

            // Update active state
            this.parentElement.querySelectorAll('.webops-template-list__filter-btn').forEach(b => b.classList.remove('webops-template-list__filter-btn--active'));
            this.classList.add('webops-template-list__filter-btn--active');

            // Update filter
            currentFilters.category = filterValue;
            filterTemplates();
        });
    });

    // Template preview buttons
    previewBtns.forEach(btn => {
        btn.addEventListener('click', function() {
            const templateId = this.dataset.templateId;
            showPreviewModal(templateId);
        });
    });

    function filterTemplates() {
        const templateCards = document.querySelectorAll('.webops-template-card');
        let visibleCount = 0;

        templateCards.forEach(card => {
            const category = card.dataset.category;
            const name = card.dataset.name;

            const matchesCategory = currentFilters.category === 'all' || category === currentFilters.category;
            const matchesSearch = !currentFilters.search || name.includes(currentFilters.search);

            if (matchesCategory && matchesSearch) {
                card.style.display = 'block';
                visibleCount++;
            } else {
                card.style.display = 'none';
            }
        });
    }

    function showPreviewModal(templateId) {
        if (previewModal) {
            previewModal.style.display = 'flex';
            previewModal.classList.add('show');

            // Load template details via AJAX
            fetch(`/automation/templates/${templateId}/preview/`)
                .then(response => response.json())
                .then(data => {
                    document.getElementById('preview-title').textContent = data.name;
                    document.getElementById('preview-subtitle').textContent = data.category;
                    document.getElementById('preview-body').innerHTML = data.html;
                    document.getElementById('use-template-btn').onclick = () => {
                        window.location.href = `/automation/template/${templateId}/create/`;
                    };
                })
                .catch(error => {
                    document.getElementById('preview-body').innerHTML = '<p>Error loading template preview.</p>';
                });
        }
    }

    window.closePreviewModal = function() {
        if (previewModal) {
            previewModal.classList.remove('show');
            setTimeout(() => {
                previewModal.style.display = 'none';
            }, 300);
        }
    };

    window.clearFilters = function() {
        currentFilters = {
            category: 'all',
            search: ''
        };

        if (searchInput) searchInput.value = '';
        filterBtns.forEach(btn => {
            btn.classList.remove('webops-template-list__filter-btn--active');
            if (btn.dataset.category === 'all') {
                btn.classList.add('webops-template-list__filter-btn--active');
            }
        });

        filterTemplates();
    };
});
