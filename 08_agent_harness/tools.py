"""
Agent 可用的工具集。

设计要点：
- 所有路径类工具都被 sandbox 限制在 ./workspace/ 目录里，防止 Agent 跑出沙箱
- 每个工具用 @tool 装饰器 + Pydantic schema 暴露给 LLM
- 错误以普通字符串返回（不抛异常）——LangGraph ToolNode 默认会把抛出的异常
  包成 ToolMessage 回灌给 LLM，但我们想要更可控的错误文案
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from langchain_core.tools import tool
from pydantic import BaseModel, Field

WORKSPACE = (Path(__file__).parent / "workspace").resolve()
WORKSPACE.mkdir(exist_ok=True)


def _safe_path(rel: str) -> Path:
    """把相对路径解析到 workspace 内，越界则抛 ValueError。"""
    p = (WORKSPACE / rel).resolve()
    if not str(p).startswith(str(WORKSPACE)):
        raise ValueError(f"路径越界: {rel} 不在 workspace 内")
    return p


# ---------- 文件读 ----------

class ReadFileArgs(BaseModel):
    path: str = Field(..., description="相对 workspace 的文件路径，例如 notes/a.md")


@tool("read_file", args_schema=ReadFileArgs)
def read_file(path: str) -> str:
    """读取 workspace 下的文本文件，返回文件内容（带行号）。"""
    try:
        p = _safe_path(path)
        if not p.exists():
            return f"[error] 文件不存在: {path}"
        text = p.read_text(encoding="utf-8")
        return "\n".join(f"{i+1:>4}\t{line}" for i, line in enumerate(text.splitlines()))
    except Exception as e:
        return f"[error] {e}"


# ---------- 文件写 ----------

class WriteFileArgs(BaseModel):
    path: str = Field(..., description="相对 workspace 的文件路径")
    content: str = Field(..., description="要写入的完整文件内容（会覆盖原文件）")


@tool("write_file", args_schema=WriteFileArgs)
def write_file(path: str, content: str) -> str:
    """覆盖式写入文件。父目录不存在时自动创建。"""
    try:
        p = _safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"[ok] 已写入 {path}（{len(content)} 字节）"
    except Exception as e:
        return f"[error] {e}"


# ---------- 列目录 ----------

class ListDirArgs(BaseModel):
    path: str = Field(default=".", description="相对 workspace 的目录路径，默认根目录")


@tool("list_dir", args_schema=ListDirArgs)
def list_dir(path: str = ".") -> str:
    """列出目录下的文件和子目录。"""
    try:
        p = _safe_path(path)
        if not p.is_dir():
            return f"[error] 不是目录: {path}"
        items = []
        for child in sorted(p.iterdir()):
            mark = "/" if child.is_dir() else ""
            items.append(f"{child.name}{mark}")
        return "\n".join(items) if items else "(空目录)"
    except Exception as e:
        return f"[error] {e}"


# ---------- grep ----------

class GrepArgs(BaseModel):
    pattern: str = Field(..., description="正则表达式")
    path: str = Field(default=".", description="搜索目录，默认 workspace 根")


@tool("grep", args_schema=GrepArgs)
def grep(pattern: str, path: str = ".") -> str:
    """在 workspace 下递归搜索匹配模式的行。返回 file:line:content 格式。"""
    try:
        p = _safe_path(path)
        regex = re.compile(pattern)
        hits = []
        for f in p.rglob("*"):
            if not f.is_file():
                continue
            try:
                for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                    if regex.search(line):
                        rel = f.relative_to(WORKSPACE)
                        hits.append(f"{rel}:{i}:{line}")
                        if len(hits) >= 100:
                            hits.append("(more results truncated)")
                            return "\n".join(hits)
            except (UnicodeDecodeError, PermissionError):
                continue
        return "\n".join(hits) if hits else "(无匹配)"
    except Exception as e:
        return f"[error] {e}"


# ---------- bash ----------

class RunBashArgs(BaseModel):
    cmd: str = Field(..., description="要执行的 shell 命令，cwd 锁定为 workspace")
    timeout: int = Field(default=30, description="超时秒数，默认 30")


@tool("run_bash", args_schema=RunBashArgs)
def run_bash(cmd: str, timeout: int = 30) -> str:
    """在 workspace 目录里执行 shell 命令，返回 stdout + stderr。"""
    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
        return f"[exit={proc.returncode}]\n{out[:8000]}"
    except subprocess.TimeoutExpired:
        return f"[error] 命令超时 ({timeout}s)"
    except Exception as e:
        return f"[error] {e}"


# ---------- todo_write：Agent 自管理任务清单 ----------

class TodoItem(BaseModel):
    id: int
    content: str
    status: str = Field(..., description="pending | in_progress | done")


class TodoWriteArgs(BaseModel):
    items: list[TodoItem] = Field(..., description="完整的待办清单（覆盖式写入）")


@tool("todo_write", args_schema=TodoWriteArgs)
def todo_write(items: list[TodoItem]) -> str:
    """写入/更新 Agent 的待办清单。每次必须传完整清单（覆盖式）。

    实际的状态合并发生在 harness 里——这里只返回一段提示文案给 LLM，
    让它知道已记录。
    """
    # @tool + args_schema 会把 dict 自动转成 TodoItem 实例，所以用属性访问
    return f"[ok] 已记录 {len(items)} 条待办：\n" + "\n".join(
        f"  [{it.status}] #{it.id} {it.content}" for it in items
    )


# ---------- 注册表 ----------

ALL_TOOLS = [read_file, write_file, list_dir, grep, run_bash, todo_write]
# spawn_subagent 在 subagent.py 里定义后追加进来，避免循环 import
