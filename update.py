# -*- coding: utf-8 -*-
import os
import sys
import datetime
import requests

# ========= 环境变量 =========
USERNAME = os.getenv("MY_GITHUB_USERNAME") or os.getenv("GITHUB_USERNAME")
TOKEN = os.getenv("MY_GITHUB_PAT") or os.getenv("GITHUB_TOKEN")  # 建议 classic PAT 勾 repo

TOP_REPO_NUM = int(os.getenv("TOP_REPO_NUM", "10"))
RECENT_REPO_NUM = int(os.getenv("RECENT_REPO_NUM", "10"))

def log(*args):
    print("[UPDATE_PROFILE]", *args, flush=True)

def headers():
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    return h

def get_json(url, what):
    log(f"GET {what}: {url}")
    r = requests.get(url, headers=headers(), timeout=30)
    log(f" -> status={r.status_code}")
    if r.status_code != 200:
        log(f" !! non-200: {r.text[:200]}")
        r.raise_for_status()
    return r.json()

# ---------- 拉取仓库（供 Top/Recent 使用；是否有 PAT 都能跑） ----------
def fetch_all_repos(username: str):
    """
    有 TOKEN：/user/repos?visibility=all&affiliation=owner,collaborator,organization_member
    无 TOKEN：/users/{username}/repos?type=owner
    注意：Top/Recent 只展示公开仓库（下方再过滤），fork 保留
    """
    repos, page = [], 1
    if TOKEN:
        base = "https://api.github.com/user/repos"
        extra = "&visibility=all&affiliation=owner,collaborator,organization_member&sort=updated"
    else:
        base = f"https://api.github.com/users/{username}/repos"
        extra = "&type=owner&sort=updated"

    while True:
        url = f"{base}?per_page=100&page={page}{extra}"
        data = get_json(url, f"repos_page_{page}")
        if not isinstance(data, list) or not data:
            break
        repos.extend(data)
        page += 1

    log(f"total repos fetched = {len(repos)}")
    return repos

# ---------- 渲染 ----------
def parse_iso(iso_str: str) -> datetime.datetime:
    return datetime.datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ")

def fmt_dt_human_slug(dt: datetime.datetime) -> tuple[str, str]:
    s = dt.strftime("%Y-%m-%d %H:%M:%S")
    slug = s.replace('-', '--').replace(' ', '-').replace(':', '%3A')
    return s, slug

# 固定技能图（你可以按需改动顺序/内容）
STATIC_SKILL_ICONS = os.getenv(
    "SKILL_ICONS_STATIC",
    "https://skillicons.dev/icons?i=c,cpp,go,py,html,css,js,nodejs,java,md,pytorch,tensorflow,flask,fastapi,express,qt,react,cmake,docker,git,linux,nginx,mysql,redis,sqlite,githubactions,heroku,vercel,visualstudio,vscode"
)

def render(username: str, repos: list) -> str:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cache_bust = now.replace(' ', '').replace(':', '').replace('-', '')

    processed = []
    for repo in repos:
        pushed_iso = repo.get("pushed_at") or repo.get("updated_at") or repo.get("created_at")
        dt = parse_iso(pushed_iso)
        pushed_human, pushed_slug = fmt_dt_human_slug(dt)
        processed.append({
            "name": repo.get("name"),
            "link": repo.get("html_url"),
            "desc": (repo.get("description") or "").replace('|','\\|').strip(),
            "star": repo.get("stargazers_count", 0),
            "pushed_dt": dt,
            "pushed_human": pushed_human,
            "pushed_slug": pushed_slug,
            "private": repo.get("private", False),
            "fork": repo.get("fork", False),
        })

    # Top / Recent：只统计公开仓库（fork 保留）
    public_processed = [r for r in processed if not r["private"]]
    top = sorted(public_processed, key=lambda x: x["star"], reverse=True)[:TOP_REPO_NUM]
    recent = sorted(public_processed, key=lambda x: x["pushed_dt"], reverse=True)[:RECENT_REPO_NUM]

    md = f"""## Abstract
<p>
  <img src="https://github-readme-stats.vercel.app/api?username={username}&show_icons=true&hide_border=true&v={cache_bust}" alt="{username}'s Github Stats" width="58%" />
  <img src="https://github-readme-stats.vercel.app/api/top-langs/?username={username}&layout=compact&hide_border=true&langs_count=10&v={cache_bust}" alt="{username}'s Top Langs" width="37%" />
</p>

<!-- 活跃度图 -->
<p>
  <img src="https://github-readme-activity-graph.vercel.app/graph?username={username}&theme=github&v={cache_bust}" width="100%" />
</p>

<!-- 奖杯墙 -->
<p>
  <img src="https://github-profile-trophy.vercel.app/?username={username}&theme=gruvbox&row=1&column=7&v={cache_bust}" width="100%" />
</p>

![skills]({STATIC_SKILL_ICONS})

## Top Projects
|Project|Description|Stars|
|:--|:--|:--|
"""
    for r in top:
        name = f"{r['name']}{' (fork)' if r['fork'] else ''}"
        md += f"|[{name}]({r['link']})|{r['desc']}|`{r['star']}⭐`|\n"

    md += """

## Recent Updates
|Project|Description|Last Update|
|:--|:--|:--|
"""
    for r in recent:
        name = f"{r['name']}{' (fork)' if r['fork'] else ''}"
        md += f"|[{name}]({r['link']})|{r['desc']}|![{r['pushed_human']}](https://img.shields.io/badge/{r['pushed_slug']}-brightgreen?style=flat-square)|\n"

    md += f"\n\n*Last updated on: {now}*\n"
    return md

def main():
    if not USERNAME:
        print("ERROR: 请在仓库 Secrets 里设置 MY_GITHUB_USERNAME", file=sys.stderr)
        sys.exit(2)
    if not TOKEN:
        log("WARN: 未提供 PAT（MY_GITHUB_PAT），将只能统计公开仓库；不过技能图标已固定不受影响")

    repos = fetch_all_repos(USERNAME)
    md = render(USERNAME, repos)

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(md)
    log("WRITE README.md -> OK")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"FATAL: {e}")
        sys.exit(1)
