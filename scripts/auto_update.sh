#!/bin/bash
# 高报Agent 数据自动更新脚本
# 用法: crontab -e → 0 3 * * 0 /path/to/auto_update.sh

PROJECT_DIR="/home/dev/projects/xuefeng/xuefeng-advisor"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/auto_update_$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

echo "=== 数据更新开始 $(date) ===" >> "$LOG_FILE"

cd "$PROJECT_DIR"

# 1. 检查百度高考 API 是否有新数据
python3 scripts/update_data.py --province all --year 2025 --with-yfdd >> "$LOG_FILE" 2>&1

echo "=== 数据更新完成 $(date) ===" >> "$LOG_FILE"

# 2. 清理 30 天前的日志
find "$LOG_DIR" -name "auto_update_*.log" -mtime +30 -delete
