#!/usr/bin/env python3
"""Build the static site: Markdown -> HTML pages with a shared sidebar.

Run from the repository root:  python build.py
Sources: src/overview.md and docs/*.md (copied from the project with redaction).
Output: index.html + one page per document + assets/style.css
"""
import hashlib
import html
import json
import re
import shutil
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent                    # E:\0ai\yealink_t4xu
DOCS_OUT = ROOT / "docs"
SRC = ROOT / "src"

# name in docs/ -> (page file, sidebar title, short description)
PAGES = [
    ("overview", "index.html", "Обзор", "статус, что сделано, что осталось"),
    ("ACCESS_MAP", "access.html", "Что чем решается", "какой способ что даёт и порядок шагов"),
    ("FINDINGS", "findings.html", "FINDINGS", "что установлено: факт / гипотеза"),
    ("BRANCHES", "branches.html", "BRANCHES", "ветки и памятка по аппарату"),
    ("PLAN", "plan.html", "PLAN", "порядок работ и гейты"),
    ("TOOLS", "tools.html", "TOOLS", "инструменты и проверки"),
    ("BRANCH_D", "branch-d.html", "BRANCH_D", "проект подмены rfs"),
    ("INSTRUCTION_DUMP", "instruction.html", "INSTRUCTION_DUMP", "инструкция для человека"),
    ("USB_MASKROM", "usb.html", "USB и maskrom", "как определить пины, дамп без паяльника"),
    ("NETWORK_FLASH", "network.html", "Прошивка по сети", "веб-интерфейс трубки, без UART"),
    ("REMOTE_ACCESS", "remote.html", "Удалённый доступ", "Tailscale: схема и два варианта"),
    ("SECURITY", "security.html", "Безопасность", "изоляция, доступ, проверка после"),
    ("PUBLISH", "publish.html", "Что публикуем", "что выкладываем, что нет и почему"),
    ("SNIFF", "sniff.html", "Сниффинг шины", "снять ключ с платы без выпайки"),
    ("REFERENCES", "sources.html", "Как делали другие", "Synacktiv и WHY2025: сравнение методов"),
]

REDACT = [
    (r"24:9A:D8:25:3D:63", "24:9A:D8:**:**:**"),
    (r"202201061525", "2022********"),
    (r"2208SN058334", "2208SN******"),
    (r"310120200003-2209002", "*********-*******"),
]

