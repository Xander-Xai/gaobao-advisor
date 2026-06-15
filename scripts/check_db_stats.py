#!/usr/bin/env python3
"""实时数据库状态快照"""
import json
import sqlite3

conn = sqlite3.connect('data/gaokao.db')
c = conn.cursor()
print('=== 当前数据库统计 ===')
c.execute('SELECT COUNT(*) FROM admission_scores')
print(f'总分数记录: {c.fetchone()[0]} 条')
c.execute('SELECT year, COUNT(*) FROM admission_scores GROUP BY year ORDER BY year')
for r in c.fetchall():
    print(f'  {r[0]}年: {r[1]} 条')
c.execute('SELECT COUNT(DISTINCT school_id) FROM admission_scores')
has = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM schools')
total = c.fetchone()[0]
print(f'有分数院校: {has}/{total} ({has*100//total}%)')
print()
print('=== Checkpoint状态 ===')
for f in ['import_checkpoint.json', 'import_checkpoint_2025.json']:
    try:
        d = json.load(open(f'data/{f}'))
        stats = d.get('stats', {})
        print(f'{f}: {d["school_index"]}/{d["total_schools"]} - {d.get("current_school", "?")}')
        print(f'  请求: {stats.get("requests",0)}, 新增: {stats.get("new_scores",0)}, 错误: {stats.get("errors",0)}')
    except Exception as e:
        print(f'{f}: {e}')
conn.close()

print()
print('=== 层级覆盖情况 ===')
c = sqlite3.connect('data/gaokao.db').cursor()
c.execute("""
    SELECT s.is_double_first_class,
           CASE WHEN s.ranking IS NOT NULL AND s.ranking <= 300 AND s.is_double_first_class = 0 THEN 1 ELSE 0 END as is_key,
           CASE WHEN s.school_type = '专科' THEN 1 ELSE 0 END as is_vocational,
           COUNT(DISTINCT s.id) as total,
           COUNT(DISTINCT CASE WHEN a.id IS NOT NULL THEN s.id END) as has_data
    FROM schools s
    LEFT JOIN admission_scores a ON s.id = a.school_id
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
    print(f'{label}: {r[3]} 校, {r[4]} 有数据 ({r[4]*100//r[3]}%)')
c.close()

