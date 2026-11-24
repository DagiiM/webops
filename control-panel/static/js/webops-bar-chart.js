/* Grouped bar chart as accessible inline SVG, no library (ui-skill: charts are content, solid colours,
 * words not colour alone; rule 17: no third-party code).
 *
 *   webopsBarChart(container, {
 *       title: 'Compliance controls overview',
 *       labels: ['SOC 2', 'ISO 27001'],
 *       series: [{ name: 'Total', values: [10, 12] }, ...]
 *   });
 *
 * Series colours come from CSS (.webops-chart__bar--1 to --6, see webops-chart.css).
 * A visually hidden data table gives screen readers the exact numbers.
 */
(function () {
    'use strict';
    var NS = 'http://www.w3.org/2000/svg';

    function el(name, attrs, parent) {
        var n = document.createElementNS(NS, name);
        Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
        if (parent) { parent.appendChild(n); }
        return n;
    }

    function niceStep(max, targetTicks) {
        if (max <= targetTicks) { return 1; }
        var raw = max / targetTicks, pow = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / pow;
        return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * pow;
    }

    function truncate(s, n) { s = String(s); return s.length > n ? s.slice(0, n - 1) + '…' : s; }

    window.webopsBarChart = function (container, cfg) {
        var labels = cfg.labels || [], series = cfg.series || [];
        container.textContent = '';
        container.classList.add('webops-chart');

        var W = 640, H = 300, M = { t: 16, r: 12, b: 44, l: 40 };
        var plotW = W - M.l - M.r, plotH = H - M.t - M.b;
        var max = 0;
        series.forEach(function (s) { s.values.forEach(function (v) { if (v > max) { max = v; } }); });
        var step = niceStep(Math.max(max, 1), 5), top = Math.ceil(Math.max(max, 1) / step) * step;

        var svg = el('svg', { viewBox: '0 0 ' + W + ' ' + H, class: 'webops-chart__svg', role: 'img',
            'aria-label': (cfg.title || 'Bar chart') + '. Data table follows.' }, container);

        for (var v = 0; v <= top; v += step) {
            var y = M.t + plotH - (v / top) * plotH;
            el('line', { x1: M.l, x2: W - M.r, y1: y, y2: y, class: v === 0 ? 'webops-chart__axis' : 'webops-chart__grid' }, svg);
            var t = el('text', { x: M.l - 6, y: y + 4, class: 'webops-chart__tick', 'text-anchor': 'end' }, svg);
            t.textContent = v;
        }

        var groupW = plotW / Math.max(labels.length, 1), gap = Math.min(16, groupW * 0.2);
        var barW = Math.max(4, (groupW - gap) / Math.max(series.length, 1));
        labels.forEach(function (label, i) {
            var gx = M.l + i * groupW + gap / 2;
            series.forEach(function (s, j) {
                var val = s.values[i] || 0, h = (val / top) * plotH;
                var bar = el('rect', { x: gx + j * barW, y: M.t + plotH - h, width: Math.max(barW - 2, 1), height: h,
                    rx: 2, class: 'webops-chart__bar webops-chart__bar--' + ((j % 6) + 1) }, svg);
                el('title', {}, bar).textContent = s.name + ' – ' + label + ': ' + val;
            });
            var lx = M.l + i * groupW + groupW / 2;
            var lt = el('text', { x: lx, y: H - M.b + 18, class: 'webops-chart__label', 'text-anchor': 'middle' }, svg);
            lt.textContent = truncate(label, Math.max(8, Math.floor(groupW / 7)));
        });

        var legend = document.createElement('ul');
        legend.className = 'webops-chart__legend';
        series.forEach(function (s, j) {
            var li = document.createElement('li');
            var sw = document.createElement('span');
            sw.className = 'webops-chart__swatch webops-chart__bar--' + ((j % 6) + 1);
            sw.setAttribute('aria-hidden', 'true');
            li.appendChild(sw);
            li.appendChild(document.createTextNode(s.name));
            legend.appendChild(li);
        });
        container.appendChild(legend);

        var table = document.createElement('table');
        table.className = 'webops-chart__data';
        var thead = table.createTHead().insertRow();
        ['Group'].concat(series.map(function (s) { return s.name; })).forEach(function (h) {
            var th = document.createElement('th'); th.scope = 'col'; th.textContent = h; thead.appendChild(th);
        });
        var tbody = table.createTBody();
        labels.forEach(function (label, i) {
            var r = tbody.insertRow();
            var th = document.createElement('th'); th.scope = 'row'; th.textContent = label; r.appendChild(th);
            series.forEach(function (s) { r.insertCell().textContent = s.values[i] || 0; });
        });
        container.appendChild(table);
    };
})();
