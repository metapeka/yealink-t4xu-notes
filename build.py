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

# name in docs/ -> (page file, sidebar title, short description, group)
# группы: "Старт" · "Состояние работ" · "Работа с аппаратом" · "Отдельное"
PAGES = [
    ("overview", "index.html", "Обзор", "статус, что сделано, что осталось", "Старт"),
    ("SAFETY", "safety.html", "Чего нельзя делать", "запреты и предупреждения при работе с платой", "Старт"),
    ("ACCESS_MAP", "access.html", "Что чем решается", "какой способ что даёт и порядок шагов", "Старт"),
    ("FINDINGS", "findings.html", "Находки", "что установлено: факт / гипотеза", "Состояние работ"),
    ("BRANCHES", "branches.html", "Ветки", "ветки и памятка по аппарату", "Состояние работ"),
    ("PLAN", "plan.html", "План", "порядок работ и гейты", "Состояние работ"),
    ("TOOLS", "tools.html", "Инструменты", "инструменты и проверки", "Состояние работ"),
    ("USB_MASKROM", "usb.html", "USB и maskrom", "как определить пины, дамп без паяльника", "Работа с аппаратом"),
    ("SNIFF", "sniff.html", "Сниффинг шины", "снять ключ с платы без выпайки", "Работа с аппаратом"),
    ("NETWORK_FLASH", "network.html", "Прошивка по сети", "веб-интерфейс трубки, без UART", "Работа с аппаратом"),
    ("RECOVERY", "recovery.html", "Восстановление", "три уровня поломки и чек-лист донора", "Работа с аппаратом"),
    ("REMOTE_ACCESS", "remote.html", "Удалённый доступ", "Tailscale: схема и два варианта", "Работа с аппаратом"),
    ("SECURITY", "security.html", "Безопасность", "изоляция, доступ, проверка после", "Работа с аппаратом"),
    ("BRANCH_D", "branch-d.html", "BRANCH_D — подмена rfs", "проект подмены rfs", "Отдельное"),
    ("INSTRUCTION_DUMP", "instruction.html", "Инструкция человеку", "инструкция для человека с аппаратом", "Отдельное"),
    ("PUBLISH", "publish.html", "Что публикуем", "что выкладываем, что нет и почему", "Отдельное"),
    ("REFERENCES", "sources.html", "Как делали другие", "Synacktiv и WHY2025: сравнение методов", "Отдельное"),
]

# порядок групп в сайдбаре
GROUPS = ["Старт", "Состояние работ", "Работа с аппаратом", "Отдельное"]

