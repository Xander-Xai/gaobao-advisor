"""
断点续传模块 — 保存/加载/清除导入进度。
断点文件为 JSON，记录当前导入位置和统计信息，用于中断后恢复。
"""
import json
import logging
import os

log = logging.getLogger(__name__)


def save_checkpoint(path: str, data: dict) -> None:
    """保存断点数据到 JSON 文件。自动创建父目录。"""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)
    log.debug("断点已保存: %s", path)


def load_checkpoint(path: str) -> dict | None:
    """加载断点数据。文件不存在或解析失败返回 None。"""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        log.warning("断点文件损坏 %s: %s", path, e)
        return None


def clear_checkpoint(path: str) -> None:
    """清除断点文件。"""
    if os.path.exists(path):
        os.remove(path)
        log.debug("断点已清除: %s", path)
