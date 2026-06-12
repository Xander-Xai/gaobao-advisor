# 高考数据管线扩展设计文档

**日期**: 2026-06-12
**状态**: 已批准
**任务**: 1.1 数据范围扩大 + 1.4 院校信息补全

---

## 1. 项目背景

### 1.1 当前数据库状态

| 数据表 | 数量 | 问题 |
|--------|------|------|
| 院校 (schools) | 3003 | ⚠️ 部分缺少城市/类型/排名信息 |
| 录取分数 (admission_scores) | 13453 | ⚠️ 仅覆盖 10 省 × 80 校 × 2024 年 |
| 一分一段 (yi_fen_yi_duan) | 0 | ❌ 完全缺失 |
| 专业 (majors) | 215 | ⚠️ 仅有分类信息 |

### 1.2 API 覆盖探测结果

- ✅ **省份覆盖**: 30/31 省份可用（西藏无数据）
- ✅ **历史数据**: 2022-2024 三年完整
- ✅ **批次类型**: 本科批/本科提前批/本科一批等主要批次覆盖
- ✅ **Curriculum**: 3+3 综合 / 3+1+2 物理历史 / 传统文理全覆盖

### 1.3 采集目标

- 3003 所院校 × 30 省 × 3 年 × 2 curriculum
- 预计总请求量：52 万+（需分批执行）
- 执行策略：**分层渐进导入 + 定时同步**

---

## 2. 设计方案

### 2.1 方案选择：方案 B + C 组合

**阶段 1 - 立即执行（30 分钟）**：
- L1 双一流（147 所）+ L2 省属重点（~200 所）
- 优先交付高价值数据

**阶段 2 - 后台执行（分批）**：
- L3 一般本科（~1000 所）：每批 500 校
- L4 专科/职业（~1600 所）：每批 500 校

**阶段 3 - 定时同步**：
- 扩展 `scripts/auto_update.sh` 为每周自动更新
- 增量同步：只导入新增/变更数据

### 2.2 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                    数据管线架构                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │ 百度高考 API │───▶│ 采集器层     │───▶│ 数据库层     │   │
│  │ (外部数据源) │    │ baidu_gaokao │    │ SQLAlchemy   │   │
│  └─────────────┘    └──────────────┘    └──────────────┘   │
│                           │                       │        │
│                           ▼                       ▼        │
│                    ┌──────────────┐    ┌──────────────┐   │
│                    │ 断点续传     │    │ 数据校验     │   │
│                    │ checkpoint   │    │ integrity    │   │
│                    └──────────────┘    └──────────────┘   │
│                           │                       │        │
│                           ▼                       ▼        │
│                    ┌──────────────┐    ┌──────────────┐   │
│                    │ 进度追踪     │    │ 统计报表     │   │
│                    │ progress.json│    │ stats        │   │
│                    └──────────────┘    └──────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 详细设计

### 3.1 任务 1.1：数据范围扩大

#### 3.1.1 数据库增强

**schools 表新增字段**（已存在，验证完整性）：
- `website` (String 200): 官网 URL
- `description` (String 500): 院校简介
- `ranking` (Integer): 软科排名

**admission_scores 表验证**：
- `plan_count` (Integer): 招生计划数（已有）
- `avg_score` (Float): 平均分（已有）

#### 3.1.2 采集脚本增强

**文件**: `scripts/import_baidu_gaokao.py`

**新增参数**：
```bash
--full              # 全量模式（L1-L4 所有院校）
--resume            # 断点续传，从上次中断处继续
--layer N           # 指定层级（1=L1双一流, 2=L2省属重点, 3=L3本科, 4=L4专科）
--provinces ALL     # 31 省全覆盖
--checkpoint FILE   # 断点文件路径（默认 data/import_checkpoint.json）
```

