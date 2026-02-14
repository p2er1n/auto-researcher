"""
模板渲染模块
使用 Jinja2 模板生成静态网站
"""

import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from loguru import logger

from config import TaskConfig
from crawler import FetchedItem


class TemplateRenderer:
    """模板渲染器"""
    
    def __init__(self, task: TaskConfig, output_dir: Path):
        self.task = task
        self.output_dir = Path(output_dir)
        
        # 模板目录
        template_dir = Path("templates") / task.template
        if not template_dir.exists():
            template_dir = Path(__file__).parent.parent / "templates" / task.template
        
        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"])
        )
        
        # 添加自定义过滤器
        self.env.filters["date"] = self._format_date
        self.env.filters["truncate"] = self._truncate
    
    def render(self, items: List[FetchedItem]) -> Path:
        """渲染模板生成网站"""
        # 生成输出目录 (带时间戳)
        timestamp = datetime.now().strftime("%Y-%m-%d-%H")
        dist_dir = self.output_dir / timestamp
        dist_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"渲染网站到: {dist_dir}")
        
        # 准备数据
        data = {
            "task": self.task,
            "items": items,
            "generated_at": datetime.now().isoformat(),
            "timestamp": timestamp,
            **self.task.variables
        }
        
        # 尝试渲染 index.html
        try:
            template = self.env.get_template("index.html")
            html = template.render(**data)
            
            index_path = dist_dir / "index.html"
            index_path.write_text(html, encoding="utf-8")
            logger.info(f"已生成: {index_path}")
        except Exception as e:
            logger.warning(f"渲染 index.html 失败: {e}")
        
        # 复制静态资源
        static_dir = self.template_dir / "static"
        if static_dir.exists():
            dest_static = dist_dir / "static"
            shutil.copytree(static_dir, dest_static, dirs_exist_ok=True)
            logger.info(f"已复制静态资源: {dest_static}")
        
        return dist_dir
    
    def update_index(self):
        """更新根目录 index.html，列出所有生成的网站"""
        # 获取所有带时间戳的目录
        dist_dirs = sorted(
            [d for d in self.output_dir.iterdir() if d.is_dir() and d.name[0].isdigit()],
            reverse=True
        )
        
        if not dist_dirs:
            return
        
        # 准备数据
        sites = []
        for dist_dir in dist_dirs[:10]:  # 只显示最近10个
            index_file = dist_dir / "index.html"
            if index_file.exists():
                # 尝试从 HTML 中提取标题
                try:
                    html = index_file.read_text(encoding="utf-8")
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, "html.parser")
                    title = soup.title.string if soup.title else dist_dir.name
                except:
                    title = dist_dir.name
                
                sites.append({
                    "name": dist_dir.name,
                    "title": title,
                    "url": f"{dist_dir.name}/index.html"
                })
        
        # 渲染 index 模板
        try:
            template = self.env.get_template("index_list.html")
            html = template.render(sites=sites, generated_at=datetime.now().isoformat())
            
            index_path = self.output_dir / "index.html"
            index_path.write_text(html, encoding="utf-8")
            logger.info(f"已更新网站列表: {index_path}")
        except Exception as e:
            # 如果没有 index_list.html，创建一个简单的
            html = self._generate_simple_index(sites)
            index_path = self.output_dir / "index.html"
            index_path.write_text(html, encoding="utf-8")
            logger.info(f"已更新网站列表: {index_path}")
    
    def _generate_simple_index(self, sites: List[Dict]) -> str:
        """生成简单的索引页面"""
        lines = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<meta charset='utf-8'>",
            "<title>AutoResearcher - 网站列表</title>",
            "<style>",
            "body { font-family: system-ui; max-width: 800px; margin: 50px auto; padding: 20px; }",
            "h1 { color: #333; }",
            "ul { list-style: none; padding: 0; }",
            "li { padding: 10px; margin: 5px 0; background: #f5f5f5; border-radius: 4px; }",
            "a { color: #0066cc; text-decoration: none; }",
            "a:hover { text-decoration: underline; }",
            "</style>",
            "</head>",
            "<body>",
            "<h1>AutoResearcher - 网站列表</h1>",
            "<ul>",
        ]
        
        for site in sites:
            lines.append(f'<li><a href="{site["name"]}/index.html">{site["title"]}</a> ({site["name"]})</li>')
        
        lines.extend([
            "</ul>",
            "</body>",
            "</html>",
        ])
        
        return "\n".join(lines)
    
    @staticmethod
    def _format_date(value, format="%Y-%m-%d %H:%M:%S"):
        """格式化日期"""
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return dt.strftime(format)
            except:
                return value
        elif isinstance(value, datetime):
            return value.strftime(format)
        return str(value)
    
    @staticmethod
    def _truncate(value, length=100, suffix="..."):
        """截断文本"""
        if len(value) <= length:
            return value
        return value[:length].rstrip() + suffix
