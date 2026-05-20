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
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Callable

LOG_DIR = Path(__file__).parent / ".sessions"
LOG_DIR.mkdir(exist_ok=True)

HookFn = Callable[[str, dict], dict | None]


class HookBus:
    def __init__(self) -> None:
        self._hooks: dict[str, list[HookFn]] = defaultdict(list)

    def register(self, event: str, fn: HookFn) -> None:
        self._hooks[event].append(fn)

    def fire(self, event: str, ctx: dict) -> dict:
        """派发事件，合并所有回调的返回值。"""
        result: dict = {}
        for fn in self._hooks[event]:
            out = fn(event, ctx) or {}
            result.update(out)
            if out.get("block"):
                break
        return result


# ----- 内置 hook：审计日志，所有事件都写到 .sessions/<id>.jsonl -----

def audit_logger(session_id: str) -> HookFn:
    log_path = LOG_DIR / f"{session_id}.jsonl"

    def _hook(event: str, ctx: dict) -> dict | None:
        record = {"ts": time.time(), "event": event}
        # ctx 里可能有不可序列化的对象，做个安全处理
        for k, v in ctx.items():
            try:
                json.dumps(v)
                record[k] = v
            except TypeError:
                record[k] = repr(v)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return None

    return _hook


# ----- 内置 hook：危险命令拦截 -----

DANGEROUS_PATTERNS = ("rm -rf /", "mkfs", ":(){", "dd if=", "> /dev/sda")


def block_dangerous_bash(event: str, ctx: dict) -> dict | None:
    if ctx.get("tool_name") != "run_bash":
        return None
    cmd = ctx.get("tool_args", {}).get("cmd", "")
    for pat in DANGEROUS_PATTERNS:
        if pat in cmd:
            return {"block": True, "reason": f"危险命令模式被拦截: {pat!r}"}
    return None
