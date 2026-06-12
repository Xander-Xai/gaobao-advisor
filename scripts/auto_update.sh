#!/bin/bash
# 高报Agent 数据自动更新脚本 v2
# 用法: crontab -e → 0 2 * * 1 /path/to/auto_update.sh
# 功能: 每周一凌晨 2:00 自动增量同步最新数据

PROJECT_DIR="/home/dev/projects/gaobao/gaobao-advisor"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/auto_update_$(date +%Y%m%d).log"
CHECKPOINT="$PROJECT_DIR/data/import_checkpoint.json"

mkdir -p "$LOG_DIR"
mkdir -p "$PROJECT_DIR/data"

echo "=== 数据更新开始 $(date) ===" >> "$LOG_FILE"

cd "$PROJECT_DIR"

# 1. 检查磁盘空间（< 1GB 则停止）
AVAIL_KB=$(df -k "$PROJECT_DIR" | tail -1 | awk '{print $4}')
if [ "$AVAIL_KB" -lt 1048576 ]; then
    echo "[ERROR] 磁盘空间不足 1GB，跳过更新" >> "$LOG_FILE"
    exit 1
fi

# 2. 增量同步院校信息（补全新增院校）
echo "[1/3] 同步院校列表..." >> "$LOG_FILE"
python3 scripts/import_baidu_gaokao.py --schools-only >> "$LOG_FILE" 2>&1

# 3. 增量同步分数线（从断点继续，无断点则跳过）
if [ -f "$CHECKPOINT" ]; then
    echo "[2/3] 从断点继续分数线采集..." >> "$LOG_FILE"
    python3 scripts/import_baidu_gaokao.py --scores-only --resume >> "$LOG_FILE" 2>&1
else
    echo "[2/3] 无断点文件，跳过分数线采集" >> "$LOG_FILE"
fi

# 4. 统计
echo "[3/3] 数据统计..." >> "$LOG_FILE"
python3 -c "
from db.database import init_db, get_session
from db.models import School, AdmissionScore
init_db()
db = get_session()
print(f'院校: {db.query(School).count()}')
print(f'录取分数: {db.query(AdmissionScore).count()}')
db.close()
" >> "$LOG_FILE" 2>&1

echo "=== 数据更新完成 $(date) ===" >> "$LOG_FILE"

# 5. 清理 30 天前的日志
find "$LOG_DIR" -name "auto_update_*.log" -mtime +30 -delete