**完整省份列表**（30 省，西藏排除）：
```python
ALL_PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古",
    "辽宁", "吉林", "黑龙江", "上海", "江苏", "浙江",
    "安徽", "福建", "江西", "山东", "河南", "湖北",
    "湖南", "广东", "广西", "海南", "重庆", "四川",
    "贵州", "云南", "陕西", "甘肃", "青海",
    "宁夏", "新疆"
]
```

#### 3.1.3 断点续传机制

**断点文件** `data/import_checkpoint.json`：
```json
{
  "last_run": "2026-06-12T15:30:00",
  "layer": "L3",
  "school_index": 523,
  "total_schools": 1200,
  "completed_provinces": ["北京", "天津", "..."],
  "current_school": "XX大学",
  "stats": {
    "new_scores": 12500,
    "errors": 15,
    "requests": 85000
  }
}
```

**恢复逻辑**：
```python
if args.resume and os.path.exists(checkpoint_file):
    with open(checkpoint_file) as f:
        checkpoint = json.load(f)
    start_school = checkpoint["school_index"]
    completed = checkpoint["completed_provinces"]
    # 从断点处继续
```

#### 3.1.4 错误处理与重试

```python
MAX_RETRIES = 3
RETRY_DELAY = 1.5  # 秒，指数退避

for attempt in range(MAX_RETRIES):
    try:
        scores = fetch_school_score(school, province, year, curriculum)
        break
    except Exception as e:
        if attempt < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY * (attempt + 1))
        else:
            log_error(school, province, year, e)
            continue  # 单条失败不影响整体
```

#### 3.1.5 批次提交与进度追踪

```python
COMMIT_INTERVAL = 50  # 每 50 条提交
PROGRESS_INTERVAL = 100  # 每 100 校保存进度

if (stats["new_scores"] % COMMIT_INTERVAL) == 0:
    db.commit()
    save_checkpoint(checkpoint_file, stats)

if (school_index % PROGRESS_INTERVAL) == 0:
    print(f"进度: {school_index}/{total_schools} 校完成")
```

---

### 3.2 任务 1.4：院校信息补全

#### 3.2.1 数据来源

- **百度高考院校列表 API**: `https://gaokao.baidu.com/gk/gkschool/list`
- **采集函数**: `iter_schools()` (已实现)

#### 3.2.2 补充字段映射

| 目标字段 | API 字段 | 转换逻辑 | 示例 |
|----------|----------|----------|------|
| name | `college_name` | strip() | "北京大学" |
| province | `province` | 直接 | "北京" |
| city | `city` 或 `location` | 直接 | "北京" |
| level | `tag[]` | `parse_school_tags()` | "985" |
| school_type | `school_type` | 直接 | "综合" |
| ranking | `rank` | `safe_int()` | 1 |
| is_985 | `tag[]` | 包含 "985" ? 1:0 | 1 |
| is_211 | `tag[]` | 包含 "211" ? 1:0 | 1 |
| is_double_first_class | `tag[]` | 包含 "双一流" ? 1:0 | 1 |
| description | `tag_text` | 直接 | "教育部直属..." |

#### 3.2.3 增量更新逻辑

```python
def update_school_info(db_session, School):
    """增量更新院校信息，不覆盖已有数据"""
    stats = {"updated": 0, "new": 0, "skipped": 0}
    
    for item in iter_schools():
        name = item.get("college_name", "").strip()
        if not name:
            continue
        
        existing = db_session.query(School).filter(School.name == name).first()
        
        if existing:
            # 增量更新：只填充空字段
            if not existing.city:
                existing.city = item.get("city", "") or item.get("location", "")
            if not existing.ranking:
                existing.ranking = safe_int(item.get("rank"))
            if not existing.description:
                existing.description = item.get("tag_text", "")
            stats["updated"] += 1
        else:
            # 新增院校
            school = School(
                name=name,
                province=item.get("province", ""),
                city=item.get("city", "") or item.get("location", ""),
                level=level,
                school_type=item.get("school_type", "综合"),
                ranking=safe_int(item.get("rank")),
                is_985=is_985,
                is_211=is_211,
                is_double_first_class=is_dfc,
                description=item.get("tag_text", ""),
            )
            db_session.add(school)
            stats["new"] += 1
        
        # 每 50 条提交
        if (stats["new"] + stats["updated"]) % 50 == 0:
            db_session.commit()
    
    db_session.commit()
    return stats
```

