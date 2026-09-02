"""
Agent 可用的工具集。

设计要点：
- 所有路径类工具都被 sandbox 限制在 ./workspace/ 目录里，防止 Agent 跑出沙箱
- 每个工具用 @tool 装饰器 + Pydantic schema 暴露给 LLM
- 错误以普通字符串返回（不抛异常）——LangGraph ToolNode 默认会把抛出的异常
  包成 ToolMessage 回灌给 LLM，但我们想要更可控的错误文案
"""
from __future__ import annotations  # 延迟注解

import re  # grep 正则匹配
import subprocess  # run_bash 执行 shell
from pathlib import Path  # 路径与沙箱解析

from langchain_core.tools import tool  # LangChain 工具装饰器
from pydantic import BaseModel, Field  # 工具参数 schema

WORKSPACE = (Path(__file__).parent / "workspace").resolve()  # 沙箱根目录绝对路径
WORKSPACE.mkdir(exist_ok=True)  # 确保 workspace 存在


def _safe_path(rel: str) -> Path:  # 定义函数
    """把相对路径解析到 workspace 内，越界则抛 ValueError。"""
    p = (WORKSPACE / rel).resolve()  # 解析为绝对路径（消除 ..）
    if not str(p).startswith(str(WORKSPACE)):  # 路径逃逸检查
        raise ValueError(f"路径越界: {rel} 不在 workspace 内")  # 拒绝越界访问
    return p  # 返回安全路径


# ---------- 文件读 ----------

class ReadFileArgs(BaseModel):  # 定义类
    """read_file 参数 schema。"""
    path: str = Field(..., description="相对 workspace 的文件路径，例如 notes/a.md")  # 赋值给 str


@tool("read_file", args_schema=ReadFileArgs)  # 声明 LangChain 工具
def read_file(path: str) -> str:  # 定义函数
    """读取 workspace 下的文本文件，返回文件内容（带行号）。"""
    try:  # 代码块起始
        p = _safe_path(path)  # 沙箱内路径
        if not p.exists():  # 文件不存在
            return f"[error] 文件不存在: {path}"  # 友好错误
        text = p.read_text(encoding="utf-8")  # 读 UTF-8 文本
        return "\n".join(f"{i+1:>4}\t{line}" for i, line in enumerate(text.splitlines()))  # 带行号输出
    except Exception as e:  # 捕获异常
        return f"[error] {e}"  # 统一错误格式


# ---------- 文件写 ----------

class WriteFileArgs(BaseModel):  # 定义类
    """write_file 参数 schema。"""
    path: str = Field(..., description="相对 workspace 的文件路径")  # 赋值给 str
    content: str = Field(..., description="要写入的完整文件内容（会覆盖原文件）")  # 赋值给 str


@tool("write_file", args_schema=WriteFileArgs)  # 声明 LangChain 工具
def write_file(path: str, content: str) -> str:  # 定义函数
    """覆盖式写入文件。父目录不存在时自动创建。"""
    try:  # 代码块起始
        p = _safe_path(path)  # 沙箱路径
        p.parent.mkdir(parents=True, exist_ok=True)  # 递归创建父目录
        p.write_text(content, encoding="utf-8")  # 覆盖写入
        return f"[ok] 已写入 {path}（{len(content)} 字节）"  # 成功反馈
    except Exception as e:  # 捕获异常
        return f"[error] {e}"  # 错误字符串


# ---------- 列目录 ----------

class ListDirArgs(BaseModel):  # 定义类
    """list_dir 参数 schema。"""
    path: str = Field(default=".", description="相对 workspace 的目录路径，默认根目录")  # 赋值给 str


@tool("list_dir", args_schema=ListDirArgs)  # 声明 LangChain 工具
def list_dir(path: str = ".") -> str:  # 定义函数
    """列出目录下的文件和子目录。"""
    try:  # 代码块起始
        p = _safe_path(path)  # 目标目录
        if not p.is_dir():  # 不是目录
            return f"[error] 不是目录: {path}"  # 返回结果
        items = []  # 收集条目名
        for child in sorted(p.iterdir()):  # 排序遍历
            mark = "/" if child.is_dir() else ""  # 目录加斜杠后缀
            items.append(f"{child.name}{mark}")  # 仅列名称
        return "\n".join(items) if items else "(空目录)"  # 换行拼接或空提示
    except Exception as e:  # 捕获异常
        return f"[error] {e}"  # 返回结果


# ---------- grep ----------

