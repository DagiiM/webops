/* Small local code editor (replaces CodeMirror from a CDN; ui-skill rule 17: no third-party code).
 *
 * A native <textarea> with a line-number gutter. It keeps the part of the CodeMirror API that the
 * deployment file editor uses: getValue, setValue, getCursor, refresh, focus, on('change'|'cursorActivity').
 * Behaviour: Tab inserts spaces, Shift+Tab outdents, Enter keeps indentation, line numbers follow
 * scrolling. There is no syntax highlighting; the native textarea keeps spellcheck off, wrapping off
 * and is fully keyboard and screen-reader accessible.
 */
(function () {
    'use strict';

    function WebopsCodeEditor(parent, options) {
        options = options || {};
        this.indent = new Array((options.tabSize || 4) + 1).join(' ');
        this.listeners = { change: [], cursorActivity: [] };

        var root = document.createElement('div');
        root.className = 'webops-code-editor';
        var gutter = document.createElement('div');
        gutter.className = 'webops-code-editor__gutter';
        gutter.setAttribute('aria-hidden', 'true');
        var area = document.createElement('textarea');
        area.className = 'webops-code-editor__input';
        area.setAttribute('spellcheck', 'false');
        area.setAttribute('autocapitalize', 'off');
        area.setAttribute('autocomplete', 'off');
        area.setAttribute('wrap', 'off');
        area.setAttribute('aria-label', options.label || 'File contents');
        area.value = options.value || '';
        root.appendChild(gutter);
        root.appendChild(area);
        parent.appendChild(root);

        this.root = root; this.gutter = gutter; this.area = area;
        this._lines = 0;
        this._numbers();

        var self = this;
        area.addEventListener('input', function () { self._numbers(); self._emit('change'); self._emit('cursorActivity'); });
        area.addEventListener('scroll', function () { gutter.scrollTop = area.scrollTop; });
        ['keyup', 'click', 'focus'].forEach(function (t) {
            area.addEventListener(t, function () { self._emit('cursorActivity'); });
        });
        area.addEventListener('keydown', function (e) { self._keydown(e); });
    }

    WebopsCodeEditor.prototype._emit = function (type) {
        var self = this;
        this.listeners[type].forEach(function (fn) { fn(self); });
    };

    WebopsCodeEditor.prototype._numbers = function () {
        var n = this.area.value.split('\n').length;
        if (n === this._lines) { return; }
        this._lines = n;
        var out = [];
        for (var i = 1; i <= n; i++) { out.push(i); }
        this.gutter.textContent = out.join('\n');
    };

    WebopsCodeEditor.prototype._replace = function (start, end, text, caret) {
        var a = this.area;
        a.focus();
        // execCommand keeps the native undo stack; fall back to direct assignment
        a.setSelectionRange(start, end);
        var ok = false;
        try { ok = document.execCommand('insertText', false, text); } catch (e) { ok = false; }
        if (!ok) {
            a.value = a.value.slice(0, start) + text + a.value.slice(end);
            a.dispatchEvent(new Event('input', { bubbles: true }));
        }
        if (caret !== undefined) { a.setSelectionRange(caret, caret); }
    };

    WebopsCodeEditor.prototype._keydown = function (e) {
        var a = this.area, v = a.value, s = a.selectionStart, en = a.selectionEnd;
        if (e.key === 'Tab' && !e.ctrlKey && !e.metaKey && !e.altKey) {
            e.preventDefault();
            var ls = v.lastIndexOf('\n', s - 1) + 1;
            if (s !== en || e.shiftKey) {
                var block = v.slice(ls, en), lines = block.split('\n');
                var out = lines.map(function (l) {
                    if (!e.shiftKey) { return this.indent + l; }
                    return l.indexOf(this.indent) === 0 ? l.slice(this.indent.length) : l.replace(/^ {1,3}|^\t/, '');
                }, this).join('\n');
                this._replace(ls, en, out, undefined);
                a.setSelectionRange(ls, ls + out.length);
            } else {
                this._replace(s, en, this.indent);
            }
        } else if (e.key === 'Enter' && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
            var lineStart = v.lastIndexOf('\n', s - 1) + 1;
            var lead = /^[ \t]*/.exec(v.slice(lineStart, s))[0];
            var extra = /[\{\[\(:]\s*$/.test(v.slice(lineStart, s)) ? this.indent : '';
            e.preventDefault();
            this._replace(s, en, '\n' + lead + extra);
        }
    };

    WebopsCodeEditor.prototype.getValue = function () { return this.area.value; };
    WebopsCodeEditor.prototype.setValue = function (v) {
        this.area.value = v; this._lines = 0; this._numbers(); this._emit('change');
    };
    WebopsCodeEditor.prototype.getCursor = function () {
        var before = this.area.value.slice(0, this.area.selectionStart).split('\n');
        return { line: before.length - 1, ch: before[before.length - 1].length };
    };
    WebopsCodeEditor.prototype.focus = function () { this.area.focus(); };
    WebopsCodeEditor.prototype.refresh = function () { this.gutter.scrollTop = this.area.scrollTop; };
    WebopsCodeEditor.prototype.on = function (type, fn) {
        if (this.listeners[type]) { this.listeners[type].push(fn); }
    };

    window.WebopsCodeEditor = function (parent, options) { return new WebopsCodeEditor(parent, options); };
})();
