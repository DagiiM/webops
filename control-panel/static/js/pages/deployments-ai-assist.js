// Deploy assistant: analyse a repository, show the result, and let the person apply suggestions to the form.
// Everything from the server is inserted with textContent, never as HTML.
(function () {
  var box = document.getElementById('aiAssist');
  if (!box) return;
  var run = document.getElementById('aiAssistRun');
  var out = document.getElementById('aiAssistOut');
  var repo = document.getElementById('repo_url');
  var csrf = (document.querySelector('meta[name="csrf-token"]') || {}).content || '';

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function list(items) {
    var ul = el('ul', 'ui-assist__list');
    items.forEach(function (t) { ul.appendChild(el('li', null, t)); });
    return ul;
  }
  function setValue(id, value, fire) {
    var f = document.getElementById(id);
    if (!f) return;
    f.value = value;
    if (fire) f.dispatchEvent(new Event('input', { bubbles: true }));
  }
  function show(nodes) {
    out.replaceChildren.apply(out, nodes);
    out.hidden = false;
  }

  function render(data) {
    var a = data.analysis, nodes = [];
    if (data.safety) {
      var sf = data.safety, dec = sf.decision;
      var banner = el('p', 'ui-assist__verdict ui-assist__verdict--' + (dec === 'auto_approved' ? 'can_deploy' : dec === 'blocked' ? 'blocked' : 'request_only'));
      banner.appendChild(el('strong', null, dec === 'auto_approved' ? 'Safety review passed. ' : dec === 'blocked' ? 'Safety review blocked this. ' : 'Safety review: an operator must approve. '));
      banner.appendChild(document.createTextNode(dec === 'auto_approved' ? 'This site would be published automatically.' : dec === 'blocked' ? 'It cannot be deployed until these are fixed.' : 'It will wait for approval.'));
      nodes.push(banner);
      var shown = (sf.findings || []).filter(function (f) { return f.severity === 'block' || f.severity === 'review' || f.severity === 'warn'; });
      if (shown.length) nodes.push(list(shown.map(function (f) { return f.severity.toUpperCase() + ': ' + f.title + (f.detail ? ' - ' + f.detail : ''); })));
      if (sf.ai && sf.ai.status === 'ran' && sf.ai.summary) nodes.push(el('p', 'webops-help-text', 'AI second opinion: ' + sf.ai.summary));
    }

    var head = el('p', 'ui-assist__verdict ui-assist__verdict--' + a.verdict);
    head.appendChild(el('strong', null, a.verdict === 'can_deploy' ? 'Can be deployed here. ' : a.verdict === 'request_only' ? 'Request only on this server. ' : 'Cannot be deployed. '));
    head.appendChild(document.createTextNode(a.reason));

    if (!(data.safety && data.safety.decision === 'blocked')) nodes.push(head);

    var facts = [];
    facts.push('Detected: ' + a.kind + (a.details && a.details.frameworks && a.details.frameworks.length ? ' (' + a.details.frameworks.join(', ') + ')' : ''));
    if (a.manifests.length) facts.push('Server or build files: ' + a.manifests.join(', '));
    if (a.private) facts.push('Private repository');
    if (a.env_vars.length) facts.push('Environment variables it expects: ' + a.env_vars.join(', '));
    nodes.push(list(facts));

    if (data.plan) {
      var p = data.plan;
      nodes.push(el('h5', 'ui-assist__sub', 'Plan from ' + data.provider.name + ' (advisory, check it)'));
      if (p.summary) nodes.push(el('p', null, p.summary));
      if (p.steps.length) nodes.push(list(p.steps));
      if (p.risks.length) { nodes.push(el('h5', 'ui-assist__sub', 'Check before deploying')); nodes.push(list(p.risks)); }
      var extra = p.env_vars.filter(function (n) { return a.env_vars.indexOf(n) < 0; });
      if (extra.length) nodes.push(el('p', 'webops-help-text', 'The model also mentions: ' + extra.join(', ') + '. Verify these.'));
    }
    (data.notices || []).forEach(function (n) { nodes.push(el('p', 'webops-help-text', n)); });

    var apply = el('button', 'webops-btn webops-btn-sm webops-btn-primary', 'Apply to form');
    apply.type = 'button';
    apply.addEventListener('click', function () {
      var s = a.suggest;
      var name = document.getElementById('name');
      if (name && !name.value.trim()) setValue('name', s.name, true);
      setValue('branch', s.branch, false);
      var so = document.getElementById('static_only');
      if (so) so.checked = !!s.static_only;
      apply.textContent = 'Applied';
      apply.disabled = true;
    });
    nodes.push(apply);
    show(nodes);
  }

  run.addEventListener('click', function () {
    var url = (repo && repo.value || '').trim();
    if (!url) { show([el('p', 'ui-assist__err', 'Enter the repository address first.')]); return; }
    var sel = document.getElementById('aiAssistProvider');
    var body = { repo_url: url, branch: (document.getElementById('branch') || {}).value || '', use_ai: !!(sel && sel.value) };
    if (sel && sel.value) body.provider = parseInt(sel.value, 10);
    run.disabled = true;
    var old = run.textContent;
    run.textContent = 'Analysing...';
    fetch(box.getAttribute('data-url'), {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, 'X-Requested-With': 'XMLHttpRequest' },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json().catch(function () { return { ok: false, error: 'Unexpected response (HTTP ' + r.status + ').' }; }); })
      .then(function (data) { if (data.ok) render(data); else show([el('p', 'ui-assist__err', data.error || 'The analysis failed.')]); })
      .catch(function () { show([el('p', 'ui-assist__err', 'Could not reach the server.')]); })
      .then(function () { run.disabled = false; run.textContent = old; });
  });
})();
