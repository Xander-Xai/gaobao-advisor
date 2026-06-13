#!/bin/bash
# 导入进度监控脚本
# 用法: bash scripts/monitor_import.sh

echo "=== 导入进度监控 $(date) ==="
echo ""

# 进程状态
if ps aux | grep import_baidu_gaokao | grep -v grep > /dev/null; then
    PID=$(ps aux | grep import_baidu_gaokao | grep -v grep | awk '{print $2}' | head -1)
    echo "✅ 进程运行中 (PID: $PID)"
else
    echo "❌ 进程已停止"
fi
echo ""

# Checkpoint 进度
if [ -f data/import_checkpoint.json ]; then
    python3 -c "
import json
with open('data/import_checkpoint.json') as f:
    d = json.load(f)
idx = d.get('school_index', 0)
total = d.get('total_schools', 0)
pct = idx * 100 // total if total else 0
stats = d['stats']
print(f'📊 进度: {idx}/{total} ({pct}%)')
print(f'   当前: {d.get(\"current_school\", \"?\")}')
print(f'   新增: {stats[\"new_scores\"]:,} | 请求: {stats[\"requests\"]:,} | 错误: {stats[\"errors\"]}')
"
else
    echo "📋 无 checkpoint 文件"
fi
echo ""

# 数据库统计
python3 -c "
from db.database import init_db, get_session
from db.models import AdmissionScore, School
from sqlalchemy import func
init_db()
db = get_session()
t = db.query(AdmissionScore).count()
s = db.query(AdmissionScore.school_id).distinct().count()
total_s = db.query(School).count()
print(f'💾 数据库:')
print(f'   分数: {t:,} 条')
print(f'   有数据院校: {s}/{total_s} ({s*100//total_s}%)')
print(f'   省份: {db.query(AdmissionScore.province).distinct().count()}/30')
years = db.query(AdmissionScore.year, func.count(AdmissionScore.id)).group_by(AdmissionScore.year).all()
for y, c in sorted(years, key=lambda x: -x[0]):
    print(f'   {y}年: {c:,}条')
db.close()
" 2>/dev/null
