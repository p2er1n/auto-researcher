"""
AutoResearcher - 自动研究助手
"""

__version__ = "0.1.0"
__author__ = "AutoResearcher"

from .config import Config, TaskConfig, SourceConfig, FilterConfig
from .crawler import Crawler, FetchedItem
from .filter import ContentFilter
from .renderer import TemplateRenderer

__all__ = [
    "Config",
    "TaskConfig", 
    "SourceConfig",
    "FilterConfig",
    "Crawler",
    "FetchedItem",
    "ContentFilter",
    "TemplateRenderer",
]
