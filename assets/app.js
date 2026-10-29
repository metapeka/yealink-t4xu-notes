(function () {
  var root = document.documentElement;
  var btn = document.getElementById('toggle-theme');
  function paint() {
    var dark = root.getAttribute('data-theme') !== 'light';
    btn.textContent = dark ? '\u263E' : '\u2600';
    btn.title = dark ? '\u0441\u0432\u0435\u0442\u043B\u0430\u044F \u0442\u0435\u043C\u0430' : '\u0442\u0451\u043C\u043D\u0430\u044F \u0442\u0435\u043C\u0430';
  }
  try {
    var keep = sessionStorage.getItem('theme-scroll');
    if (keep !== null) {
      sessionStorage.removeItem('theme-scroll');
      window.addEventListener('load', function () { setTimeout(function () { window.scrollTo(0, parseInt(keep, 10) || 0); }, 60); });
    }
  } catch (e) {}

  var navBtn = document.getElementById('toggle-nav');
  if (navBtn) {
    navBtn.addEventListener('click', function () {
      document.querySelector('.sidebar').classList.toggle('nav-open');
    });
  }
  if (btn) {
    paint();
    btn.addEventListener('click', function () {
      var next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      try {
        sessionStorage.setItem('theme-scroll', String(window.scrollY));
        localStorage.setItem('theme', next);
      } catch (e) {}
      location.reload();
    });
  }

  var wrap = document.getElementById('palette-wrap');
  var input = document.getElementById('palette-input');
  var list = document.getElementById('palette-list');
  var VER = 'af3202f9';
  var data = null, items = [], sel = 0;

  function load() {
    if (data) return;
    data = [];
    fetch('search.json?v=' + VER).then(function (r) { return r.json(); }).then(function (j) { data = j; render(input.value); }).catch(function () {});
  }
  function openPalette() {
    load();
    wrap.classList.add('open');
    input.value = '';
    render('');
    setTimeout(function () { input.focus(); }, 0);
  }
  function closePalette() { wrap.classList.remove('open'); }
  function paintSel() {
    var kids = list.children;
    for (var i = 0; i < kids.length; i++) kids[i].classList.toggle('sel', i === sel);
  }
  function go(it) {
    if (!it) return;
    closePalette();
    location.href = it.u;
  }
  function render(q) {
    q = (q || '').trim().toLowerCase();
    items = [];
    (data || []).forEach(function (p) {
      var hit = !q || p.t.toLowerCase().indexOf(q) >= 0 || p.d.toLowerCase().indexOf(q) >= 0;
      if (hit) items.push({ u: p.u, t: p.t, s: p.d });
      (p.h || []).forEach(function (h) {
        if (q && h.t.toLowerCase().indexOf(q) >= 0) items.push({ u: p.u + '#' + h.a, t: h.t, s: p.t });
      });
      if (q && !hit && p.b) {
        var at = p.b.toLowerCase().indexOf(q);
        if (at >= 0) {
          var from = Math.max(0, at - 45);
          var snip = (from > 0 ? '…' : '') + p.b.slice(from, at + q.length + 55).trim() + '…';
          items.push({ u: p.u, t: p.t, s: snip });
        }
      }
    });
    items = items.slice(0, 40);
    sel = 0;
    list.innerHTML = '';
    if (!items.length) {
      var empty = document.createElement('li');
      empty.className = 'empty';
      empty.textContent = '\u043D\u0438\u0447\u0435\u0433\u043E \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D\u043E';
      list.appendChild(empty);
      return;
    }
    items.forEach(function (it) {
      var li = document.createElement('li');
      var b = document.createElement('b');
      var em = document.createElement('em');
      b.textContent = it.t;
      em.textContent = it.s;
      li.appendChild(b);
      li.appendChild(em);
      li.addEventListener('click', function () { go(it); });
      list.appendChild(li);
    });
    paintSel();
  }
  if (wrap && input && list) {
    document.getElementById('open-search').addEventListener('click', openPalette);
    wrap.addEventListener('click', function (e) { if (e.target === wrap) closePalette(); });
    input.addEventListener('input', function () { render(input.value); });
    document.addEventListener('keydown', function (e) {
      if ((e.ctrlKey || e.metaKey) && String(e.key).toLowerCase() === 'k') {
        e.preventDefault();
        openPalette();
        return;
      }
      if (!wrap.classList.contains('open')) {
        if (e.key === 'Escape') closePalette();
        return;
      }
      if (e.key === 'Escape') { closePalette(); }
      else if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(sel + 1, items.length - 1); paintSel(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(sel - 1, 0); paintSel(); }
      else if (e.key === 'Enter') { e.preventDefault(); go(items[sel]); }
    });
  }
})();
