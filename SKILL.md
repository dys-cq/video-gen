---
name: video-gen
description: 视频生成工具，支持文生视频和图生视频。当前主线为火山引擎 Seedance 官方 Ark 接口，支持本地图片自动上传、自动下载和可选 JSON 结果输出。触发词：生成视频、文生视频、图生视频、video generation
---

# 视频生成（Video Generation）

使用火山引擎 Seedance 模型生成高质量视频，支持：

- 文生视频（text-to-video）
- 图生视频（image-to-video）

当前推荐主线为 **官方 Ark 直连**。

---

## 当前实现状态

本 skill 现已拆分为两条执行链：

- **兼容保留链（旧版）**：`scripts/generate_video_easyclaw.py`
  - 保留 EasyClaw 网关逻辑
  - 继续依赖 `uid/token`
  - 仅用于兼容历史调用
- **官方直连链（推荐主线）**：`scripts/generate_video_ark.py`
  - 直连官方 Ark API：`https://ark.cn-beijing.volces.com/api/v3`
  - 使用 `ARK_API_KEY`
  - 支持本地图片通过独立适配层上传为公网 URL
  - 支持 `catbox` / `kieai` / `none`
  - 支持成功后自动下载视频
  - 支持轮询容错与补查提示
  - 支持 `--json` 可选结果输出

默认建议优先使用：

```bash
uv run python {baseDir}/scripts/generate_video_ark.py ...
```

详细环境变量、迁移背景与验证记录见同目录下 `README.md`。

---

## 触发条件

- 生成视频 / 文生视频 / 图生视频
- video generation / text to video / image to video
- 把图片转成视频 / 让图片动起来

---

## 前置依赖

### 推荐：官方 Ark 直连

从技能目录 `.env` 读取：

- `ARK_API_KEY`
- `ARK_BASE_URL`（可选，默认官方北京区 v3 地址）
- `KIEAI_API_KEY`（仅当 provider 为 `kieai` 时使用）
- `IMAGE_UPLOAD_PROVIDER`（可选，当前推荐默认 `catbox`）
- `IMAGE_UPLOAD_MAX_MB`（可选）

### 兼容保留：EasyClaw 旧链路

旧脚本仍可从以下文件读取认证信息：

- `~/.easyclaw/easyclaw.json`
- `~/.easyclaw/identity/easyclaw-userinfo.json`

但它不是未来主线，不建议新流程继续依赖。

---

## 官方主线能力

### 1) 文生视频

```bash
uv run python {baseDir}/scripts/generate_video_ark.py \
  --prompt "a cinematic drone flight through futuristic city lights" \
  --duration 5
```

### 2) 图生视频（公网 URL）

```bash
uv run python {baseDir}/scripts/generate_video_ark.py \
  --prompt "slow camera push in, subtle wind motion, cinematic lighting" \
  --image "https://example.com/demo.jpg" \
  --duration 5
```

### 3) 图生视频（本地图片自动上传）

```bash
uv run python {baseDir}/scripts/generate_video_ark.py \
  --prompt "ink dragon emerges from a drawing" \
  --image "C:\\path\\to\\dragon.png" \
  --duration 5
```

### 4) 指定使用 catbox 上传本地图

```bash
uv run python {baseDir}/scripts/generate_video_ark.py \
  --prompt "ink dragon emerges from a drawing" \
  --image "C:\\path\\to\\dragon.png" \
  --upload-provider catbox \
  --duration 5
```

### 5) 自动下载视频

```bash
uv run python {baseDir}/scripts/generate_video_ark.py \
  --prompt "a dragon emerges from a sketchbook" \
  --image "C:\\path\\to\\dragon.png" \
  --duration 5 \
  --auto-download \
  --download-output "C:\\path\\to\\output.mp4"
```

### 6) 成功后输出结构化 JSON

```bash
uv run python {baseDir}/scripts/generate_video_ark.py \
  --prompt "a dragon emerges from a sketchbook" \
  --image "C:\\path\\to\\dragon.png" \
  --duration 5 \
  --auto-download \
  --download-output "C:\\path\\to\\output.mp4" \
  --json
```

### 7) 控制轮询容错

```bash
uv run python {baseDir}/scripts/generate_video_ark.py \
  --prompt "a dragon emerges from a sketchbook" \
  --duration 5 \
  --max-polls 120 \
  --max-query-failures 6
```

### 8) 按任务 ID 补查状态

```bash
uv run python {baseDir}/scripts/query_video_task_ark.py cgt-xxxxxxxxxxxxxxxx
```

---

## 推荐执行流程

### 第一步：确认生成模式

询问用户是：

- **文生视频**：直接输入文字描述生成视频
- **图生视频**：提供图片 + 文字描述，让图片动起来

### 第二步：收集输入内容

**文生视频模式**：

- 收集视频描述文字
- 询问视频时长（可选）

**图生视频模式**：

- 收集用户上传的图片（支持本地路径或 URL）
- 收集用户描述（图片中元素如何运动）
- 询问视频时长（可选）

### 第三步：构建 Prompt

继续建议使用专业电影/视频术语来提升质量，例如：

- 镜头类型：`close-up`, `wide shot`, `medium shot`
- 运镜方式：`tracking shot`, `dolly in`, `pan`, `static`
- 光线条件：`golden hour`, `rim light`, `soft light`
- 氛围/特效：`cinematic tone`, `motion blur`, `bokeh`, `shallow depth of field`

Prompt 构建公式：

```text
[主体描述], [动作/运动], [场景环境], [镜头类型], [运镜方式],
[光线条件], [色彩风格], [特效/氛围], [画质要求]
```

### 第四步：执行官方主线脚本

优先使用：

```bash
uv run python {baseDir}/scripts/generate_video_ark.py ...
```

### 第五步：必要时补查

如果轮询超时或连续失败，可用：

```bash
uv run python {baseDir}/scripts/query_video_task_ark.py <task_id>
```

---

## 当前已验证状态

截至当前版本，以下官方链路已经完成真实回归验证：

**本地图片 → Catbox 上传 → Ark 官方接口 → Seedance 生成 → 自动下载 mp4 → 脚本正常 exit 0**

已验证样例：

- Task ID：`cgt-20260402194840-lnd4n`
- 模型：`doubao-seedance-1-5-pro-251215`
- 时长：`12s`
- 自动下载输出：
  - `C:\Users\Administrator\.openclaw\workspace\output\dragon-video-12s-rerun.mp4`

这说明 `generate_video_ark.py --auto-download` 目前已经可以单脚本闭环运行。

---

## 注意事项

1. `generate_video_ark.py` 是当前主线
2. `generate_video_easyclaw.py` 只做兼容保留
3. `catbox` 适合测试和轻量桥接，不适合作长期正式素材库
4. 默认不改变人类可读输出；只有显式传入 `--json` 才追加结构化结果
5. 当前 `.env` 中的真实 key 不要提交到 GitHub
6. 如果需要高稳定长期方案，后续建议换成自建 OSS / S3 / R2 之类的稳定对象存储

---

## 文件位置

| 文件 | 路径 |
|------|------|
| 官方主线脚本 | `{baseDir}/scripts/generate_video_ark.py` |
| 旧兼容脚本 | `{baseDir}/scripts/generate_video_easyclaw.py` |
| 任务查询脚本 | `{baseDir}/scripts/query_video_task_ark.py` |
| 下载脚本 | `{baseDir}/scripts/download_video.py` |
| 上传适配层 | `{baseDir}/scripts/image_url_adapter.py` |

> `{baseDir}` = skill 所在目录（如 `C:\Users\Administrator\.openclaw\skills\video-gen`）
