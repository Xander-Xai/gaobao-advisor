# 基于 Python 3.11 slim
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 系统依赖（sqlite3 等）
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 curl && \
    rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码（排除 .git, data, .env 等通过 .dockerignore）
COPY . .

# 创建 data 目录并设置权限
RUN mkdir -p data && chmod 700 data

# 环境变量（运行时通过 .env 或 docker-compose 注入）
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
