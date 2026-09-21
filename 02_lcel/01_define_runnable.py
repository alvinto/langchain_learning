"""
02-0 自定义 Runnable（理解 LCEL 底层协议）

学到：
- Runnable 的核心是统一调用面：invoke / stream / batch（LangChain 里还有 ainvoke / astream 等异步版本）。
- 表达式 `A | B | C` 在 Python 里走 `__or__`，左结合：((A | B) | C)；每次 `|` 得到更长的 RunnableSequence。
- stream 默认可退化为「整段 invoke 再 yield」；RunnableSequence 里则把上游 chunk 逐块交给下游 stream。
- RunnableLambda 把普通函数包成 Runnable，对应 langchain_core.runnables.RunnableLambda。
- RunnablePassthrough 恒等变换，链末占位或与其它算子组合时保留输入；LangChain 版还有 .assign(...) 往 dict 里加字段（见 03_runnable_passthrough.py）。
- RunnableParallel 同一输入分发给多条分支，结果合并为 dict；LangChain 版可并发执行（见 02_runnable_parallel.py）。

文件结构（自上而下）：
  MyRunnable          — 协议与 `|` 重载
  RunnableSequence    — 两步串行组合
  ToUpper / ToLower / AddPrefix — 无状态的字符串变换示例
  RunnableLambda      — 函数 → Runnable 的适配器
  RunnablePassthrough — 输入原样输出
  RunnableParallel    — 多分支同输入 → dict
  main                — 串行链 + 并行 dict 演示

对照 LangChain（概念同名，本文件为教学用最小实现）：
  MyRunnable          ≈ Runnable
  RunnableSequence    ≈ RunnableSequence
  RunnableLambda      ≈ RunnableLambda
  RunnablePassthrough ≈ RunnablePassthrough（无 .assign）
  RunnableParallel    ≈ RunnableParallel（此处 invoke 为顺序 for 循环，未做真并发）

运行：python3 02_lcel/01_define_runnable.py
"""
from typing import Any, Callable, Dict, Iterator, List


# ---------------------------------------------------------------------------
# Runnable 协议：子类实现 invoke；stream / batch 有默认实现；`|` 拼串行链
# ---------------------------------------------------------------------------


class MyRunnable:
    """Runnable 协议的最小抽象：子类必须实现 invoke，其余方法有合理默认。"""

    def invoke(self, input: Any) -> Any:
        """同步执行一步变换：input → output。"""
        raise NotImplementedError("必须实现 invoke 方法")

    def stream(self, input: Any) -> Iterator[Any]:
        """流式执行；默认不做分片，整段结果一次性 yield（与 LangChain Runnable 默认行为一致）。"""
        yield self.invoke(input)

    def batch(self, inputs: List[Any]) -> List[Any]:
        """对多个输入逐个 invoke；生产环境 Runnable 会做并发优化，这里保持最简单语义。"""
        return [self.invoke(i) for i in inputs]

    def __or__(self, other: "MyRunnable") -> "RunnableSequence":
        """重载 `|`：返回 RunnableSequence(self, other)，先执行 self 再执行 other。

        类型注解里的 "RunnableSequence" 用引号是前向引用，避免类尚未定义时无法解析。
        """
        return RunnableSequence(self, other)


# ---------------------------------------------------------------------------
# 组合：两个 Runnable 串行；更长的链由多次 `|` 嵌套 RunnableSequence 形成
# ---------------------------------------------------------------------------


class RunnableSequence(MyRunnable):
    """串行组合：first 的输出作为 second 的输入。"""

    def __init__(self, first: MyRunnable, second: MyRunnable) -> None:
        self.first = first
        self.second = second

    def invoke(self, input: Any) -> Any:
        intermediate = self.first.invoke(input)
        return self.second.invoke(intermediate)

    def stream(self, input: Any) -> Iterator[Any]:
        # 上游 stream 的每个 chunk 再交给下游 stream（演示「管道 + 流」的组合方式）
        for chunk in self.first.stream(input):
            yield from self.second.stream(chunk)


