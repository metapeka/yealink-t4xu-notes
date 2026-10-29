#!/usr/bin/env python3
"""Build the static site: Markdown -> HTML pages with a shared sidebar.

Run from the repository root:  python build.py
Sources: src/overview.md and docs/*.md (copied from the project with redaction).
Output: index.html + one page per document + assets/style.css
"""
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
    ("FINDINGS", "findings.html", "FINDINGS", "что установлено: факт / гипотеза"),
    ("BRANCHES", "branches.html", "BRANCHES", "ветки и памятка по аппарату"),
    ("PLAN", "plan.html", "PLAN", "порядок работ и гейты"),
    ("TOOLS", "tools.html", "TOOLS", "инструменты и проверки"),
    ("BRANCH_D", "branch-d.html", "BRANCH_D", "проект подмены rfs"),
    ("INSTRUCTION_DUMP", "instruction.html", "INSTRUCTION_DUMP", "инструкция для человека"),
    ("USB_MASKROM", "usb.html", "USB и maskrom", "как определить пины, дамп без паяльника"),
]

REDACT = [
    (r"24:9A:D8:25:3D:63", "24:9A:D8:**:**:**"),
    (r"202201061525", "2022********"),
    (r"2208SN058334", "2208SN******"),
    (r"310120200003-2209002", "*********-*******"),
]

CSS = """
:root{--bg:#0f1115;--fg:#e6e6e6;--muted:#9aa0a6;--card:#171a21;--line:#2a2f3a;--accent:#7aa2f7;--ok:#3ddc97;--warn:#ffb020;--bad:#ff5c5c}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.65 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;display:flex;min-height:100vh}
a{color:var(--accent)}
.sidebar{width:280px;flex:0 0 280px;border-right:1px solid var(--line);padding:24px 20px;position:sticky;top:0;height:100vh;overflow-y:auto;background:#0c0e12}
.brand{font-weight:700;font-size:16px;margin:0 0 4px}
.brand span{display:block;font-weight:400;font-size:12px;color:var(--muted);margin-top:4px}
.sidebar h4{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:24px 0 8px}
.sidebar ul{list-style:none;margin:0;padding:0}
.sidebar li{margin:2px 0}
.sidebar a{display:block;text-decoration:none;color:var(--muted);padding:6px 8px;border-radius:6px;font-size:14px}
.sidebar a:hover{color:var(--fg);background:#151922}
.sidebar a.active{color:var(--fg);background:#1b2130;box-shadow:inset 2px 0 0 var(--accent)}
.sidebar a small{display:block;font-size:11px;color:#6b7280;margin-top:1px}
.toc a{font-size:13px;padding:3px 8px}
.toc ul ul a{padding-left:20px}
main{flex:1;min-width:0;padding:40px 48px 96px;max-width:900px}
h1{font-size:30px;margin:0 0 16px;line-height:1.25}
h2{font-size:21px;margin:40px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--line)}
h3{font-size:16px;margin:24px 0 8px;color:#cfd6e4}
p,li{color:#dfe3ea}
table{width:100%;border-collapse:collapse;margin:14px 0;font-size:14px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.04em}
code{background:#11141a;border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:13.5px}
pre{background:#11141a;border:1px solid var(--line);border-radius:8px;padding:14px;overflow:auto;font-size:13.5px}
pre code{border:0;padding:0;background:none}
blockquote{margin:14px 0;padding:10px 16px;border-left:3px solid var(--warn);background:#1a1710;border-radius:0 8px 8px 0;color:#f0e2c4}
img{max-width:100%;border-radius:10px;border:1px solid var(--line);display:block;margin:18px 0 6px}
em{color:var(--muted)}
hr{border:0;border-top:1px solid var(--line);margin:32px 0}
footer{margin-top:56px;padding-top:16px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}
.mdlink{font-size:13px;color:var(--muted)}
@media(max-width:860px){
  body{flex-direction:column}
  .sidebar{position:static;width:auto;flex:none;height:auto;border-right:0;border-bottom:1px solid var(--line)}
  .sidebar ul{display:flex;flex-wrap:wrap;gap:6px}
  .sidebar a{padding:6px 10px}
  .sidebar a small{display:none}
  .toc{display:none}
  main{padding:24px}
}
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Yealink T4xU</title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<aside class="sidebar">
  <div class="brand">Yealink T4xU<span>разбор прошивки · T43U · 108.86.14.4</span></div>
  <h4>Разделы</h4>
  <ul>{nav}</ul>
  {tocblock}
</aside>
<main>
{body}
<footer>
<p class="mdlink">Исходник этой страницы: <a href="docs/{md}">docs/{md}</a> · <a href="https://github.com/metapeka/yealink-t4xu-notes">репозиторий</a></p>
</footer>
</main>
</body>
</html>
"""


def redact(text):
    for pat, repl in REDACT:
        text = re.sub(pat, repl, text)
    return text


def build_nav(active):
    items = []
    for key, page, title, desc in PAGES:
        cls = ' class="active"' if page == active else ""
        items.append(f'<li><a{cls} href="{page}">{title}<small>{desc}</small></a></li>')
    return "\n    ".join(items)


def render(md_text, md_name, active_page, title):
    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc"], extension_configs={"toc": {"toc_depth": "2-2"}})
    body = md.convert(md_text)
    toc_html = md.toc or ""
    tocblock = f'<h4>На странице</h4>\n  {toc_html}' if len(toc_html) > 80 else ""
    return TEMPLATE.format(
        title=title,
        nav=build_nav(active_page),
        tocblock=tocblock,
        body=body,
        md=md_name,
    )


def main():
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "assets" / "style.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    DOCS_OUT.mkdir(exist_ok=True)

    # 1. copy project docs into docs/ with redaction
    for key, page, title, desc in PAGES:
        if key == "overview":
            continue
        src = PROJECT / f"{key}.md"
        if not src.exists():
            print("missing source:", src)
            continue
        DOCS_OUT.joinpath(f"{key}.md").write_text(redact(src.read_text(encoding="utf-8")), encoding="utf-8")

    # 2. overview source lives in src/
    overview = redact((SRC / "overview.md").read_text(encoding="utf-8"))
    DOCS_OUT.joinpath("overview.md").write_text(overview, encoding="utf-8")

    # 3. render every page
    for key, page, title, desc in PAGES:
        md_path = DOCS_OUT / f"{key}.md"
        text = md_path.read_text(encoding="utf-8")
        html = render(text, md_path.name, page, title)
        (ROOT / page).write_text(html, encoding="utf-8")
        print(f"{page:18} <- docs/{md_path.name}  {len(html)} bytes")


if __name__ == "__main__":
    main()