---

## 4. 执行计划

### 4.1 阶段 1：立即执行（L1+L2，约 40 分钟）

```bash
# 1. 补全院校信息（~10 分钟）
cd gaobao/gaobao-advisor
python scripts/import_baidu_gaokao.py --schools-only --max-schools 3000

# 2. 导入双一流分数线（~15 分钟）
python scripts/import_baidu_gaokao.py --layer 1 --top-n 147 --provinces ALL --years 2024 2023 2022

# 3. 导入省属重点分数线（~25 分钟）
python scripts/import_baidu_gaokao.py --layer 2 --top-n 300 --provinces ALL --years 2024 2023 2022
```

**预计耗时**：
- 院校信息补全：10 分钟（3000 条 API 请求，0.4s/请求）
- L1 分数线：147 校 × 30 省 × 3 年 × 2 curriculum × 0.4s ≈ 106k 秒，限流后约 15 分钟
- L2 分数线：300 校 × 30 省 × 3 年 × 2 curriculum × 0.4s ≈ 216k 秒，限流后约 25 分钟

### 4.2 阶段 2：后台执行（L3+L4，分批）

```bash
# L3 一般本科（每批 500 校）
nohup python scripts/import_baidu_gaokao.py --layer 3 --resume --batch-size 500 &

# L4 专科（每批 500 校）
nohup python scripts/import_baidu_gaokao.py --layer 4 --resume --batch-size 500 &
```

**预计耗时**：
- L3: 1000 校 × 30 × 3 × 2 × 0.4s ≈ 720k 秒 / 3000 ≈ 6 小时
- L4: 1600 校 × 30 × 3 × 2 × 0.4s ≈ 1.15M 秒 / 3000 ≈ 10 小时

### 4.3 阶段 3：定时同步

**扩展 `scripts/auto_update.sh`**：
```bash
#!/bin/bash
# 每周一凌晨 2:00 自动同步最新数据
cd /path/to/gaobao-advisor
python scripts/import_baidu_gaokao.py --resume --sync-mode incremental
```

**配置 crontab**：
```crontab
0 2 * * 1 /path/to/scripts/auto_update.sh >> /var/log/gaokao_update.log 2>&1
```

---

## 5. 验证与测试

### 5.1 单元测试

- `test_import_baidu_gaokao.py`: 测试采集逻辑
- `test_checkpoint_resume.py`: 测试断点续传
- `test_school_update.py`: 测试院校信息增量更新

### 5.2 集成测试

```bash
# 小规模验证
python scripts/import_baidu_gaokao.py --layer 1 --top-n 5 --provinces 北京

# 检查数据完整性
python -c "
from db.database import init_db, get_session
from db.models import AdmissionScore
db = get_session()
print('分数记录数:', db.query(AdmissionScore).count())
db.close()
"
```

### 5.3 数据质量检查

```python
def validate_import():
    """验证导入数据质量"""
    checks = {
        "学校完整性": "school_id IS NOT NULL",
        "省份完整性": "province IS NOT NULL",
        "年份合理性": "year BETWEEN 2022 AND 2024",
        "分数合理性": "min_score BETWEEN 100 AND 750",
        "位次合理性": "min_rank > 0 OR min_rank IS NULL",
    }
    # 执行检查并生成报告
```

---

## 6. 监控与告警

### 6.1 进度监控

- 实时打印进度：`[INFO] 523/3003 校完成 (17.4%)`
- 保存 checkpoint：每 100 校自动保存
- 日志记录：`data/import_YYYYMMDD.log`

### 6.2 错误告警

