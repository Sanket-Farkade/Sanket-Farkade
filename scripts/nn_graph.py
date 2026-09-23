#!/usr/bin/env python3
"""
Neural network trained on my own contributions (animated SVG).

A tiny MLP (6 -> 8 -> 4 -> 1, tanh) is trained from scratch in pure Python
with backprop + SGD, learning to predict a week's contributions from the
6 weeks before it. The animation shows:
  1. Training: the loss curve draws itself while edge weights grow from
     their random init to their trained values (blue = +, pink = -).
  2. Forward pass: my last 6 complete weeks feed in, signals pulse through
     each layer, neurons light up by activation.
  3. Output: the network's forecast for this week, next to the real count so far.

Usage:
  python nn_graph.py --user USERNAME --theme dark --out dist/nn-dark.svg
  python nn_graph.py --demo --theme dark --out demo.svg
"""
import argparse, copy, datetime as dt, math, os, random, sys
from gossip_graph import fetch, demo_data, THEMES

CYCLE = 14
WIN = 6
ARCH = [WIN, 8, 4, 1]
EPOCHS = 1500
LR = 0.03
PULSE = {"dark": "#e3b341", "light": "#9a6700"}
TRAIN_END = 34
LAYER_ON = [36, 48, 60, 71]                     # when each layer lights up
EDGE_WIN = [(37, 47), (49, 59), (61, 70)]       # when signals travel each weight layer
FADE0, FADE1 = 92, 97


class MLP:
    def __init__(self, arch, rng):
        self.W = [[[rng.gauss(0, 1 / math.sqrt(arch[l])) for _ in range(arch[l])]
                   for _ in range(arch[l + 1])] for l in range(len(arch) - 1)]
        self.b = [[0.0] * arch[l + 1] for l in range(len(arch) - 1)]

    def forward(self, x):
        acts = [x]
        for l, (W, b) in enumerate(zip(self.W, self.b)):
            z = [sum(w * a for w, a in zip(row, acts[-1])) + bj for row, bj in zip(W, b)]
            acts.append(z if l == len(self.W) - 1 else [math.tanh(v) for v in z])
        return acts

    def step(self, x, y, lr):
        acts = self.forward(x)
        delta = [acts[-1][0] - y]
        for l in range(len(self.W) - 1, -1, -1):
            prev = acts[l]
            nd = None
            if l > 0:
                nd = [sum(self.W[l][j][i] * delta[j] for j in range(len(delta))) * (1 - prev[i] ** 2)
                      for i in range(len(prev))]
            for j in range(len(delta)):
                for i in range(len(prev)):
                    self.W[l][j][i] -= lr * delta[j] * prev[i]
                self.b[l][j] -= lr * delta[j]
            delta = nd
        return (acts[-1][0] - y) ** 2


def weekly(cells):
    wk = {}
    for c in cells:
        wk[c["x"]] = wk.get(c["x"], 0) + c["count"]
    return [wk[i] for i in sorted(wk)]


def f(v):
    return f"{v:.2f}"


