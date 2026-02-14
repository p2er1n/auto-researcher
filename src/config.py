"""
配置加载模块
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

import yaml
from loguru import logger


@dataclass
class SourceConfig:
    """数据源配置"""
    type: str  # "api" or "web"
    name: str
    url: str
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    selector: Optional[str] = None
    fields: Optional[Dict[str, str]] = None
    auth: Optional[Dict[str, str]] = None


@dataclass
class FilterConfig:
    """筛选规则配置"""
    type: str  # "regex", "keyword", "length", "deduplicate", "date"
    pattern: Optional[str] = None
    action: str = "keep"
    keywords: Optional[List[str]] = None
    match: str = "any"  # "any" or "all"
    min: Optional[int] = None
    max: Optional[int] = None
    fields: Optional[List[str]] = None
    # 新增: 筛选范围
    scope: str = "all"  # "all"(全部), "title"(仅标题), "abstract"(仅摘要), "title_only"(仅标题), "content_only"(仅内容)
    # 新增: 大小写敏感
    case_sensitive: bool = False
    # 新增: 日期过滤（支持小时和天）
    days: Optional[int] = None
    hours: Optional[int] = None  # 新增：支持按小时过滤


@dataclass
class TaskConfig:
    """任务配置"""
    name: str
    interval: str
    sources: List[SourceConfig]
    filters: List[FilterConfig]
    template: str
    output: str
    variables: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SettingsConfig:
    """全局设置"""
    timezone: str = "Asia/Shanghai"
    max_workers: int = 3
    timeout: int = 30
    retry: int = 3
    user_agent: str = "AutoResearcher/1.0"


@dataclass
class GitHubConfig:
    """GitHub 配置"""
    branch: str = "gh-pages"
    dir: str = "dists/latest"
    token: Optional[str] = None
    repo: Optional[str] = None


@dataclass
class Config:
    """完整配置"""
    tasks: List[TaskConfig]
    settings: SettingsConfig
    github: Optional[GitHubConfig] = None
    
    @classmethod
    def load(cls, path: Path) -> "Config":
        """从 YAML 文件加载配置"""
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        # 解析任务
        tasks = []
        for task_data in data.get("tasks", []):
            sources = []
            for source_data in task_data.get("sources", []):
                source = SourceConfig(
                    type=source_data["type"],
                    name=source_data.get("name", ""),
                    url=source_data["url"],
                    method=source_data.get("method", "GET"),
                    headers=source_data.get("headers", {}),
                    selector=source_data.get("selector"),
                    fields=source_data.get("fields"),
                    auth=source_data.get("auth"),
                )
                sources.append(source)
            
            filters = []
            for filter_data in task_data.get("filters", []):
                filter_cfg = FilterConfig(
                    type=filter_data["type"],
                    pattern=filter_data.get("pattern"),
                    action=filter_data.get("action", "keep"),
                    keywords=filter_data.get("keywords"),
                    match=filter_data.get("match", "any"),
                    min=filter_data.get("min"),
                    max=filter_data.get("max"),
                    fields=filter_data.get("fields"),
                    scope=filter_data.get("scope", "all"),
                    case_sensitive=filter_data.get("case_sensitive", False),
                )
                filters.append(filter_cfg)
            
            task = TaskConfig(
                name=task_data["name"],
                interval=task_data.get("interval", "6h"),
                sources=sources,
                filters=filters,
                template=task_data.get("template", "default"),
                output=task_data.get("output", "output"),
                variables=task_data.get("variables", {}),
            )
            tasks.append(task)
        
        # 解析全局设置
        settings_data = data.get("settings", {})
        settings = SettingsConfig(
            timezone=settings_data.get("timezone", "Asia/Shanghai"),
            max_workers=settings_data.get("max_workers", 3),
            timeout=settings_data.get("timeout", 30),
            retry=settings_data.get("retry", 3),
            user_agent=settings_data.get("user_agent", "AutoResearcher/1.0"),
        )
        
        # 解析 GitHub 配置
        github_data = data.get("github")
        github = None
        if github_data:
            github = GitHubConfig(
                branch=github_data.get("branch", "gh-pages"),
                dir=github_data.get("dir", "dists/latest"),
                token=github_data.get("token"),
                repo=github_data.get("repo"),
            )
        
        return cls(tasks=tasks, settings=settings, github=github)
