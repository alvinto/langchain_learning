"""
工具权限网关：模仿 Claude Code 的 auto / ask / deny 三档策略。

每个工具调用前都会查策略：
- auto: 直接执行
- ask:  打印工具名+参数，等用户回车批准（拒绝则把 "denied" 作为工具结果回灌给 Agent）
- deny: 直接拒绝，Agent 收到一条错误消息

策略可以热更新（用户在 REPL 里输入 /allow read_file 之类）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Decision = Literal["auto", "ask", "deny"]


@dataclass
class PermissionPolicy:
    # 默认对未列出的工具采取的策略
    default: Decision = "ask"
    # 单个工具的覆盖策略
    rules: dict[str, Decision] = field(default_factory=dict)

    def decide(self, tool_name: str) -> Decision:
        return self.rules.get(tool_name, self.default)

    def set(self, tool_name: str, decision: Decision) -> None:
        self.rules[tool_name] = decision


def default_policy() -> PermissionPolicy:
    """开箱即用的合理默认值：读类工具 auto，写/执行类工具 ask。"""
    return PermissionPolicy(
        default="ask",
        rules={
            "read_file": "auto",
            "list_dir": "auto",
            "grep": "auto",
            "todo_write": "auto",
            "spawn_subagent": "auto",  # 子 agent 内部的工具仍然走权限检查
            "write_file": "ask",
            "run_bash": "ask",
        },
    )


def prompt_user(tool_name: str, tool_args: dict) -> tuple[bool, bool]:
    """同步问用户要不要批准。返回 (是否批准, 是否本会话内此工具一律 auto)。"""
    print(f"\n[permission] tool={tool_name} args={tool_args}")
    ans = input("批准? [y/N/a=本会话内此工具一律 auto] ").strip().lower()
    return ans in {"y", "yes", "a"}, ans == "a"