CSS = """
:root{--bg:#0f1115;--fg:#e6e6e6;--muted:#9aa0a6;--card:#171a21;--line:#2a2f3a;--accent:#7aa2f7;--ok:#3ddc97;--warn:#ffb020;--bad:#ff5c5c;--panel:#0c0e12;--hover:#151922;--active:#1b2130;--code:#11141a;--mesh:#12151c;--text2:#dfe3ea;--h3:#cfd6e4;--quote-bg:#1a1710;--quote-fg:#f0e2c4;--shadow:none}
html[data-theme="light"]{--bg:#f7f8fb;--fg:#15181f;--muted:#5a6272;--card:#fff;--line:#dde2ea;--accent:#2563eb;--ok:#0f9d63;--warn:#b26b00;--bad:#c62828;--panel:#eef1f6;--hover:#e4e9f2;--active:#d9e3f7;--code:#f1f3f7;--mesh:#fff;--text2:#242a35;--h3:#333a47;--quote-bg:#fff7e6;--quote-fg:#6b4a00;--shadow:0 1px 2px rgba(16,24,40,.06)}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.65 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;display:block;min-height:100vh}
.shell{display:flex;min-height:calc(100vh - 57px)}
a{color:var(--accent)}
.sidebar{width:280px;flex:0 0 280px;border-right:1px solid var(--line);padding:20px;position:sticky;top:57px;height:calc(100vh - 57px);overflow-y:auto;background:var(--panel)}
.brand{font-weight:700;font-size:16px;margin:0 0 4px}
.brand span{display:block;font-weight:400;font-size:12px;color:var(--muted);margin-top:4px}
.sidebar h4{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:24px 0 8px}
.sidebar ul{list-style:none;margin:0;padding:0}
.sidebar li{margin:2px 0}
.sidebar a{display:block;text-decoration:none;color:var(--muted);padding:6px 8px;border-radius:6px;font-size:14px}
.sidebar a:hover{color:var(--fg);background:var(--hover)}
.sidebar a.active{color:var(--fg);background:var(--active);box-shadow:inset 2px 0 0 var(--accent)}
.sidebar a small{display:block;font-size:11px;color:var(--muted);margin-top:1px}
.toc a{font-size:13px;padding:3px 8px}
.toc ul ul a{padding-left:20px}
main{flex:1;min-width:0;padding:40px 48px 96px;max-width:900px}
h1{font-size:30px;margin:0 0 16px;line-height:1.25}
h2{font-size:21px;margin:40px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--line)}
h3{font-size:16px;margin:24px 0 8px;color:var(--h3)}
p,li{color:var(--text2)}
table{width:100%;border-collapse:collapse;margin:14px 0;font-size:14px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
code{background:var(--code);border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:13.5px}
pre{background:var(--code);border:1px solid var(--line);border-radius:8px;padding:14px;overflow:auto;font-size:13.5px}
pre code{border:0;padding:0;background:none}
blockquote{margin:14px 0;padding:10px 16px;border-left:3px solid var(--warn);background:var(--quote-bg);border-radius:0 8px 8px 0;color:var(--quote-fg)}
img{max-width:100%;border-radius:10px;border:1px solid var(--line);display:block;margin:18px 0 6px}
em{color:var(--muted)}
hr{border:0;border-top:1px solid var(--line);margin:32px 0}
.mermaid{background:var(--mesh);border:1px solid var(--line);border-radius:12px;padding:18px;margin:20px 0;text-align:center;overflow-x:auto}
.mermaid svg{max-width:100%;height:auto}
footer{margin-top:56px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}
.mdlink{font-size:13px;color:var(--muted)}
.pipe{display:grid;grid-template-columns:repeat(auto-fit,minmax(168px,1fr));gap:10px;margin:16px 0 0}
.stage{position:relative;background:var(--card);border:1px solid var(--line);border-top:3px solid var(--line);border-radius:10px;padding:12px 13px 13px;box-shadow:var(--shadow);display:flex;flex-direction:column;gap:5px}
.stage .num{font-size:11px;color:var(--muted);letter-spacing:.08em}
.stage b{font-size:14px;font-weight:600;color:var(--fg);line-height:1.3}
.stage .note{font-size:12px;color:var(--muted);line-height:1.45}
.stage .pill{align-self:flex-start;font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;padding:1px 7px;border-radius:999px;border:1px solid var(--line);color:var(--muted)}
.stage.done{border-top-color:var(--ok)} .stage.done .pill{color:var(--ok);border-color:var(--ok)}
.stage.now{border-top-color:var(--warn);box-shadow:0 0 0 1px var(--warn)} .stage.now .pill{color:var(--warn);border-color:var(--warn)}
.stage.blocked{border-top-color:var(--bad)} .stage.blocked .pill{color:var(--bad);border-color:var(--bad)}
.stage.current b{color:var(--warn)}
.forkline{display:flex;align-items:center;gap:12px;margin:16px 0 8px;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.06em}
.forkline::before,.forkline::after{content:"";height:1px;background:var(--line);flex:1}
.branches{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px}
.branch{display:grid;grid-template-columns:auto 1fr;gap:3px 10px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:11px 13px;text-decoration:none;color:inherit;box-shadow:var(--shadow)}
.branch:hover{border-color:var(--accent);background:var(--hover)}
.branch .lt{grid-row:span 3;width:26px;height:26px;border-radius:7px;border:1px solid var(--line);display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:650;color:var(--muted)}
.branch b{font-size:13.5px;font-weight:600;color:var(--fg);line-height:1.3}
.branch .pill{justify-self:start;font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;padding:1px 7px;border-radius:999px;border:1px solid var(--line);color:var(--muted)}
.branch .note{grid-column:2;font-size:12px;color:var(--muted);line-height:1.45}
.branch.ok .lt{border-color:var(--ok);color:var(--ok)} .branch.ok .pill{color:var(--ok);border-color:var(--ok)}
.branch.blocked .lt{border-color:var(--bad);color:var(--bad)} .branch.blocked .pill{color:var(--bad);border-color:var(--bad)}
.branch.todo .lt{border-color:var(--warn);color:var(--warn)} .branch.todo .pill{color:var(--warn);border-color:var(--warn)}
.topbar{position:sticky;top:0;z-index:30;display:flex;align-items:center;gap:14px;height:57px;padding:0 20px;background:var(--panel);border-bottom:1px solid var(--line)}
.topbar .brand{display:flex;align-items:baseline;gap:9px;text-decoration:none;color:var(--fg);font-weight:700;font-size:15px;white-space:nowrap}
.topbar .brand span{font-weight:400;font-size:11.5px;color:var(--muted)}
.topnav{display:flex;gap:2px;margin-left:6px;overflow-x:auto;scrollbar-width:none}
.topnav::-webkit-scrollbar{display:none}
.topnav a{font-size:13.5px;color:var(--muted);text-decoration:none;padding:6px 10px;border-radius:7px;white-space:nowrap}
.topnav a:hover{color:var(--fg);background:var(--hover)}
.topnav a.active{color:var(--fg);background:var(--active);box-shadow:inset 0 -2px 0 var(--accent)}
.topact{margin-left:auto;display:flex;gap:8px}
.topact button{display:flex;align-items:center;gap:6px;background:var(--card);color:var(--muted);border:1px solid var(--line);border-radius:8px;padding:7px 11px;font:inherit;font-size:13px;cursor:pointer}
.topact button:hover{color:var(--fg);border-color:var(--accent)}
.tools{display:flex;gap:8px;margin:14px 0 0}
.tools button{flex:1;display:flex;align-items:center;justify-content:center;gap:6px;background:var(--card);color:var(--muted);border:1px solid var(--line);border-radius:8px;padding:8px 10px;font-size:13px;cursor:pointer;font-family:inherit}
.tools button:hover{color:var(--fg);border-color:var(--accent)}
.tools kbd{font-family:inherit;font-size:11px;border:1px solid var(--line);border-radius:4px;padding:0 4px;color:var(--muted)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:20px 0 8px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;box-shadow:var(--shadow);text-decoration:none;color:inherit;display:block}
.card:hover{border-color:var(--accent)}
.card .k{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}
.card .v{display:block;font-size:16px;font-weight:650;margin:6px 0 2px;color:var(--fg)}
.card .s{display:block;font-size:12.5px;color:var(--muted)}
.card.ok .v{color:var(--ok)} .card.warn .v{color:var(--warn)} .card.bad .v{color:var(--bad)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px;margin:14px 0 8px}
.tile{display:block;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;text-decoration:none;color:inherit;box-shadow:var(--shadow)}
.tile:hover{border-color:var(--accent);background:var(--hover)}
.tile b{display:block;font-size:14px;font-weight:600;color:var(--fg)}
.tile span{display:block;font-size:12.5px;color:var(--muted);margin-top:3px}
.gates{list-style:none;padding:0;margin:14px 0}
.gates li{display:flex;gap:10px;align-items:baseline;padding:7px 0;border-bottom:1px solid var(--line);font-size:14.5px}
.gates li:last-child{border-bottom:0}
.gates .n{flex:0 0 22px;height:22px;border-radius:50%;border:1px solid var(--line);display:inline-flex;align-items:center;justify-content:center;font-size:12px;color:var(--muted)}
.gates li.done .n{border-color:var(--ok);color:var(--ok)}
.gates li.now .n{border-color:var(--warn);color:var(--warn)}
.gates .st{margin-left:auto;font-size:12px;color:var(--muted);white-space:nowrap}
.overlay{position:fixed;inset:0;background:rgba(6,8,12,.62);display:none;align-items:flex-start;justify-content:center;padding:12vh 16px;z-index:50}
.overlay.open{display:flex}
.palette{width:min(680px,100%);background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:0 18px 50px rgba(0,0,0,.45);overflow:hidden}
.palette input{width:100%;border:0;border-bottom:1px solid var(--line);background:var(--card);color:var(--fg);font:inherit;font-size:16px;padding:16px 18px;outline:none}
.palette ul{list-style:none;margin:0;padding:6px;max-height:52vh;overflow-y:auto}
.palette li{padding:9px 12px;border-radius:8px;cursor:pointer;font-size:14px}
.palette li.sel{background:var(--active)}
.palette li b{font-weight:600}
.palette li em{display:block;font-style:normal;font-size:12px;color:var(--muted)}
.palette .empty{padding:18px;color:var(--muted);font-size:14px;text-align:center}
.topact .navbtn{display:none}
@media(max-width:860px){
  .shell{flex-direction:column}
  .topnav{display:none}
  .topbar{padding:0 12px;gap:8px}
  .topbar .brand span{display:none}
  .topact kbd{display:none}
  .sidebar{display:none;position:static;width:auto;flex:none;height:auto;border-right:0;border-bottom:1px solid var(--line)}
  .sidebar.nav-open{display:block}
  .sidebar ul{display:flex;flex-wrap:wrap;gap:6px}
  .sidebar a{padding:6px 10px}
  .sidebar a small{display:none}
  .toc{display:none}
  main{padding:24px}
  .topact .navbtn{display:flex}
  .navbtn::after{content:"▾";margin-left:6px;font-size:10px}
  .sidebar:not(.nav-open) ul{display:none}
  .sidebar:not(.nav-open) h4{display:none}
  .sidebar:not(.nav-open) .toc{display:none}
}
"""

