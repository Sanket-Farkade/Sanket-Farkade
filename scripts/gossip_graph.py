#!/usr/bin/env python3
"""
Gossip Graph: renders your GitHub contribution calendar as a live
gossip-protocol broadcast (animated SVG).

Every day in your contribution graph is a node in a cluster.
1. Leader election: your busiest day becomes the leader node.
2. Push gossip:     each round, every informed node forwards the rumor
                    to `fanout` random peers.
3. Convergence:     the whole cluster is informed in ~O(log N) rounds,
                    and each node lights up with its real contribution level.

Usage:
  python gossip_graph.py --user USERNAME --theme dark --out dist/gossip-dark.svg
  python gossip_graph.py --demo --theme dark --out demo.svg     # fake data
Requires GITHUB_TOKEN in the environment (not needed for --demo).
"""
import argparse, datetime as dt, json, os, random, sys, urllib.request

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date weekday contributionCount contributionLevel } }
      }
    }
  }
}"""
LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
          "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

THEMES = {
    "dark": dict(bg="#0d1117", text="#c9d1d9", muted="#6e7681", node="#30363d",
                 levels=["#161b22", "#1b3a5c", "#1f6feb", "#58a6ff", "#a5d6ff"],
                 flash="#f778ba", edge="#bc8cff", leader="#f778ba"),
    "light": dict(bg="#ffffff", text="#24292f", muted="#6e7781", node="#d0d7de",
                  levels=["#ebedf0", "#c6dbff", "#79b8ff", "#2188ff", "#044289"],
                  flash="#d63384", edge="#8250df", leader="#d63384"),
}

CYCLE = 16          # seconds per animation loop
P_START, P_END = 6.0, 62.0   # % of the cycle used for gossip rounds
HOLD_END, FADE_END = 88.0, 95.0


def fetch(user, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": user}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "gossip-graph"})
    with urllib.request.urlopen(req) as r:
        payload = json.load(r)
    if "errors" in payload:
        sys.exit(f"GraphQL error: {payload['errors']}")
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    cells = []
    for x, week in enumerate(cal["weeks"]):
        for d in week["contributionDays"]:
            cells.append(dict(x=x, y=d["weekday"], date=d["date"],
                              count=d["contributionCount"], level=LEVELS[d["contributionLevel"]]))
    return cells, cal["totalContributions"]


def demo_data():
    rng = random.Random(7)
    today = dt.date.today()
    start = today - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)   # back to Sunday
    cells, i = [], 0
    while start + dt.timedelta(days=i) <= today:
        c = rng.choice([0] * 5 + [1, 2, 3, 4, 6, 8, 12, 17])
        lvl = 0 if c == 0 else 1 if c < 3 else 2 if c < 6 else 3 if c < 10 else 4
        cells.append(dict(x=i // 7, y=i % 7, date=str(start + dt.timedelta(days=i)),
                          count=c, level=lvl))
        i += 1
    return cells, sum(c["count"] for c in cells)


def simulate(n, leader, fanout, rng):
    """Push gossip. Returns (round each node was informed, who informed it, total rounds)."""
    rnd, parent = [None] * n, [None] * n
    rnd[leader] = 0
    informed, r = [leader], 0
    while len(informed) < n:
        r += 1
        new = []
        for s in informed:
            for _ in range(fanout):
                t = rng.randrange(n)
                if rnd[t] is None:
                    rnd[t], parent[t] = r, s
                    new.append(t)
        informed += new
    return rnd, parent, r


def f(v):
    return f"{v:.2f}"


def render(cells, total, theme, fanout, seed):
    th = THEMES[theme]
    n = len(cells)
    leader = max(range(n), key=lambda i: cells[i]["count"])
    rnd, parent, R = simulate(n, leader, fanout, random.Random(seed))

    pitch, size = 14, 11
    ox, oy = 20, 56
    weeks = max(c["x"] for c in cells) + 1
    W, H = ox * 2 + weeks * pitch - (pitch - size), oy + 7 * pitch + 44
    cx = lambda c: ox + c["x"] * pitch + size / 2
    cy = lambda c: oy + c["y"] * pitch + size / 2

    step = (P_END - P_START) / max(R, 1)
    T = lambda r: 3.0 if r == 0 else P_START + (r - 1) * step

    css = [f"text{{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;fill:{th['text']}}}",
           f".m{{fill:{th['muted']}}}",
           f"line{{stroke:{th['edge']};stroke-width:1;stroke-dasharray:1;stroke-dashoffset:1;opacity:0}}",
           ".c,.fl,.t{opacity:0}",
           ".ring{transform-box:fill-box;transform-origin:center;animation:pulse 1.8s ease-out infinite}",
           ".ring2{animation-delay:.9s}",
           "@keyframes pulse{0%{transform:scale(.15);opacity:.9}100%{transform:scale(1);opacity:0}}"]
    for r in range(R + 1):
        t = T(r)
        css.append(f"@keyframes c{r}{{0%,{f(t)}%{{opacity:0}}{f(t+1)}%,{f(HOLD_END)}%{{opacity:1}}"
                   f"{f(FADE_END)}%,100%{{opacity:0}}}}.c{r}{{animation:c{r} {CYCLE}s infinite}}")
        css.append(f"@keyframes f{r}{{0%,{f(t)}%{{opacity:0}}{f(t+.5)}%{{opacity:1}}"
                   f"{f(t+4)}%,100%{{opacity:0}}}}.f{r}{{animation:f{r} {CYCLE}s infinite}}")
        if r > 0:
            s = t - step * 0.8
            css.append(f"@keyframes e{r}{{0%,{f(s)}%{{opacity:0;stroke-dashoffset:1}}"
                       f"{f(s+.1)}%{{opacity:.75;stroke-dashoffset:1}}{f(t)}%{{opacity:.75;stroke-dashoffset:0}}"
                       f"{f(t+3)}%,100%{{opacity:0;stroke-dashoffset:0}}}}"
                       f".e{r}{{animation:e{r} {CYCLE}s ease-in infinite}}")
        end = T(r + 1) if r < R else T(R) + step
        css.append(f"@keyframes t{r}{{0%,{f(t)}%{{opacity:0}}{f(t+.1)}%,{f(end)}%{{opacity:1}}"
                   f"{f(end+.1)}%,100%{{opacity:0}}}}.t{r}{{animation:t{r} {CYCLE}s infinite}}")
    done = T(R) + step
    css.append(f"@keyframes td{{0%,{f(done)}%{{opacity:0}}{f(done+.1)}%,{f(FADE_END)}%{{opacity:1}}"
               f"{f(FADE_END+.1)}%,100%{{opacity:0}}}}.td{{animation:td {CYCLE}s infinite}}")

    L = cells[leader]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
           f"<style>{''.join(css)}</style>",
           f'<rect width="{W}" height="{H}" rx="10" fill="{th["bg"]}"/>',
           f'<text x="{ox}" y="24" font-size="13" font-weight="700">gossip broadcast · contribution cluster</text>',
           f'<text x="{ox}" y="42" font-size="11" class="m">leader elected: {L["date"]} ({L["count"]} contributions) · push-gossip, fanout={fanout}</text>',
           f'<text x="{W-ox}" y="24" font-size="11" class="m" text-anchor="end">{n} nodes · {total} contributions</text>']

    # edges under nodes
    for i, c in enumerate(cells):
        if parent[i] is not None:
            p = cells[parent[i]]
            out.append(f'<line class="e{rnd[i]}" pathLength="1" x1="{f(cx(p))}" y1="{f(cy(p))}" x2="{f(cx(c))}" y2="{f(cy(c))}"/>')
    # nodes: hollow base, real-level fill, flash on receive
    for i, c in enumerate(cells):
        x, y, r = ox + c["x"] * pitch, oy + c["y"] * pitch, rnd[i]
        out.append(f'<rect x="{x}" y="{y}" width="{size}" height="{size}" rx="2" fill="none" stroke="{th["node"]}"/>'
                   f'<rect class="c c{r}" x="{x}" y="{y}" width="{size}" height="{size}" rx="2" fill="{th["levels"][c["level"]]}"/>'
                   f'<rect class="fl f{r}" x="{x}" y="{y}" width="{size}" height="{size}" rx="2" fill="{th["flash"]}"/>')
    # leader heartbeat rings
    for cls in ("ring", "ring ring2"):
        out.append(f'<circle class="{cls}" cx="{f(cx(L))}" cy="{f(cy(L))}" r="26" fill="none" stroke="{th["leader"]}" stroke-width="1.5"/>')

    # round counter
    by = oy + 7 * pitch + 26
    informed = 0
    for r in range(R + 1):
        informed += sum(1 for v in rnd if v == r)
        label = "round 0 · leader holds the rumor" if r == 0 else f"round {r} · informed {informed}/{n} nodes"
        out.append(f'<text class="t t{r}" x="{ox}" y="{by}" font-size="12">&gt; {label}</text>')
    out.append(f'<text class="t td" x="{ox}" y="{by}" font-size="12">&gt; converged ✔ all {n} nodes informed in {R} rounds · O(log N)</text>')
    lx = W - ox - 5 * 14 - 30   # colour legend
    out.append(f'<text x="{lx-6}" y="{by}" font-size="11" class="m" text-anchor="end">less</text>')
    for k, col in enumerate(th["levels"]):
        out.append(f'<rect x="{lx + k*14}" y="{by-10}" width="{size}" height="{size}" rx="2" fill="{col}"/>')
    out.append(f'<text x="{lx + 5*14 + 2}" y="{by}" font-size="11" class="m">more</text>')
    out.append("</svg>")
    return "\n".join(o for o in out if o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user")
    ap.add_argument("--theme", choices=THEMES, default="dark")
    ap.add_argument("--fanout", type=int, default=2)
    ap.add_argument("--out", required=True)
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    if a.demo:
        cells, total = demo_data()
        seed = 42
    else:
        token = os.environ.get("GITHUB_TOKEN") or sys.exit("GITHUB_TOKEN not set")
        cells, total = fetch(a.user, token)
        seed = dt.date.today().isoformat()   # new gossip pattern every day
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(render(cells, total, a.theme, a.fanout, seed))
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
