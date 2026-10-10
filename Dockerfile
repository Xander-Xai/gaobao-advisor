# syntax=docker/dockerfile:1.7
# 基于 Python 3.11 slim
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 系统依赖（sqlite3 等）
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 curl && \
    rm -rf /var/lib/apt/lists/*

# 复制锁定依赖并安装（确保构建可重复性）
# 依赖来源只有一个可信索引：官方 PyPI。wheels/ 是可选的本地离线包目录，
# 在没有外网或网络抖动时由 `pip download` 预先填充；目录为空时 pip 自动回退到索引。
COPY requirements.lock .
COPY wheels /wheels/
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    if ls /wheels/*.whl >/dev/null 2>&1; then \
        echo "installing from local wheelhouse (offline)"; \
        pip install --no-index --find-links /wheels -r requirements.lock; \
    else \
        echo "installing from $PIP_INDEX_URL"; \
        pip install --index-url "$PIP_INDEX_URL" --retries 10 --timeout 120 -r requirements.lock; \
    fi

# 复制项目代码（排除 .git, data, .env 等通过 .dockerignore）
COPY . .

# 创建 data 目录并设置权限
RUN mkdir -p data && chmod 700 data

# 创建非特权用户并设置权限
RUN useradd -m appuser && chown -R appuser:appuser /app

# 环境变量（运行时通过 .env 或 docker-compose 注入）
ENV PYTHONUNBUFFERED=1

# 健康检查 — FastAPI 健康端点
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

EXPOSE 8000

USER appuser

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
