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

# 各章开头的碑文题记：作者暂定不在网页上显示（2026-11-09）。正文 Markdown 中保留不动，
# 日后要显示，把这里改成 True 再重新生成即可。
SHOW_EPIGRAPH = False
# 章末"附注"（人名对照、史实说明等）：网页不显示，保证阅读连贯；正文 Markdown 保留（2026-11-09）。
SHOW_CHAPTER_NOTES = False

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
    chars = len(re.findall(r"[\u4e00-\u9fff]", re.sub(r"!\[[^\]]*\]\([^)]*\)", "", body)))
    return dict(part=part, vol=vol, title=title, body=body, version=version, chars=chars)


import hashlib
ASSET_V = hashlib.md5((Path(__file__).parent / "site" / "style.css").read_bytes() + (Path(__file__).parent / "site" / "app.js").read_bytes()).hexdigest()[:8]


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
<link rel="stylesheet" href="style.css?v={ASSET_V}">
<link rel="icon" href="img/icon.png">
{extra_head}
</head>
<body class="{body_class}">
<script>try{{if(localStorage.getItem('jing-dark')==='1')document.body.classList.add('dark');var fs=localStorage.getItem('jing-fs');if(fs)document.documentElement.style.setProperty('--fs',fs+'px');}}catch(e){{}}</script>
{content}
<script src="app.js?v={ASSET_V}"></script>
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
        elif num >= "067":
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
    fig_src = ROOT / "图片"
    if fig_src.exists():
        (OUT / "img" / "fig").mkdir(parents=True, exist_ok=True)
        for p in fig_src.iterdir():
            if p.is_file():
                shutil.copy(p, OUT / "img" / "fig" / p.name)
    trailer = ROOT / "预告片" / "景_预告片.mp4"
    if trailer.exists():
        shutil.copy(trailer, OUT / "trailer.mp4")

    md = markdown.Markdown(extensions=["extra"])
    total = sum(c["chars"] for c in chapters)
    n_app = sum(1 for c in chapters if "090" <= c["num"] <= "098")
    app_cn = "零一二三四五六七八九"[n_app]

    # 章节页
    for i, c in enumerate(chapters):
        md.reset()
        body_html = md.convert(c["body"])
        if not SHOW_EPIGRAPH:
            body_html = re.sub(r"\A\s*<blockquote>.*?</blockquote>\s*", "", body_html, count=1, flags=re.S)
        if not SHOW_CHAPTER_NOTES:
            body_html = re.sub(r"<hr\s*/?>\s*<p>附注[：:].*\Z", "", body_html, flags=re.S)
        body_html = body_html.replace('src="../图片/', 'src="img/fig/')
        body_html = re.sub(r'<p><img alt="([^"]*)" src="([^"]+)" ?/?></p>',
                           r'<figure class="fig"><a href="\2" target="_blank"><img src="\2" alt="\1" loading="lazy"></a><figcaption>\1</figcaption></figure>',
                           body_html)
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
  <span class="tools"><button id="tts-btn" title="朗读本章" hidden>▶ 朗读</button><button data-act="smaller" title="字号减小">A−</button><button data-act="bigger" title="字号加大">A＋</button><button data-act="dark" title="日间/夜间">◐</button></span>
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
<div id="tts-bar" class="tts-bar" hidden>
  <button data-tts="prev" title="上一段">⏮</button>
  <button data-tts="toggle" class="tts-main" title="播放/暂停">❚❚</button>
  <button data-tts="next" title="下一段">⏭</button>
  <button data-tts="stop" title="停止">■</button>
  <label>语速<select data-tts="rate"><option value="0.8">0.8×</option><option value="1" selected>1.0×</option><option value="1.2">1.2×</option><option value="1.5">1.5×</option><option value="1.8">1.8×</option></select></label>
  <label class="tts-voice">声音<select data-tts="voice"></select></label>
  <label class="tts-auto"><input type="checkbox" data-tts="auto" checked>读完自动下一章</label>
  <span class="tts-tip">朗读时点任一段落，可从该段读起</span>
</div>
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
    apps, tails = [], []
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
            (apps if "090" <= c["num"] <= "098" else tails).append(c)
            continue
        li = f'<li><a href="{c["slug"]}">{html.escape(c["title"])}</a><span class="n">{c["chars"]:,}</span></li>'
        if open_vol:
            toc.append(li)
        else:
            toc.append(f'<ol class="toc-single">{li}</ol>')
    if open_vol:
        toc.append("</ol></section>")
    if tails or apps:
        toc.append('<div class="toc-gap"></div><div class="toc-extra">')
        if tails:
            toc.append('<section class="toc-vol toc-tail"><h3>尾声　后记</h3><ol>')
            for c in tails:
                toc.append(f'<li><a href="{c["slug"]}">{html.escape(c["title"])}</a><span class="n">{c["chars"]:,}</span></li>')
            toc.append("</ol></section>")
        if apps:
            toc.append('<section class="toc-vol toc-app"><h3>附　录</h3><ol>')
            for c in apps:
                lab, _, rest = c["title"].partition("　")
                toc.append(f'<li><a href="{c["slug"]}"><b>{html.escape(lab)}</b><span class="t">{html.escape(rest or lab)}</span></a><span class="n">{c["chars"]:,}</span></li>')
            toc.append("</ol></section>")
        toc.append("</div>")

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
      <p class="blurb">大明天启三年，西安城外挖出一块唐碑，碑面上还粘着烂透了的麻布。西洋神父读了碑文，认定碑上的人是自己的弟兄，却不知道这些人早被西方教会定为异端。碑上刻得下一千七百多个字，刻不下字背后的人：一个替郭子仪看路的僧人，一个翻经立碑的儿子，一个亲手埋碑的徒孙。</p>
      <p class="stat">三部　十二卷　六十六章　另有序章、尾声、后记、附录{app_cn}篇　·　约 {total/10000:.1f} 万字</p>
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
