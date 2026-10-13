# 合成演示流程（不提供真实志愿建议）

此文件只定义可以通过当前开源代码复现的演示步骤，**不是模型实际生成记录**。

旧版本曾包含带真实学校名称、真实省份分数和未经验证录取结论的示例对话。这些内容既不对应当前合成数据库，也不能证明本项目的咨询准确性，因此不在当前示例中展示。

## 演示目标

1. 在无 LLM Key 的情况下启动后端并检查 `/api/v1/health`。
2. 读取 `/api/v1/data/schools?limit=3`，确认有合成学校数据。
3. 检查 `data_profile = SYNTHETIC_DEMO`，以及 `optional_services.rag.state = RAG_DISABLED`。
4. 根据 [README](../README.md) 启动前端，观察 Chat / Report / Profile / Admin 四个视图；前端交互需要独立运行 Vite。
5. 如需验证多轮对话、槽位补齐和 SSE，参考 [`server/routes/chat.py`](../server/routes/chat.py) 与相关测试；不要将模板回复当成经过真实招生数据校验的建议。

## 复现命令

```bash
docker build -t gb-advisor .
docker run --rm -p 8000:8000 gb-advisor

# 另一个终端
curl http://localhost:8000/api/v1/health
curl "http://localhost:8000/api/v1/data/schools?limit=3"
```

更多步骤见 [TUTORIAL.md](../TUTORIAL.md)。任何从合成数据生成的报告都仅用于软件行为演示，不应用于实际选校。
