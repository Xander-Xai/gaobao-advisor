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
# BuildKit pip 缓存挂载：CI 网络抖动时可复用已下载的 wheel，避免整层重来。
# 索引固定为官方 PyPI，不引入第三方镜像源。
COPY requirements.lock .
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --index-url "$PIP_INDEX_URL" --retries 10 --timeout 120 -r requirements.lock

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