- 单校失败率 > 10%：暂停并通知
- API 被封（429/403）：自动退避并重试
- 数据库连接失败：立即停止并恢复

---

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| API 被封 | 中 | 高 | 限流 0.4s/请求，指数退避 |
| 网络中断 | 高 | 中 | 断点续传机制 |
| 数据库满 | 低 | 高 | 监控磁盘空间，定期清理旧数据 |
| 数据质量差 | 中 | 高 | 数据校验 + 人工审核 |

---

## 8. 成功标准

### 8.1 任务 1.1 完成标准

- [ ] 30 省 × 3 年数据覆盖率 > 95%
- [ ] 院校分数线记录数 > 100 万条
- [ ] 数据来源标注完整（T1/T2/T3 等级）
- [ ] 断点续传机制验证通过

### 8.2 任务 1.4 完成标准

- [ ] 3000+ 院校基础信息完整（省份/城市/类型/排名）
- [ ] 空字段率 < 5%
- [ ] 985/211 标记准确率 100%

---

## 9. 后续优化

### 9.1 性能优化

- 并行请求：使用 `asyncio` + `aiohttp` 加速（需评估 API 限制）
- 数据库索引：为 `province`, `year`, `school_id` 建立复合索引
- 缓存热点数据：Redis 缓存高频查询的分数线

### 9.2 功能扩展

- 一分一段表导入（任务 1.2）
- 招生计划完整导入（任务 1.3）
- 实时数据监控大盘

---

## 10. 附录

### 10.1 省份 → Curriculum 映射

```python
PROVINCE_CURRICULUMS = {
    # 3+3 综合（新高考六选三）
    "北京": ["3+3综合"], "天津": ["3+3综合"], "上海": ["3+3综合"],
    "山东": ["3+3综合"], "海南": ["3+3综合"], "浙江": ["3+3综合"],
    # 3+1+2（新高考物理/历史）
    "广东": ["物理类", "历史类"], "江苏": ["物理类", "历史类"],
    "河北": ["物理类", "历史类"], "辽宁": ["物理类", "历史类"],
    "重庆": ["物理类", "历史类"], "安徽": ["物理类", "历史类"],
    "福建": ["物理类", "历史类"], "湖北": ["物理类", "历史类"],
    "湖南": ["物理类", "历史类"], "广西": ["物理类", "历史类"],
    "江西": ["物理类", "历史类"], "贵州": ["物理类", "历史类"],
    "甘肃": ["物理类", "历史类"], "黑龙江": ["物理类", "历史类"],
    "吉林": ["物理类", "历史类"],
    # 传统文理分科
    "四川": ["理科", "文科"], "河南": ["理科", "文科"],
    "山西": ["理科", "文科"], "陕西": ["理科", "文科"],
    "云南": ["理科", "文科"], "内蒙古": ["理科", "文科"],
    "宁夏": ["理科", "文科"], "青海": ["理科", "文科"],
    "新疆": ["理科", "文科"],
}
```

### 10.2 API 请求模板

```
院校列表: https://gaokao.baidu.com/gk/gkschool/list?rn=50&pn={page}
院校分数线: https://gaokao.baidu.com/gk/gkschool/schoolscore?curriculum={c}&school={s}&province={p}&year={y}
专业分数线: https://gaokao.baidu.com/gk/gkschool/majorscore?rn=50&school={s}&province={p}&year={y}&pn={page}
招生计划: https://gaokao.baidu.com/gk/gkschool/getrecruitingscheme?curriculum={c}&school={s}&province={p}&year={y}
```

### 10.3 院校层级分类

```python
SCHOOL_LAYERS = {
    "L1": {"name": "双一流", "filter": "is_double_first_class == 1", "count": 147},
    "L2": {"name": "省属重点", "filter": "ranking <= 200", "count": "~200"},
    "L3": {"name": "一般本科", "filter": "school_type != '专科'", "count": "~1000"},
    "L4": {"name": "专科/职业", "filter": "school_type == '专科'", "count": "~1600"},
}
```
