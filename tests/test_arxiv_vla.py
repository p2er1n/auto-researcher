#!/usr/bin/env python3
"""
测试 arXiv RSS 采集和 VLA 关键词过滤
"""

import sys
from pathlib import Path

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import Config
from crawler import Crawler
from filter import ContentFilter


def main():
    print("=" * 60)
    print("AutoResearcher 测试 - arXiv VLA 论文")
    print("=" * 60)
    
    # 加载配置
    config_path = Path(__file__).parent.parent / "config.yaml"
    print(f"\n1. 加载配置: {config_path}")
    config = Config.load(config_path)
    print(f"   任务: {config.tasks[0].name}")
    print(f"   数据源: {[s.type for s in config.tasks[0].sources]}")
    print(f"   筛选关键词: {config.tasks[0].filters[0].keywords}")
    print(f"   大小写敏感: {config.tasks[0].filters[0].case_sensitive}")
    
    # 创建爬虫
    print("\n2. 初始化爬虫...")
    crawler = Crawler(config)
    
    # 执行任务
    task = config.tasks[0]
    print(f"\n3. 采集 arXiv RSS 数据...")
    raw_data = crawler.fetch(task)
    print(f"   采集到 {len(raw_data)} 条论文")
    
    if not raw_data:
        print("\n❌ 没有采集到任何数据!")
        return
    
    # 打印采集到的分类统计
    from collections import Counter
    sources = Counter(item.source for item in raw_data)
    print("\n   各分类论文数量:")
    for src, count in sources.most_common():
        print(f"   - {src}: {count}")
    
    # 过滤
    print("\n4. 应用过滤规则...")
    content_filter = ContentFilter(task)
    filtered_data = content_filter.filter(raw_data)
    print(f"   过滤后剩余 {len(filtered_data)} 条")
    
    # 打印结果
    print("\n" + "=" * 60)
    if filtered_data:
        print(f"找到 {len(filtered_data)} 篇 VLA 相关论文:")
        print("=" * 60)
        
        for i, item in enumerate(filtered_data[:10], 1):
            print(f"\n【{i}】{item.title[:100]}")
            print(f"    日期: {item.date}")
            print(f"    来源: {item.source}")
            if item.authors:
                print(f"    作者: {', '.join(item.authors[:3])}")
            if item.url:
                print(f"    链接: {item.url}")
    else:
        print("❌ 没有找到匹配的论文")
        print("\n可能的原因:")
        print("  1. 最近没有包含 'VLA' 的新论文")
        print("  2. 可以尝试扩大搜索分类 (cs.AI, cs.LG, cs.CV, cs.RO, cs.NE)")
        print("  3. 可以尝试关闭大小写敏感 (case_sensitive: false)")
        
        # 显示一些样本标题供参考
        print("\n参考 - 最近采集到的论文标题:")
        for item in raw_data[:5]:
            print(f"  - {item.title[:80]}")
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()