MERMAID_JS = """<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
const light = document.documentElement.getAttribute('data-theme') === 'light';
mermaid.initialize({ startOnLoad: true, theme: light ? 'default' : 'dark', themeVariables: { fontFamily: 'Segoe UI, sans-serif' } });
</script>"""

APP_JS = """(function () {
  var root = document.documentElement;
  var btn = document.getElementById('toggle-theme');
  function paint() {
    var dark = root.getAttribute('data-theme') !== 'light';
    btn.textContent = dark ? '\\u263E' : '\\u2600';
    btn.title = dark ? '\\u0441\\u0432\\u0435\\u0442\\u043B\\u0430\\u044F \\u0442\\u0435\\u043C\\u0430' : '\\u0442\\u0451\\u043C\\u043D\\u0430\\u044F \\u0442\\u0435\\u043C\\u0430';
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
  var VER = '__VER__';
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
          var snip = (from > 0 ? '\u2026' : '') + p.b.slice(from, at + q.length + 55).trim() + '\u2026';
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
      empty.textContent = '\\u043D\\u0438\\u0447\\u0435\\u0433\\u043E \\u043D\\u0435 \\u043D\\u0430\\u0439\\u0434\\u0435\\u043D\\u043E';
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
"""

STAGES = [
    ("1", "Формат пакета", "done", "заголовок 0x80, блоки, CRC, LZMA / cypher3"),
    ("2", "Пересборка", "done", "identity совпал: .118, .20, 86.14.4"),
    ("3", "Пакет-проба", "done", "test_108.86.14.99.rom — меняется только строка версии"),
    ("4", "Гейт 1: приём пакета", "now", "открыт по разбору; нужен донор для проверки"),
    ("5", "Гейт 2: доступ к ФС", "blocked", "ключ или свой загрузчик — два пути ниже"),
    ("6", "Своя прошивка", "todo", "правки, свои файлы, свои модули"),
]

