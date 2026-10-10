# 基于 Python 3.11 slim
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 系统依赖（sqlite3 等）
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 curl && \
    rm -rf /var/lib/apt/lists/*

# 复制锁定依赖并安装（确保构建可重复性）
# retries/timeout：PyPI 在 CI 网络下偶发读超时，默认 5 次/15s 不足以完成 ~115 个包的解析
COPY requirements.lock .
RUN pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.lock

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
