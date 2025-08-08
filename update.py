# -*- coding: utf-8 -*-
import os
import sys
import datetime
import requests
from dateutil import tz

# ==== 配置 ====
token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or ""
current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
TOP_REPO_NUM = int(os.getenv("TOP_REPO_NUM", "10"))
RECENT_REPO_NUM = int(os.getenv("RECENT_REPO_NUM", "10"))

from_zone = tz.tzutc()
to_zone = tz.tzlocal()


def log(*args):
    print("[UPDATE_PROFILE]", *args, flush=True)


def _headers():
    return {} if not token else {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get_json(url, what):
    """带日志的请求封装"""
    log(f"GET {what}: {url}")
    try:
        r = requests.get(url, headers=_headers(), timeout=30)
        log(f" -> status={r.status_code}")
        if r.status_code != 200:
            log(f" !! non-200 for {what}: {r.text[:200]}")
        return r.json()
    except Exception as e:
        log(f" !! request error for {what}: {e}")
        return None


def fetcher(username: str):
    """
    拉取用户信息与仓库，产出：
      - top_repos: 按 Star 数排序 Top N
      - recent_repos: 按最后 push 时间排序 Top N
    """
    log("=== FETCH START ===")
    log(f"username = {username}")
    log(f"token_present = {bool(token)} (len={len(token) if token else 0})")
    result = {
        'name': '',
        'public_repos': 0,
        'top_repos': [],
        'recent_repos': []
    }

    # 用户信息
    user_info_url = f"https://api.github.com/users/{username}"
    user = _get_json(user_info_url, "user_info")
    if not isinstance(user, dict):
        log(" !! user_info invalid, abort")
        return result
    result['name'] = (user.get('name') or username)
    result['public_repos'] = user.get('public_repos', 0)
    log(f"name = {result['name']}, public_repos = {result['public_repos']}")

    # 全量仓库（分页）
    repos = []
    page = 1
    while True:
        all_repos_url = (
            f"https://api.github.com/users/{username}/repos"
            f"?per_page=100&page={page}&type=owner&sort=updated"
        )
        data = _get_json(all_repos_url, f"repos_page_{page}")
        if not isinstance(data, list) or not data:
            break
        repos.extend(data)
        log(f"  -> page {page} repos fetched: {len(data)}, total so far: {len(repos)}")
        page += 1

    log(f"total repos fetched (raw) = {len(repos)}")

    processed = []
    for repo in repos:
        if repo.get('fork'):
            continue

        pushed_iso = repo.get('pushed_at') or repo.get('updated_at') or repo.get('created_at')
        try:
            dt = datetime.datetime.strptime(pushed_iso, "%Y-%m-%dT%H:%M:%SZ")
            dt = dt.replace(tzinfo=from_zone).astimezone(to_zone)
        except Exception as e:
            log(f"  -> time parse error for {repo.get('name')}: {e}")
            continue

        processed.append({
            'score': (repo.get('stargazers_count', 0) +
                      repo.get('watchers_count', 0) +
                      repo.get('forks_count', 0)),
            'star': repo.get('stargazers_count', 0),
            'link': repo.get('html_url'),
            'created_at': repo.get('created_at'),
            'updated_at': repo.get('updated_at'),
            'pushed_at_dt': dt,  # 用于排序
            'pushed_at': dt.strftime('%Y-%m-%d %H:%M:%S'),  # 用于展示
            'name': repo.get('name'),
            'description': (repo.get('description') or '')
        })

    log(f"processed repos (non-fork) = {len(processed)}")

    # Top by star
    top_repos = sorted(processed, key=lambda x: x['star'], reverse=True)[:TOP_REPO_NUM]
    # Recent by pushed time
    recent_repos = sorted(processed, key=lambda x: x['pushed_at_dt'], reverse=True)[:RECENT_REPO_NUM]

    log(f"TOP_REPO_NUM = {TOP_REPO_NUM}, selected = {len(top_repos)}")
    log(f"RECENT_REPO_NUM = {RECENT_REPO_NUM}, selected = {len(recent_repos)}")

    result['top_repos'] = top_repos
    result['recent_repos'] = recent_repos

    log("=== FETCH DONE ===")
    return result


def render(github_username, github_data) -> str:
    """
    生成 README 文本。
    已将 LeetCode/知乎 换成：
      - GitHub 活跃度图
      - 访客计数
      - GitHub streak（两张不同主题）
    """
    log("=== RENDER START ===")
    cache_bust = current_time.replace(' ', '').replace(':', '').replace('-', '')
    abstract_tpl = f"""## Abstract
<p>
  <img src="https://github-readme-stats.vercel.app/api?username={{github_username}}&show_icons=true&hide_border=true&v={cache_bust}" alt="{{github_name}}'s Github Stats" width="58%" />
  <img src="https://github-readme-stats.vercel.app/api/top-langs/?username={{github_username}}&layout=compact&hide_border=true&langs_count=10&v={cache_bust}" alt="{{github_name}}'s Top Langs" width="37%" /> 
</p>

<!-- GitHub 活跃度图 -->
<p>
  <img src="https://github-readme-activity-graph.vercel.app/graph?username={{github_username}}&theme=github&v={cache_bust}" width="100%" />
</p>

<!-- 访客计数 -->
<p>
  <img src="https://komarev.com/ghpvc/?username={{github_username}}&color=blue&style=flat-square&label=Profile+Views&v={cache_bust}" />
</p>

<!-- GitHub streak 连续提交天数（主题1） -->
<p>
  <img src="https://streak-stats.demolab.com/?user={{github_username}}&theme=tokyonight&hide_border=true&v={cache_bust}" width="100%" />
</p>

<!-- GitHub streak 连续提交天数（主题2） -->
<p>
  <img src="https://streak-stats.demolab.com/?user={{github_username}}&theme=default&hide_border=false&v={cache_bust}" width="100%" />
</p>

![skills](https://skillicons.dev/icons?i=c,cpp,go,py,html,css,js,nodejs,java,md,pytorch,tensorflow,flask,fastapi,express,qt,react,cmake,docker,git,linux,nginx,mysql,redis,sqlite,githubactions,heroku,vercel,visualstudio,vscode)

"""

    top_repos_tpl = """
## Top Projects
|Project|Description|Stars|
|:--|:--|:--|
"""

    recent_repos_tpl = """
## Recent Updates
|Project|Description|Last Update|
|:--|:--|:--|
"""

    md = abstract_tpl.format(
        github_username=github_username,
        github_name=github_data['name'],
    )

    # 关键修复：先把表头拼进去
    md += top_repos_tpl

    # Top
    for repo in github_data['top_repos']:
        desc = (repo['description'] or '').replace('|', '\\|').strip()
        md += f"|[{repo['name']}]({repo['link']})|{desc}|`{repo['star']}⭐`|\n"

    # Recent
    md += recent_repos_tpl
    for repo in github_data['recent_repos']:
        desc = (repo['description'] or '').replace('|', '\\|').strip()
        date_slug = repo['pushed_at'].replace('-', '--').replace(' ', '-').replace(':', '%3A')
        md += f"|[{repo['name']}]({repo['link']})|{desc}|![{repo['pushed_at']}](https://img.shields.io/badge/{date_slug}-brightgreen?style=flat-square)|\n"

    md += f"\n\n*Last updated on: {current_time}*\n"
    log("=== RENDER DONE ===")
    return md


def writer(markdown) -> bool:
    try:
        with open('./README.md', 'w', encoding='utf-8') as f:
            f.write(markdown)
        log("WRITE README.md -> OK")
        return True
    except IOError as e:
        log(f"WRITE README.md -> FAILED: {e}")
        return False


def pusher():
    commit_message = f":pencil2: update on {current_time}"
    os.system('git add ./README.md')
    if os.getenv('DEBUG'):
        log("DEBUG=1 -> skip commit/push")
        return
    code = os.system(f'git commit -m "{commit_message}"')
    log(f"git commit exit={code}")
    code = os.system('git push')
    log(f"git push exit={code}")


def main():
    log("=== JOB START ===")
    log(f"TIME = {current_time}")
    github_username = os.getenv('GITHUB_USERNAME')
    if not github_username:
        cwd = os.getcwd()
        github_username = os.path.split(cwd)[-1]
        log(f"GITHUB_USERNAME not set, fallback to cwd name: {github_username}")
    else:
        log(f"GITHUB_USERNAME from env: {github_username}")

    data = fetcher(github_username)
    md = render(github_username, data)
    if writer(md):
        log("READY to commit (pusher disabled by default).")
        # 如需自动提交，取消下一行注释
        # pusher()
    log("=== JOB END ===")


if __name__ == '__main__':
    # 失败时让 Action 直接显示错误并退出非零
    try:
        main()
    except Exception as e:
        log(f"FATAL ERROR: {e}")
        sys.exit(1)