# точка-статус рядом с пунктом сайдбара: ok / warn / bad; единый источник статуса проекта
STATUS_DOT = {
    "FINDINGS": ("ok", "формат пакета и апдейтер разобраны"),
    "PLAN": ("warn", "офлайн закрыт, дальше нужен аппарат"),
    "BRANCHES": ("warn", "ждёт донор или доступ к железу"),
    "BRANCH_D": ("bad", "блокер: ключ ФС"),
}

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
.sidebar h4.grp{margin-top:0}
.sidebar h4.grp.notfirst{margin-top:22px}
.sidebar .dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;vertical-align:1px;flex:none}
.sidebar .dot.ok{background:var(--ok)} .sidebar .dot.warn{background:var(--warn)} .sidebar .dot.bad{background:var(--bad)}
.sidebar .lbl-bad{display:inline-block;font-size:10px;font-weight:700;color:var(--bad);border:1px solid var(--bad);border-radius:999px;padding:0 5px;margin-left:5px;line-height:1.5;vertical-align:1px}
/* чипы факт / гипотеза */
.chip{display:inline-block;font-size:11px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;border-radius:999px;padding:0 8px;vertical-align:1px;line-height:1.7}
.chip.fact{color:var(--ok);border:1px solid var(--ok);background:color-mix(in srgb, var(--ok) 9%, transparent)}
.chip.hypo{color:var(--warn);border:1px solid var(--warn);background:color-mix(in srgb, var(--warn) 9%, transparent)}
/* чип в начале абзаца не отрывается от текста */
p:has(> .chip:first-child){text-indent:0}
p:has(> .chip:first-child) .chip:first-child{margin-right:6px}
/* кнопка «наверх» */
#to-top{position:fixed;right:22px;bottom:22px;width:40px;height:40px;border-radius:50%;border:1px solid var(--line);background:var(--card);color:var(--muted);font-size:17px;cursor:pointer;display:none;align-items:center;justify-content:center;z-index:40;box-shadow:0 4px 14px rgba(0,0,0,.35)}
#to-top.show{display:flex}
#to-top:hover{color:var(--fg);border-color:var(--accent)}
/* полоса прогресса чтения */
#progress{position:fixed;top:0;left:0;height:2px;width:0;background:var(--accent);z-index:50;transition:width .08s linear}
/* свёрнутые датированные записи в findings */
details.logentry{border:1px solid var(--line);border-radius:10px;padding:10px 14px;margin:10px 0;background:var(--card)}
details.logentry summary{cursor:pointer;font-weight:600;font-size:14.5px;list-style:none;display:flex;align-items:center;gap:8px}
details.logentry summary::-webkit-details-marker{display:none}
details.logentry summary::before{content:"▸";color:var(--muted);transition:transform .15s}
details.logentry[open] summary::before{transform:rotate(90deg)}
details.logentry summary .date{font-size:12px;color:var(--muted);font-weight:400;margin-left:auto;white-space:nowrap}
details.logentry > *:not(summary){margin-top:10px}
.toc a{font-size:13px;padding:3px 8px}
.toc ul ul a{padding-left:20px}
main{flex:1;min-width:0;padding:40px 48px 96px;max-width:900px}
h1{font-size:30px;margin:0 0 16px;line-height:1.25}
h2{font-size:21px;margin:40px 0 12px;padding-bottom:8px;padding-left:12px;border-bottom:1px solid var(--line);box-shadow:inset 3px 0 0 var(--accent);scroll-margin-top:72px;border-radius:2px 0 0 0}
h3{font-size:16px;margin:24px 0 8px;color:var(--h3);scroll-margin-top:72px}
p,li{color:var(--text2)}
/* таблицы: карточка со скроллом на узких экранах, зебра для таблиц с шапкой */
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch;border:1px solid var(--line);border-radius:10px;margin:14px 0;background:var(--card);box-shadow:var(--shadow)}
.tw table{margin:0;border-collapse:collapse;width:100%;font-size:14px}
.tw th,.tw td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}
.tw th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em;background:var(--panel);border-bottom:1px solid var(--border)}
.tw tbody tr:last-child td{border-bottom:0}
.tw table:has(thead) tbody tr:nth-child(even) td{background:color-mix(in srgb, var(--panel) 55%, transparent)}
.tw td code{word-break:break-all;font-size:12.5px}
html[data-theme="light"] .tw table:has(thead) tbody tr:nth-child(even) td{background:var(--panel)}
table{width:100%;border-collapse:collapse;margin:14px 0;font-size:14px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
code{background:var(--code);border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:13.5px}
pre{background:var(--code);border:1px solid var(--line);border-radius:8px;padding:14px;overflow:auto;font-size:13.5px}
pre code{border:0;padding:0;background:none}
.stop{border:2px solid var(--bad);border-left-width:6px;border-radius:12px;padding:14px 18px;margin:20px 0;background:rgba(255,92,92,.08)}
.stop b{color:var(--bad)}
.stop ul{margin:8px 0 0;padding-left:20px}
.stop li{margin:5px 0}
html[data-theme="light"] .stop{background:#fff1f1}
blockquote{margin:14px 0;padding:10px 16px;border-left:3px solid var(--warn);background:var(--quote-bg);border-radius:0 8px 8px 0;color:var(--quote-fg)}
img{max-width:100%;border-radius:10px;border:1px solid var(--line);display:block;margin:18px 0 6px}
em{color:var(--muted)}
hr{border:0;border-top:1px solid var(--line);margin:32px 0}
.mermaid{background:var(--mesh);border:1px solid var(--line);border-radius:12px;padding:18px;margin:20px 0;text-align:center;overflow-x:auto}
.mermaid svg{max-width:100%;height:auto}
.fig{margin:22px 0;padding:16px 16px 10px;background:var(--mesh);border:1px solid var(--line);border-radius:12px;overflow-x:auto}
.fig svg{display:block;min-width:640px}
.fig figcaption{margin-top:10px;font-size:13px;color:var(--muted);line-height:1.5}
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
.topact{margin-left:auto;display:flex;gap:8px}
.topact button{display:flex;align-items:center;gap:6px;background:var(--card);color:var(--muted);border:1px solid var(--line);border-radius:8px;padding:7px 11px;font:inherit;font-size:13px;cursor:pointer}
.topact button:hover{color:var(--fg);border-color:var(--accent)}
/* ===== ВЕРХНЕЕ МЕНЮ (дропдауны по группам) ===== */
.topmenu{display:flex;gap:2px;margin-left:10px;align-self:stretch;align-items:stretch}
/* полный список страниц в сайдбаре — только для мобильного меню «Меню» */
.pagegroups{display:none}
.tm-item{position:relative;display:flex;align-items:center}
.tm-item>a{display:flex;align-items:center;gap:5px;font-size:13.5px;color:var(--muted);text-decoration:none;padding:6px 11px;border-radius:7px;white-space:nowrap;cursor:pointer}
.tm-item>a:hover{color:var(--fg);background:var(--hover)}
.tm-item>a i{font-style:normal;font-size:10px;transition:transform .15s}
.tm-item.open>a i{transform:rotate(180deg)}
.tm-item>a.cur{color:var(--fg);background:var(--active);box-shadow:inset 0 -2px 0 var(--accent)}
.tm-drop{position:absolute;top:100%;left:0;min-width:290px;background:var(--card);border:1px solid var(--line);border-radius:12px;box-shadow:0 14px 40px rgba(0,0,0,.45);padding:6px;display:none;z-index:60}
.tm-item.open .tm-drop{display:block}
.tm-drop a{display:block;padding:8px 11px;border-radius:8px;text-decoration:none;color:var(--fg);font-size:13.5px;line-height:1.35}
.tm-drop a:hover{background:var(--hover)}
.tm-drop a.active{background:var(--active);box-shadow:inset 2px 0 0 var(--accent)}
.tm-drop a small{display:block;font-size:11.5px;color:var(--muted);margin-top:1px}
.tm-drop .dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;vertical-align:1px}
.tm-drop .dot.ok{background:var(--ok)} .tm-drop .dot.warn{background:var(--warn)} .tm-drop .dot.bad{background:var(--bad)}
.tm-drop .lbl-bad{display:inline-block;font-size:10px;font-weight:700;color:var(--bad);border:1px solid var(--bad);border-radius:999px;padding:0 5px;margin-left:5px;line-height:1.5}
.topact .gh{display:flex;align-items:center;gap:5px;color:var(--muted);text-decoration:none;font-size:13px;border:1px solid var(--line);border-radius:8px;padding:7px 11px}
.topact .gh:hover{color:var(--fg);border-color:var(--accent)}
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
  .topbar{padding:0 12px;gap:8px}
  .topbar .brand span{display:none}
  .topmenu{display:none}
  .topact .gh{display:none}
  .topact kbd{display:none}
  .sidebar{display:none;position:static;width:auto;flex:none;height:auto;border-right:0;border-bottom:1px solid var(--line)}
  .sidebar.nav-open{display:block}
  .pagegroups{display:block}
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

  // якорь внутри свёрнутого <details> — раскрыть перед скроллом
  function openForHash() {
    var h = window.location.hash && window.location.hash.slice(1);
    if (!h) return;
    var el = document.getElementById(h);
    var d = el && el.closest ? el.closest('details.logentry') : null;
    if (d) {
      d.open = true;
      setTimeout(function () { d.scrollIntoView({ block: 'start' }); }, 30);
    }
  }
  window.addEventListener('hashchange', openForHash);
  openForHash();

  // дропдауны верхнего меню: клик открывает, клик вне — закрывает
  document.querySelectorAll('.tm-item').forEach(function (item) {
    item.querySelector(':scope > a').addEventListener('click', function (e) {
      e.preventDefault();
      var was = item.classList.contains('open');
      document.querySelectorAll('.tm-item.open').forEach(function (o) { o.classList.remove('open'); });
      if (!was) item.classList.add('open');
    });
  });
  document.addEventListener('click', function (e) {
    if (!e.target.closest('.tm-item')) {
      document.querySelectorAll('.tm-item.open').forEach(function (o) { o.classList.remove('open'); });
    }
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') document.querySelectorAll('.tm-item.open').forEach(function (o) { o.classList.remove('open'); });
  });

  // полоса прогресса чтения + кнопка «наверх»
  var bar = document.getElementById('progress');
  var top = document.getElementById('to-top');
  function onScroll() {
    var h = document.documentElement;
    var max = h.scrollHeight - h.clientHeight;
    if (bar) bar.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + '%';
    if (top) top.classList.toggle('show', h.scrollTop > 600);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
  if (top) top.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });
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
  <nav class="topmenu">{topmenu}</nav>
  <div class="topact">
    <a class="gh" href="https://github.com/metapeka/yealink-t4xu-notes" title="Репозиторий" aria-label="GitHub">⌂ GitHub</a>
    <button id="open-search" type="button" aria-label="Поиск">Поиск <kbd>Ctrl K</kbd></button>
    <button id="toggle-theme" type="button" aria-label="Тема">☾</button>
    <button class="navbtn" id="toggle-nav" type="button">Меню</button>
  </div>
