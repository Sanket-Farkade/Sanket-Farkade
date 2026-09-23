#!/usr/bin/env python3
"""
K-means over my contribution graph (animated SVG).

1. Start: the normal contribution calendar (1 square = 1 day).
2. Project: every day flies into a 2-D feature space
            x = time, y = log(1 + contributions).
3. Cluster: Lloyd's algorithm runs live with k-means++ init. Centroids move,
            points get reassigned, until the assignments stop changing.
4. Map back: days fly back onto the calendar, coloured by their cluster.

Usage:
  python kmeans_graph.py --user USERNAME --theme dark --out dist/kmeans-dark.svg
  python kmeans_graph.py --demo --theme dark --out demo.svg
"""
import argparse, datetime as dt, math, os, random, sys
from gossip_graph import fetch, demo_data, THEMES

CYCLE = 18
K = 4
PALETTE = {"dark": ["#58a6ff", "#3fb950", "#bc8cff", "#f778ba"],
           "light": ["#0969da", "#1a7f37", "#8250df", "#d63384"]}
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
# timeline, in % of the cycle
G_END, S_IN, IT0, IT1, BACK0, BACK1, HOLD = 6, 14, 18, 66, 74, 84, 94


def d2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def kmeans(pts, k, rng, max_iter=10):
    """Lloyd's algorithm with k-means++ init. Returns [(centroids, assignment, inertia), ...]."""
    cents = [rng.choice(pts)]
    while len(cents) < k:
        d = [min(d2(p, c) for c in cents) for p in pts]
        s = sum(d)
        if s == 0:
            cents.append(rng.choice(pts))
            continue
        r, acc = rng.random() * s, 0.0
        for p, di in zip(pts, d):
            acc += di
            if acc >= r:
                cents.append(p)
                break
        else:
            cents.append(pts[-1])
    hist, assign = [], None
    for _ in range(max_iter):
        new = [min(range(k), key=lambda j: d2(p, cents[j])) for p in pts]
        hist.append((list(cents), new, sum(d2(p, cents[a]) for p, a in zip(pts, new))))
        if new == assign:
            break
        assign = new
        nc = []
        for j in range(k):
            m = [p for p, a in zip(pts, new) if a == j]
            nc.append((sum(p[0] for p in m) / len(m), sum(p[1] for p in m) / len(m)) if m else cents[j])
        cents = nc
    return hist


def f(v):
    return f"{v:.2f}"


def T(x, y, s=1):
    return f"translate({f(x)}px,{f(y)}px) scale({s})"


def window(name, a, b, extra_end=None):
    """opacity keyframes: visible from a% to b%."""
    return (f"@keyframes {name}{{0%,{f(a)}%{{opacity:0}}{f(a+.1)}%,{f(b)}%{{opacity:1}}"
            f"{f(b+.1)}%,100%{{opacity:0}}}}")


