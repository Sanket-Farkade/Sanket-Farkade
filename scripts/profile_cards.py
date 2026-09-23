#!/usr/bin/env python3
"""
Self-hosted profile cards: node stats + top languages, generated from the
GitHub GraphQL API inside your own workflow (no third-party servers).

Usage:
  python profile_cards.py --user USERNAME --theme dark --outdir dist
  python profile_cards.py --demo --theme dark --outdir demo
Writes stats-<theme>.svg and langs-<theme>.svg. Needs GITHUB_TOKEN (not for --demo).
"""
import argparse, json, os, sys, urllib.request
from html import escape

QUERY = """
query($login: String!) {
  user(login: $login) {
    name login
    followers { totalCount }
    contributionsCollection {
      totalCommitContributions totalPullRequestContributions
      totalIssueContributions totalPullRequestReviewContributions
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}"""

THEMES = {
    "dark": dict(bg="#1a1b27", title="#70a5fd", text="#c0caf5", muted="#565f89",
                 accent="#bf91f3", value="#38bdae", track="#24283b"),
    "light": dict(bg="#ffffff", title="#0969da", text="#24292f", muted="#6e7781",
                  accent="#8250df", value="#1a7f37", track="#eaeef2"),
}
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"


def fetch(user, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": user}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-cards"})
    with urllib.request.urlopen(req) as r:
        p = json.load(r)
    if "errors" in p:
        sys.exit(f"GraphQL error: {p['errors']}")
    u = p["data"]["user"]
    cc = u["contributionsCollection"]
    langs = {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            n = e["node"]["name"]
            langs.setdefault(n, [0, e["node"]["color"] or "#8b949e"])[0] += e["size"]
    return dict(
        name=u["name"] or u["login"],
        stars=sum(r["stargazerCount"] for r in u["repositories"]["nodes"]),
        commits=cc["totalCommitContributions"], prs=cc["totalPullRequestContributions"],
        issues=cc["totalIssueContributions"], reviews=cc["totalPullRequestReviewContributions"],
        repos=u["repositories"]["totalCount"], followers=u["followers"]["totalCount"],
        langs=langs)


def demo():
    return dict(name="Sanket Farkade", stars=12, commits=68, prs=5, issues=2, reviews=1,
                repos=9, followers=14,
                langs={"Python": [52000, "#3572A5"], "Jupyter Notebook": [30000, "#DA5B0B"],
                       "SQL": [9000, "#e38c00"], "Scala": [6000, "#c22d40"],
                       "Shell": [2500, "#89e051"], "Dockerfile": [900, "#384d54"]})


def frame(w, h, th, title, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<style>text{{font-family:{FONT}}}'
            '.in{opacity:0;animation:in .6s ease forwards}'
            '@keyframes in{to{opacity:1}}'
            '.grow{transform-box:fill-box;transform-origin:left;transform:scaleX(0);'
            'animation:grow 1s cubic-bezier(.2,.8,.2,1) forwards}'
            '@keyframes grow{to{transform:scaleX(1)}}</style>'
            f'<rect width="{w}" height="{h}" rx="8" fill="{th["bg"]}"/>'
            f'<text x="22" y="32" font-size="14" font-weight="700" fill="{th["title"]}">{escape(title)}</text>'
            f'{body}</svg>')


def stats_card(d, th):
    rows = [("★", "total stars", d["stars"]),
            ("◆", "commits (last year)", d["commits"]),
            ("⇄", "pull requests", d["prs"]),
            ("◉", "issues opened", d["issues"]),
            ("✓", "code reviews", d["reviews"]),
            ("▣", "public repos", d["repos"]),
            ("◎", "followers", d["followers"])]
    body = [f'<text x="22" y="52" font-size="11" fill="{th["muted"]}">$ kubectl top node {escape(d["name"].lower().replace(" ", "-"))}</text>']
    for i, (icon, label, val) in enumerate(rows):
        y = 80 + i * 20
        body.append(f'<g class="in" style="animation-delay:{0.1*i:.1f}s">'
                    f'<text x="22" y="{y}" font-size="12" fill="{th["accent"]}">{icon}</text>'
                    f'<text x="42" y="{y}" font-size="12" fill="{th["text"]}">{label}</text>'
                    f'<text x="240" y="{y}" font-size="12" font-weight="700" fill="{th["value"]}" text-anchor="end">{val}</text></g>')
    # "cluster load" ring: share of days-worth activity, purely decorative score
    score = min(100, round((d["commits"] + 3 * d["prs"] + 2 * d["issues"] + 2 * d["reviews"] + 5 * d["stars"]) / 5))
    import math
    r, cx, cy = 48, 355, 118
    circ = 2 * math.pi * r
    body.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{th["track"]}" stroke-width="9"/>'
                f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{th["title"]}" stroke-width="9" stroke-linecap="round" '
                f'stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ:.1f}" transform="rotate(-90 {cx} {cy})">'
                f'<animate attributeName="stroke-dashoffset" from="{circ:.1f}" to="{circ*(1-score/100):.1f}" dur="1.2s" fill="freeze"/></circle>'
                f'<text x="{cx}" y="{cy+6}" font-size="22" font-weight="700" fill="{th["text"]}" text-anchor="middle">{score}%</text>'
                f'<text x="{cx}" y="{cy+r+24}" font-size="11" fill="{th["muted"]}" text-anchor="middle">cluster load</text>')
    return frame(460, 225, th, "node stats", "".join(body))


