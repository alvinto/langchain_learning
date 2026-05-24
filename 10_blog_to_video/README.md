# 10 · 博客 → 讲解视频

把一篇 markdown 博客自动转成一段 1-2 分钟的带旁白讲解视频。整条 pipeline 现在按 **Analyze → Design → Generate → Preview → Video** 跑：先生成视觉大纲和 HTML 预览，确认页面效果后再截图、配音、合成 MP4。每一步产物都落盘，可以单独重跑。

## 跑通它（首次）

```bash
# 1. 装新依赖（在仓库根目录）
pip install -r requirements.txt

# 2. 装 Playwright 浏览器（首次必须，~150 MB）
playwright install chromium

# 3. 装 ffmpeg（MoviePy 底层调用）
brew install ffmpeg                    # macOS
# sudo apt install ffmpeg              # Ubuntu/Debian

# 4. 一键跑（用自带样例博客）
python 10_blog_to_video/pipeline.py
```

跑完会得到 `10_blog_to_video/out/run-<时间戳>/video.mp4`（含烧入硬字幕）+ 同目录 `video.srt`（软字幕）。

> 每次运行都会自动建一个 `out/run-YYYYMMDD-HHMMSS/` 子目录，避免覆盖上一次产物。
> 同时会维护 `out/latest` 符号链接指向最新一次，所以下面写脚本时可以放心引用 `out/latest/video.mp4`。

```bash
# 看最新一次的视频
open 10_blog_to_video/out/latest/video.mp4
```

> 不需要任何新的 API key —— 复用 `.env` 里你已经配好的 LLM（任何 OpenAI 兼容的都行），TTS 走免费的 edge-tts。

## 关键交互：先预览，再生成视频

页面效果要在 MP4 之前解决，所以 pipeline 有三个审核点：

1. `outline.json`：主题、叙事弧、每页 layout 和视觉意图
2. `script.json`：最终短文案、结构化字段和旁白
3. `slides.html`：浏览器预览，满意后才进入截图、TTS、MP4

跑到第 ⓪ 步生成 `outline.json` 后，pipeline 会先暂停：

```
──────────────────────────────────────────────────────────
  视觉大纲已生成：out/outline.json
  现在是你检查/编辑它的机会（编辑器随便用）。
  [Enter] 继续  [r] 让 LLM 重新生成  [Ctrl-C] 中止
──────────────────────────────────────────────────────────
> _
```

- 直接回车 → 用当前 JSON 继续
- 改完再回车 → 用**你编辑后的 JSON** 继续
- 输 `r` → 让 LLM 重新生成一份覆盖（创意不满意时用）

`slides.html` 生成后会再次暂停：

```
──────────────────────────────────────────────────────────
  HTML 预览已生成：out/slides.html
  先打开确认页面效果：file:///.../slides.html
  [Enter] 继续截图/TTS/MP4  [r] 重新按 script.json 渲染 HTML  [s] 停在这里
──────────────────────────────────────────────────────────
> _
```

不想被打断（CI / 批量跑），加 `-y` 跳过：

```bash
python 10_blog_to_video/pipeline.py -y                          # 用样例博客
python 10_blog_to_video/pipeline.py your_blog.md -y             # 一气呵成
python 10_blog_to_video/pipeline.py your_blog.md -n harness-v2  # 给本次 run 起个有意义的名字（默认 run-时间戳）
python 10_blog_to_video/pipeline.py your_blog.md --style midnight-tech
python 10_blog_to_video/pipeline.py your_blog.md --style midnight-tech,editorial-contrast
python 10_blog_to_video/pipeline.py your_blog.md --preview-only # 只到 HTML 预览，不生成视频
python 10_blog_to_video/pipeline.py your_blog.md --ignore-quality # 视觉预检失败也继续出视频
```

### 交互修改

开局会先让你选视觉风格。可以只选一个，也可以多选几个让模型在候选里判断：

- `studio-clean`：白底产品感，适合教程、产品解释、轻技术内容
- `midnight-tech`：深色技术演示，适合代码、架构、Agent、系统设计
- `editorial-contrast`：杂志/商业分析风格，适合观点、方法论、趋势分析

每个审核点都支持“看结果 → 输入修改提示词 → 重新生成”：

- `outline.json`：输入 `m`，再写“整体更像发布会 Keynote，少一点技术栈”
- `script.json`：输入 `m`，再写“第 4 页换成 compare，旁白更口语”
- `slides.html`：输入 `m`，再写“第 2 页标题太大，流程图页再突出中间节点”
- 视觉预检失败：直接输入修改意见，pipeline 会带着 `quality_report.json` 让模型修复后重新渲染

## 用你自己的博客

```bash
python 10_blog_to_video/pipeline.py path/to/your_blog.md           # → out/run-时间戳/
python 10_blog_to_video/pipeline.py path/to/your_blog.md -o myout  # → myout/run-时间戳/
```

## 核心模块

