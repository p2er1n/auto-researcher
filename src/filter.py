"""
内容筛选模块
根据配置规则过滤内容
"""

import re
from typing import List
from dataclasses import dataclass, field

from loguru import logger

from config import TaskConfig, FilterConfig
from crawler import FetchedItem


class ContentFilter:
    """内容筛选器"""
    
    def __init__(self, task: TaskConfig):
        self.task = task
        self.filters = task.filters
    
    def filter(self, items: List[FetchedItem]) -> List[FetchedItem]:
        """执行所有筛选规则"""
        filtered = items
        
        for filter_config in self.filters:
            filter_type = filter_config.type
            
            if filter_type == "regex":
                filtered = self._filter_regex(filtered, filter_config)
            elif filter_type == "keyword":
                filtered = self._filter_keyword(filtered, filter_config)
            elif filter_type == "length":
                filtered = self._filter_length(filtered, filter_config)
            elif filter_type == "deduplicate":
                filtered = self._filter_deduplicate(filtered, filter_config)
            elif filter_type == "date":
                filtered = self._filter_date(filtered, filter_config)
            else:
                logger.warning(f"未知的筛选类型: {filter_type}")
        
        return filtered
    
    def _filter_regex(self, items: List[FetchedItem], config: FilterConfig) -> List[FetchedItem]:
        """正则表达式筛选"""
        if not config.pattern:
            return items
        
        # 获取筛选范围和大小写敏感配置
        scope = getattr(config, 'scope', 'all')
        case_sensitive = getattr(config, 'case_sensitive', False)
        
        # 编译正则表达式
        flags = 0 if case_sensitive else re.IGNORECASE
        pattern = re.compile(config.pattern, flags)
        
        filtered = []
        
        for item in items:
            # 根据 scope 确定要搜索的文本
            if scope == "title" or scope == "title_only":
                search_text = item.title
            elif scope == "abstract" or scope == "content_only":
                search_text = item.abstract or item.content
            else:
                search_text = item.title + " " + (item.abstract or item.content)
            
            match = pattern.search(search_text)
            
            should_keep = (config.action == "keep" and match) or \
                         (config.action == "remove" and not match)
            
            if should_keep:
                filtered.append(item)
        
        return filtered
    
    def _filter_keyword(self, items: List[FetchedItem], config: FilterConfig) -> List[FetchedItem]:
        """关键词筛选"""
        if not config.keywords:
            return items
        
        # 获取筛选范围和大小写敏感配置
        # scope: "all"(默认), "title"(仅标题), "abstract"(仅摘要), "title_only"(仅标题), "content_only"(仅内容)
        scope = getattr(config, 'scope', 'all')
        
        # 大小写敏感: 默认 False (不敏感)
        case_sensitive = getattr(config, 'case_sensitive', False)
        
        keywords = config.keywords
        if not case_sensitive:
            keywords = [k.lower() for k in keywords]
        
        filtered = []
        
        for item in items:
            # 根据 scope 确定要搜索的文本
            if scope == "title" or scope == "title_only":
                # 仅搜索标题
                search_text = item.title
            elif scope == "abstract" or scope == "content_only":
                # 仅搜索摘要/内容
                search_text = item.abstract or item.content
            else:
                # 搜索标题 + 摘要/内容
                search_text = item.title + " " + (item.abstract or item.content)
            
            # 大小写处理
            if not case_sensitive:
                search_text = search_text.lower()
            
            # 检查匹配
            matched = any(kw in search_text for kw in keywords)
            
            if config.match == "all":
                # 所有关键词都匹配
                should_keep = matched and all(kw in search_text for kw in keywords)
            else:
                # 任意关键词匹配
                should_keep = matched
            
            # action: keep = 保留匹配的, remove = 移除匹配的
            should_keep = should_keep if config.action == "keep" else not should_keep
            
            if should_keep:
                filtered.append(item)
        
        return filtered
    
    def _filter_length(self, items: List[FetchedItem], config: FilterConfig) -> List[FetchedItem]:
        """长度筛选"""
        filtered = []
        
        for item in items:
            text = item.title + " " + item.content
            length = len(text)
            
            if config.min is not None and length < config.min:
                continue
            if config.max is not None and length > config.max:
                continue
            
            filtered.append(item)
        
        return filtered
    
    def _filter_deduplicate(self, items: List[FetchedItem], config: FilterConfig) -> List[FetchedItem]:
        """去重筛选"""
        if not config.fields:
            # 默认按标题去重
            fields = ["title"]
        else:
            fields = config.fields
        
        seen = set()
        filtered = []
        
        for item in items:
            # 生成唯一键
            key_parts = []
            for field in fields:
                if field == "title":
                    key_parts.append(item.title)
                elif field == "content":
                    key_parts.append(item.content[:100])  # 取前100字符
                elif field == "url" and item.url:
                    key_parts.append(item.url)
            
            key = "|".join(key_parts)
            
            if key not in seen:
                seen.add(key)
                filtered.append(item)
        
        return filtered
    
    def _filter_date(self, items: List[FetchedItem], config: FilterConfig) -> List[FetchedItem]:
        """日期筛选 - 只保留最近 N 天/小时的论文"""
        # 支持 days 或 hours
        days = config.days or 0
        hours = config.hours or 0
        
        if days == 0 and hours == 0:
            return items
        
        from datetime import datetime, timedelta
        
        # 计算截止时间
        if hours > 0:
            cutoff_date = datetime.now() - timedelta(hours=hours)
        else:
            cutoff_date = datetime.now() - timedelta(days=days)
        
        filtered = []
        
        for item in items:
            # 尝试解析日期
            item_date = None
            
            # 尝试从各种字段获取日期
            if item.date:
                # 尝试多种日期格式
                date_formats = [
                    "%Y-%m-%d",
                    "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M:%S",
                    "%d %b %Y",
                    "%Y",
                ]
                for fmt in date_formats:
                    try:
                        item_date = datetime.strptime(str(item.date).strip(), fmt)
                        break
                    except:
                        continue
            
            # 如果没有日期，跳过过滤（保留）
            if not item_date:
                logger.debug(f"论文无日期信息，跳过日期过滤: {item.title[:50]}")
                filtered.append(item)
                continue
            
            # 检查是否在日期范围内
            if item_date >= cutoff_date:
                filtered.append(item)
            else:
                logger.debug(f"论文日期过旧 ({item.date})，已过滤: {item.title[:50]}")
        
        logger.info(f"日期过滤: {len(items)} -> {len(filtered)} (保留 {hours if hours > 0 else days} {'小时' if hours > 0 else '天'}内)")
        
        return filtered
