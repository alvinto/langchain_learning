"""
REPL 入口：跑起来体验完整 harness。

用法：
    python 08_agent_harness/app.py

支持的斜杠命令：
    /todos         查看 Agent 当前的待办清单
    /policy        查看权限策略
    /allow <tool>  把某工具改成 auto（本会话）
    /deny  <tool>  把某工具改成 deny（本会话）
    /reset         开新会话（之前的对话历史丢弃）
    /quit          退出
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解，允许前向引用类型

import sys  # 用于修改 sys.path，保证同目录模块可被 import
from pathlib import Path  # 跨平台路径处理

# 确保子模块可以 import：把当前脚本所在目录插入模块搜索路径最前面
sys.path.insert(0, str(Path(__file__).resolve().parent))  # 执行本行逻辑

from langchain_core.messages import AIMessage, HumanMessage  # LangChain 消息类型

from harness import build_harness, initial_state, new_session_id  # harness 构建与会话工具
from hooks import audit_logger  # 审计日志 hook 工厂函数


BANNER = """
============================================================
  Mini Agent Harness — 迷你版 Claude Code 风格代码助手
  workspace: ./08_agent_harness/workspace/
  /quit 退出，/help 看所有命令
============================================================
"""  # 启动时打印的欢迎横幅


def print_help():  # 定义函数
    """打印模块级 docstring 作为帮助信息。"""
    print(__doc__)  # 输出文件顶部的用法说明


def print_todos(todos):  # 定义函数
    """格式化打印待办清单。"""
    if not todos:  # 清单为空
        print("(还没有待办)")  # 提示用户
        return  # 提前返回
    icon = {"pending": "○", "in_progress": "▶", "done": "✔"}  # 状态 → 图标映射
    for t in todos:  # 遍历每条待办
        print(f"  {icon.get(t['status'], '?')} #{t['id']} {t['content']}")  # 打印带图标的一行


def main():  # demo 入口函数
    """REPL 主循环：读取用户输入并驱动 Agent。"""
    print(BANNER)  # 显示欢迎信息
    app, hooks, policy = build_harness()  # 编译 LangGraph 应用并拿到 hook 总线与权限策略

    session_id = new_session_id()  # 生成 12 位十六进制会话 ID
    hooks.register("pre_tool", audit_logger(session_id))  # 工具执行前写审计日志
    hooks.register("post_tool", audit_logger(session_id))  # 工具执行后写审计日志
    print(f"[session {session_id}] 日志写入 .sessions/{session_id}.jsonl\n")  # 告知日志路径

    # LangGraph thread id —— checkpointer 用它区分不同 session
    config = {"configurable": {"thread_id": session_id}}  # LangGraph 运行时配置
    first_turn = True  # 标记是否为本会话的第一轮对话

    while True:  # REPL 无限循环，直到用户退出
        try:  # 代码块起始
            user = input("\n你 > ").strip()  # 读取并去掉首尾空白
        except (EOFError, KeyboardInterrupt):  # Ctrl+D / Ctrl+C
            print()  # 换行，避免光标留在行首
            break  # 退出循环

        if not user:  # 空输入
            continue  # 忽略，继续下一轮
        if user in {"/quit", "/exit"}:  # 退出命令
            break  # 结束 REPL
        if user == "/help":  # 帮助命令
            print_help()  # 打印帮助
            continue  # 不跑 Agent
        if user == "/todos":  # 查看待办
            snap = app.get_state(config).values  # 从 checkpointer 读取当前 state
            print_todos(snap.get("todos", []))  # 打印 todos 字段，缺省为空列表
            continue  # 跳过本次循环
        if user == "/policy":  # 查看权限策略
            print(f"default = {policy.default}")  # 打印默认决策
            for k, v in policy.rules.items():  # 遍历工具级覆盖规则
                print(f"  {k}: {v}")  # 打印每条规则
            continue  # 跳过本次循环
        if user.startswith("/allow "):  # 本会话把某工具设为 auto
            policy.set(user.split(" ", 1)[1].strip(), "auto")  # 解析工具名并更新策略
            print("ok")  # 确认
            continue  # 跳过本次循环
        if user.startswith("/deny "):  # 本会话把某工具设为 deny
            policy.set(user.split(" ", 1)[1].strip(), "deny")  # 解析工具名并更新策略
            print("ok")  # 确认
            continue  # 跳过本次循环
        if user == "/reset":  # 开新会话
            session_id = new_session_id()  # 新 session id
            config = {"configurable": {"thread_id": session_id}}  # 更新 thread 配置
            first_turn = True  # 下一轮需重新 initial_state
            print(f"[session {session_id}] 新会话已开始")  # 提示
            continue  # 跳过本次循环

        # ---- 真正跑 Agent ----
        if first_turn:  # 本会话首次用户消息
            inputs = initial_state(session_id, user)  # 构造完整初始 state
            first_turn = False  # 后续轮次只追加消息
        else:  # else 分支
            # 已有 thread，只追加新的 HumanMessage，state 由 checkpointer 续上
            inputs = {"messages": [HumanMessage(content=user)]}  # 增量输入

        # 流式打印每个节点的输出
        try:  # 代码块起始
            for chunk in app.stream(inputs, config=config, stream_mode="values"):  # 流式执行图
                last = chunk["messages"][-1] if chunk.get("messages") else None  # 取最新一条消息
                if isinstance(last, AIMessage):  # 只展示 AI 输出
                    if last.tool_calls:  # AI 决定调用工具
                        for c in last.tool_calls:  # 逐个打印工具调用
                            print(f"  ⚙ {c['name']}({_short(c['args'])})")  # 工具名 + 截断参数
                    elif last.content:  # AI 直接回复文本
                        print(f"\nAgent > {last.content}")  # 打印最终回答
        except KeyboardInterrupt:  # 流式过程中 Ctrl+C
            print("\n[interrupted]")  # 提示中断
            continue  # 回到 REPL，不退出程序
        except Exception as e:  # harness 运行异常
            print(f"\n[harness error] {type(e).__name__}: {e}")  # 打印错误类型与信息


def _short(d: dict, n: int = 80) -> str:  # 定义函数
    """把工具参数字典格式化为短字符串，便于终端显示。"""
    s = ", ".join(f"{k}={_trunc(v, 30)}" for k, v in d.items())  # key=value 拼接
    return s if len(s) <= n else s[:n] + "..."  # 超长则截断


def _trunc(v, n):  # 定义函数
    """把任意值转成字符串并限制最大长度。"""
    s = str(v)  # 转字符串
    return s if len(s) <= n else s[:n] + "..."  # 超长截断


if __name__ == "__main__":  # 脚本直接运行时
    main()  # 进入 REPL