def render(cells, total, theme, seed):
    th, pal = THEMES[theme], PALETTE[theme]
    n = len(cells)
    rng = random.Random(seed)
    mx = max(c["count"] for c in cells)
    den = math.log1p(mx) or 1
    pts = [(i / max(n - 1, 1), math.log1p(c["count"]) / den) for i, c in enumerate(cells)]
    k = min(K, len(set(pts)))
    hist = kmeans(pts, k, rng)
    final = hist[-1][1]

    groups = [[i for i, a in enumerate(final) if a == j] for j in range(k)]
    avg = [sum(cells[i]["count"] for i in g) / len(g) if g else 0 for g in groups]
    order = sorted(range(k), key=lambda j: avg[j])
    color = {j: pal[r] for r, j in enumerate(order)}

    W, H = 800, 290
    pitch, size = 14, 10
    weeks = max(c["x"] for c in cells) + 1
    ox = (W - weeks * pitch) / 2
    px0, px1, py0, py1 = 48, W - 24, 62, 208
    gy0 = (py0 + py1) / 2 - 49
    jit = random.Random(1)
    gpos = [(ox + c["x"] * pitch + size / 2, gy0 + c["y"] * pitch + size / 2) for c in cells]
    sx = lambda p: px0 + p[0] * (px1 - px0)
    sy = lambda p: py1 - 4 - p[1] * (py1 - py0 - 8)
    spos = [(sx(p), sy(p) + jit.uniform(-3, 3)) for p in pts]

    steps = len(hist)
    w = (IT1 - IT0) / steps
    tm = lambda i: IT0 + i * w

    css = [f"text{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;fill:{th['text']}}}",
           f".m{{fill:{th['muted']}}}", ".p,.cg{transform-box:view-box;transform-origin:0 0}",
           ".o{opacity:0}"]
    body = []

    # axes (visible only in feature-space phase)
    css.append(f"@keyframes ax{{0%,{G_END+2}%{{opacity:0}}{S_IN}%,{BACK0}%{{opacity:1}}{BACK0+4}%,100%{{opacity:0}}}}"
               f".ax{{animation:ax {CYCLE}s infinite}}")
    ax = [f'<g class="ax o">',
          f'<line x1="{px0-10}" y1="{py1+6}" x2="{px1}" y2="{py1+6}" stroke="{th["node"]}"/>',
          f'<line x1="{px0-10}" y1="{py0}" x2="{px0-10}" y2="{py1+6}" stroke="{th["node"]}"/>',
          f'<text x="{px0-16}" y="{(py0+py1)/2}" font-size="10" class="m" text-anchor="middle" '
          f'transform="rotate(-90 {px0-16} {(py0+py1)/2})">log(1 + contributions)</text>']
    seen = set()
    for i, c in enumerate(cells):
        mth = c["date"][:7]
        if mth not in seen and c["date"][8:] <= "07":
            seen.add(mth)
            ax.append(f'<text x="{f(sx(pts[i]))}" y="{py1+20}" font-size="10" class="m">{MONTHS[int(mth[5:])-1]}</text>')
    ax.append("</g>")
    body += ax

    # points
    for i, c in enumerate(cells):
        lev = th["levels"][c["level"]]
        (gx, gy), (qx, qy) = gpos[i], spos[i]
        kf = [f"0%,{G_END}%{{transform:{T(gx,gy)};fill:{lev}}}",
              f"{S_IN}%{{transform:{T(qx,qy,.55)};fill:{th['muted']}}}"]
        prev = th["muted"]
        for s, (_, a, _) in enumerate(hist):
            col = color[a[i]]
            if col != prev:
                t = tm(s) + .5 * w
                kf.append(f"{f(t)}%{{fill:{prev}}}{f(t+.1*w)}%{{fill:{col}}}")
                prev = col
        kf.append(f"{BACK0}%{{transform:{T(qx,qy,.55)}}}{BACK1}%,{HOLD}%{{transform:{T(gx,gy)};fill:{prev}}}"
                  f"100%{{transform:{T(gx,gy)};fill:{lev}}}")
        css.append(f"@keyframes p{i}{{{''.join(kf)}}}")
        body.append(f'<rect class="p" x="-5" y="-5" width="{size}" height="{size}" rx="2" fill="{lev}" '
                    f'transform="translate({f(gx)} {f(gy)})" style="animation:p{i} {CYCLE}s ease-in-out infinite"/>')

    # centroids
    for j in range(k):
        c0 = hist[0][0][j]
        kf = [f"0%,{G_END+4}%{{opacity:0;transform:{T(sx(c0),sy(c0))}}}{S_IN+2}%{{opacity:1}}"]
        for s in range(1, steps):
            a, b = hist[s-1][0][j], hist[s][0][j]
            kf.append(f"{f(tm(s))}%{{transform:{T(sx(a),sy(a))}}}{f(tm(s)+.45*w)}%{{transform:{T(sx(b),sy(b))}}}")
        kf.append(f"{BACK0-2}%{{opacity:1}}{BACK0+1}%,100%{{opacity:0}}")
        css.append(f"@keyframes c{j}{{{''.join(kf)}}}")
        body.append(f'<g class="cg o" style="animation:c{j} {CYCLE}s ease-in-out infinite">'
                    f'<circle r="9" fill="{color[j]}" stroke="{th["bg"]}" stroke-width="3"/>'
                    f'<circle r="3" fill="{th["bg"]}"/></g>')

    # narration
    by = H - 42
    lines = [("> raw data: one node per day", 0, S_IN),
             ("> projecting days into feature space: (time, log activity)", S_IN, IT0)]
    for s, (_, _, inertia) in enumerate(hist):
        lbl = (f"> init: k-means++ seeds {k} centroids · inertia {inertia:.2f}" if s == 0 else
               f"> iteration {s}: assign → update · inertia {inertia:.2f}")
        lines.append((lbl, tm(s), tm(s + 1)))
    lines.append((f"> converged after {steps-1} iterations ✔", IT1, BACK0))
    lines.append(("> clusters mapped back onto the calendar", BACK0, HOLD))
    for i, (txt, a, b) in enumerate(lines):
        if i == 0:
            css.append(f"@keyframes l0{{0%,{f(b)}%{{opacity:1}}{f(b+.1)}%,{f(HOLD-.1)}%{{opacity:0}}{HOLD}%,100%{{opacity:1}}}}")
        else:
            css.append(window(f"l{i}", a, b))
        css.append(f".l{i}{{animation:l{i} {CYCLE}s infinite}}")
        body.append(f'<text class="l{i}{" o" if i else ""}" x="24" y="{by}" font-size="12">{txt}</text>')

    # cluster legend
    css.append(window("lg", IT1, HOLD) + f".lg{{animation:lg {CYCLE}s infinite}}")
    lg, lx = ['<g class="lg o">'], 24
    for r, j in enumerate(order):
        g = groups[j]
        if not g:
            continue
        mon = lambda d: f"{MONTHS[int(d[5:7])-1]}’{d[2:4]}"
        m0, m1 = mon(cells[g[0]]["date"]), mon(cells[g[-1]]["date"])
        span = m0 if m0 == m1 else f"{m0}–{m1}"
        lg.append(f'<circle cx="{lx+5}" cy="{H-20}" r="5" fill="{pal[r]}"/>'
                  f'<text x="{lx+15}" y="{H-16}" font-size="11" class="m">{span} · {avg[j]:.1f}/day</text>')
        lx += 190
    lg.append("</g>")
    body += lg

    head = [f'<rect width="{W}" height="{H}" rx="10" fill="{th["bg"]}"/>',
            f'<text x="24" y="26" font-size="13" font-weight="700">k-means clustering · contribution days</text>',
            f'<text x="24" y="44" font-size="11" class="m">Lloyd\'s algorithm · k={k} · k-means++ init · {n} days · {total} contributions</text>']
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">'
            f"<style>{''.join(css)}</style>" + "".join(head + body) + "</svg>")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user")
    ap.add_argument("--theme", choices=THEMES, default="dark")
    ap.add_argument("--out", required=True)
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    if a.demo:
        cells, total = demo_data()
        seed = 3
    else:
        token = os.environ.get("GITHUB_TOKEN") or sys.exit("GITHUB_TOKEN not set")
        cells, total = fetch(a.user, token)
        seed = dt.date.today().isoformat()
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(render(cells, total, a.theme, seed))
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
