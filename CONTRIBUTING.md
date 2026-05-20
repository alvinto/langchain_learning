# 贡献指南

感谢愿意贡献！这是一份学习仓库，目标是让人**最短时间内能跑、能懂**，所以风格上有几点约定。

## 风格约定

- **一文件一知识点**：单独跑、单独懂，不要把一节做成需要读完别处才能理解的"半截代码"。
- **顶部 docstring 必带**：用中文写清楚"这个文件学到什么"，并以 `if __name__ == "__main__"` 为入口。
- **依赖最小化**：能用标准库、`langchain-core` 解决的就不要引入新包。新增依赖请同步更新 `requirements.txt`。
- **走 `_common.py` 拿模型**：不要在 demo 里手工构造 `ChatOpenAI` / `OpenAIEmbeddings`，否则用户无法通过 `.env` 切换提供方。
- **同时兼容 LangChain 0.3 / 1.x**：涉及到改名的 API 用 `try/except` fallback（参考 [05_tools_agents/03_react_agent.py](05_tools_agents/03_react_agent.py)）。
- **国内可访问**：示例不能假设能直连 OpenAI 官方接口；默认配置走 DeepSeek。

## 提交 PR 前的检查清单

- [ ] 你新加/改的 demo 能用 `python <path>.py` 独立跑通
- [ ] 没有把 `.env` / `_faiss_index/` / `.DS_Store` / `__pycache__/` 提交进来
- [ ] README 表格、目录索引（如有）已更新
- [ ] 至少一种主流模型方（DeepSeek 或 OpenAI）能跑通

## 适合的贡献方向

- 修 typo / bug / 老版本 API 兼容问题
- 补一个新章节或新 demo（请先开 issue 聊一下定位）
- 在 [08_agent_harness/](08_agent_harness/) 里加新工具 / Hook / 子 Agent 形态
- 写英文版 README / 章节翻译
- 把示例数据换成更有趣的语料

## 不太适合的贡献方向

- 把示例改成"全功能框架"——这是教学仓库，不是生产库
- 引入 Web UI、Docker、CI 等额外脚手架，除非你做成 **可选 extras**
- 大规模重构现有代码风格

## 报 bug

带上：
- 操作系统 + Python 版本
- `pip freeze | grep langchain` 输出
- 完整报错栈
- 复现命令

谢谢！
