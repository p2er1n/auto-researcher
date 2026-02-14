# AutoResearcher

> 自动研究助手 - 基于 GitHub Actions 的自动化网站生成与部署工具

## 项目简介

AutoResearcher 是一个利用 GitHub Actions 实现的自动化工具，它能够：

1. **定时执行** - 根据设定的固定时间间隔自动运行
2. **数据采集** - 爬取指定网站或获取指定 API 的内容
3. **智能筛选** - 根据配置好的规则过滤出需要的内容
4. **模板生成** - 将筛选后的内容传入模板生成静态网站
5. **自动部署** - 通过 GitHub Actions 部署到 GitHub Pages

## 目录结构

```
auto-researcher/
├── src/                    # Python 程序源代码
├── templates/              # 网站模板代码
├── dists/                  # 每次执行生成的网站
│   ├── 2026-2-14-12/      # 2026年2月14日12点生成的网站
│   └── index.html         # 网站根目录，列举所有生成的网站
├── requirements.txt        # Python 依赖
└── config.yaml            # 配置文件
```

## 配置文件说明

### config.yaml

配置文件用于定义采集任务、筛选规则和模板参数。

```yaml
# 采集任务配置
tasks:
  - name: "科技新闻"
    interval: "6h"  # 执行间隔
    
    # 数据源
    sources:
      - type: "api"
        url: "https://api.example.com/news"
        method: "GET"
      - type: "web"
        url: "https://news.example.com"
        selector: ".article-list .item"
    
    # 筛选规则
    filters:
      - type: "regex"
        pattern: "\\d{4}-\\d{2}-\\d{2}"
        action: "keep"
      - type: "keyword"
        keywords: ["AI", "技术", "科技"]
        action: "keep"
    
    # 模板配置
    template: "news-template"
    output: "tech-news"

# 全局设置
settings:
  timezone: "Asia/Shanghai"
  max_workers: 3
  timeout: 30
```

## 工作流程

```
┌─────────────────┐
│ GitHub Actions │
│   定时触发     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  读取 config   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  执行采集任务   │
│ (Python爬虫/API)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   内容筛选     │
│ (正则/关键词)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  模板生成网站  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  部署到Pages   │
└─────────────────┘
```

## 快速开始

1. 克隆仓库
2. 安装依赖：`pip install -r requirements.txt`
3. 修改 `config.yaml` 配置你的任务
4. 提交推送，GitHub Actions 会自动执行

## GitHub Actions

工作流程文件位于 `.github/workflows/auto-researcher.yml`，负责：
- 定时触发任务
- 安装 Python 环境
- 运行采集程序
- 生成静态网站
- 部署到 GitHub Pages
# Force rebuild
