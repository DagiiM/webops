/* Moved from templates/api/token_list.html (ui-skill rule 17: no inline <script>). */
// Search functionality
const searchInput = document.getElementById('search');
if (searchInput) {
    searchInput.addEventListener('input', function(e) {
        const searchTerm = e.target.value.toLowerCase();
        const cards = document.querySelectorAll('.webops-card-body');

        cards.forEach(card => {
            const text = card.textContent.toLowerCase();
            const parentCard = card.closest('.webops-card');
            if (parentCard && parentCard.parentElement.style.gridTemplateColumns) {
                parentCard.style.display = text.includes(searchTerm) ? '' : 'none';
            }
        });
    });
}

// Modal functions
function openCreateModal() {
    document.getElementById('createModal').classList.add('active');
    document.getElementById('name').focus();
}

function closeCreateModal() {
    document.getElementById('createModal').classList.remove('active');
    document.getElementById('createForm').reset();
}

// Close modal on outside click
document.getElementById('createModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeCreateModal();
    }
});

// Close modal on escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeCreateModal();
    }
});

// Show loader on form submit
document.getElementById('createForm').addEventListener('submit', function() {
    showLoader();
});