class GrepArgs(BaseModel):  # 定义类
    """grep 参数 schema。"""
    pattern: str = Field(..., description="正则表达式")  # 赋值给 str
    path: str = Field(default=".", description="搜索目录，默认 workspace 根")  # 赋值给 str


@tool("grep", args_schema=GrepArgs)  # 声明 LangChain 工具
def grep(pattern: str, path: str = ".") -> str:  # 定义函数
    """在 workspace 下递归搜索匹配模式的行。返回 file:line:content 格式。"""
    try:  # 代码块起始
        p = _safe_path(path)  # 搜索根目录
        regex = re.compile(pattern)  # 编译正则
        hits = []  # 匹配行列表
        for f in p.rglob("*"):  # 递归所有路径
            if not f.is_file():  # 跳过非文件
                continue  # 跳过本次循环
            try:  # 代码块起始
                for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):  # 逐行
                    if regex.search(line):  # 命中
                        rel = f.relative_to(WORKSPACE)  # workspace 相对路径
                        hits.append(f"{rel}:{i}:{line}")  # 标准 grep 输出格式
                        if len(hits) >= 100:  # 结果上限
                            hits.append("(more results truncated)")  # 截断提示
                            return "\n".join(hits)  # 提前返回
            except (UnicodeDecodeError, PermissionError):  # 二进制或无权限
                continue  # 跳过该文件
        return "\n".join(hits) if hits else "(无匹配)"  # 有结果或无匹配
    except Exception as e:  # 捕获异常
        return f"[error] {e}"  # 返回结果


# ---------- bash ----------

class RunBashArgs(BaseModel):  # 定义类
    """run_bash 参数 schema。"""
    cmd: str = Field(..., description="要执行的 shell 命令，cwd 锁定为 workspace")  # 赋值给 str
    timeout: int = Field(default=30, description="超时秒数，默认 30")  # 赋值给 int


@tool("run_bash", args_schema=RunBashArgs)  # 声明 LangChain 工具
def run_bash(cmd: str, timeout: int = 30) -> str:  # 定义函数
    """在 workspace 目录里执行 shell 命令，返回 stdout + stderr。"""
    try:  # 代码块起始
        proc = subprocess.run(  # 同步执行子进程
            cmd,  # 序列/元组元素
            shell=True,  # 通过 shell 解析命令（受权限网关约束）
            cwd=str(WORKSPACE),  # 工作目录锁定沙箱
            capture_output=True,  # 捕获 stdout/stderr
            text=True,  # 文本模式
            timeout=timeout,  # 超时秒数
        )  # 闭合括号/元组/字典
        out = (proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")  # 合并输出
        return f"[exit={proc.returncode}]\n{out[:8000]}"  # 附带退出码并截断过长输出
    except subprocess.TimeoutExpired:  # 捕获异常
        return f"[error] 命令超时 ({timeout}s)"  # 超时错误
    except Exception as e:  # 捕获异常
        return f"[error] {e}"  # 其他错误


# ---------- todo_write：Agent 自管理任务清单 ----------

class TodoItem(BaseModel):  # 定义类
    """单条待办 schema。"""
    id: int  # 序号
    content: str  # 描述
    status: str = Field(..., description="pending | in_progress | done")  # 状态


class TodoWriteArgs(BaseModel):  # 定义类
    """todo_write 参数 schema。"""
    items: list[TodoItem] = Field(..., description="完整的待办清单（覆盖式写入）")  # 赋值给 list[TodoItem]


@tool("todo_write", args_schema=TodoWriteArgs)  # 声明 LangChain 工具
def todo_write(items: list[TodoItem]) -> str:  # 定义函数
    """写入/更新 Agent 的待办清单。每次必须传完整清单（覆盖式）。

    实际的状态合并发生在 harness 里——这里只返回一段提示文案给 LLM，
    让它知道已记录。
    """
    # @tool + args_schema 会把 dict 自动转成 TodoItem 实例，所以用属性访问
    return f"[ok] 已记录 {len(items)} 条待办：\n" + "\n".join(  # 返回结果
        f"  [{it.status}] #{it.id} {it.content}" for it in items  # 格式化每条待办
    )  # 闭合括号/元组/字典


# ---------- 注册表 ----------

ALL_TOOLS = [read_file, write_file, list_dir, grep, run_bash, todo_write]  # 主 Agent 基础工具
# spawn_subagent 在 subagent.py 里定义后追加进来，避免循环 import
