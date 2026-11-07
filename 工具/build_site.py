#!/usr/bin/env python3
"""从 正文/*.md 生成 GitHub Pages 阅读网站，输出到 docs/。

用法：在仓库根目录运行  python3 工具/build_site.py
每次改动正文后重新运行一次，再提交 docs/。
"""
import html
import json
import re
import shutil
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "正文"
OUT = ROOT / "docs"
IMG_SRC = ROOT / "封面"

def parse(path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    part = vol = title = None
    body_start = 0
    for i, ln in enumerate(lines):
        if ln.startswith("# ") or ln.startswith("## "):
            h = ln.lstrip("#").strip()
            if re.match(r"第.部", h):
                part = h
            elif re.match(r"第.+卷", h) and ln.startswith("# "):
                vol = h
            else:
                title = h
            body_start = i + 1
        elif ln.strip():
            break
    body = "\n".join(lines[body_start:])
    m = re.search(r"\n---\s*\n\s*\*\*版本\*\*(.+)$", body, re.S)
    version = ""
    if m:
        version = re.sub(r"\*\*(.+?)\*\*", r"\1", "版本" + m.group(1)).strip()
        body = body[: m.start()]
    chars = len(re.findall(r"[一-鿿]", body))
    return dict(part=part, vol=vol, title=title, body=body, version=version, chars=chars)


def page(title, content, extra_head="", body_class=""):
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Ma+Shan+Zheng&family=Noto+Serif+SC:wght@400;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="style.css">
<link rel="icon" href="img/icon.png">
{extra_head}
</head>
<body class="{body_class}">
<script>try{{if(localStorage.getItem('jing-dark')==='1')document.body.classList.add('dark');var fs=localStorage.getItem('jing-fs');if(fs)document.documentElement.style.setProperty('--fs',fs+'px');}}catch(e){{}}</script>
{content}
<script src="app.js"></script>
</body>
</html>
"""


def main():
    files = sorted(SRC.glob("*.md"))
    chapters = []
    cur_part = cur_vol = None
    for f in files:
        d = parse(f)
        if d["part"]:
            cur_part = d["part"]
        if d["vol"]:
            cur_vol = d["vol"]
        num = f.name[:3]
        d["slug"] = f"{num}.html"
        d["num"] = num
        if num == "000":
            d["group_part"], d["group_vol"] = None, None
        elif num in ("067", "099"):
            d["group_part"], d["group_vol"] = None, None
        else:
            d["group_part"], d["group_vol"] = cur_part, cur_vol
        chapters.append(d)

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "img").mkdir(parents=True)
    for p in IMG_SRC.glob("*.jpg"):
        shutil.copy(p, OUT / "img" / p.name)
    shutil.copy(IMG_SRC / "icon.png", OUT / "img" / "icon.png")
    shutil.copy(Path(__file__).parent / "site" / "style.css", OUT / "style.css")
    shutil.copy(Path(__file__).parent / "site" / "app.js", OUT / "app.js")
    (OUT / ".nojekyll").write_text("")
    trailer = ROOT / "预告片" / "景_预告片.mp4"
    if trailer.exists():
        shutil.copy(trailer, OUT / "trailer.mp4")

    md = markdown.Markdown(extensions=["extra"])
    total = sum(c["chars"] for c in chapters)

    # 章节页
    for i, c in enumerate(chapters):
        md.reset()
        body_html = md.convert(c["body"])
        prev_c = chapters[i - 1] if i > 0 else None
        next_c = chapters[i + 1] if i + 1 < len(chapters) else None
        crumbs = " · ".join(x for x in (c["group_part"], c["group_vol"]) if x)
        nav = '<nav class="pn">'
        nav += f'<a href="{prev_c["slug"]}" rel="prev">← {html.escape(prev_c["title"])}</a>' if prev_c else "<span></span>"
        nav += '<a href="index.html#toc" class="up">目录</a>'
        nav += f'<a href="{next_c["slug"]}" rel="next">{html.escape(next_c["title"])} →</a>' if next_c else "<span></span>"
        nav += "</nav>"
        head_part = ""
        if c["part"]:
            head_part = f'<div class="part-title">{html.escape(c["part"])}</div>'
        content = f"""
<header class="bar">
  <a href="index.html" class="brand">景</a>
  <span class="crumb">{html.escape(crumbs)}</span>
  <span class="tools"><button data-act="smaller" title="字号减小">A−</button><button data-act="bigger" title="字号加大">A＋</button><button data-act="dark" title="日间/夜间">◐</button></span>
</header>
<main class="reader" data-slug="{c['slug']}" data-title="{html.escape(c['title'])}">
  {head_part}
  {f'<div class="vol-title">{html.escape(c["vol"])}</div>' if c['vol'] else ''}
  <h1>{html.escape(c['title'])}</h1>
  <article>
{body_html}
  </article>
  <p class="ver">{html.escape(c['version'])}　·　本章约 {c['chars']:,} 字</p>
  {nav}
</main>
"""
        extra = ""
        if prev_c:
            extra += f'<link rel="prev" href="{prev_c["slug"]}">'
        if next_c:
            extra += f'<link rel="next" href="{next_c["slug"]}">'
        (OUT / c["slug"]).write_text(page(f"{c['title']}｜景", content, extra), encoding="utf-8")

    # 目录
    toc = []
    last_part = last_vol = None
    part_vols = {"第一部": "Vol1", "第二部": "Vol2", "第三部": "Vol3"}
    open_vol = False
    for c in chapters:
        if c["group_part"] != last_part and c["group_part"]:
            if open_vol:
                toc.append("</ol></section>")
                open_vol = False
            pid = "p" + str(list(part_vols).index(c["group_part"][:3]) + 1)
            toc.append(f'<h2 class="toc-part" id="{pid}">{html.escape(c["group_part"])}</h2>')
            last_part = c["group_part"]
        if c["group_vol"] != last_vol:
            if open_vol:
                toc.append("</ol></section>")
                open_vol = False
            if c["group_vol"]:
                toc.append(f'<section class="toc-vol"><h3>{html.escape(c["group_vol"])}</h3><ol>')
                open_vol = True
            last_vol = c["group_vol"]
        if not c["group_vol"] and c["num"] != "000":
            if last_part is not None:
                last_part = None
                toc.append('<div class="toc-gap"></div>')
        li = f'<li><a href="{c["slug"]}">{html.escape(c["title"])}</a><span class="n">{c["chars"]:,}</span></li>'
        if open_vol:
            toc.append(li)
        else:
            toc.append(f'<ol class="toc-single">{li}</ol>')
    if open_vol:
        toc.append("</ol></section>")

    index = f"""
<header class="bar">
  <a href="index.html" class="brand">景</a>
  <span class="crumb">长篇小说　第一稿</span>
  <span class="tools"><a href="gallery.html">封面</a><button data-act="dark" title="日间/夜间">◐</button></span>
</header>
<main class="home">
  <section class="hero">
    <img src="img/Main.jpg" alt="《景》封面" class="cover-main">
    <div class="hero-text">
      <h1 class="big">景</h1>
      <p class="by">老铁　CLAUDE　著</p>
      <p class="blurb">天宝十四载，安禄山起兵范阳。吐火罗人伊斯，长安大秦寺的一名僧人，在黄河边的一个小镇上被郭子仪收在帐下。他不领兵，不冲阵，只替郭公看路。从这一声开始，三代景教僧人在大唐的刀兵、译场与禁令之间，守着门口那盏灯，一直守到会昌。</p>
      <p class="stat">三部　十三卷　六十六章　另有序章、尾声、后记　·　约 {total/10000:.1f} 万字</p>
      <p class="cta"><a href="000.html" class="btn">从序章读起</a><a href="#" class="btn ghost" id="resume" hidden>继续上次阅读</a></p>
    </div>
  </section>
  <section class="trailer">
    <video src="trailer.mp4" poster="img/Mockup.jpg" controls preload="none" playsinline></video>
    <p>预告片　32 秒</p>
  </section>
  <section class="vols">
    <a href="#p1"><img src="img/Vol1.jpg" alt="第一卷"><span>第一部　阿罗诃</span></a>
    <a href="#p2"><img src="img/Vol2.jpg" alt="第二卷"><span>第二部　弥施诃</span></a>
    <a href="#p3"><img src="img/Vol3.jpg" alt="第三卷"><span>第三部　净风王</span></a>
  </section>
  <section class="toc" id="toc">
    <h2 class="toc-head">目　录</h2>
    {''.join(toc)}
  </section>
  <section class="mock">
    <img src="img/Mockup.jpg" alt="三卷本合集">
  </section>
  <footer class="foot">第一稿 · 文字与版本记录见 <a href="https://github.com/ny83427/jing">GitHub 仓库</a></footer>
</main>
"""
    (OUT / "index.html").write_text(page("景｜老铁 CLAUDE 著", index), encoding="utf-8")

    gallery_items = [
        ("Main", "总封面"), ("Vol1", "第一卷封面　阿罗诃"), ("Vol2", "第二卷封面　弥施诃"),
        ("Vol3", "第三卷封面　净风王"), ("Back1", "第一卷封底"), ("Back2", "第二卷封底"),
        ("Back3", "第三卷封底"), ("Mockup", "三卷本合集"),
    ]
    g = "".join(
        f'<figure class="{"wide" if k=="Mockup" else ""}"><a href="img/{k}.jpg"><img src="img/{k}.jpg" alt="{t}" loading="lazy"></a><figcaption>{t}</figcaption></figure>'
        for k, t in gallery_items
    )
    gallery = f"""
<header class="bar">
  <a href="index.html" class="brand">景</a>
  <span class="crumb">封面与封底</span>
  <span class="tools"><a href="index.html#toc">目录</a><button data-act="dark" title="日间/夜间">◐</button></span>
</header>
<main class="gallery">{g}</main>
"""
    (OUT / "gallery.html").write_text(page("封面｜景", gallery), encoding="utf-8")
    print(f"生成 {len(chapters)} 个章节页，共 {total:,} 字")


if __name__ == "__main__":
    main()