| 文件 | 学到什么 |
| --- | --- |
| [00_outline.py](00_outline.py) | **先设计再生成**：主题选择、叙事弧、每页 layout 和视觉意图，借鉴 Presenta / HTMLSlides / Slidebook 的前置规划 |
| [01_script.py](01_script.py) | **Pydantic Discriminated Union**（17 个 layout 各一个模型 + `max_length` 硬约束）按 outline 填最终字段 |
| [02_slides.py](02_slides.py) | Jinja2 主模板按 `slide.layout` 分发到 `templates/layouts/*.html.j2` 各 partial |
| [03_render.py](03_render.py) | Playwright 截图 `.slide`；显式 `wait_for_function` 等 Lucide / Mermaid 渲染完成 |
| [03_quality.py](03_quality.py) | MP4 前视觉门禁：检查元素越界、文本溢出、图标/Mermaid 未渲染、diagram 过小等硬伤 |
| [04_narrate.py](04_narrate.py) | edge-tts 异步并发合成中文旁白 + `SubMaker.feed(SentenceBoundary)` 拿时间戳产 srt |
| [05_compose.py](05_compose.py) | MoviePy 拼 mp4 + 用 srt 烧硬字幕 + 合并全片软字幕 |
| [pipeline.py](pipeline.py) | 串联 0-5；大纲、脚本、HTML 三个前置审核点；截图后做视觉预检，通过后才进 TTS/MP4 |
| [templates/slides.html.j2](templates/slides.html.j2) | base 模板：三套主题 token + 共享 CSS + Lucide/Mermaid CDN + 派发 include |
| [templates/layouts/](templates/layouts/) | 17 个 layout 各一个 `.html.j2` partial，加 layout 边际成本 = 半小时 |

每个模块都能 `python 10_blog_to_video/0N_xxx.py` 单跑，方便调试或换某一步的实现。

## 输出目录结构

```
out/
├── latest -> run-20260523-200000/    # 软链，永远指向最新一次
└── run-20260523-200000/              # 一次 run 一个独立目录
    ├── outline.json    # ⓪ 视觉大纲：主题、叙事弧、每页 layout 和视觉意图
    ├── script.json     # ① 结构化脚本：短文案 + 旁白，可手工编辑
    ├── slides.html     # ② 完整 HTML，浏览器直接打开就能预览
    ├── png/            # ③ 每页一张 1920x1080 PNG
    ├── quality_report.json # ③.5 MP4 前视觉预检报告
    ├── audio/          # ④ 每页一段 mp3 旁白 + 同名 srt（页内相对时间）
    ├── video.mp4       # ⑤ 最终视频（已烧入硬字幕）
    └── video.srt       # ⑤ 全片软字幕（绝对时间，分发到 YouTube/B 站可用）
```

不想要时间戳堆积？随手 `rm -rf out/run-2026*` 即可（latest 软链会自动失效，下次跑会重建）。

**调试建议**：先改 `outline.json`，再生成 `script.json`；先肉眼检查 `slides.html` 满意了，再让 03/04/05 跑下去。不要等 MP4 出来才改页面效果。

## 验收效果

- 1920×1080 mp4，时长 1-2 分钟
- 5-10 张幻灯片：1 cover + 中间内容（视觉化层占 ≥ 25%） + 1 收尾
- **17 种版式自动切换**，并由 `outline.json` 先做 layout planner
- **3 套视觉主题**：`studio-clean`、`midnight-tech`、`editorial-contrast`
- 中文旁白每页 60-140 字，**讲解口吻、不复述页面文字**
- 每页停留时长跟随旁白长度，音画同步无错位
- **底部硬字幕**白字黑描边，跟着 TTS 的 SentenceBoundary 走，每句一段
- **字幕安全带**：成片里幻灯片缩到上方 16:9 安全画布，底部独立字幕带，不遮挡页面文字
- **软字幕** `video.srt` 同名同目录，VLC/mpv/IINA 自动加载

## v6 关键升级：设计阶段前移

这版的核心变化不是“视频后校验”，而是把页面效果问题提前到 HTML 之前：

```text
博客 Markdown
 -> 00_outline.py 生成 outline.json    # 主题、叙事、layout planner
 -> 人工审核/编辑 outline.json
 -> 01_script.py 生成 script.json      # 按设计合同填短字段和旁白
 -> 人工审核/编辑 script.json
 -> 02_slides.py 生成 slides.html      # 浏览器预览页面效果
 -> 人工确认 HTML
 -> 03_render.py 截图 PNG
 -> 03_quality.py 视觉预检             # 失败则停在 MP4 之前
 -> 04/05 配音、字幕、MP4              # 硬字幕在独立底部字幕带，不压页面
```

这更接近目前开源项目里效果较好的路线：

- **Presenta**：Analyze / Design / Generate，先设计再生成。
- **HTMLSlides**：用组件和 layout 约束模型，不让模型裸写 HTML。
- **Slidebook / Starry Slides**：HTML/JSX 是可编辑源文件，生成后先预览和修改。

## Layout 目录

