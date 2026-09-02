"""
工具权限网关：模仿 Claude Code 的 auto / ask / deny 三档策略。

每个工具调用前都会查策略：
- auto: 直接执行
- ask:  打印工具名+参数，等用户回车批准（拒绝则把 "denied" 作为工具结果回灌给 Agent）
- deny: 直接拒绝，Agent 收到一条错误消息

策略可以热更新（用户在 REPL 里输入 /allow read_file 之类）。
"""
from __future__ import annotations  # 延迟注解

from dataclasses import dataclass, field  # 数据类，简化策略对象定义
from typing import Literal  # 字面量联合类型

Decision = Literal["auto", "ask", "deny"]  # 权限三档决策类型别名


@dataclass  # dataclass 装饰器
class PermissionPolicy:  # 定义类
    """可热更新的工具权限策略表。"""

    # 默认对未列出的工具采取的策略
    default: Decision = "ask"  # 未配置工具默认需询问
    # 单个工具的覆盖策略
    rules: dict[str, Decision] = field(default_factory=dict)  # 工具名 → 决策

    def decide(self, tool_name: str) -> Decision:  # 定义函数
        """查询某工具应执行的权限决策。"""
        return self.rules.get(tool_name, self.default)  # 有规则用规则，否则 default

    def set(self, tool_name: str, decision: Decision) -> None:  # 定义函数
        """运行时覆盖某工具的决策（REPL /allow /deny 用）。"""
        self.rules[tool_name] = decision  # 写入或更新规则


def default_policy() -> PermissionPolicy:  # 定义函数
    """开箱即用的合理默认值：读类工具 auto，写/执行类工具 ask。"""
    return PermissionPolicy(  # 返回结果
        default="ask",  # 未知工具默认询问
        rules={  # 执行本行逻辑
            "read_file": "auto",  # 读文件免询问
            "list_dir": "auto",  # 列目录免询问
            "grep": "auto",  # 搜索免询问
            "todo_write": "auto",  # 写待办免询问
            "spawn_subagent": "auto",  # 子 agent 内部的工具仍然走权限检查
            "write_file": "ask",  # 写文件需确认
            "run_bash": "ask",  # 执行命令需确认
        },  # 执行本行逻辑
    )  # 闭合括号/元组/字典


def prompt_user(tool_name: str, tool_args: dict) -> tuple[bool, bool]:  # 定义函数
    """同步问用户要不要批准。返回 (是否批准, 是否本会话内此工具一律 auto)。"""
    print(f"\n[permission] tool={tool_name} args={tool_args}")  # 展示待批准调用
    ans = input("批准? [y/N/a=本会话内此工具一律 auto] ").strip().lower()  # 读用户输入
    return ans in {"y", "yes", "a"}, ans == "a"  # (批准?, 是否选 a 永久 auto)
