# 🎬 ComfyUI Director — 一句话变成片

> **"我 build 这个项目的原因,是觉得手动搭建 ComfyUI 工作流真的太麻烦了,对小白完全不友好。"**
> 于是我在 ComfyUI 里挂了个「导演」,你说一句话,它自己当编剧、制片人、摄影师和剪辑师,把成片递给你。

[English README](README.en.md) · [中文](README.md)

---

## 这是什么?

ComfyUI 左侧的一个**浮动导演面板**。你输入一句话(或分镜脚本),它自动:

1. **想方案** — 后端 LLM 拆解需求,决定用什么模型/时长/分辨率/运镜
2. **写提示词** — 生成带分镜 timecode、镜头、音频的完整英文 megaprompt
3. **搭工作流** — 把你的 MiniMax H3 工作流模板自动组装好(不需要你连线)
4. **一键成片** — 排队执行、监控进度、生成完成直接在面板里预览成片

手动搭 H3 工作流要拖一堆节点、填 unet/clip/vae 路径、调分辨率、写英文提示词……导演把这些全包了。

## ✨ 亮点

- **零门槛**:只说人话,如 *"一只机械鸟在雨夜霓虹城市上空盘旋,赛博朋克风,3秒"*
- **四类流水线**:`t2v` 文生视频 / `i2v` 首帧图生视频 / `r2v` 参考图生视频 / `sdxl2v` SDXL 关键帧全流程
- **导演设计能力**:内置设计知识库(风格库/镜头语言/色彩情绪/节奏设计),每次按需求给出独特的创意方向与情绪标签
- **长剧本自动拆场景**:输入多场景脚本,自动拆成多个分镜,每个场景独立构建工作流、独立出片
- **多模型协调(dual 模式)**:deepseek 梳理需求 + 写提示词,qwen 做执行终审(制片人视角复查),分工协作
- **可干预**:生成的方案直接可编辑,工作流载入画布后看得见、改得动
- **真·一键**:从文案到成片全程一个按钮,含进度监控 + 成片预览

## 🚀 安装

1. 克隆到 ComfyUI 的 `custom_nodes` 目录:

   ```bash
   cd D:\MiniMaxH3\ComfyUI_windows_portable\ComfyUI\custom_nodes
   git clone https://github.com/toothless66/comfyui-total-director.git
   ```

2. 放好你的 H3 工作流模板:`server/templates/` 下放你导出的
   `h3_t2v.json` / `h3_i2v.json` / `h3_r2v.json`(save-format,含 subgraph)。
3. 安装 [Ollama](https://ollama.com) 并拉取要用的模型(默认 `qwen3-vl:8b`,可换)。
4. 重启 ComfyUI。刷新浏览器,面板出现在画布左侧(**Alt+D** 切换显隐)。

## 🎥 怎么用

| 步骤 | 操作 |
|------|------|
| 1. 说需求 | 「创作」tab 输入一句话 / 分镜脚本(可选上传首帧图) |
| 2. 生成方案 | 点「生成方案」,看导演怎么拆解(含设计理念、情绪标签) |
| 3. 构建工作流 | 点「构建并载入画布」,可微调 |
| 4. 一键成片 | 点「一键成片」,面板显示进度,完成后直接预览 |

> **多场景脚本**:方案 tab 会把长剧本拆成多个分镜卡片,每个卡片可单独「构建并运行」,
> 各自生成独立视频,方便逐条剪辑。

### Dual 模式(多模型协调)

`设置` tab 里把 `roles_mode` 改成 `dual`,plan 阶段由三个角色协作:

| 角色 | 职责 | 默认模型 |
|------|------|----------|
| 🧠 A | 梳理需求 → 参数 | `deepseek-r1:14b` |
| ✍️ B | 写完整 megaprompt | `deepseek-r1:14b` |
| 🎬 C | 执行终审 / 视觉核对 | `qwen3-vl:8b` |

- 方案预览会显示 `协调 A→B→C` 各自的模型,全程透明
- `stage_*_model` 可单独换;留空跳过该角色
- 对 deepseek 系推理模型自动切换思考模式并禁用强制 JSON(否则会塌缩成 `{ }`)

> 💡 提速:dual 单次约 2-4 分钟(deepseek 推理较慢),可让 stage_a/b 用 qwen3-vl:8b。

## ⚙️ 配置

`config.json`(首次保存时在扩展根目录生成):

```jsonc
{
  "llm": {
    "provider": "ollama",            // "ollama" | "api"
    "ollama_host": "http://127.0.0.1:11434",
    "ollama_model": "qwen3-vl:8b",
    "api_base": "https://api.deepseek.com/v1",
    "api_key": "",                    // 仅 provider=api 时需要
    "api_model": "deepseek-chat",
    "roles_mode": "single",           // "single" | "dual"
    "stage_a_model": "deepseek-r1:14b",
    "stage_b_model": "deepseek-r1:14b",
    "stage_c_model": "qwen3-vl:8b"
  },
  "build": {
    "default_aspect": "16:9",
    "default_megapixels": 0.4,        // 8GB VRAM 建议 0.2-0.4
    "max_duration_s": 15.0,
    "sampler": "res_multistep",
    "steps": 20,
    "output_prefix": "video/Director"
  }
}
```

## 🛠 架构

```
┌─────────────────────────────┐     ┌──────────────────────────────────┐
│  前端 Floating Panel        │     │  后端 (ComfyUI custom node)      │
│  js/director.js             │────▶│  server/routes.py  (aiohttp 路由) │
│  - 创作 / 方案 / 设置 3个tab │     │  server/llm.py     (LLM 规划)     │
│  - 附图上传 → /upload/image  │     │  server/workflow.py(工作流组装)   │
│  - 构建 → app.loadGraphData()│     │  server/env.py     (环境快照)     │
│  - 运行 → api.queuePrompt()  │     │  server/config.py  (配置管理)     │
└─────────────────────────────┘     └──────────────────────────────────┘
```

## 📡 API

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/director/status` | 环境快照 + 配置摘要 |
| POST | `/api/director/plan` | `{message, image_base64?}` → `{plan, preview, model}` |
| POST | `/api/director/refine` | 改写方案 |
| POST | `/api/director/build` | 组装工作流 JSON |
| GET/POST | `/api/director/config` | 读写配置(api_key 打码) |
| GET | `/api/director/result/{prompt_id}` | 按 prompt_id 回收成片文件 |

## 🧪 开发 & 测试

```powershell
# 用 ComfyUI 自带的 python(含 aiohttp)
& D:\MiniMaxH3\ComfyUI_windows_portable\python_embeded\python.exe test_standalone.py env
& ...\python.exe test_standalone.py build        # 流水线组装冒烟
& ...\python.exe test_standalone.py plan "需求"   # LLM 实测(需 Ollama)
& ...\python.exe test_routes.py                  # 路由冒烟
```

## 📝 说明

- 模板是**你自己**的 H3 工作流,后端只打补丁装参数,兼容你当前的 ComfyUI 版本
- 本项目是 **vibe coding** 的产物:边聊天边实现,可能有不完美的地方,欢迎 PR / Issues
- 参考:ComfyUI、[MiniMax H3](https://www.minimax.io/blog/minimax-h3)、Ollama
