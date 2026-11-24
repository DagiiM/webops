// Give feedback while the database is being created (it takes a few seconds).
(function () {
  var form = document.getElementById('deployForm');
  var btn = document.getElementById('deployBtn');
  if (!form || !btn) return;
  form.addEventListener('submit', function () {
    if (form.checkValidity && !form.checkValidity()) return;
    btn.disabled = true;
    btn.textContent = 'Deploying...';
  });
})();
