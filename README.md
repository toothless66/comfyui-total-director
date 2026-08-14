# ComfyUI Total Director

Chat→Director-Plan→MiniMax H3 工作流的「总调度」扩展。在 ComfyUI 左侧浮动面板里输入一句话需求/分镜脚本,后端 LLM 自动生成导演方案,一键组装可运行的工作流并载入画布或直接排队。

## 架构

```
┌─────────────────────────────┐     ┌──────────────────────────────────┐
│  前端 Floating Panel        │     │  后端 (ComfyUI custom node)      │
│  js/director.js             │     │  ──────────────────────────────── │
│  - 创作 / 方案 / 设置 3个tab │────▶│  server/routes.py  (aiohttp 路由) │
│  - 附图上传→/upload/image    │     │  server/llm.py     (两阶段 LLM)  │
│  - 构建→app.loadGraphData()  │     │  server/workflow.py(工作流组装)   │
│  - 运行→app.graphToPrompt()  │     │  server/env.py     (环境快照)     │
│    + api.queuePrompt()       │     │  server/config.py  (配置管理)     │
└─────────────────────────────┘     └──────────────────────────────────┘
```

端口速览:所有 `/director/*` 路由同时以 `/api/director/*` 注册(ComfyUI 在
`PromptServer.add_routes()` 里统一加 `/api` 前缀,该步骤在 custom_nodes 加载完之后执行)。

## 前端提交机制

1. `POST /api/director/plan` → 返回 `{plan, preview}`(两阶段 LLM,方案可直接改)。
2. `POST /api/director/build` → 返回 save-format 工作流 JSON(`workflow` / `workflow_json`)。
3. `await app.loadGraphData(workflow)` 载入画布(用户可见可改)。
4. 可选自动运行:`const p = await app.graphToPrompt()` 得到 `{output, workflow}`
   (output 即 API-format),再 `await api.queuePrompt(0, p)` 提交执行。

模板是用户自己的 MiniMax H3 工作流(含 subgraph),后端只打补丁装参数,保证结构/连接对该版本 ComfyUI 有效。

## 四类流水线

| pipeline  | 说明 | 数据来源 |
|-----------|------|----------|
| `t2v`     | 文本直接转视频 | H3 模板 `h3_t2v.json` |
| `i2v`     | 首帧图 → 视频 | `h3_i2v.json` + 面板附图(`/upload/image` 后按 `subfolder/name`) |
| `r2v`     | 1-2 张参考图 → 视频 | `h3_r2v.json` |
| `sdxl2v`  | SDXL 生成关键帧 → H3 I2V 全流程 | `h3_t2v.json` + 动态拼接 SDXL 段 |

## LLM 两阶段设计

- **Stage A** — 紧凑参数 JSON(`pipeline/duration_s/aspect/megapixels/sampler/steps/audio/notes_cn/keyframe_*`),小模型也容易填对。
- **Stage B** — 单独生成完整英文 `megaprompt`(带分镜 timecode、镜头、音频),`_merge_stage_b` 合并;
  对本地 qwen3-vl 等推理模型做 `thinking` 回退。
- 数据来源 `_summarize_env()`:把当前 models/流水线/GPU/Ollama 喂给 LLM 让其自行选 pipeline。

## 多模型协调(dual 模式)

`llm.roles_mode` 设为 `dual` 后,plan 拆成三个角色,可由不同本地模型协作:

| 角色 | 职责 | 默认模型 |
|------|------|----------|
| `stage_a` | 梳理需求 → 生产参数 | `deepseek-r1:14b` |
| `stage_b` | 写完整 megaprompt | `deepseek-r1:14b` |
| `stage_c` | 执行终审 / 视觉核对(制片人视角) | `qwen3-vl:8b` |

- `llm.roles_mode`: `"single"`(默认,单模型走两阶段)或 `"dual"`。
- `stage_*_model` 可单独指定任意 Ollama 模型;留空则跳过该角色(如跳过 stage_c 只做双阶段)。
- 前端方案预览会显示 `协调 A→B→C` 各自模型。
- 对 deepseek 系推理模型,后端自动切换为思考模式并禁用 `format:json`(已验证:强制 JSON 会让 deepseek-r1 输出塌缩成 `{ }`)。

> 提示:dual 模式会多次调用本地 LLM,单次全链路约 2-4 分钟(deepseek 推理较慢);想提速可让 stage_a/b 使用 qwen3-vl:8b。

## 配置

`config.json`(首次保存时在扩展根目录生成),默认值见 `server/config.py` `_DEFAULTS`:

