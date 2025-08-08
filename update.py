# -*- coding: utf-8 -*-
import os
import sys
import datetime
import requests

# ========= 环境变量 =========
USERNAME = os.getenv("MY_GITHUB_USERNAME") or os.getenv("GITHUB_USERNAME")
# 建议用 classic PAT 且勾 repo 权限；没有的话只能拿公开库
TOKEN = os.getenv("MY_GITHUB_PAT") or os.getenv("GITHUB_TOKEN")

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

# ---------- 拉取仓库：图标统计需要“包含私有+fork”；Top/Recent 后面再按需求过滤 ----------
def fetch_all_repos(username: str):
    """
    若有 TOKEN：/user/repos?visibility=all&affiliation=owner,collaborator,organization_member
      -> 可拿到 私有 + 公开，且包含 fork（我们不在这里过滤）
    否则：/users/{username}/repos?type=owner -> 只能拿公开
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

# ---------- 技能图标（基于“所有仓库”的 primary language；不做映射/白名单；动态探测；过滤 jupyter） ----------
_ICON_SUPPORT_CACHE = {}

def skillicon_supported(code: str) -> bool:
    """
    动态检测 skillicons 是否支持某个 code。
    不做任何映射：直接拿 language 的小写作为 code。
    """
    if not code:
        return False
    if code in _ICON_SUPPORT_CACHE:
        return _ICON_SUPPORT_CACHE[code]
    try:
        resp = requests.get(f"https://skillicons.dev/icons?i={code}", timeout=10)
        ok = (resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"))
    except Exception:
        ok = False
    _ICON_SUPPORT_CACHE[code] = ok
    return ok

def build_skill_icons_from_repos(repos):
    """
    统计范围：所有仓库（含私有 + fork）
    逻辑：语言 -> 小写代号 -> 过滤 jupyter -> 动态探测支持 -> 去重保序
    加 cache-bust 参数避免 GitHub camo 缓存。
    """
    seen, raw_codes = set(), []
    for r in repos:
        lang = (r.get("language") or "").strip()
        if not lang:
            continue
        code = lang.lower()
        # 过滤 jupyter
        if "jupyter" in code:
            continue
        if code not in seen:
            seen.add(code)
            raw_codes.append(code)

    supported = []
    for c in raw_codes:
        if skillicon_supported(c):
            supported.append(c)

    if not supported:
        # 兜底一组常见项，避免整排空
        supported = ["python", "java", "javascript", "go", "typescript", "html", "css", "nodejs", "docker", "git", "linux"]

    cache_bust = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    url = f"https://skillicons.dev/icons?i={','.join(supported)}&v={cache_bust}"
    log(f"SKILL_ICONS raw={raw_codes} -> used={supported} -> {url}")
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

    # 1) 技能图标：基于“所有仓库（含私有+fork）”，动态探测 + 过滤 jupyter
    skills_url = build_skill_icons_from_repos(repos)

    # 2) Top / Recent：保持“只统计公开仓库（fork 保留）”
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
        log("WARN: 未提供 PAT（MY_GITHUB_PAT），将只能统计公开仓库；技能图标将缺少私仓语言")

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
