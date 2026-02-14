#!/usr/bin/env python3
"""生成 index.html 的脚本"""
import os
import glob

dirs = []
for d in glob.glob('*/'):
    if os.path.isfile(os.path.join(d, 'index.html')):
        title = d
        try:
            with open(os.path.join(d, 'index.html'), 'r', encoding='utf-8') as f:
                c = f.read()
                if '<title>' in c and '</title>' in c:
                    s = c.find('<title>') + 7
                    e = c.find('</title>', s)
                    if e > s:
                        t = c[s:e].strip()
                        title = t.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        except:
            pass
        dirs.append({'name': d.rstrip('/'), 'title': title, 'mtime': os.path.getmtime(d)})

dirs.sort(key=lambda x: x['mtime'], reverse=True)

html = '''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>AutoResearcher - 网站列表</title>
<style>body{font-family:system-ui;max-width:900px;margin:50px auto;padding:20px}h1{color:#333}ul{list-style:none;padding:0}li{padding:12px;margin:8px 0;background:#f5f5f5;border-radius:6px}a{color:#0066cc;text-decoration:none;font-size:1.1em}a:hover{text-decoration:underline}.date{color:#888;font-size:0.85em;margin-left:10px}</style></head>
<body><h1>AutoResearcher - 网站列表</h1><ul>
'''
for d in dirs:
    html += f'<li><a href="{d["name"]}/index.html">{d["title"]}</a><span class="date">({d["name"]})</span></li>\n'
html += '</ul></body></html>'

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f'Generated index with {len(dirs)} entries')
