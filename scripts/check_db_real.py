#!/usr/bin/env python3
"""实时数据库状态快照 - 使用绝对路径"""
import json
import os
import sqlite3

DB = '/home/dev/projects/gaobao/gaobao-advisor/data/gaokao.db'

# Try with timeout for locked DB
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()
c.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = [r[0] for r in c.fetchall()]
print(f'数据库表: {tables}')

# Find the right table name
score_table = None
for t in tables:
    if 'score' in t.lower() and t not in ('graduate_score',):
        score_table = t
        break

if not score_table:
    print('未找到分数表!')
    conn.close()
    exit(1)

print(f'使用分数表: {score_table}')
print()

print('=== 当前数据库统计 ===')
c.execute(f'SELECT COUNT(*) FROM {score_table}')
print(f'总分数记录: {c.fetchone()[0]} 条')

c.execute(f'SELECT year, COUNT(*) FROM {score_table} GROUP BY year ORDER BY year')
for r in c.fetchall():
    print(f'  {r[0]}年: {r[1]} 条')

c.execute(f'SELECT COUNT(DISTINCT school_id) FROM {score_table}')
has = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM schools')
total = c.fetchone()[0]
print(f'有分数院校: {has}/{total} ({has*100//total}%)')

print()
print('=== Checkpoint状态 ===')
data_dir = '/home/dev/projects/gaobao/gaobao-advisor/data'
for f in ['import_checkpoint.json', 'import_checkpoint_2025.json']:
    fpath = os.path.join(data_dir, f)
    try:
        d = json.load(open(fpath))
        stats = d.get('stats', {})
        print(f'{f}: {d["school_index"]}/{d["total_schools"]} - {d.get("current_school", "?")}')
        print(f'  请求: {stats.get("requests",0)}, 新增: {stats.get("new_scores",0)}, 错误: {stats.get("errors",0)}')
    except Exception as e:
        print(f'{f}: {e}')

print()
print('=== 层级覆盖情况（2025年） ===')
c.execute(f"""
    SELECT s.is_double_first_class,
           CASE WHEN s.ranking IS NOT NULL AND s.ranking <= 300 AND s.is_double_first_class = 0 THEN 1 ELSE 0 END as is_key,
           CASE WHEN s.school_type = '专科' THEN 1 ELSE 0 END as is_vocational,
           COUNT(DISTINCT s.id) as total,
           COUNT(DISTINCT CASE WHEN a.id IS NOT NULL AND a.year=2025 THEN s.id END) as has_2025
    FROM schools s
    LEFT JOIN {score_table} a ON s.id = a.school_id
    GROUP BY s.is_double_first_class,
             CASE WHEN s.ranking IS NOT NULL AND s.ranking <= 300 AND s.is_double_first_class = 0 THEN 1 ELSE 0 END,
             CASE WHEN s.school_type = '专科' THEN 1 ELSE 0 END
    ORDER BY s.is_double_first_class DESC,
             CASE WHEN s.ranking IS NOT NULL AND s.ranking <= 300 AND s.is_double_first_class = 0 THEN 1 ELSE 0 END DESC
""")
for r in c.fetchall():
    if r[0] == 1:
        label = 'L1 双一流'
    elif r[1] == 1:
        label = 'L2 省属重点'
    elif r[2] == 1:
        label = 'L4 专科'
    else:
        label = 'L3 一般本科'
    print(f'{label}: {r[3]} 校, {r[4]} 有2025数据 ({r[4]*100//r[3]}%)')

conn.close()