def render(cells, theme, seed):
    th = THEMES[theme]
    pos, neg, pulse = th["levels"][3], th["flash"], PULSE[theme]
    weeks = weekly(cells)
    complete, this_week = weeks[:-1], weeks[-1]
    den = math.log1p(max(complete) if complete and max(complete) > 0 else 1)
    norm = lambda v: math.log1p(v) / den

    rng = random.Random(seed)
    net = MLP(ARCH, rng)
    W_init = copy.deepcopy(net.W)
    data = [([norm(v) for v in complete[t - WIN:t]], norm(complete[t])) for t in range(WIN, len(complete))]
    losses = []
    for _ in range(EPOCHS if data else 1):
        rng.shuffle(data)
        losses.append(sum(net.step(x, y, LR) for x, y in data) / len(data) if data else 0.0)

    last = complete[-WIN:]
    last = [0] * (WIN - len(last)) + last
    acts = net.forward([norm(v) for v in last])
    pred = max(0, round(math.expm1(acts[-1][0] * den)))

    W, H = 820, 300
    xs = [120, 245, 360, 465]
    ys = lambda n: [155] if n == 1 else [70 + i * 170 / (n - 1) for i in range(n)]
    Y = [ys(n) for n in ARCH]
    R = [11, 10, 10, 16]

    css = [f"text{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;fill:{th['text']}}}",
           f".m{{fill:{th['muted']}}}", ".o{opacity:0}",
           f".pl{{stroke:{pulse};stroke-width:3;stroke-linecap:round;stroke-dasharray:.06 2;stroke-dashoffset:.06;opacity:0}}"]
    body = []

    # weights: animate init -> trained during training
    maxw = max(abs(w) for L in net.W for row in L for w in row) or 1
    wcol = lambda w: pos if w >= 0 else neg
    wwid = lambda w: .4 + 3.2 * min(1, abs(w) / maxw)
    eid = 0
    for l in range(len(ARCH) - 1):
        contrib = [[abs(net.W[l][j][i] * acts[l][i]) for i in range(ARCH[l])] for j in range(ARCH[l + 1])]
        mc = max(max(r) for r in contrib) or 1
        a, b = EDGE_WIN[l]
        for j in range(ARCH[l + 1]):
            for i in range(ARCH[l]):
                wi, wt = W_init[l][j][i], net.W[l][j][i]
                x1, y1, x2, y2 = xs[l] + R[l], Y[l][i], xs[l + 1] - R[l + 1], Y[l + 1][j]
                init = f"stroke:{wcol(wi)};stroke-width:{f(wwid(wi))}px;opacity:.25"
                trained = f"stroke:{wcol(wt)};stroke-width:{f(wwid(wt))}px;opacity:.55"
                css.append(f"@keyframes w{eid}{{0%,2%{{{init}}}{TRAIN_END}%,{FADE0}%{{{trained}}}{FADE1}%,100%{{{init}}}}}")
                body.append(f'<line x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}" '
                            f'style="{init};animation:w{eid} {CYCLE}s ease-in-out infinite"/>')
                op = .25 + .75 * contrib[j][i] / mc
                css.append(f"@keyframes q{eid}{{0%,{a}%{{stroke-dashoffset:.06;opacity:0}}"
                           f"{a+.1}%{{opacity:{op:.2f}}}{b}%{{stroke-dashoffset:-1;opacity:{op:.2f}}}"
                           f"{b+.1}%,100%{{stroke-dashoffset:-1;opacity:0}}}}")
                body.append(f'<line class="pl" pathLength="1" x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}" '
                            f'style="animation:q{eid} {CYCLE}s ease-in-out infinite"/>')
                eid += 1

    # neurons
    nid = 0
    for l, n in enumerate(ARCH):
        on = LAYER_ON[l]
        for i in range(n):
            a = acts[l][i]
            lvl = min(1, abs(a)) if l < len(ARCH) - 1 else min(1, abs(a) + .3)
            col = wcol(a)
            css.append(f"@keyframes n{nid}{{0%,{on}%{{opacity:0}}{on+2}%,{FADE0}%{{opacity:{.2+.8*lvl:.2f}}}{FADE1}%,100%{{opacity:0}}}}")
            body.append(f'<circle cx="{xs[l]}" cy="{f(Y[l][i])}" r="{R[l]}" fill="{th["bg"]}" stroke="{th["node"]}" stroke-width="1.5"/>'
                        f'<circle class="o" cx="{xs[l]}" cy="{f(Y[l][i])}" r="{R[l]-2}" fill="{col}" '
                        f'style="animation:n{nid} {CYCLE}s infinite"/>')
            nid += 1
    for i, v in enumerate(last):
        body.append(f'<text x="{xs[0]-20}" y="{f(Y[0][i]+4)}" font-size="11" class="m" text-anchor="end">w-{WIN-i} · {v}</text>')
    for l, name in enumerate(["input", "hidden · tanh", "hidden · tanh", "output"]):
        body.append(f'<text x="{xs[l]}" y="262" font-size="10" class="m" text-anchor="middle">{name}</text>')
    css.append(f"@keyframes out{{0%,{LAYER_ON[3]+1}%{{opacity:0}}{LAYER_ON[3]+3}%,{FADE0}%{{opacity:1}}{FADE1}%,100%{{opacity:0}}}}"
               f".out{{animation:out {CYCLE}s infinite}}")
    body.append(f'<text class="o out" x="{xs[3]}" y="{Y[3][0]+5}" font-size="13" font-weight="700" '
                f'text-anchor="middle" fill="{th["bg"]}" style="fill:{th["bg"]}">{pred}</text>')

    # loss panel
    lx0, lx1, ly0, ly1 = 560, 796, 84, 206
    body.append(f'<text x="{lx0}" y="{ly0-14}" font-size="11">training loss (MSE, log scale)</text>'
                f'<rect x="{lx0}" y="{ly0}" width="{lx1-lx0}" height="{ly1-ly0}" rx="6" fill="none" stroke="{th["node"]}"/>'
                f'<text x="{lx0}" y="{ly1+16}" font-size="10" class="m">epoch 0</text>'
                f'<text x="{lx1}" y="{ly1+16}" font-size="10" class="m" text-anchor="end">{EPOCHS}</text>')
    step = max(1, len(losses) // 90)
    sample = [math.log10(v + 1e-6) for v in losses[::step] + [losses[-1]]]   # log scale
    top, lo = max(sample) or 1, min(sample)
    rng_ = (top - lo) or 1
    pts = " ".join(f"{f(lx0+8+(lx1-lx0-16)*i/max(len(sample)-1,1))},{f(ly1-8-(ly1-ly0-16)*(v-lo)/rng_)}"
                   for i, v in enumerate(sample))
    css.append(f"@keyframes lc{{0%,2%{{stroke-dashoffset:1;opacity:1}}{TRAIN_END}%,{FADE0}%{{stroke-dashoffset:0;opacity:1}}"
               f"{FADE1}%{{stroke-dashoffset:0;opacity:0}}100%{{stroke-dashoffset:1;opacity:0}}}}")
    body.append(f'<polyline points="{pts}" fill="none" stroke="{pos}" stroke-width="2" pathLength="1" '
                f'stroke-dasharray="1" style="animation:lc {CYCLE}s ease-out infinite"/>')
    css.append(f"@keyframes fl{{0%,{TRAIN_END}%{{opacity:0}}{TRAIN_END+1}%,{FADE0}%{{opacity:1}}{FADE1}%,100%{{opacity:0}}}}"
               f".fl{{animation:fl {CYCLE}s infinite}}")
    body.append(f'<text class="o fl m" x="{lx1-8}" y="{ly0+18}" font-size="11" text-anchor="end">'
                f'loss {losses[0]:.3f} → {losses[-1]:.4f}</text>')

    # narration
    by = H - 16
    lines = [("> training: backprop + SGD on my weekly contributions", 0, TRAIN_END),
             (f"> forward pass: last {WIN} weeks → hidden layers → forecast", TRAIN_END, LAYER_ON[3]),
             (f"> forecast for this week: ~{pred} contributions · so far: {this_week}", LAYER_ON[3], FADE1)]
    for i, (txt, a, b) in enumerate(lines):
        if i == 0:
            css.append(f"@keyframes t0{{0%,{b}%{{opacity:1}}{b+.1}%,{FADE1-.1}%{{opacity:0}}{FADE1}%,100%{{opacity:1}}}}")
        else:
            css.append(f"@keyframes t{i}{{0%,{a}%{{opacity:0}}{a+.1}%,{b}%{{opacity:1}}{b+.1}%,100%{{opacity:0}}}}")
        css.append(f".t{i}{{animation:t{i} {CYCLE}s infinite}}")
        body.append(f'<text class="t{i}{" o" if i else ""}" x="24" y="{by}" font-size="12">{txt}</text>')

    arch = "→".join(map(str, ARCH))
    head = [f'<rect width="{W}" height="{H}" rx="10" fill="{th["bg"]}"/>',
            f'<text x="24" y="26" font-size="13" font-weight="700">neural network · trained on my contributions</text>',
            f'<text x="24" y="44" font-size="11" class="m">MLP {arch} · tanh · pure-Python backprop · {len(data)} training windows · {EPOCHS} epochs</text>']
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
        cells, _ = demo_data()
    else:
        token = os.environ.get("GITHUB_TOKEN") or sys.exit("GITHUB_TOKEN not set")
        cells, _ = fetch(a.user, token)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(render(cells, a.theme, seed=7))
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
