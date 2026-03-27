import base64
import requests


class GitHubAPI:
    """GitHub API 封装"""

    def __init__(self, token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        self.base_url = "https://api.github.com"

    def get_file(self, repo: str, path: str, branch: str = "main") -> dict:
        """获取文件内容和 SHA"""
        url = f"{self.base_url}/repos/{repo}/contents/{path}"
        resp = self.session.get(url, params={"ref": branch})
        resp.raise_for_status()
        return resp.json()

    def create_file(
        self,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str,
    ) -> dict:
        """创建新文件"""
        url = f"{self.base_url}/repos/{repo}/contents/{path}"
        encoded = base64.b64encode(content.encode()).decode()
        payload = {
            "message": message,
            "content": encoded,
            "branch": branch,
        }
        resp = self.session.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    def update_file(
        self,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str,
        sha: str,
    ) -> dict:
        """更新已有文件"""
        url = f"{self.base_url}/repos/{repo}/contents/{path}"
        encoded = base64.b64encode(content.encode()).decode()
        payload = {
            "message": message,
            "content": encoded,
            "branch": branch,
            "sha": sha,
        }
        resp = self.session.put(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    def create_branch(self, repo: str, branch: str, from_sha: str) -> dict:
        """创建新分支"""
        url = f"{self.base_url}/repos/{repo}/git/refs"
        payload = {"sha": from_sha, "ref": f"refs/heads/{branch}"}
        resp = self.session.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    def create_pr(
        self,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> dict:
        """创建 Pull Request"""
        url = f"{self.base_url}/repos/{repo}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
        }
        resp = self.session.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

    def comment_on_issue(self, repo: str, issue_number: int, body: str) -> dict:
        """在 issue 上评论"""
        url = f"{self.base_url}/repos/{repo}/issues/{issue_number}/comments"
        resp = self.session.post(url, json={"body": body})
        resp.raise_for_status()
        return resp.json()

    def fork_repo(self, repo: str) -> dict:
        """Fork 仓库"""
        url = f"{self.base_url}/repos/{repo}/forks"
        resp = self.session.post(url)
        resp.raise_for_status()
        return resp.json()