# ---------------------------------------------------------------------------
# 示例步骤：纯字符串变换，便于肉眼跟踪 invoke 的中间结果
# ---------------------------------------------------------------------------


class ToUpperRunnable(MyRunnable):
    """示例步骤：字符串转大写。"""

    def invoke(self, input: str) -> str:
        return input.upper()


class ToLowerRunnable(MyRunnable):
    """示例步骤：字符串转小写。"""

    def invoke(self, input: str) -> str:
        return input.lower()


class AddPrefixRunnable(MyRunnable):
    """示例步骤：为字符串加上可配置前缀。"""

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix

    def invoke(self, input: str) -> str:
        return f"{self.prefix}: {input}"


# ---------------------------------------------------------------------------
# 适配器：不必为每个函数写子类，与 02_lcel/04_runnable_lambda.py 中的用法对应
# ---------------------------------------------------------------------------


class RunnableLambda(MyRunnable):
    """把任意 callable(input) 包装成 Runnable，invoke 时直接调用 self.func。"""

    def __init__(self, func: Callable[[Any], Any]) -> None:
        self.func = func

    def invoke(self, input: Any) -> Any:
        return self.func(input)


def add_suffix(s: str) -> str:
    """RunnableLambda 示例：在字符串末尾追加标记。"""
    return s + " !!!"


# ---------------------------------------------------------------------------
# 透传：输出与输入相同；常用于链末「占位」或后续与 dict/assign 模式配合（本文件仅实现恒等）
# ---------------------------------------------------------------------------


class RunnablePassthrough(MyRunnable):
    """恒等 Runnable：invoke(input) 直接 return input，不做任何变换。"""

    def invoke(self, input: Any) -> Any:
        return input


# ---------------------------------------------------------------------------
# 并行（结构上的「多路」）：同一 input 依次喂给 mapping 里每个 Runnable，键名 → 各分支结果
# ---------------------------------------------------------------------------


class RunnableParallel(MyRunnable):
    """多分支汇聚为 dict：{ 键: runnable.invoke(同一 input) }。

    与 LangChain 的 RunnableParallel 语义一致；此处用 for 循环顺序调用，便于阅读，
    不等同于线程/异步意义上的并行。
    """

    def __init__(self, mapping: Dict[str, MyRunnable]) -> None:
        # 键是结果 dict 的字段名，值是该分支上的 Runnable（可与主链里的步骤复用同一类）
        self.mapping = mapping

    def invoke(self, input: Any) -> Dict[str, Any]:
        output: Dict[str, Any] = {}
        for key, runnable in self.mapping.items():
            output[key] = runnable.invoke(input)
        return output


def main() -> None:
    # --- 演示 1：串行链（`|` + invoke）---
    # 左结合：每次 `|` 调用左侧 Runnable 的 __or__，得到嵌套的 RunnableSequence。
    #
    # 数据流：
    #   "hello langchain"
    #     → 大写 → "HELLO LANGCHAIN"
    #     → 小写 → "hello langchain"
    #     → 大写 → "HELLO LANGCHAIN"
    #     → 加前缀 → "结果: HELLO LANGCHAIN"
    #     → add_suffix → "结果: HELLO LANGCHAIN !!!"
    #     → Passthrough → 不变（说明链末可接「空操作」节点）
    chain = (
        ToUpperRunnable()
        | ToLowerRunnable()
        | ToUpperRunnable()
        | AddPrefixRunnable("结果")
        | RunnableLambda(add_suffix)
        | RunnablePassthrough()
    )
    print(">> 串行链 invoke:")
    print(chain.invoke("hello langchain"))

    # --- 演示 2：RunnableParallel（一次 invoke，多个键）---
    # 同一字符串同时走「大写分支」和「加后缀分支」，互不依赖，结果放进 dict。
    p_chain = RunnableParallel(
        {
            "upper": ToUpperRunnable(),
            "suffix": RunnableLambda(lambda s: s + " end"),
        }
    )
    print("\n>> 并行结构 invoke（dict 输出）:")
    print(p_chain.invoke("parallel test"))


if __name__ == "__main__":  # 脚本直接运行时执行 demo
    main()
