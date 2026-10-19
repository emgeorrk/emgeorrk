"""Render the GitHub stats and language cards for the profile README.

Only public data is counted, so the default GITHUB_TOKEN of a workflow is
enough. Usage: GITHUB_TOKEN=... python3 scripts/stats.py [out_dir]
"""

import datetime
import html
import json
import os
import sys
import urllib.parse
import urllib.request

USER = os.environ.get("GH_USER", "emgeorrk")
TOKEN = os.environ["GITHUB_TOKEN"]
API = "https://api.github.com"

# Notebooks and generated pages inflate the byte counts without saying much.
HIDDEN_LANGUAGES = {"Jupyter Notebook", "HTML"}
TOP_LANGUAGES = 5

THEMES = {
    "": {"bg": "#ffffff", "title": "#0969da", "text": "#1f2328",
         "muted": "#59636e", "icon": "#0969da", "track": "#eff2f5"},
    "-dark": {"bg": "#0d1117", "title": "#58a6ff", "text": "#e6edf3",
              "muted": "#9198a1", "icon": "#58a6ff", "track": "#21262d"},
}

FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"

# Primer octicons, 16px.
ICONS = {
    "star": '<path d="M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Zm0 2.445L6.615 5.5a.75.75 0 0 1-.564.41l-3.097.45 2.24 2.184a.75.75 0 0 1 .216.664l-.528 3.084 2.769-1.456a.75.75 0 0 1 .698 0l2.77 1.456-.53-3.084a.75.75 0 0 1 .216-.664l2.24-2.183-3.096-.45a.75.75 0 0 1-.564-.41L8 2.694Z"/>',
    "commit": '<path d="M11.93 8.5a4.002 4.002 0 0 1-7.86 0H.75a.75.75 0 0 1 0-1.5h3.32a4.002 4.002 0 0 1 7.86 0h3.32a.75.75 0 0 1 0 1.5Zm-1.43-.75a2.5 2.5 0 1 0-5 0 2.5 2.5 0 0 0 5 0Z"/>',
    "pr": '<path d="M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354ZM3.75 2.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm0 9.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm8.25.75a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Z"/>',
    "issue": '<path d="M8 9.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"/><path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Z"/>',
    "repo": '<path d="M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z"/>',
}


def request(url, body=None):
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USER}-profile-stats",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def graphql(query, **variables):
    body = json.dumps({"query": query, "variables": variables}).encode()
    data = request(f"{API}/graphql", body)
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    return data["data"]


def search_count(kind, query):
    q = urllib.parse.quote(query)
    return request(f"{API}/search/{kind}?q={q}&per_page=1")["total_count"]


def owned_repos():
    query = """
    query($login: String!, $after: String) {
      user(login: $login) {
        repositories(first: 100, after: $after, ownerAffiliations: OWNER,
                     privacy: PUBLIC, isFork: false) {
          pageInfo { hasNextPage endCursor }
          nodes {
            stargazerCount
            languages(first: 20) { edges { size node { name color } } }
          }
        }
      }
    }"""
    repos, after = [], None
    while True:
        page = graphql(query, login=USER, after=after)["user"]["repositories"]
        repos += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return repos
        after = page["pageInfo"]["endCursor"]


def contributed_to():
    """Public repos of other owners the user has ever contributed to.

    repositoriesContributedTo only covers the last year, so walk
    contributionsCollection one calendar year at a time.
    """
    created = graphql("query($login: String!) { user(login: $login) { createdAt } }",
                      login=USER)["user"]["createdAt"]
    by_repo = ["commitContributionsByRepository", "issueContributionsByRepository",
               "pullRequestContributionsByRepository",
               "pullRequestReviewContributionsByRepository"]
    fields = " ".join(f"{f}(maxRepositories: 100) {{ repository {{ nameWithOwner isPrivate }} }}"
                      for f in by_repo)
    query = f"""
    query($login: String!, $from: DateTime!, $to: DateTime!) {{
      user(login: $login) {{
        contributionsCollection(from: $from, to: $to) {{ {fields} }}
        repositoriesContributedTo(first: 100, includeUserRepositories: false,
          contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, PULL_REQUEST_REVIEW, REPOSITORY]) {{
          nodes {{ nameWithOwner isPrivate }}
        }}
      }}
    }}"""
    found = set()
    for year in range(int(created[:4]), datetime.date.today().year + 1):
        user = graphql(query, login=USER, **{"from": f"{year}-01-01T00:00:00Z",
                                             "to": f"{year}-12-31T23:59:59Z"})["user"]
        repos = [c["repository"] for f in by_repo for c in user["contributionsCollection"][f]]
        repos += user["repositoriesContributedTo"]["nodes"]
        found |= {r["nameWithOwner"].lower() for r in repos if not r["isPrivate"]}
    return len({r for r in found if not r.startswith(f"{USER.lower()}/")})