BRANCHES = [
    ("1", "Ключ ФС (сниффинг MCU)", "todo", "шина SoC ↔ MCU: анализатор и 3–4 щупа, паять не надо"),
    ("2", "Свой загрузчик", "blocked", "убрать ubifs crypto: консоль U-Boot, дамп или maskrom"),
    ("3", "Свой version.elf", "idea", "пишет rfs своим апдейтером; имеет смысл только после пути 2"),
]

STATE_LABEL = {"done": "готово", "now": "сейчас", "blocked": "блокер", "todo": "не начато", "ok": "применимо", "idea": "идея"}


def pipeline_html():
    steps = []
    for num, title, state, note in STAGES:
        cls = f"{state}" + (" current" if state == "now" else "")
        steps.append(
            f'<div class="stage {cls}"><span class="num">{num}</span>'
            f'<b>{title}</b><span class="pill">{STATE_LABEL[state]}</span>'
            f'<span class="note">{note}</span></div>'
        )
    branches = []
    for letter, title, state, note in BRANCHES:
        branches.append(
            f'<a class="branch {state}" href="access.html"><span class="lt">{letter}</span>'
            f'<b>{title}</b><span class="pill">{STATE_LABEL[state]}</span>'
            f'<span class="note">{note}</span></a>'
        )
    return (
        '<div class="pipe">' + "".join(steps) + "</div>"
        '<div class="forkline"><span>два пути через гейт 2 — ведут к одной цели</span></div>'
        '<div class="branches">' + "".join(branches) + "</div>"
    )

