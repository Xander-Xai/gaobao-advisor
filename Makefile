PYTHON ?= $(shell command -v python3 || command -v python)

.PHONY: install install-dev test test-cov lint lint-fix format run run-api clean help

help:  ## 显示帮助信息
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## 安装生产依赖
	pip install .

install-dev:  ## 安装开发依赖（含 pytest, ruff）
	pip install -e ".[dev]"

test:  ## 运行测试
	$(PYTHON) -m pytest tests/

test-cov:  ## 运行测试（含覆盖率）
	$(PYTHON) -m pytest tests/ --cov=. --cov-report=term-missing --cov-report=html:htmlcov

lint:  ## 检查代码质量
	ruff check .

lint-fix:  ## 自动修复 lint 问题
	ruff check --fix .

format:  ## 格式化代码
	ruff format .

run:  ## 启动 Streamlit Web 界面
	streamlit run app.py

run-api:  ## 启动 FastAPI 服务
	uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload

clean:  ## 清理构建产物
	rm -rf build/ dist/ *.egg-info htmlcov/ .pytest_cache/ __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
