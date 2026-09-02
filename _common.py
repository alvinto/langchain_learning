"""
共享配置：所有 demo 都从这里拿 LLM / Embedding 实例。
只需修改 .env，全部 demo 自动切换提供方。
"""
from __future__ import annotations  # 启用 PEP 563 延迟注解

import os  # 导入 os 标准库
from pathlib import Path  # 导入 Path 处理路径

from dotenv import load_dotenv  # 导入 dotenv 环境变量加载器

# 自动加载项目根目录的 .env
ROOT = Path(__file__).resolve().parent  # 赋值给 ROOT
load_dotenv(ROOT / ".env")  # 加载 .env 环境变量

# 让国内 API 域名绕过本地代理（Clash/V2Ray 等），避免 SSL 握手失败。
# 如果你只用 OpenAI 官方接口可以删掉这段。
_BYPASS_HOSTS = (  # 赋值给 _BYPASS_HOSTS
    "aliyuncs.com",  # 字符串/template 参数
    "deepseek.com",  # 字符串/template 参数
    "bigmodel.cn",  # 字符串/template 参数
    "dashscope.com",  # 字符串/template 参数
    "qwen.com",  # 字符串/template 参数
    "moonshot.cn",  # 字符串/template 参数
    "siliconflow.cn",  # 字符串/template 参数
    "localhost",  # 字符串/template 参数
    "127.0.0.1",  # 字符串/template 参数
)  # 闭合括号/元组/字典
_no_proxy = os.environ.get("NO_PROXY", "")  # 赋值给 _no_proxy
_existing = {h.strip() for h in _no_proxy.split(",") if h.strip()}  # for 循环
_merged = sorted(_existing | set(_BYPASS_HOSTS))  # 赋值给 _merged
os.environ["NO_PROXY"] = ",".join(_merged)  # 赋值给 os.environ["NO_PROXY"]
os.environ["no_proxy"] = os.environ["NO_PROXY"]   # httpx 同时识别小写


_FALSY = {"false", "0", "no", "off"}  # 赋值给 _FALSY


def _setup_langsmith() -> None:  # 定义函数
    """检测到 LangSmith key 就自动启用 tracing。

    - 没填 key → 完全跳过，不影响 demo 运行。
    - 填了 key → 所有 LCEL chain / Agent / LangGraph 节点会自动把运行轨迹
                上报到 https://smith.langchain.com（提示词、tool_calls、token
                用量等都看得到），不需要在 demo 代码里写一行额外代码。
    - 填了 key 但同时显式设了 LANGCHAIN_TRACING_V2=false → 尊重用户设置，
      但打印一行提示，免得"以为开了实际没开"。

    LangChain 0.3 用 LANGCHAIN_*，1.x 改名 LANGSMITH_*。这里两套都设上，
    无论用户装的是哪一版都能工作。
    """
    key = os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY")  # 赋值给 key
    if not key:  # 代码块起始
        return  # 提前返回

    if (  # 执行本行逻辑
        os.getenv("LANGCHAIN_TRACING_V2", "").lower() in _FALSY  # 执行本行逻辑
        or os.getenv("LANGSMITH_TRACING", "").lower() in _FALSY  # 执行本行逻辑
    ):  # 代码块起始
        print(  # 打印输出
            "[langsmith] 检测到 API key，但 LANGCHAIN_TRACING_V2/LANGSMITH_TRACING "  # 字符串/template 参数
            "被显式设为 false。如需启用追踪，请把该项改为 true 或删掉这一行。"  # 字符串/template 参数
        )  # 闭合括号/元组/字典
        return  # 提前返回

    os.environ["LANGCHAIN_API_KEY"] = key  # 赋值给 os.environ["LANGCHAIN_API_KEY"]
    os.environ["LANGSMITH_API_KEY"] = key  # 赋值给 os.environ["LANGSMITH_API_KEY"]
    os.environ["LANGCHAIN_TRACING_V2"] = "true"  # 赋值给 os.environ["LANGCHAIN_TRACING_V2"]
    os.environ["LANGSMITH_TRACING"] = "true"  # 赋值给 os.environ["LANGSMITH_TRACING"]
    os.environ.setdefault("LANGCHAIN_PROJECT", "langchain_learning")  # 若键不存在则设置默认值
    os.environ.setdefault("LANGSMITH_PROJECT", os.environ["LANGCHAIN_PROJECT"])  # 若键不存在则设置默认值

    print(  # 打印输出
        f"[langsmith] tracing on · project={os.environ['LANGCHAIN_PROJECT']}"  # 字符串/template 参数
        f" · dashboard https://smith.langchain.com"  # 字符串/template 参数
    )  # 闭合括号/元组/字典