</header>
<div class="shell">
<aside class="sidebar">
  <div class="pagegroups">{nav}</div>
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
<div id="progress"></div>
<button id="to-top" type="button" aria-label="Наверх">↑</button>
{mermaid}
<script src="assets/app.js?v={ver}" defer></script>
</body>
</html>
"""


def redact(text):
    for pat, repl in REDACT:
        text = re.sub(pat, repl, text)
    return text


def build_topmenu(active):
    """Верхнее меню: 4 дропдауна по группам сайдбара + важно в «Состоянии работ»."""
    parts = []
    for group in GROUPS:
        pages = [(t, p, d, k) for k, p, t, d, g in PAGES if g == group]
        # активный дропдаун — тот, где лежит текущая страница
        cur = next((p for t, p, d, k in pages if p == active), None)
        cls = ' class="cur"' if cur else ""
        label = group if group != "Состояние работ" else "Состояние"
        items = []
        for t, p, d, k in pages:
            a_cls = ' class="active"' if p == active else ""
            dot = STATUS_DOT.get(k, "")
            dot_html = f'<span class="dot {dot[0]}"></span>' if dot else ""
            warn = ' <span class="lbl-bad">!</span>' if k == "SAFETY" else ""
            items.append(f'<a{a_cls} href="{p}">{dot_html}{t}{warn}<small>{d}</small></a>')
        parts.append(
            f'<div class="tm-item{"" if cur is None else " open-cur"}"><a{cls} href="{pages[0][1]}" '
            f'aria-haspopup="true">{label} <i>▾</i></a><div class="tm-drop">{"".join(items)}</div></div>'
        )
    return "".join(parts)


def build_nav(active):
    """Сгруппированный список страниц; на десктопе скрыт CSS (.pagegroups), на мобильных — это меню «Меню»."""
    parts = []
    for gi, group in enumerate(GROUPS):
        parts.append(f'<h4 class="grp{"" if gi == 0 else " notfirst"}">{group}</h4><ul>')
        for key, page, title, desc, grp in PAGES:
            if grp != group:
                continue
            cls = ' class="active"' if page == active else ""
            dot = STATUS_DOT.get(key, "")
            dot_html = f'<span class="dot {dot[0]}"></span>' if dot else ""
            warn = ' <span class="lbl-bad">!</span>' if key == "SAFETY" else ""
            parts.append(f'<li><a{cls} href="{page}">{dot_html}{title}{warn}<small>{desc}</small></a></li>')
        parts.append("</ul>")
    return "\n    ".join(parts)


def tiles_html(active):
    parts = []
    for key, page, title, desc, group in PAGES:
        if page == active:
            continue
        parts.append(f'<a class="tile" href="{page}"><b>{title}</b><span>{desc}</span></a>')
    return '<div class="tiles">' + "".join(parts) + "</div>"


def fold_dated_sections(body):
    """Свернуть секции с датой в заголовке (2026-…) в <details class="logentry">.

    Заголовок h2 теряется из toc — в summary кладём полный текст, а в toc
    остаётся один пункт «Хронология» на весь свёрнутый блок.
    """
    parts = re.split(r'(<h2 id="[^"]+">.*?</h2>)', body, flags=re.S)
    # parts: [до, заголовок, тело, заголовок, тело, ...]
    out, cur = [], None  # cur: [heading_html, [chunks]]
    def flush():
        nonlocal cur
        if cur:
            title = re.sub(r"<[^>]+>", "", cur[0])
            m = re.search(r"\((\d{4}-\d{2}-\d{2})\)", title)
            date = m.group(1) if m else ""
            title_short = re.sub(r"\s*\(\d{4}-\d{2}-\d{2}\)", "", title)
            hid = re.search(r'id="([^"]+)"', cur[0])
            id_attr = f' id="{hid.group(1)}"' if hid else ""
            inner = "".join(cur[1])
            out.append(
                f'<details class="logentry"{id_attr}><summary>'
                f'<span>{html.escape(title_short)}</span><span class="date">{date}</span>'
                f"</summary>{inner}</details>"
            )
            cur = None
    for chunk in parts:
        if re.fullmatch(r'<h2 id="[^"]+">.*?</h2>', chunk or "", flags=re.S):
            flush()
            if re.search(r"\(\d{4}-\d{2}-\d{2}\)", chunk):
                cur = [chunk, []]  # датированная — собираем
            else:
                out.append(chunk)  # обычная — как было
        else:
            if cur is not None:
                cur[1].append(chunk)
            else:
                out.append(chunk)
    flush()
    return "".join(out)


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

    # метки факт/гипотеза/следствие/инструмент -> цветные чипы (после markdown: <strong>[факт]</strong>)
    body = body.replace("<strong>[факт]</strong>", '<span class="chip fact">факт</span>')
    body = body.replace("<strong>[гипотеза]</strong>", '<span class="chip hypo">гипотеза</span>')
    body = body.replace("<strong>[следствие]</strong>", '<span class="chip fact">следствие</span>')
    body = body.replace("<strong>[инструмент]</strong>", '<span class="chip fact">инструмент</span>')
    body = body.replace("<strong>[открыто]</strong>", '<span class="chip hypo">открыто</span>')
    body = body.replace("<strong>Вывод [факт]:</strong>", '<span class="chip fact">факт</span> <strong>Вывод:</strong>')

    # таблицы в обёртку с горизонтальным скроллом
    body = body.replace("<table>", '<div class="tw"><table>').replace("</table>", "</table></div>")

    toc_html = md.toc or ""
    tocblock = f'<h4>На странице</h4>\n  {toc_html}' if len(toc_html) > 80 else ""
    mermaid_js = MERMAID_JS if blocks else ""
    if "<!-- TILES -->" in body:
        body = body.replace("<p><!-- TILES --></p>", tiles_html(active_page)).replace("<!-- TILES -->", tiles_html(active_page))
    if "<!-- PIPELINE -->" in body:
        body = body.replace("<p><!-- PIPELINE --></p>", pipeline_html()).replace("<!-- PIPELINE -->", pipeline_html())
    if md_name == "FINDINGS.md":
        body = fold_dated_sections(body)
    return TEMPLATE.format(
        ver=ASSET_VER,
        title=title,
        topmenu=build_topmenu(active_page),
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
    for key, page, title, desc, group in PAGES:
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
    for key, page, title, desc, group in PAGES:
        md_path = DOCS_OUT / f"{key}.md"
        text = md_path.read_text(encoding="utf-8")
        page_html = render(text, md_path.name, page, title)
        (ROOT / page).write_text(page_html, encoding="utf-8")
        say(f"{page:18} <- docs/{md_path.name}  {len(page_html)} bytes")

    # 4. search index for the Ctrl+K palette
    entries = []
    for key, page, title, desc, group in PAGES:
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