def languages(repos):
    sizes, colors = {}, {}
    for repo in repos:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            if name in HIDDEN_LANGUAGES:
                continue
            sizes[name] = sizes.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#8b949e"
    total = sum(sizes.values())
    ranked = sorted(sizes.items(), key=lambda kv: kv[1], reverse=True)
    top = [(name, size / total * 100, colors[name]) for name, size in ranked[:TOP_LANGUAGES]]
    rest = sum(size for _, size in ranked[TOP_LANGUAGES:]) / total * 100
    if rest >= 0.1:
        top.append(("Other", rest, "#8b949e"))
    return top


def card(width, height, theme, title, body):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" role="img" aria-label="{html.escape(title)}">
<style>
  .title {{ font: 600 18px {FONT}; fill: {theme["title"]}; }}
  .label {{ font: 400 14px {FONT}; fill: {theme["text"]}; }}
  .value {{ font: 600 14px {FONT}; fill: {theme["text"]}; }}
  .muted {{ font: 400 13px {FONT}; fill: {theme["muted"]}; }}
</style>
<rect width="{width}" height="{height}" rx="6" fill="{theme["bg"]}"/>
<text class="title" x="25" y="35">{html.escape(title)}</text>
{body}
</svg>
"""


def stats_card(stats, theme):
    width, height = 380, 185
    rows = []
    for i, (icon, label, value) in enumerate(stats):
        y = 68 + i * 25
        rows.append(
            f'<g transform="translate(25 {y - 12})" fill="{theme["icon"]}">{ICONS[icon]}</g>'
            f'<text class="label" x="50" y="{y}">{label}</text>'
            f'<text class="value" x="{width - 25}" y="{y}" text-anchor="end">{value:,}</text>')
    return card(width, height, theme, "GitHub stats", "\n".join(rows))


def languages_card(langs, theme):
    width, height = 350, 185
    bar_x, bar_y, bar_w = 25, 56, width - 50
    parts = [f'<clipPath id="bar"><rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="8" rx="4"/></clipPath>',
             f'<rect x="{bar_x}" y="{bar_y}" width="{bar_w}" height="8" rx="4" fill="{theme["track"]}"/>',
             '<g clip-path="url(#bar)">']
    x = bar_x
    for _, share, color in langs:
        w = bar_w * share / 100
        parts.append(f'<rect x="{x:.2f}" y="{bar_y}" width="{w:.2f}" height="8" fill="{color}"/>')
        x += w
    parts.append("</g>")
    for i, (name, share, color) in enumerate(langs):
        cx = 25 + (i % 2) * 160
        y = 98 + (i // 2) * 30
        parts.append(f'<circle cx="{cx + 5}" cy="{y - 5}" r="5" fill="{color}"/>'
                     f'<text class="label" x="{cx + 18}" y="{y}">{html.escape(name)}'
                     f'<tspan class="muted" dx="6">{share:.1f}%</tspan></text>')
    return card(width, height, theme, "Most used languages", "\n".join(parts))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "assets"
    os.makedirs(out, exist_ok=True)
    repos = owned_repos()
    stats = [
        ("star", "Stars earned", sum(r["stargazerCount"] for r in repos)),
        ("commit", "Commits", search_count("commits", f"author:{USER}")),
        ("pr", "Pull requests", search_count("issues", f"author:{USER} type:pr is:public")),
        ("issue", "Issues", search_count("issues", f"author:{USER} type:issue is:public")),
        ("repo", "Contributed to", contributed_to()),
    ]
    langs = languages(repos)
    for suffix, theme in THEMES.items():
        with open(os.path.join(out, f"stats{suffix}.svg"), "w", encoding="utf-8") as f:
            f.write(stats_card(stats, theme))
        with open(os.path.join(out, f"langs{suffix}.svg"), "w", encoding="utf-8") as f:
            f.write(languages_card(langs, theme))
    print(*(f"{label}: {value}" for _, label, value in stats), sep="\n")
    print(*(f"{name}: {share:.1f}%" for name, share, _ in langs), sep="\n")


if __name__ == "__main__":
    main()
