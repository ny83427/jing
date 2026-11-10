"""Side-by-side (left/right) paragraph diff for Chinese manuscripts.
Usage: python3 sbsdiff.py OLD.md NEW.md OUT.html "标题" "旧版本号" "新版本号"
"""
import difflib, html, sys

old_p, new_p, out, title, va, vb = sys.argv[1:7]
A = open(old_p, encoding="utf-8").read().split("\n")
B = open(new_p, encoding="utf-8").read().split("\n")
esc = html.escape


def inline(x, y):
    m = difflib.SequenceMatcher(None, x, y, autojunk=False)
    ox = oy = ""
    for op, i1, i2, j1, j2 in m.get_opcodes():
        if op == "equal":
            ox += esc(x[i1:i2]); oy += esc(y[j1:j2])
        else:
            if i2 > i1: ox += "<del>" + esc(x[i1:i2]) + "</del>"
            if j2 > j1: oy += "<ins>" + esc(y[j1:j2]) + "</ins>"
    return ox, oy


def sim(x, y):
    return difflib.SequenceMatcher(None, x, y, autojunk=False).ratio()


rows = []  # (kind, ln_a, text_a, ln_b, text_b)
sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
ops = sm.get_opcodes()
CTX = 2
changed_a = changed_b = 0
for k, (op, i1, i2, j1, j2) in enumerate(ops):
    if op == "equal":
        n = i2 - i1
        idxs = list(range(n))
        show = set()
        if k > 0: show |= set(idxs[:CTX])
        if k < len(ops) - 1: show |= set(idxs[-CTX:])
        skipped = False
        for t in idxs:
            if t in show:
                rows.append(("ctx", i1 + t + 1, esc(A[i1 + t]), j1 + t + 1, esc(B[j1 + t])))
            elif not skipped:
                rows.append(("skip", None, "", None, "")); skipped = True
        continue
    xa = A[i1:i2]; yb = B[j1:j2]
    # greedy pairing of similar paragraphs to show them on the same row
    used = set(); pairs = []
    for a_i, xs in enumerate(xa):
        best, bj = 0.0, None
        for b_j, ys in enumerate(yb):
            if b_j in used or not xs.strip() or not ys.strip(): continue
            r = sim(xs, ys)
            if r > best: best, bj = r, b_j
        if bj is not None and best >= 0.35:
            used.add(bj); pairs.append((a_i, bj))
    pairs.sort()
    ai = bj = 0
    for (pa, pb) in pairs + [(len(xa), len(yb))]:
        if pb < bj:  # crossing pair, treat as unpaired
            continue
        while ai < pa or bj < pb:
            ta = xa[ai] if ai < pa else None
            tb = yb[bj] if bj < pb else None
            rows.append(("chg",
                         i1 + ai + 1 if ta is not None else None,
                         ("<del>" + esc(ta) + "</del>") if ta and ta.strip() else (esc(ta) if ta is not None else None),
                         j1 + bj + 1 if tb is not None else None,
                         ("<ins>" + esc(tb) + "</ins>") if tb and tb.strip() else (esc(tb) if tb is not None else None)))
            if ta is not None and ta.strip(): changed_a += 1
            if tb is not None and tb.strip(): changed_b += 1
            if ai < pa: ai += 1
            if bj < pb: bj += 1
        if pa < len(xa) and pb < len(yb):
            ox, oy = inline(xa[pa], yb[pb])
            rows.append(("chg", i1 + pa + 1, ox, j1 + pb + 1, oy))
            changed_a += 1; changed_b += 1
            ai = pa + 1; bj = pb + 1

out_rows = []
for kind, la, ta, lb, tb in rows:
    if kind == "skip":
        out_rows.append('<tr class="skip"><td colspan="4">⋯ 未改动段落已折叠 ⋯</td></tr>')
        continue
    cls_a = "" if kind == "ctx" else (" class=\"a\"" if ta is not None else " class=\"empty\"")
    cls_b = "" if kind == "ctx" else (" class=\"b\"" if tb is not None else " class=\"empty\"")
    out_rows.append(
        f'<tr><td class="n">{la or ""}</td><td{cls_a}>{ta if ta is not None else ""}</td>'
        f'<td class="n">{lb or ""}</td><td{cls_b}>{tb if tb is not None else ""}</td></tr>')

page = f"""<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} {esc(va)} ↔ {esc(vb)}</title>
<style>
body{{margin:0;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:#f6f8fa;color:#1f2328}}
header{{position:sticky;top:0;background:#fff;border-bottom:1px solid #d0d7de;padding:12px 18px;z-index:2}}
h1{{font-size:17px;margin:0 0 4px}} .sum{{font-size:13px;color:#59636e}}
table{{border-collapse:collapse;width:100%;table-layout:fixed;background:#fff}}
th{{position:sticky;top:62px;background:#eaeef2;font-size:13px;padding:6px;border-bottom:1px solid #d0d7de}}
td{{vertical-align:top;padding:4px 10px;font-size:15px;line-height:1.8;white-space:pre-wrap;word-break:break-all;border-bottom:1px solid #f0f0f0}}
td.n{{width:34px;color:#8c959f;font-size:11px;text-align:right;font-family:monospace;background:#fafbfc}}
td.a{{background:#fff5f5}} td.b{{background:#f2fff4}} td.empty{{background:#f6f8fa}}
del{{background:#ffc1bf;text-decoration:line-through;text-decoration-color:#cf222e88}}
ins{{background:#acf2bd;text-decoration:none}}
tr.skip td{{background:#ddf4ff;color:#59636e;font-size:12px;text-align:center}}
</style></head><body>
<header><h1>{esc(title)}　左：{esc(va)}　右：{esc(vb)}</h1>
<div class="sum">左栏红色为删去的字句，右栏绿色为新增的字句；同一行左右是对应的同一段。左栏改动 {changed_a} 段，右栏改动 {changed_b} 段；未改动的段落已折叠。</div></header>
<table><colgroup><col style="width:34px"><col><col style="width:34px"><col></colgroup>
<tr><th></th><th>{esc(va)}（修改前）</th><th></th><th>{esc(vb)}（修改后）</th></tr>
{''.join(out_rows)}</table></body></html>"""
open(out, "w", encoding="utf-8").write(page)
print(changed_a, changed_b)