def _asset_version():
    blob = (CSS + APP_JS).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()[:8]


ASSET_VER = _asset_version()

TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Yealink T4xU</title>
<link rel="stylesheet" href="assets/style.css?v={ver}">
<script>try{{var t=localStorage.getItem("theme");if(t)document.documentElement.setAttribute("data-theme",t)}}catch(e){{}}</script>
</head>
<body>
<header class="topbar">
  <a class="brand" href="index.html" title="На главную">Yealink T4xU<span>разбор прошивки · T43U · 108.86.14.4</span></a>
  <nav class="topnav">{topnav}</nav>
  <div class="topact">
    <button id="open-search" type="button" aria-label="Поиск">Поиск <kbd>Ctrl K</kbd></button>
    <button id="toggle-theme" type="button" aria-label="Тема">☾</button>
    <button class="navbtn" id="toggle-nav" type="button">Меню</button>
  </div>
</header>
<div class="shell">
<aside class="sidebar">
  <h4>Разделы</h4>
  <ul>{nav}</ul>
  {tocblock}
</aside>
<div class="overlay" id="palette-wrap">
  <div class="palette">
    <input id="palette-input" type="text" placeholder="Страница или раздел…" autocomplete="off" spellcheck="false">
    <ul id="palette-list"></ul>
  </div>
