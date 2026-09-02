"""
Hook 总线：在关键时刻派发事件给注册的回调。

支持的事件：
- pre_tool:   工具即将执行（可改写参数，可阻止）
- post_tool:  工具执行完毕（拿到结果，可记日志）
- on_user_msg: 用户输入了一条消息
- on_stop:    本轮 Agent 循环停机

回调签名：fn(event: str, ctx: dict) -> dict | None
- 返回 None 表示放行
- 返回 {"block": True, "reason": "..."} 表示阻断（仅 pre_tool 有效）
- 返回 {"override_args": {...}} 可改写工具参数
"""
from __future__ import annotations  # 延迟注解

import json  # 序列化审计日志
import time  # 记录时间戳
from collections import defaultdict  # 默认 dict，简化 event → hooks 列表
from pathlib import Path  # 日志目录路径
from typing import Callable  # 回调类型注解

LOG_DIR = Path(__file__).parent / ".sessions"  # 会话审计日志目录
LOG_DIR.mkdir(exist_ok=True)  # 不存在则创建

HookFn = Callable[[str, dict], dict | None]  # hook 回调类型：事件名 + 上下文 → 可选指令 dict


class HookBus:  # 定义类
    """按事件名注册/派发 hook 的简单总线。"""

    def __init__(self) -> None:  # 定义函数
        self._hooks: dict[str, list[HookFn]] = defaultdict(list)  # event → 回调列表

    def register(self, event: str, fn: HookFn) -> None:  # 定义函数
        """为某事件注册一个回调。"""
        self._hooks[event].append(fn)  # 追加到该事件的回调链

    def fire(self, event: str, ctx: dict) -> dict:  # 定义函数
        """派发事件，合并所有回调的返回值。"""
        result: dict = {}  # 累积各 hook 返回的指令
        for fn in self._hooks[event]:  # 按注册顺序执行
            out = fn(event, ctx) or {}  # hook 返回 None 当空 dict
            result.update(out)  # 合并键值（后者覆盖前者）
            if out.get("block"):  # 若某 hook 要求阻断
                break  # 后续 hook 不再执行
        return result  # 返回合并后的指令（block / override_args 等）


# ----- 内置 hook：审计日志，所有事件都写到 .sessions/<id>.jsonl -----

def audit_logger(session_id: str) -> HookFn:  # 定义函数
    """工厂：返回把事件追加写入 jsonl 的 hook。"""
    log_path = LOG_DIR / f"{session_id}.jsonl"  # 本会话日志文件

    def _hook(event: str, ctx: dict) -> dict | None:  # 定义函数
        """实际 hook 实现：写一行 JSON。"""
        record = {"ts": time.time(), "event": event}  # 基础字段：时间戳 + 事件名
        # ctx 里可能有不可序列化的对象，做个安全处理
        for k, v in ctx.items():  # 遍历上下文
            try:  # 代码块起始
                json.dumps(v)  # 试探能否 JSON 序列化
                record[k] = v  # 可序列化则原样写入
            except TypeError:  # 捕获异常
                record[k] = repr(v)  # 不可序列化则用 repr 字符串
        with log_path.open("a", encoding="utf-8") as f:  # 追加模式打开日志
            f.write(json.dumps(record, ensure_ascii=False) + "\n")  # 写一行 JSONL
        return None  # 审计 hook 不阻断、不改写

    return _hook  # 返回闭包供 register 使用


# ----- 内置 hook：危险命令拦截 -----

DANGEROUS_PATTERNS = ("rm -rf /", "mkfs", ":(){", "dd if=", "> /dev/sda")  # 危险 shell 子串黑名单


def block_dangerous_bash(event: str, ctx: dict) -> dict | None:  # 定义函数
    """pre_tool hook：拦截 run_bash 中的明显危险命令。"""
    if ctx.get("tool_name") != "run_bash":  # 只检查 bash 工具
        return None  # 其他工具放行
    cmd = ctx.get("tool_args", {}).get("cmd", "")  # 取出命令字符串
    for pat in DANGEROUS_PATTERNS:  # 逐个匹配危险模式
        if pat in cmd:  # 命中
            return {"block": True, "reason": f"危险命令模式被拦截: {pat!r}"}  # 阻断并说明原因
    return None  # 未命中则放行
