/* Declarative event actions without inline handlers (ui-skill rule 17: strict CSP).
 *
 *   data-on-click="openModal()"            was data-on-click="openModal()"
 *   data-on-change="toggle(this.value)"    was data-on-change="toggle(this.value)"
 *   data-on-submit="validate(event)"       was data-on-submit="validate(event)"
 *   data-confirm="Delete this item?"       was onsubmit/onclick="return confirm('...')"
 *
 * Expressions are parsed, never passed to eval()/new Function(), so this works
 * under `script-src 'self'`. Supported: calls to global functions or methods on
 * globals, `this`, `event`, string/number/boolean literals, property chains,
 * `a.b = value`, `;` between statements and a leading `return`.
 * A statement that returns false cancels the default action, like an inline handler.
 */
(function () {
    'use strict';

    function tokenize(src) {
        var tokens = [], i = 0, m;
        while (i < src.length) {
            var c = src.charAt(i);
            if (/\s/.test(c)) { i++; continue; }
            if (c === '"' || c === "'") {
                var out = '', j = i + 1;
                while (j < src.length && src.charAt(j) !== c) {
                    if (src.charAt(j) === '\\' && j + 1 < src.length) {
                        j++;
                        var e = src.charAt(j);
                        out += e === 'n' ? '\n' : e === 't' ? '\t' : e;
                    } else { out += src.charAt(j); }
                    j++;
                }
                if (j >= src.length) { throw new Error('unterminated string'); }
                tokens.push({ t: 'str', v: out }); i = j + 1; continue;
            }
            m = /^[A-Za-z_$][\w$]*/.exec(src.slice(i));
            if (m) { tokens.push({ t: 'id', v: m[0] }); i += m[0].length; continue; }
            m = /^\d+(\.\d+)?/.exec(src.slice(i));
            if (m) { tokens.push({ t: 'num', v: parseFloat(m[0]) }); i += m[0].length; continue; }
            if ('.(),=;'.indexOf(c) !== -1) { tokens.push({ t: 'p', v: c }); i++; continue; }
            throw new Error('unsupported character "' + c + '"');
        }
        return tokens;
    }

    function run(src, el, ev) {
        var tokens = tokenize(src), pos = 0, cancel = false;

        function peek() { return tokens[pos]; }
        function isP(v) { var t = tokens[pos]; return t && t.t === 'p' && t.v === v; }
        function expectP(v) {
            if (!isP(v)) { throw new Error('expected ' + v); }
            pos++;
        }

        function primary() {
            var t = tokens[pos++];
            if (!t) { throw new Error('unexpected end'); }
            if (t.t === 'str' || t.t === 'num') { return { value: t.v, owner: null, key: null }; }
            if (t.t !== 'id') { throw new Error('unexpected ' + t.v); }
            switch (t.v) {
                case 'this': return { value: el, owner: null, key: null };
                case 'event': return { value: ev, owner: null, key: null };
                case 'true': return { value: true, owner: null, key: null };
                case 'false': return { value: false, owner: null, key: null };
                case 'null': return { value: null, owner: null, key: null };
                case 'undefined': return { value: undefined, owner: null, key: null };
            }
            return { value: window[t.v], owner: window, key: t.v };
        }

        function chain() {
            var ref = primary();
            for (;;) {
                if (isP('.')) {
                    pos++;
                    var name = tokens[pos++];
                    if (!name || name.t !== 'id') { throw new Error('expected property name'); }
                    if (ref.value === null || ref.value === undefined) { throw new Error('cannot read ' + name.v); }
                    ref = { value: ref.value[name.v], owner: ref.value, key: name.v };
                } else if (isP('(')) {
                    pos++;
                    var args = [];
                    while (!isP(')')) {
                        args.push(chain().value);
                        if (isP(',')) { pos++; } else if (!isP(')')) { throw new Error('expected , or )'); }
                    }
                    pos++;
                    if (typeof ref.value !== 'function') { throw new Error((ref.key || 'value') + ' is not a function'); }
                    ref = { value: ref.value.apply(ref.owner, args), owner: null, key: null };
                } else { return ref; }
            }
        }

        while (pos < tokens.length) {
            var isReturn = false;
            if (peek().t === 'id' && peek().v === 'return') { isReturn = true; pos++; }
            var ref = chain();
            if (isP('=')) {
                pos++;
                var rhs = chain().value;
                if (!ref.owner) { throw new Error('invalid assignment target'); }
                ref.owner[ref.key] = rhs;
            } else if (isReturn && ref.value === false) {
                cancel = true;
            }
            if (isP(';')) { pos++; } else if (pos < tokens.length) { throw new Error('unexpected ' + tokens[pos].v); }
        }
        return cancel;
    }

    function dispatch(type) {
        var attr = 'data-on-' + type;
        document.addEventListener(type, function (ev) {
            var node = ev.target;
            while (node && node !== document) {
                if (node.nodeType === 1 && node.hasAttribute(attr)) {
                    try {
                        if (run(node.getAttribute(attr), node, ev)) { ev.preventDefault(); }
                    } catch (err) {
                        if (window.console) { console.error('[ui-actions] ' + attr + '="' + node.getAttribute(attr) + '": ' + err.message); }
                    }
                    if (ev.cancelBubble) { break; }
                }
                node = node.parentNode;
            }
        }, false);
    }
    ['click', 'change', 'submit'].forEach(dispatch);

    /* data-confirm: ask before a click (links, buttons) or a submit (forms). Capture
       phase, so a refusal also stops data-on-* actions and navigation. */
    document.addEventListener('click', function (ev) {
        var el = ev.target.closest ? ev.target.closest('[data-confirm]') : null;
        if (!el || el.tagName === 'FORM') { return; }
        if (!window.confirm(el.getAttribute('data-confirm'))) {
            ev.preventDefault();
            ev.stopPropagation();
        }
    }, true);
    document.addEventListener('submit', function (ev) {
        var form = ev.target;
        if (form && form.tagName === 'FORM' && form.hasAttribute('data-confirm') &&
            !window.confirm(form.getAttribute('data-confirm'))) {
            ev.preventDefault();
            ev.stopPropagation();
        }
    }, true);
})();
