"""
数据采集模块
支持从 API 和网页采集数据
"""

import asyncio
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup
from loguru import logger

from config import Config, TaskConfig, SourceConfig


@dataclass
class FetchedItem:
    """采集到的单条数据"""
    source: str
    title: str
    content: str
    url: Optional[str] = None
    date: Optional[str] = None
    metadata: Dict[str, Any] = None
    authors: Optional[List[str]] = None
    abstract: Optional[str] = None
    categories: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class Crawler:
    """数据采集器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.settings.user_agent
        })
    
    def fetch(self, task: TaskConfig) -> List[FetchedItem]:
        """执行采集任务"""
        all_data = []
        
        for source in task.sources:
            try:
                if source.type == "api":
                    data = self._fetch_api(source)
                elif source.type == "web":
                    data = self._fetch_web(source)
                elif source.type == "arxiv":
                    data = self._fetch_arxiv(source)
                elif source.type == "arxiv_rss":
                    data = self._fetch_arxiv_rss(source)
                elif source.type == "acl_anthology":
                    data = self._fetch_acl_anthology(source)
                elif source.type == "semantic_scholar":
                    data = self._fetch_semantic_scholar(source)
                elif source.type == "dblp":
                    data = self._fetch_dblp(source)
                else:
                    logger.warning(f"未知数据源类型: {source.type}")
                    continue
                
                all_data.extend(data)
                logger.info(f"从 {source.name} 采集到 {len(data)} 条数据")
                
            except Exception as e:
                logger.error(f"采集 {source.name} 失败: {e}")
                continue
        
        return all_data
    
    def _fetch_api(self, source: SourceConfig) -> List[FetchedItem]:
        """从 API 获取数据"""
        kwargs = {
            "url": source.url,
            "method": source.method,
            "timeout": self.config.settings.timeout,
        }
        
        # 添加 headers
        headers = dict(source.headers)
        if source.auth:
            if source.auth.get("type") == "bearer":
                headers["Authorization"] = f"Bearer {source.auth.get('token', '')}"
        kwargs["headers"] = headers
        
        # 发送请求
        response = self.session.request(**kwargs)
        response.raise_for_status()
        
        # 解析 JSON
        try:
            json_data = response.json()
        except Exception as e:
            logger.error(f"解析 JSON 失败: {e}")
            return []
        
        # 转换为自己需要的格式
        items = []
        if isinstance(json_data, list):
            data_list = json_data
        elif isinstance(json_data, dict):
            # 尝试找到数据列表
            data_list = json_data.get("data", []) or [json_data]
        else:
            logger.warning(f"未知的 JSON 格式: {type(json_data)}")
            return []
        
        for idx, item in enumerate(data_list):
            if isinstance(item, dict):
                title = item.get("title", item.get("name", f"Item {idx}"))
                content = item.get("content", item.get("description", item.get("body", "")))
                url = item.get("url", item.get("link"))
                date = item.get("date", item.get("created_at", item.get("published")))
            else:
                title = str(item)
                content = str(item)
                url = None
                date = None
            
            items.append(FetchedItem(
                source=source.name,
                title=title,
                content=content,
                url=url,
                date=date,
                metadata={"raw": item}
            ))
        
        return items
    
    def _fetch_web(self, source: SourceConfig) -> List[FetchedItem]:
        """从网页获取数据"""
        response = self.session.get(
            source.url,
            timeout=self.config.settings.timeout
        )
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "lxml")
        
        # 如果指定了选择器
        if source.selector:
            elements = soup.select(source.selector)
        else:
            elements = [soup]
        
        items = []
        for element in elements:
            # 提取字段
            if source.fields:
                title = element.select_one(source.fields.get("title", "h1")).get_text(strip=True) if element.select_one(source.fields.get("title", "h1")) else ""
                content = element.select_one(source.fields.get("content", ".content")).get_text(strip=True) if element.select_one(source.fields.get("content", ".content")) else ""
                date = element.select_one(source.fields.get("date", ".date"))
                date = date.get_text(strip=True) if date else None
            else:
                # 默认提取标题和内容
                title = element.select_one("h1, h2, h3, title")
                title = title.get_text(strip=True) if title else ""
                content = element.get_text(strip=True)
                date = element.select_one("[datetime], time, .date")
                date = date.get_text(strip=True) if date else None
            
            items.append(FetchedItem(
                source=source.name,
                title=title or "Untitled",
                content=content,
                url=source.url,
                date=date,
                metadata={"html": str(element)}
            ))
        
        return items
    
    def _fetch_arxiv(self, source: SourceConfig) -> List[FetchedItem]:
        """从 arXiv 获取论文"""
        import urllib.parse
        from datetime import datetime
        
        # 解析 arXiv 配置
        search_query = source.auth.get("search_query", "all") if source.auth else "all"
        max_results = source.auth.get("max_results", 10) if source.auth else 10
        sort_by = source.auth.get("sort_by", "submittedDate") if source.auth else "submittedDate"
        sort_order = source.auth.get("sort_order", "descending") if source.auth else "descending"
        categories = source.auth.get("categories", []) if source.auth else []
        
        # 构建查询
        # 如果有多个类别，用 OR 连接；如果没有类别，则只使用 search_query
        if categories:
            cat_queries = []
            for cat in categories:
                if cat.startswith("cat:"):
                    cat_queries.append(cat)
                else:
                    cat_queries.append(f"cat:{cat}")
            
            if search_query and search_query != "all":
                # 如果有额外的搜索查询，与类别用 AND 连接
                categories_query = "+OR+".join(cat_queries)
                query = f"{search_query}+AND+({categories_query})"
            else:
                # 只搜索类别
                query = "+OR+".join(cat_queries)
        else:
            # 只使用搜索查询
            query = search_query
        
        # 构建 API URL
        base_url = "https://export.arxiv.org/api/query"
        params = {
            "search_query": query,
            "max_results": max_results,
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }
        
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        logger.info(f"查询 arXiv API: {url}")
        
        response = self.session.get(url, timeout=self.config.settings.timeout)
        response.raise_for_status()
        
        # 解析 XML 响应
        logger.info(f"arXiv API 响应长度: {len(response.text)}")
        soup = BeautifulSoup(response.text, "xml")
        entries = soup.find_all("entry")
        
        logger.info(f"arXiv API 返回条目数: {len(entries)}")
        
        items = []
        for entry in entries:
            # 提取论文信息
            title = entry.find("title")
            title = title.get_text(strip=True).replace("\n", " ") if title else ""
            
            summary = entry.find("summary")
            abstract = summary.get_text(strip=True).replace("\n", " ") if summary else ""
            
            # 作者
            authors = []
            for author in entry.find_all("author"):
                name = author.find("name")
                if name:
                    authors.append(name.get_text(strip=True))
            
            # 日期
            published = entry.find("published")
            date = published.get_text(strip=True) if published else None
            
            # 分类
            categories_list = []
            for cat in entry.find_all("category"):
                term = cat.get("term")
                if term:
                    categories_list.append(term)
            
            # PDF URL
            pdf_link = entry.find("link", {"title": "pdf"})
            url = pdf_link.get("href") if pdf_link else None
            
            # arXiv ID
            arxiv_id = entry.find("id")
            arxiv_id = arxiv_id.get_text(strip=True).split("/")[-1] if arxiv_id else None
            
            items.append(FetchedItem(
                source=source.name,
                title=f"[{arxiv_id}] {title}" if arxiv_id else title,
                content=abstract,
                url=url,
                date=date,
                authors=authors,
                abstract=abstract,
                categories=categories_list,
                metadata={
                    "arxiv_id": arxiv_id,
                    "raw": str(entry)
                }
            ))
        
        return items
    
    def _fetch_arxiv_rss(self, source: SourceConfig) -> List[FetchedItem]:
        """从 arXiv RSS/Atom 获取最新论文
        
        使用 rss.arxiv.org 获取每日更新的论文列表
        """
        import warnings
        from bs4 import XMLParsedAsHTMLWarning
        
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        
        categories = source.auth.get("categories", []) if source.auth else []
        
        if not categories:
            logger.warning("arXiv RSS 需要指定分类")
            return []
        
        items = []
        
        # 使用 rss.arxiv.org (新版) + 号连接多分类
        categories_str = "+".join(categories)
        
        # 尝试 RSS 格式
        url = f"https://rss.arxiv.org/rss/{categories_str}"
        logger.info(f"获取 arXiv RSS: {url}")
        
        try:
            response = self.session.get(url, timeout=self.config.settings.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "xml")
            
            # 查找 item 元素
            entries = soup.find_all("item")
            
            # 如果 RSS 没数据，尝试 ATOM
            if not entries:
                url = f"https://rss.arxiv.org/atom/{categories_str}"
                logger.info(f"RSS 无数据，尝试 ATOM: {url}")
                response = self.session.get(url, timeout=self.config.settings.timeout)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "xml")
                entries = soup.find_all("entry")
            
            logger.info(f"arXiv RSS 返回 {len(entries)} 条")
            
            for entry in entries:
                # 提取论文信息
                title = entry.find("title")
                title = title.get_text(strip=True).replace("\n", " ") if title else ""
                
                # 摘要
                description = entry.find("description")
                summary = entry.find("summary")
                abstract = None
                if description:
                    abstract = description.get_text(strip=True).replace("\n", " ")
                elif summary:
                    abstract = summary.get_text(strip=True).replace("\n", " ")
                
                # 作者
                authors = []
                author_tags = entry.find_all("author")
                for author in author_tags:
                    name = author.find("name")
                    if name:
                        authors.append(name.get_text(strip=True))
                
                # 日期
                date = None
                pub_date = entry.find("pubDate")
                if pub_date:
                    date_str = pub_date.get_text(strip=True)
                    try:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(date_str)
                        date = dt.isoformat()
                    except:
                        pass
                
                if not date:
                    published = entry.find("published")
                    if published:
                        date = published.get_text(strip=True)
                
                # 分类
                categories_list = []
                cat_tags = entry.find_all("category")
                for cat_tag in cat_tags:
                    term = cat_tag.get_text(strip=True)
                    if term:
                        categories_list.append(term)
                
                # 获取链接
                link = entry.find("link")
                paper_url = None
                arxiv_id = None
                if link:
                    paper_url = link.get_text(strip=True)
                    if not paper_url:
                        paper_url = link.get("href")
                
                # 从 URL 提取 arXiv ID
                if paper_url and "arxiv.org" in paper_url:
                    arxiv_id = paper_url.split("/")[-1]
                    if ".pdf" in arxiv_id:
                        arxiv_id = arxiv_id.replace(".pdf", "")
                
                # 如果没有 PDF 链接，尝试构建
                if arxiv_id and not paper_url:
                    paper_url = f"https://arxiv.org/abs/{arxiv_id}"
                
                # 论文标题加上 ID
                title = f"[{arxiv_id}] {title}" if arxiv_id else title
                
                if title:
                    items.append(FetchedItem(
                        source=source.name,
                        title=title,
                        content=abstract or "",
                        url=paper_url,
                        date=date,
                        authors=authors,
                        abstract=abstract,
                        categories=categories_list,
                        metadata={
                            "arxiv_id": arxiv_id,
                            "source": "arxiv_rss"
                        }
                    ))
                    
        except Exception as e:
            logger.error(f"获取 arXiv RSS 失败: {e}")
        
        # 按日期排序，最新的在前
        items.sort(key=lambda x: x.date or "", reverse=True)
        
        # 限制数量
        max_results = source.auth.get("max_results", 20) if source.auth else 20
        return items[:max_results]
    
    def _fetch_acl_anthology(self, source: SourceConfig) -> List[FetchedItem]:
        """从 ACL Anthology 获取论文 (ACL, EMNLP, NAACL, etc.)"""
        import warnings
        from bs4 import XMLParsedAsHTMLWarning
        
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        
        conferences = source.auth.get("conferences", []) if source.auth else []
        max_results = source.auth.get("max_results", 20) if source.auth else 20
        
        items = []
        
        rss_url = "https://aclanthology.org/rss-feed.xml"
        
        logger.info("获取 ACL Anthology 论文")
        
        try:
            response = self.session.get(rss_url, timeout=self.config.settings.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "lxml")
            entries = soup.find_all("item")
            
            for entry in entries:
                title_elem = entry.find("title")
                title = title_elem.get_text(strip=True) if title_elem else "Untitled"
                
                link_elem = entry.find("link")
                paper_url = link_elem.get_text(strip=True) if link_elem else None
                
                desc_elem = entry.find("description")
                abstract = desc_elem.get_text(strip=True) if desc_elem else ""
                
                pub_date_elem = entry.find("pubDate")
                date = None
                if pub_date_elem:
                    from email.utils import parsedate_to_datetime
                    try:
                        dt = parsedate_to_datetime(pub_date_elem.get_text(strip=True))
                        date = dt.isoformat()
                    except:
                        pass
                
                categories = []
                for cat in entry.find_all("category"):
                    cat_text = cat.get_text(strip=True)
                    if cat_text:
                        categories.append(cat_text)
                
                conference = None
                for cat in categories:
                    if cat in ["ACL", "EMNLP", "NAACL", "EACL", "COLING", "AAACL", "Findings"]:
                        conference = cat
                        break
                
                if conferences and conference not in conferences:
                    continue
                
                items.append(FetchedItem(
                    source=source.name,
                    title=title,
                    content=abstract,
                    url=paper_url,
                    date=date,
                    authors=[],
                    abstract=abstract,
                    categories=categories,
                    metadata={"conference": conference, "source": "acl_anthology"}
                ))
                
        except Exception as e:
            logger.error(f"获取 ACL Anthology 失败: {e}")
        
        items.sort(key=lambda x: x.date or "", reverse=True)
        return items[:max_results]
    
    def _fetch_semantic_scholar(self, source: SourceConfig) -> List[FetchedItem]:
        """从 Semantic Scholar 获取论文"""
        query = source.auth.get("query", "") if source.auth else ""
        limit = source.auth.get("max_results", 20) if source.auth else 20
        
        if not query:
            logger.warning("Semantic Scholar 需要指定查询 (query)")
            return []
        
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {"query": query, "limit": limit, "fields": "title,abstract,authors,year,venue,url"}
        
        logger.info(f"搜索 Semantic Scholar: {query}")
        response = self.session.get(url, params=params, timeout=self.config.settings.timeout)
        response.raise_for_status()
        
        data = response.json()
        papers = data.get("data", [])
        
        items = []
        for paper in papers:
            title = paper.get("title", "Untitled")
            abstract = paper.get("abstract") or ""
            year = paper.get("year")
            venue = paper.get("venue", "")
            
            authors = [a.get("name") for a in paper.get("authors", []) if a.get("name")]
            
            items.append(FetchedItem(
                source=source.name,
                title=title,
                content=abstract,
                url=paper.get("url"),
                date=str(year) if year else None,
                authors=authors,
                abstract=abstract,
                categories=[venue] if venue else [],
                metadata={"paperId": paper.get("paperId"), "venue": venue, "source": "semantic_scholar"}
            ))
        
        return items
    
    def _fetch_dblp(self, source: SourceConfig) -> List[FetchedItem]:
        """从 DBLP 获取顶会和期刊论文
        
        支持两种方式:
        1. 搜索 API: 通过关键词搜索论文
        2. RSS 订阅: 获取最新会议论文集，然后筛选
        """
        import warnings
        from bs4 import XMLParsedAsHTMLWarning
        
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        
        # 搜索模式
        query = source.auth.get("query", "") if source.auth else ""
        max_results = source.auth.get("max_results", 20) if source.auth else 20
        
        # RSS 订阅模式
        conferences = source.auth.get("conferences", []) if source.auth else []
        
        items = []
        
        # 方式1: 关键词搜索 (已有实现)
        if query:
            items.extend(self._fetch_dblp_search(query, max_results))
        
        # 方式2: RSS 订阅 - 获取最新会议论文集
        if conferences:
            rss_items = self._fetch_dblp_rss(conferences, max_results)
            items.extend(rss_items)
        
        # 去重
        seen = set()
        unique_items = []
        for item in items:
            if item.title not in seen:
                seen.add(item.title)
                unique_items.append(item)
        
        return unique_items[:max_results]
    
    def _fetch_dblp_search(self, query: str, max_results: int) -> List[FetchedItem]:
        """使用 DBLP 搜索 API"""
        import json
        
        search_term = query.replace(" ", "+")
        api_url = f"https://dblp.org/search/publ/api?q={search_term}&h={max_results}&format=json"
        
        logger.info(f"DBLP 搜索: {query}")
        items = []
        
        try:
            response = self.session.get(api_url, timeout=self.config.settings.timeout)
            response.raise_for_status()
            
            data = response.json()
            hits = data.get("result", {}).get("hits", {})
            hit_list = hits.get("hit", [])
            
            for hit in hit_list:
                info = hit.get("info", {})
                title = info.get("title", "Untitled")
                title = title.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                
                authors_data = info.get("authors", {}).get("author", [])
                if isinstance(authors_data, dict):
                    authors_data = [authors_data]
                authors = [a.get("text", "") for a in authors_data if a.get("text")]
                
                venue = info.get("venue", "")
                year = info.get("year", "")
                paper_url = info.get("ee", "") or info.get("url", "")
                doi = info.get("doi", "")
                
                # 如果是 DOI 链接且包含 arXiv，转换为直接 arXiv 链接
                if paper_url and "doi.org" in paper_url and "arXiv" in paper_url:
                    arxiv_id = paper_url.split("arXiv.")[-1] if "arXiv." in paper_url else ""
                    if arxiv_id:
                        paper_url = f"https://arxiv.org/abs/{arxiv_id}"
                
                items.append(FetchedItem(
                    source=f"DBLP/{venue}" if venue else "DBLP",
                    title=title,
                    content=f"{venue} ({year})",
                    url=paper_url,
                    date=year if year else None,
                    authors=authors,
                    abstract=f"{title}. {venue} ({year})",
                    categories=[venue] if venue else [],
                    metadata={"source": "dblp", "venue": venue, "year": year, "doi": doi}
                ))
            
            logger.info(f"DBLP 搜索获取到 {len(items)} 条")
            
        except Exception as e:
            logger.error(f"DBLP 搜索失败: {e}")
        
        return items
    
    def _fetch_dblp_rss(self, conferences: List[str], max_results: int) -> List[FetchedItem]:
        """从 DBLP 获取最新会议论文
        
        工作流程:
        1. 从 RSS feed 获取最新会议/期刊列表
        2. 匹配目标会议，获取其详情页链接
        3. 解析详情页获取论文列表
        """
        items = []
        
        # 1. 先从 RSS feed 获取会议列表
        rss_url = "https://dblp.org/feed/"
        logger.info("获取 DBLP RSS 源")
        
        try:
            response = self.session.get(rss_url, timeout=self.config.settings.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "xml")
            channel = soup.find("channel")
            if not channel:
                logger.warning("无法解析 DBLP RSS")
                return items
        except Exception as e:
            logger.error(f"获取 DBLP RSS 失败: {e}")
            return items
        
        # 2. 从 RSS 中提取匹配的会议链接
        conf_urls = {}  # conf_name -> url
        for item in channel.find_all("item"):
            title_elem = item.find("title")
            link_elem = item.find("link")
            if not title_elem or not link_elem:
                continue
            
            title = title_elem.get_text(strip=True)
            link = link_elem.get_text(strip=True)
            
            # 检查是否匹配目标会议
            for conf in conferences:
                if conf.lower() in title.lower():
                    conf_urls[conf.upper()] = link
                    logger.info(f"从 RSS 匹配到会议: {title} -> {link}")
                    break
        
        # 3. 解析每个会议的详情页
        for conf_name, conf_url in conf_urls.items():
            logger.info(f"解析会议论文: {conf_name} from {conf_url}")
            
            try:
                conf_response = self.session.get(conf_url, timeout=self.config.settings.timeout)
                if conf_response.status_code != 200:
                    continue
                
                conf_soup = BeautifulSoup(conf_response.text, "lxml")
                
                # 查找论文列表 - 新版 DBLP 使用 li.entry
                paper_count = 0
                for paper in conf_soup.find_all("li", class_="entry"):
                    if paper_count >= max_results:
                        break
                    
                    # 提取标题
                    title_elem = paper.find("span", class_="title")
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    
                    # 提取作者
                    authors = []
                    for author in paper.find_all("span", class_="author"):
                        author_name = author.get_text(strip=True)
                        if author_name:
                            authors.append(author_name)
                    
                    # 提取链接
                    paper_url = None
                    for link in paper.find_all("a", href=True):
                        href = link.get("href", "")
                        if href.endswith(".pdf"):
                            paper_url = href
                            break
                        elif "dblp.org/rec/" in href:
                            paper_url = href
                    
                    # 提取年份
                    year_elem = paper.find("span", class_="year")
                    year = year_elem.get_text(strip=True) if year_elem else ""
                    
                    if title:
                        items.append(FetchedItem(
                            source=f"DBLP RSS/{conf_name}",
                            title=title,
                            content=f"{conf_name} {year}",
                            url=paper_url,
                            date=year,
                            authors=authors,
                            abstract=title,
                            categories=[conf_name],
                            metadata={
                                "source": "dblp_rss",
                                "venue": conf_name,
                                "year": year
                            }
                        ))
                        paper_count += 1
                
                logger.info(f"从 {conf_name} 获取到 {paper_count} 篇论文")
                
            except Exception as e:
                logger.error(f"解析 {conf_name} 失败: {e}")
                continue
        
        # 去重并限制数量
        seen = set()
        unique_items = []
        for item in items:
            if item.title not in seen:
                seen.add(item.title)
                unique_items.append(item)
        
        logger.info(f"DBLP RSS 共获取 {len(unique_items)} 篇论文")
        return unique_items[:max_results]
    
    def close(self):
        """关闭会话"""
        self.session.close()