_setup_langsmith()  # 执行本行逻辑


def get_llm(temperature: float = 0.7, role: str | None = None, **kwargs):  # 获取 ChatOpenAI 兼容 LLM
    """返回一个 ChatOpenAI 实例（兼容所有 OpenAI 协议提供方）。

    role 用来做模型分层 —— 09 章 deep_research 这种 multi-agent 系统
    可以在不同节点用不同档位的模型省钱+提速：
        - role="cheap"  → 总结/压缩这种粗活，用便宜模型
        - role="smart"  → 决策/规划这种关键路径，用好模型
        - role="writer" → 最终报告，质量优先

    实际取哪个模型按这个优先级解析：
        1. kwargs 里显式传的 model （最高）
        2. 环境变量 LLM_MODEL_<ROLE>（如 LLM_MODEL_SMART）
        3. 环境变量 LLM_MODEL（兜底，所有 demo 都能直接跑）

    不传 role 时跟旧行为完全一致 —— 老 demo（01~08 章）不受影响。
    """
    from langchain_openai import ChatOpenAI  # 导入 OpenAI 协议兼容客户端

    model = kwargs.pop("model", None)  # 赋值给 model
    if model is None and role:  # 代码块起始
        model = os.getenv(f"LLM_MODEL_{role.upper()}")  # 赋值给 model
    if model is None:  # 代码块起始
        model = os.getenv("LLM_MODEL", "deepseek-chat")  # 赋值给 model

    return ChatOpenAI(  # 构造 ChatOpenAI 客户端
        base_url=os.getenv("LLM_BASE_URL"),  # 执行本行逻辑
        api_key=os.getenv("LLM_API_KEY"),  # 执行本行逻辑
        model=model,  # 执行本行逻辑
        temperature=temperature,  # 执行本行逻辑
        timeout=600,  # 全局超时10分钟，解决长推理断开
        max_retries=0,  # 超时不自动重试，避免重复占用slot
        #max_tokens=-1,  # 不限制输出token，由上下文窗口-c 8192控制
        #max_completion_tokens=
        **kwargs,  # 执行本行逻辑
    )  # 闭合括号/元组/字典


def get_embeddings(**kwargs):  # 获取 Embedding 模型
    """返回 OpenAI 兼容的 Embeddings。

    注意：check_embedding_ctx_length=False 关闭本地 tiktoken 预切分，
    直接把字符串发给服务端。否则 DashScope / 智谱 / 部分国产兼容接口会报
    "contents is neither str nor list of str"。
    """
    from langchain_openai import OpenAIEmbeddings  # 导入 OpenAI 协议兼容客户端

    return OpenAIEmbeddings(  # 返回结果
        base_url=os.getenv("EMBED_BASE_URL") or os.getenv("LLM_BASE_URL"),  # 执行本行逻辑
        api_key=os.getenv("EMBED_API_KEY") or os.getenv("LLM_API_KEY"),  # 执行本行逻辑
        model=os.getenv("EMBED_MODEL", "text-embedding-v3"),  # 执行本行逻辑
        check_embedding_ctx_length=False,  # 执行本行逻辑
        **kwargs,  # 执行本行逻辑
    )  # 闭合括号/元组/字典


def banner(title: str) -> None:  # 打印章节标题分隔条
    """打印分隔条，让 demo 输出更易读。"""
    line = "=" * 60  # 赋值给 line
    print(f"\n{line}\n  {title}\n{line}")  # 打印输出
