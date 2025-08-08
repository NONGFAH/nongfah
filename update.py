# -*- coding: utf-8 -*-
import os
import datetime
import requests
from dateutil import tz

# ==== 可选：从环境变量读取 Token，提升 API 限额 ====
# 例如在 GitHub Actions 的 Secrets 里设置 GITHUB_TOKEN 或 GH_TOKEN
token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN") or ""

# ==== 基本配置 ====
current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
TOP_REPO_NUM = 10
RECENT_REPO_NUM = 10

from_zone = tz.tzutc()
to_zone = tz.tzlocal()


def _headers():
    return {} if not token else {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def fetcher(username: str):
    """
    拉取用户信息与仓库，产出：
      - top_repos: 按 Star 数排序 Top N
      - recent_repos: 按最后 push 时间排序 Top N
    """
    result = {
        'name': '',
        'public_repos': 0,
        'top_repos': [],
        'recent_repos': []
    }

    # 用户信息
    user_info_url = f"https://api.github.com/users/{username}"
    user = requests.get(user_info_url, headers=_headers()).json()
    result['name'] = (user.get('name') or username)
    result['public_repos'] = user.get('public_repos', 0)

    # 全量仓库（分页）
    repos = []
    page = 1
    while True:
        all_repos_url = f"https://api.github.com/users/{username}/repos?per_page=100&page={page}&type=owner&sort=updated"
        resp = requests.get(all_repos_url, headers=_headers())
        data = resp.json()
        if not isinstance(data, list) or not data:
            break
        repos.extend(data)
        page += 1

    processed = []
    for repo in repos:
        if repo.get('fork'):
            continue

        pushed_iso = repo.get('pushed_at') or repo.get('updated_at') or repo.get('created_at')
        dt = datetime.datetime.strptime(pushed_iso, "%Y-%m-%dT%H:%M:%SZ")
        dt = dt.replace(tzinfo=from_zone).astimezone(to_zone)

        processed.append({
            'score': (repo.get('stargazers_count', 0) +
                      repo.get('watchers_count', 0) +
                      repo.get('forks_count', 0)),
            'star': repo.get('stargazers_count', 0),
            'link': repo.get('html_url'),
            'created_at': repo.get('created_at'),
            'updated_at': repo.get('updated_at'),
            'pushed_at_dt': dt,                                     # 用于排序
            'pushed_at': dt.strftime('%Y-%m-%d %H:%M:%S'),          # 用于展示
            'name': repo.get('name'),
            'description': (repo.get('description') or '')
        })

    # Top by star
    top_repos = sorted(processed, key=lambda x: x['star'], reverse=True)[:TOP_REPO_NUM]
    # Recent by pushed time
    recent_repos = sorted(processed, key=lambda x: x['pushed_at_dt'], reverse=True)[:RECENT_REPO_NUM]

    result['top_repos'] = top_repos
    result['recent_repos'] = recent_repos
    return result


def render(github_username, github_data) -> str:
    """
    生成 README 文本。
    已将 LeetCode/知乎 换成：
      - GitHub 活跃度图
      - 访客计数
      - GitHub streak（两张不同主题）
    """
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
  <img src="https://streak-stats.demolab.com?user={{github_username}}&theme=tokyonight&hide_border=true&v={cache_bust}" width="100%" />
</p>

<!-- GitHub streak 连续提交天数（主题2） -->
<p>
  <img src="https://streak-stats.demolab.com?user={{github_username}}&theme=default&hide_border=false&v={cache_bust}" width="100%" />
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
    return md


def writer(markdown) -> bool:
    try:
        with open('./README.md', 'w', encoding='utf-8') as f:
            f.write(markdown)
        return True
    except IOError:
        print('unable to write to file')
        return False


def pusher():
    commit_message = f":pencil2: update on {current_time}"
    os.system('git add ./README.md')
    if os.getenv('DEBUG'):
        return
    os.system(f'git commit -m "{commit_message}" || echo "no changes"')
    os.system('git push || true')


def main():
    # 读取用户名（未设置则用当前目录名）
    github_username = os.getenv('GITHUB_USERNAME')
    if not github_username:
        cwd = os.getcwd()
        github_username = os.path.split(cwd)[-1]

    data = fetcher(github_username)
    md = render(github_username, data)
    if writer(md):
        pass
        # 如需自动提交，取消下一行注释
        # pusher()


if __name__ == '__main__':
    main()