```jsonc
{
  "llm": {
    "provider": "ollama",            // "ollama" | "api"
    "ollama_host": "http://127.0.0.1:11434",
    "ollama_model": "qwen3-vl:8b",   // 本地首选；qwen3-vl 支持附图
    "api_base": "https://api.deepseek.com/v1",
    "api_key": "",
    "api_model": "deepseek-chat",
    "vision_enabled": true,
    "roles_mode": "single",              // "single" | "dual"
    "stage_a_model": "deepseek-r1:14b",  // dual: 梳理参数
    "stage_b_model": "deepseek-r1:14b",  // dual: 写提示词
    "stage_c_model": "qwen3-vl:8b"       // dual: 执行终审
  },
  "build": {
    "default_aspect": "16:9",
    "default_megapixels": 0.4,       // 8GB VRAM 友好 0.2-0.6
    "max_duration_s": 15.0,
    "sampler": "res_multistep",
    "steps": 20,
    "sdxl_checkpoint": "RealVisXL_V5.0_fp16.safetensors",
    "output_prefix": "video/Director",
    "keyframe_prefix": "director/keyframes"
  }
}
```

## API

| Method | Path | Body | 返回 |
|--------|------|------|------|
| GET  | `/api/director/status` | — | 环境快照 + LLM/build 配置摘要 |
| POST | `/api/director/plan` | `{message, image_base64?}` | `{plan, preview, model}` |
| POST | `/api/director/refine` | `{plan, instruction}` | 同上 |
| POST | `/api/director/build` | `{plan, first_frame_image?, reference_images?, name?}` | `{workflow, workflow_json, name}` |
| GET  | `/api/director/config` | — | 配置(api_key 打码) |
| POST | `/api/director/config` | `{config}` | 更新后的配置 |
| GET  | `/api/director/models` | — | models/pipelines/gpu |

## 安装

1. 克隆到 ComfyUI 的 `custom_nodes` 目录:

   ```powershell
   cd D:\MiniMaxH3\ComfyUI_windows_portable\ComfyUI\custom_nodes
   git clone https://github.com/toothless66/comfyui-total-director.git
   ```

2. 准备你自己的 MiniMax H3 工作流模板:`server/templates/` 下放你导出的
   `h3_t2v.json` / `h3_i2v.json` / `h3_r2v.json`(save-format,含 subgraph)。
3. 安装/运行 Ollama 并拉取要用的模型(见"多模型协调")。
4. 重启 ComfyUI。面板会在画布左侧出现(快捷键 **Alt+D** 切换显隐)。

## 使用方法(一键成片)

1. **创作 tab**:输入一句话需求或分镜脚本,如
   `一只机械鸟在雨夜霓虹城市上空盘旋,赛博朋克风,3秒短视频`。
   - i2v/sdxl2v 可先在"附图"上传首帧或参考图。
2. 点 **生成方案**:后端 LLM 返回导演方案(参数 + 英文 megaprompt + 中文备注),
   显示在"方案"tab,可直接编辑。
3. 点 **构建**:组装出可运行工作流并载入画布(可见、可手动微调)。
4. 点 **一键成片**:自动提交队列执行并监控结果,完成后在面板内预览成片。
   执行期间面板显示生成进度,完成后自动回收输出文件。

## 调优建议

- 8GB VRAM 建议 `build.default_megapixels: 0.2-0.4`,时长 ≤ 5s,避免爆显存。
- 生成耗时较长(3-4 分钟)属正常;监控已按 prompt_id 精确判定,不会误报超时。
- 想换 LLM:设置 tab 里改 `ollama_model` / `roles_mode` / `stage_*_model`,保存立即生效。

## 开发 & 测试

用 ComfyUI 自带的 python(含 aiohttp):

```powershell
cd C:\project\comfyui-total-director
& D:\MiniMaxH3\ComfyUI_windows_portable\python_embeded\python.exe test_standalone.py env     # 环境快照
& ...python.exe test_standalone.py build     # 四种流水线组装冒烟
& ...python.exe test_standalone.py plan "您的需求"   # 两阶段 LLM 实测(需 Ollama 运行)
& ...python.exe test_routes.py               # aiohttp 路由冒烟(打桩 LLM/workflow)
```

部署:项目通过 junction 挂到 `ComfyUI\custom_nodes\comfyui-total-director`,重启 ComfyUI 生效。
前端面板:Alt+D 切换显隐(URL 加载后才有,需等 ComfyUI 完成启动)。