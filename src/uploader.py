"""
上传部署模块
将生成的网站部署到 GitHub Pages
"""

import os
import subprocess
from pathlib import Path
from typing import Optional

from loguru import logger

from config import Config, GitHubConfig


class Uploader:
    """GitHub Pages 上传器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.github = config.github
    
    def upload(self, dist_path: Path):
        """上传到 GitHub Pages"""
        if not self.github:
            logger.warning("未配置 GitHub 部署")
            return
        
        # 检查 git 仓库
        repo_path = Path.cwd()
        git_dir = repo_path / ".git"
        
        if not git_dir.exists():
            logger.error("当前目录不是 git 仓库")
            return
        
        # 检查 token
        token = self.github.token or os.environ.get("GITHUB_TOKEN")
        if not token:
            logger.warning("未设置 GITHUB_TOKEN，将使用 git push")
        
        # 部署
        self._deploy(dist_path)
    
    def _deploy(self, dist_path: Path):
        """执行部署"""
        branch = self.github.branch
        
        # 检查 gh-pages 分支是否存在
        result = subprocess.run(
            ["git", "rev-parse", "--verify", branch],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            # 分支不存在，创建它
            logger.info(f"创建分支: {branch}")
            subprocess.run(["git", "checkout", "--orphan", branch], check=True)
        else:
            # 分支存在，切换到它
            subprocess.run(["git", "checkout", branch], check=True)
        
        # 移除旧内容
        for item in Path(".").iterdir():
            if item.name in [".git", ".github", "src", "templates", "config.yaml", "requirements.txt"]:
                continue
            if item.is_dir():
                import shutil
                shutil.rmtree(item)
            else:
                item.unlink()
        
        # 复制新内容
        import shutil
        for item in dist_path.iterdir():
            if item.name == ".git":
                continue
            dest = Path(item.name)
            if item.is_dir():
                shutil.copytree(item, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest)
        
        # 提交
        subprocess.run(["git", "add", "-A"], check=True)
        
        # 检查是否有更改
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if not result.stdout.strip():
            logger.info("没有新内容需要提交")
            return
        
        subprocess.run([
            "git", "commit", "-m",
            f"AutoResearcher: 更新网站 ({dist_path.name})"
        ], check=True)
        
        # 推送
        logger.info(f"推送到 {branch} 分支...")
        
        # 获取远程 URL
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True
        )
        remote_url = result.stdout.strip()
        
        # 如果有 token，替换 URL
        token = self.github.token or os.environ.get("GITHUB_TOKEN")
        if token and "github.com" in remote_url:
            # 将 https://github.com/ 替换为带 token 的 URL
            remote_url = remote_url.replace(
                "https://github.com/",
                f"https://x-access-token:{token}@github.com/"
            )
        
        subprocess.run(["git", "push", "origin", branch, "--force"], check=True)
        
        logger.info(f"部署完成! 网站将在 GitHub Pages 上可用")
