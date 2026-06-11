"""
结构化日志配置 — 输出到 stdout（Streamlit Cloud 可查看）。
"""
import logging
import sys


def setup_logger(name: str = "xuefeng-advisor") -> logging.Logger:
    """配置并返回 logger 实例。"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    logger.addHandler(handler)
    return logger


log = setup_logger()