| Layout | 视觉 | LLM 字段约束 |
| --- | --- | --- |
| **cover** | 深色渐变封面 | title ≤20 / subtitle ≤30 |
| **statement** | 全屏单句巨字 + 左侧色条 | text ≤30 |
| **stat-hero** | 280px 大数字 + 注解（"90% 工作量在 Harness 层"） | number ≤8 / caption ≤25 |
| **bullets** | 短要点列表 | 每条 ≤18 字 |
| **icon-grid** | 3-4 个 Lucide 图标卡片 | name ≤8 / desc ≤18 |
| **timeline** | 横向 3-5 节点串联 + 编号圆 | label ≤10 / desc ≤20 |
| **compare** | 2-3 列表格，emerald 表头 | cell ≤14 |
| **two-col** | 短要点 + 解释段 | body ≤80 |
| **quote** | 居中大字 + 出处 | text ≤50 |
| **diagram** | Mermaid 流程图/架构图 | LLM 出 mermaid 代码 |
| **roadmap** | 演讲路线图 | 4-7 个短节点 |
| **architecture** | 技术分层栈 | 3-5 层，每层 1-4 个组件 |
| **quadrant** | 2×2 决策矩阵 | 两条轴 + 四象限建议 |
| **principles** | 原则卡片 | 2-4 条行动原则 |
| **pattern-card** | Context / Problem / Solution 模式卡 | 三段各 ≤50 |
| **code** | 深色代码窗口 | 建议 ≤15 行 |
| **callout** | info/tip/warn/danger 提示框 | body ≤80 |

**视觉精美度的本质**：把视觉决策从 LLM 手里夺回来交给 schema —— LLM 只填短字段，layout 决定一切视觉。这是 PPTAgent / Gamma / Beautiful.ai 共同的设计哲学。

强制配比：**一份 deck 至少一半页面是视觉型 layout**，否则跟原博客摘要没区别。

## 常见扩展（按可玩性排序）

| 想加什么 | 改哪 |
| --- | --- |
| 换 TTS 音色 | `TTS_VOICE=zh-CN-YunxiNeural python pipeline.py` |
| 换视觉风格（深色主题、改字体、加 logo） | 开局用 `--style` 或交互选择；需要新风格再改 [templates/slides.html.j2](templates/slides.html.j2) 的 token |
| 加新 layout（如 code-snippet / chart / image-fullbleed） | 三步：① `01_script.py` 加 Pydantic 模型 + Literal；② `templates/layouts/xxx.html.j2`；③ base 模板加 scoped CSS。半小时一个 |
| 旁白生成后让 LLM 再润色一遍 | 在 01 章后面加 critic 节点，这时就值得上 LangGraph 了 |
| 加背景音乐 | 05 章 `CompositeAudioClip([narration, bgm.volumex(0.1)])` |
| 升级到 CosyVoice 克隆你自己的声音 | 04 章换实现（本地跑模型，6-8GB 显存） |
| 更强的 vision-LLM 检查质量 | 接在 `03_quality.py` 后：先用规则门禁挡硬伤，再把 PNG 喂给 vision model 做审美评分 |

## 常见问题

**Q：跑 03 章报 `Executable doesn't exist`？**
A：忘了 `playwright install chromium`。

**Q：跑 05 章报 `No such file or directory: 'ffmpeg'`？**
A：MoviePy 调系统 ffmpeg，需要 `brew install ffmpeg` 或 `apt install ffmpeg`。

**Q：edge-tts 报网络错误？**
A：edge-tts 走微软的公共 endpoint，国内大多数地区可达；如果你在公司网或有 strict proxy，把 `*.tts.speech.microsoft.com` 加进白名单。

**Q：跑完字幕显示成方框 □□□？**
A：MoviePy 找不到中文字体。设环境变量 `CN_FONT` 指定一个支持中文的 .ttf/.ttc：
```bash
CN_FONT=/System/Library/Fonts/PingFang.ttc python 10_blog_to_video/pipeline.py
```
默认会扫这几个常见路径（macOS PingFang / Linux Noto CJK / Windows 微软雅黑），全找不到才会方框。

**Q：想关掉硬字幕，只留软字幕（YouTube 平台需求）？**
A：改 `05_compose.py` 调用 `compose_video(..., burn_subtitles=False)`，或单跑 05 时改默认。

**Q：LLM 输出的页数或版式不稳？**
A：把 `01_script.py` 里 `temperature=0.3` 调到 0；想要更稳定的版式分布，把 system prompt 里 "5-8 张" 写死成具体数量。

**Q：想要更精致的视觉？**
A：模板这一版很克制（白底 + emerald accent）。可以参考 [tailgrids.com](https://tailgrids.com) / [tailwindui.com](https://tailwindui.com) 的 hero / pricing 组件改写，CSS 那一段是天花板。

## 设计取舍

- **没用 LangGraph**：当前仍是线性工作流，只是多了大纲和 HTML 冻结点；等加 critic loop 再上图更合适
- **没用 Slidev**：Slidev 是 Node.js 工具，引入跨语言依赖；纯 HTML+Jinja+Playwright 全 Python 链路，调试简单
- **没用 LLM 生图**：所有"视觉"都来自 CSS。LLM 在结构化文案上稳定且便宜，生图既贵又不稳，对讲解视频意义不大
- **没加数字人**：MuseTalk / LivePortrait 显存门槛 4GB+，且加上以后质量下限反而被脸的"AI 感"拉低
