// AI providers: show only the settings that belong to the chosen provider type.
(function () {
  var radios = document.querySelectorAll('input[name="kind"]');
  var sets = document.querySelectorAll('fieldset[data-kind]');
  function sync() {
    var chosen = 'external';
    radios.forEach(function (r) { if (r.checked) chosen = r.value; });
    sets.forEach(function (f) {
      var on = f.getAttribute('data-kind') === chosen;
      f.hidden = !on;
      f.querySelectorAll('input,select').forEach(function (el) { el.disabled = !on; });
    });
  }
  radios.forEach(function (r) { r.addEventListener('change', sync); });
  sync();
})();