</div>
<main>
{body}
<footer>
<p class="mdlink">Исходник этой страницы: <a href="docs/{md}">docs/{md}</a> · <a href="https://github.com/metapeka/yealink-t4xu-notes">репозиторий</a></p>
</footer>
</main>
</div>
{mermaid}
<script src="assets/app.js?v={ver}" defer></script>
</body>
</html>
"""


def redact(text):
    for pat, repl in REDACT:
        text = re.sub(pat, repl, text)
    return text


TOPNAV = [
    ("index.html", "Обзор"),
    ("access.html", "Пути"),
    ("findings.html", "Находки"),
    ("branches.html", "Ветки"),
    ("plan.html", "План"),
    ("publish.html", "Публикация"),
    ("sources.html", "Источники"),
]


def build_topnav(active):
    items = []
    for page, label in TOPNAV:
        cls = ' class="active"' if page == active else ""
        items.append(f'<a{cls} href="{page}">{label}</a>')
    return "".join(items)


def build_nav(active):
    items = []
    for key, page, title, desc in PAGES:
        cls = ' class="active"' if page == active else ""
        items.append(f'<li><a{cls} href="{page}">{title}<small>{desc}</small></a></li>')
    return "\n    ".join(items)


def tiles_html(active):
    parts = []
    for key, page, title, desc in PAGES:
        if page == active:
            continue
        parts.append(f'<a class="tile" href="{page}"><b>{title}</b><span>{desc}</span></a>')
    return '<div class="tiles">' + "".join(parts) + "</div>"


def render(md_text, md_name, active_page, title):
    # pull mermaid blocks out before markdown (their syntax is not markdown-safe)
    blocks = []

    def stash(m):
        blocks.append(m.group(1))
        return f"\n\nMERMAIDBLOCK{len(blocks)-1}END\n\n"

    md_text = re.sub(r"^```mermaid\n(.*?)^```\s*$", stash, md_text, flags=re.S | re.M)

    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc"], extension_configs={"toc": {"toc_depth": "2-2"}})
    body = md.convert(md_text)

    for i, code in enumerate(blocks):
        escaped = code.replace("&", "&amp;").replace("<", "&lt;")
        body = body.replace(f"<p>MERMAIDBLOCK{i}END</p>", f'<div class="mermaid">\n{escaped}\n</div>')
        body = body.replace(f"MERMAIDBLOCK{i}END", f'<div class="mermaid">\n{escaped}\n</div>')

    toc_html = md.toc or ""
    tocblock = f'<h4>На странице</h4>\n  {toc_html}' if len(toc_html) > 80 else ""
    mermaid_js = MERMAID_JS if blocks else ""
    if "<!-- TILES -->" in body:
        body = body.replace("<p><!-- TILES --></p>", tiles_html(active_page)).replace("<!-- TILES -->", tiles_html(active_page))
    if "<!-- PIPELINE -->" in body:
        body = body.replace("<p><!-- PIPELINE --></p>", pipeline_html()).replace("<!-- PIPELINE -->", pipeline_html())
    return TEMPLATE.format(
        ver=ASSET_VER,
        title=title,
        topnav=build_topnav(active_page),
        nav=build_nav(active_page),
        tocblock=tocblock,
        body=body,
        md=md_name,
        mermaid=mermaid_js,
    )


def say(msg):
    """Print without dying when stdout is a closed pipe (e.g. `| head`)."""
    try:
        print(msg, flush=True)
    except (BrokenPipeError, OSError):
        pass


def main():
    (ROOT / "assets").mkdir(exist_ok=True)
    css_text = CSS.strip() + "\n"
    js_text = APP_JS.strip().replace("__VER__", ASSET_VER) + "\n"
    (ROOT / "assets" / "style.css").write_text(css_text, encoding="utf-8")
    (ROOT / "assets" / "app.js").write_text(js_text, encoding="utf-8")
    (ROOT / "assets" / "ver.txt").write_text(ASSET_VER + "\n", encoding="utf-8")
    DOCS_OUT.mkdir(exist_ok=True)
    # 0. our own analysis scripts, published as text (no vendor binaries)
    tools_src = PROJECT / "tools"
    tools_dst = ROOT / "tools"
    if tools_src.is_dir():
        tools_dst.mkdir(exist_ok=True)
        for f in sorted(tools_src.glob("*.py")):
            shutil.copyfile(f, tools_dst / f.name)
        say(f"{'tools/':18} <- {len(list(tools_dst.glob('*.py')))} scripts")

    # 1. copy project docs into docs/ with redaction
    for key, page, title, desc in PAGES:
        if key == "overview":
            continue
        src = PROJECT / f"{key}.md"
        if not src.exists():
            say(f"missing source: {src}")
            continue
        DOCS_OUT.joinpath(f"{key}.md").write_text(redact(src.read_text(encoding="utf-8")), encoding="utf-8")

    # 2. overview source lives in src/
    overview = redact((SRC / "overview.md").read_text(encoding="utf-8"))
    DOCS_OUT.joinpath("overview.md").write_text(overview, encoding="utf-8")

    # 3. render every page
    for key, page, title, desc in PAGES:
        md_path = DOCS_OUT / f"{key}.md"
        text = md_path.read_text(encoding="utf-8")
        page_html = render(text, md_path.name, page, title)
        (ROOT / page).write_text(page_html, encoding="utf-8")
        say(f"{page:18} <- docs/{md_path.name}  {len(page_html)} bytes")

    # 4. search index for the Ctrl+K palette
    entries = []
    for key, page, title, desc in PAGES:
        html_page = (ROOT / page).read_text(encoding="utf-8")
        heads = []
        for m in re.finditer(r'<h([23]) id="([^"]+)">(.*?)</h\1>', html_page, re.S):
            text = html.unescape(re.sub(r"<[^>]+>", "", m.group(3))).strip()
            if text:
                heads.append({"a": m.group(2), "t": text})
        plain = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<pre.*?</pre>|<div class=\"mermaid\".*?</div>", " ", html_page, flags=re.S)))
        plain = re.sub(r"\s+", " ", plain).strip()[:8000]
        entries.append({"u": page, "t": title, "d": desc, "h": heads, "b": plain})
    (ROOT / "search.json").write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    say(f"{'search.json':18} <- {len(entries)} pages, {sum(len(e['h']) for e in entries)} headings")


if __name__ == "__main__":
    main()
