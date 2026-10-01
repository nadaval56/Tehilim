/* תהילים — התנהגות בצד הלקוח. בלי תלויות.
   העדפות נשמרות דרך PRIVACY (privacy.js), תחת המפתח 'tehillim:prefs'. */
(function () {
  'use strict';
  var KEY = 'tehillim:prefs';
  var root = document.documentElement;

  function load() {
    try { return JSON.parse((window.PRIVACY && PRIVACY.get(KEY)) || '{}') || {}; }
    catch (e) { return {}; }
  }
  function save(p) {
    try { if (window.PRIVACY) PRIVACY.set(KEY, JSON.stringify(p)); } catch (e) { /* no storage */ }
  }
  var prefs = load();

  /* ── ערכת נושא: auto → light → dark ── */
  var themeBtn = document.querySelector('.theme-btn');
  var LABELS = { auto: 'ערכת נושא: לפי המכשיר', light: 'ערכת נושא: בהירה', dark: 'ערכת נושא: כהה' };
  function applyTheme() {
    var t = prefs.theme || 'auto';
    if (t === 'auto') root.removeAttribute('data-theme'); else root.setAttribute('data-theme', t);
    if (themeBtn) { themeBtn.setAttribute('aria-label', LABELS[t]); themeBtn.title = LABELS[t]; }
  }
  applyTheme();
  if (themeBtn) themeBtn.addEventListener('click', function () {
    var order = ['auto', 'light', 'dark'];
    prefs.theme = order[(order.indexOf(prefs.theme || 'auto') + 1) % 3];
    save(prefs); applyTheme();
  });

  /* ── טעמים / ניקוד בלבד ──
     הטקסט נשלח עם טעמים. במצב "ניקוד בלבד" מסירים את סימני הטעמים
     (U+0591–U+05AF) מצמתי הטקסט, ושומרים את המקור כדי להחזירו. */
  var TEAMIM = /[֑-֯]/g;
  var originals = [];
  function setTeamim(on) {
    var areas = document.querySelectorAll('.psalm-text, .pair-text');
    if (!areas.length) return;
    if (!on && !originals.length) {
      areas.forEach(function (a) {
        var w = document.createTreeWalker(a, NodeFilter.SHOW_TEXT);
        var n;
        while ((n = w.nextNode())) { originals.push([n, n.nodeValue]); n.nodeValue = n.nodeValue.replace(TEAMIM, ''); }
      });
    } else if (on && originals.length) {
      originals.forEach(function (p) { p[0].nodeValue = p[1]; });
      originals = [];
    }
    root.classList.toggle('plain-text', !on);
  }

  function bindToggle(sel, key, def, apply) {
    var b = document.querySelector(sel);
    var val = key in prefs ? prefs[key] : def;
    apply(val);
    if (!b) return;
    b.setAttribute('aria-pressed', String(val));
    b.addEventListener('click', function () {
      val = !val; prefs[key] = val; save(prefs);
      b.setAttribute('aria-pressed', String(val)); apply(val);
    });
  }
  bindToggle('#tg-teamim', 'teamim', true, setTeamim);
  bindToggle('#tg-names', 'names', false, function (v) { root.classList.toggle('show-names', v); });

  /* ── מפת הספר: בחירת ממד ── */
  document.querySelectorAll('[data-map]').forEach(function (box) {
    var map = box.querySelector('.book-map');
    box.querySelectorAll('.seg button').forEach(function (btn) {
      btn.addEventListener('click', function () {
        box.querySelectorAll('.seg button').forEach(function (b) { b.setAttribute('aria-pressed', 'false'); });
        btn.setAttribute('aria-pressed', 'true');
        map.setAttribute('data-dim', btn.value);
        box.querySelectorAll('.legend').forEach(function (l) { l.hidden = l.getAttribute('data-for') !== btn.value; });
        map.querySelectorAll('.cell').forEach(function (c) {
          c.setAttribute('aria-label', c.getAttribute('data-label-' + btn.value) || c.getAttribute('aria-label'));
        });
      });
    });
  });

  /* ── tooltip לתאים (המידע זמין גם כ-aria-label וגם בטבלה שבדף) ── */
  var tip = document.createElement('div');
  tip.className = 'tooltip'; tip.hidden = true; tip.setAttribute('aria-hidden', 'true');
  document.body.appendChild(tip);
  function show(e) {
    var c = e.target.closest('.cell');
    if (!c) return;
    tip.textContent = c.getAttribute('aria-label');
    tip.hidden = false;
    var r = c.getBoundingClientRect();
    var x = Math.min(window.innerWidth - tip.offsetWidth - 8, Math.max(8, r.left + r.width / 2 - tip.offsetWidth / 2));
    var y = r.top - tip.offsetHeight - 8;
    if (y < 8) y = r.bottom + 8;
    tip.style.left = x + 'px'; tip.style.top = y + 'px';
  }
  function hide() { tip.hidden = true; }
  document.addEventListener('mouseover', show);
  document.addEventListener('focusin', show);
  document.addEventListener('mouseout', function (e) { if (e.target.closest('.cell')) hide(); });
  document.addEventListener('focusout', hide);
  window.addEventListener('scroll', hide, { passive: true });
})();
