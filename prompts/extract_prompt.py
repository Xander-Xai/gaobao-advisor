#!/usr/bin/env python3
"""
提示词自动归档工具

用法：
    # 交互模式 — 粘贴新的提示词内容
    python3 prompts/extract_prompt.py

    # 从文件归档
    python3 prompts/extract_prompt.py --file system_prompt.md --version 2.1

    # 记录一次对话迭代（session 归档）
    python3 prompts/extract_prompt.py --session "知识库接入优化" --note "增加了工具调用格式限制"
"""

import argparse
import re
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
PROMPTS_DIR = Path(__file__).parent
SYSTEM_DIR = PROMPTS_DIR / "system"
SESSION_DIR = PROMPTS_DIR / "sessions"
CHANGELOG = PROMPTS_DIR / "CHANGELOG.md"


def get_next_version():
    """扫描 system/ 目录，返回下一个版本号"""
    versions = []
    for f in SYSTEM_DIR.glob("v*.md"):
        match = re.match(r"v(\d+)\.(\d+)\.md", f.name)
        if match:
            versions.append((int(match.group(1)), int(match.group(2))))
    if not versions:
        return "1.0"
    major, minor = max(versions)
    return f"{major}.{minor + 1}"


def archive_system_prompt(content: str, version: str, note: str = ""):
    """归档一个 system prompt 版本"""
    dest = SYSTEM_DIR / f"v{version}.md"
    dest.write_text(content, encoding="utf-8")
    print(f"✅ 已归档: {dest.relative_to(PROJECT_ROOT)}")

    # 更新 CHANGELOG
    today = datetime.now().strftime("%Y-%m-%d")
    entry = f"\n## v{version}\n> 日期：{today}\n\n"
    if note:
        entry += f"### 改动说明\n{note}\n\n"
    entry += "---\n"

    if CHANGELOG.exists():
        existing = CHANGELOG.read_text(encoding="utf-8")
        # 插入到最新版本之后、历史版本之前
        insert_pos = existing.find("\n---\n## v")
        if insert_pos == -1:
            content_new = existing.rstrip() + "\n" + entry
        else:
            content_new = existing[:insert_pos] + entry + existing[insert_pos:]
        CHANGELOG.write_text(content_new, encoding="utf-8")
    print("📝 已更新 CHANGELOG")


def archive_session(name: str, content: str, note: str = ""):
    """归档一次对话中的提示词迭代"""
    today = datetime.now().strftime("%Y-%m-%d")
    safe_name = re.sub(r"[^\w\-]", "-", name)
    filename = f"{today}-{safe_name}.md"
    dest = SESSION_DIR / filename

    header = f"# Session: {name}\n"
    header += f"> 日期：{today}\n"
    if note:
        header += f"> 备注：{note}\n"
    header += "\n---\n\n"

    dest.write_text(header + content, encoding="utf-8")
    print(f"✅ 会话归档: {dest.relative_to(PROJECT_ROOT)}")


def extract_from_conversation():
    """交互模式：从标准输入读取提示词"""
    print("=" * 50)
    print("提示词归档工具 — 交互模式")
    print("=" * 50)
    print("\n请选择归档类型：")
    print("  1. System Prompt 新版本")
    print("  2. 会话迭代（session）")
    print()

    choice = input("选择 [1/2]: ").strip()

    if choice == "1":
        version = input(f"版本号 [自动: {get_next_version()}]: ").strip()
        if not version:
            version = get_next_version()
        note = input("改动说明（可选）: ").strip()
        print("\n请粘贴提示词内容（输入 END 结束）：")
        lines = []
        while True:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        content = "\n".join(lines)
        if content.strip():
            archive_system_prompt(content, version, note)
        else:
            print("⚠️ 内容为空，跳过")

    elif choice == "2":
        name = input("会话名称: ").strip()
        note = input("备注（可选）: ").strip()
        print("\n请粘贴提示词内容（输入 END 结束）：")
        lines = []
        while True:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        content = "\n".join(lines)
        if content.strip():
            archive_session(name, content, note)
        else:
            print("⚠️ 内容为空，跳过")


def main():
    parser = argparse.ArgumentParser(description="提示词归档工具")
    parser.add_argument("--file", help="从文件归档 system prompt")
    parser.add_argument("--version", help="指定版本号")
    parser.add_argument("--session", help="归档为会话迭代，指定会话名称")
    parser.add_argument("--note", default="", help="改动说明/备注")
    args = parser.parse_args()

    if args.file:
        filepath = Path(args.file)
        if not filepath.exists():
            print(f"❌ 文件不存在: {filepath}")
            return
        content = filepath.read_text(encoding="utf-8")
        version = args.version or get_next_version()
        archive_system_prompt(content, version, args.note)

    elif args.session:
        print(f"请粘贴会话「{args.session}」中的提示词内容（输入 END 结束）：")
        lines = []
        while True:
            try:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
            except EOFError:
                break
        content = "\n".join(lines)
        if content.strip():
            archive_session(args.session, content, args.note)
        else:
            print("⚠️ 内容为空，跳过")

    else:
        extract_from_conversation()


if __name__ == "__main__":
    main()
