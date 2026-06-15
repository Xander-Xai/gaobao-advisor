# 异步并行采集器设计文档

> **项目**: gaobao-advisor（高考志愿AI顾问）
> **日期**: 2026-06-15
> **状态**: 已批准

## 1. 问题

百度高考 API 采集器当前为同步串行架构：

```
for school in schools:           # 3000 校
    for province in provinces:   # 30 省
        for year in years:       # 3 年
            for curriculum in curriculums:  # 2 课程
                fetch + 0.2s DELAY  # 串行
```

每校最多 180 次 API 调用（30省 × 3年 × 2课程），每次 0.2s 延迟 → 单校 36s → 全量 30 小时。

## 2. 方案：校内并行，校间串行

三阶段流水线：

```
阶段1: 扫描（同步）  →  阶段2: 并行获取（异步）  →  阶段3: 串行写入（同步）
检查已有数据               httpx.AsyncClient            SQLAlchemy commit
生成待获取列表             asyncio.gather()              按省份有序写入
```

### 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 并行粒度 | 校内，不是全局 | 保持 checkpoint 顺序，避免学校间竞态 |
| 异步库 | httpx.AsyncClient | 已安装，连接复用，不用新依赖 |
| 并发控制 | Semaphore(5) | 保守值，防限频 |
| DB 操作 | 主线程同步 | SQLAlchemy session 非线程安全 |
| 协议升级 | 无，后续可做 | 先保证正确，再优化速度 |
| 错误隔离 | 每请求独立 try/except | 一个省份失败不影响其它省份 |
| 回退 | `--async` 标志，默认 sync | 降级路径明确 |

### 数据流

```
为每个学校：
  1. build_tasks() → 生成 (province, year, curriculum) 列表
  2. 用 existing_count 过滤列表（DB 查询），输出 fetch_list
  3. asyncio.gather(async_fetch_school_score(...) for each in fetch_list)
  4. for each result in zip(fetch_list, results):
       if 有数据 → 去重检查 → INSERT → commit
  5. 保存 checkpoint
```

### 限频策略

- Semaphore(5)：最多 5 个并发连接
- 500/503/429 响应 → 立即释放 semaphore slot 并重试（最多 3 次）
- 连续错误（学校内 >50% 请求失败）→ 自动降低到 semaphore(2) 并 sleep(2)
- 全额失败 → 回退到同步模式处理该校

### 测试策略

- 单元测试：mock httpx.AsyncClient 返回固定的 JSON，验证 parse 逻辑
- 集成测试：用 `--async` 标志跑小数据集（2校 × 3省 × 1年），对比结果与 sync 模式一致
- 压力测试：Semaphore(10) 跑 10 校验证不会触发 API 限频

## 3. 改动清单

| 文件 | 改动 |
|------|------|
| `scrapers/baidu_gaokao.py` | +`async_fetch_json()` +`async_fetch_school_score()` +`import_scores_async()` +`build_fetch_tasks()` |
| `scripts/import_baidu_gaokao.py` | +`--async` 标志，调用 `import_scores_async` |
| `scripts/auto_update.sh` | 启用 `--async` 模式 |
| 依赖 | 无新增 |
| 文档 | 更新 `docs/data-pipeline-task-list.md` |

## 4. 成功标准

- [ ] async 模式与 sync 模式对同一学校集合输出一致（数据条数相同）
- [ ] 单一学校处理时间从 ~36s 降至 ~4s（5 并发）
- [ ] 全量 3000 校导入时间从 ~30h 降至 ~4h
- [ ] 655 测试继续通过
- [ ] 异常时降级到 sync 模式不丢数据