def langs_card(d, th):
    total = sum(v[0] for v in d["langs"].values())
    top = sorted(d["langs"].items(), key=lambda kv: -kv[1][0])[:6]
    body = [f'<text x="22" y="52" font-size="11" fill="{th["muted"]}">$ du -sh --by-language ~/repos</text>']
    if not total:
        body.append(f'<text x="22" y="100" font-size="12" fill="{th["text"]}">no language data yet</text>')
        return frame(340, 225, th, "top languages", "".join(body))
    x, bw = 22, 296
    body.append(f'<clipPath id="bar"><rect x="22" y="66" width="{bw}" height="10" rx="5"/></clipPath><g clip-path="url(#bar)">')
    for name, (size, color) in top:
        w = bw * size / total
        body.append(f'<rect class="grow" x="{x:.1f}" y="66" width="{w+0.5:.1f}" height="10" fill="{color}"/>')
        x += w
    body.append(f'<rect x="{x:.1f}" y="66" width="{max(0, 318-x):.1f}" height="10" fill="{th["track"]}"/></g>')
    for i, (name, (size, color)) in enumerate(top):
        col, row = i % 2, i // 2
        lx, ly = 22 + col * 156, 104 + row * 34
        body.append(f'<g class="in" style="animation-delay:{0.15*i+0.4:.2f}s">'
                    f'<circle cx="{lx+5}" cy="{ly-4}" r="5" fill="{color}"/>'
                    f'<text x="{lx+16}" y="{ly}" font-size="12" fill="{th["text"]}">{escape(name if len(name) <= 18 else name[:17] + "…")}</text>'
                    f'<text x="{lx+16}" y="{ly+15}" font-size="11" fill="{th["muted"]}">{100*size/total:.1f}%</text></g>')
    return frame(340, 225, th, "top languages", "".join(body))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user")
    ap.add_argument("--theme", choices=THEMES, default="dark")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    if a.demo:
        d = demo()
    else:
        token = os.environ.get("GITHUB_TOKEN") or sys.exit("GITHUB_TOKEN not set")
        d = fetch(a.user, token)
    th = THEMES[a.theme]
    os.makedirs(a.outdir, exist_ok=True)
    for fname, svg in ((f"stats-{a.theme}.svg", stats_card(d, th)), (f"langs-{a.theme}.svg", langs_card(d, th))):
        with open(os.path.join(a.outdir, fname), "w", encoding="utf-8") as fh:
            fh.write(svg)
        print("wrote", fname)


if __name__ == "__main__":
    main()
