# -*- coding: utf-8 -*-
import os
import sys
import datetime
import requests

# ========== 环境变量 ==========
USERNAME = os.getenv("MY_GITHUB_USERNAME") or os.getenv("GITHUB_USERNAME")
TOKEN = os.getenv("MY_GITHUB_PAT") or os.getenv("GITHUB_TOKEN")  # 建议用 MY_GITHUB_PAT (classic, 勾 repo)

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

# ---------- 拉取仓库：包含私有 + fork ----------
def fetch_all_repos(username: str):
    """
    优先 /user/repos（需要 PAT: repo 权限），可拿到私有仓库；
    包含 fork；仅 owner 身份；按更新时间倒序分页。
    若无 TOKEN，则退回 /users/{username}/repos（只能拿公开库）。
    """
    repos = []
    page = 1
    if TOKEN:
        base = "https://api.github.com/user/repos"
        extra = "&visibility=all&affiliation=owner&sort=updated"
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

# ---------- 技能图标（基于所有仓库；过滤 jupyter） ----------
VALID = {
    # 够用的一小撮，避免“空格卡”
    "py","java","js","ts","go","html","css","vue","php","kotlin","cpp","c","cs",
    "bash","docker","git","linux","nginx","mysql","postgres","sqlite","redis",
    "pytorch","tensorflow","fastapi","flask","express","qt","cmake","vercel",
    "vscode","visualstudio","githubactions","nodejs","react"
}
ALIAS = {
    "golang":"go",
    "javascript":"js",
    "typescript":"ts",
    "c++":"cpp",
    "c#":"cs",
    "objective-c":"objectivec",  # skillicons 支持 objectivec，如需可加入 VALID
    "node":"nodejs",
    "jupyter":"",                # 过滤
    "jupyter notebook":"",       # 过滤
}

def to_icon_code(language_name: str) -> str:
    if not language_name:
        return ""
    x = language_name.strip().lower()
    x = ALIAS.get(x, x)
    return x if x in VALID else ""

def build_skill_icons_from_repos(repos):
    seen = set()
    codes = []
    for r in repos:
        lang = (r.get("language") or "").strip()
        code = to_icon_code(lang)
        if code and code not in seen:
            seen.add(code); codes.append(code)
    if not codes:
        codes = ["py","java","js","go","ts","html","css","nodejs","docker","git","linux"]
    url = f"https://skillicons.dev/icons?i={','.join(codes)}"
    log(f"SKILL_ICONS -> {url}")
    return url

# ---------- 渲染 ----------
def parse_iso(iso_str: str) -> datetime.datetime:
    return datetime.datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ")

def fmt_dt_human_slug(dt: datetime.datetime) -> tuple[str, str]:
    s = dt.strftime("%Y-%m-%d %H:%M:%S")
    slug = s.replace('-', '--').replace(' ', '-').replace(':', '%3A')
    return s, slug

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

    # 技能图标用“全部仓库”（含私有+fork）
    skills_url = build_skill_icons_from_repos(repos)

    # Top / Recent 只统计“公开仓库”（fork 保留）
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

![skills]({skills_url})

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
        log("WARN: 未提供 PAT（MY_GITHUB_PAT），将只能统计公开仓库")

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
