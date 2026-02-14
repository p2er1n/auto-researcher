#!/usr/bin/env python3
"""
AutoResearcher - 自动研究助手
主入口文件
"""

import argparse
import sys
from pathlib import Path

from loguru import logger

from config import Config
from crawler import Crawler
from filter import ContentFilter
from renderer import TemplateRenderer
from uploader import Uploader


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="AutoResearcher - 自动网站生成工具")
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="配置文件路径 (默认: config.yaml)"
    )
    parser.add_argument(
        "-o", "--output",
        default="dists",
        help="输出目录 (默认: dists)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细日志"
    )
    return parser.parse_args()


def setup_logging(verbose: bool = False):
    """配置日志"""
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    )


def main():
    """主函数"""
    args = parse_args()
    setup_logging(args.verbose)
    
    logger.info("AutoResearcher 启动...")
    
    # 加载配置
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"配置文件不存在: {config_path}")
        sys.exit(1)
    
    config = Config.load(config_path)
    logger.info(f"已加载配置: {config_path}")
    
    # 创建输出目录
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 遍历任务执行
    for task in config.tasks:
        logger.info(f"执行任务: {task.name}")
        
        # 1. 采集数据
        crawler = Crawler(config)
        raw_data = crawler.fetch(task)
        logger.info(f"采集到 {len(raw_data)} 条数据")
        
        # 2. 筛选内容
        content_filter = ContentFilter(task)
        filtered_data = content_filter.filter(raw_data)
        logger.info(f"筛选后剩余 {len(filtered_data)} 条数据")
        
        # 3. 生成网站
        renderer = TemplateRenderer(task, output_dir)
        dist_path = renderer.render(filtered_data)
        logger.info(f"网站生成完成: {dist_path}")
        
        # 4. 更新 index
        renderer.update_index()
        
        # 5. 上传到 GitHub Pages
        if config.github:
            uploader = Uploader(config)
            uploader.upload(dist_path)
            logger.info("已部署到 GitHub Pages")
    
    logger.info("所有任务执行完成!")


if __name__ == "__main__":
    main()
