---
name: video-gen
description: 视频生成工具，支持文生视频和图生视频。使用火山引擎 Seedance 模型，支持专业电影术语构建 Prompt。触发词：生成视频、文生视频、图生视频、video generation
---

# 视频生成（Video Generation）

使用火山引擎 Seedance 模型生成高质量视频，支持文生视频和图生视频两种模式。

## 当前实现状态

本 skill 现已拆分为两条执行链：

- **兼容保留链（旧版）**：`scripts/generate_video_easyclaw.py`
  - 继续走 EasyClaw 网关
  - 继续依赖 `uid/token`
- **官方直连链（推荐）**：`scripts/generate_video_ark.py`
  - 直连官方 Ark API
  - 使用 `ARK_API_KEY`
  - 本地图片会通过独立适配层转换为公网 URL

默认建议优先使用：

```bash
uv run python {baseDir}/scripts/generate_video_ark.py ...
```

详细环境变量和迁移说明见同目录下 `README.md`。

## 触发条件

- 生成视频 / 文生视频 / 图生视频
- video generation / text to video / image to video
- 把图片转成视频 / 让图片动起来

## 前置依赖

### 推荐：官方 Ark 直连

从技能目录 `.env` 读取：

- `ARK_API_KEY`
- `ARK_BASE_URL`（可选）
- `KIEAI_API_KEY`（仅当本地图片需要自动上传成公网 URL 时使用）
- `IMAGE_UPLOAD_PROVIDER`（可选，默认 `kieai`）

### 兼容保留：EasyClaw 旧链路

旧脚本仍可从以下文件读取认证信息：

- `~/.easyclaw/easyclaw.json`（包含 baseUrl 配置）
- `~/.easyclaw/identity/easyclaw-userinfo.json`（包含 uid 和 token）

---

## 执行流程

### 第一步：确认生成模式

询问用户是**文生视频**还是**图生视频**：

> 请选择生成模式：
>
> - **文生视频**：直接输入文字描述生成视频
> - **图生视频**：提供图片 + 文字描述，让图片动起来（推荐：保持角色/场景一致性）
>
> 请发送图片（图生视频）或直接描述视频内容（文生视频）~

### 第二步：收集输入内容

**文生视频模式**：

- 收集用户的视频描述文字
- 询问视频时长（可选，默认自动）

**图生视频模式**：

- 收集用户上传的图片（支持本地路径或 URL）
- 收集用户描述（图片中元素如何运动）
- 询问视频时长（可选，默认自动）

---

## 图生视频详解（Image-to-Video）

### 为什么用图生视频？

**文生视频的痛点**：

- 每次生成结果不可控，同样描述可能产出完全不同的角色/场景
- 无法保持系列视频的视觉一致性
- "开盲盒"式体验，需要多次抽卡

**图生视频的优势**：

| 优势           | 说明                                            |
| -------------- | ----------------------------------------------- |
| **视觉一致性** | 输入图片成为视频第 1 帧，角色/场景/风格完全一致 |
| **精准控制**   | 图片决定"长什么样"，文字决定"怎么动"            |
| **系列制作**   | 同一角色可生成多个场景视频，保持连贯性          |
| **可控性高**   | 避免随机性，一次生成即可满足需求                |

### 适用场景

- **角色动画**：让固定角色做不同动作（走路、跳舞、说话）
- **产品展示**：产品外观固定，展示不同角度/使用场景
- **分镜制作**：保持场景基调一致，只改变镜头运动
- **系列内容**：同一 IP 形象的多集视频（如"旺财的日常生活"）

### 图生视频 Prompt 技巧

**不要重复描述画面内容**（图片已经决定了），而是描述：

- **运动方式**：如何移动、旋转、缩放
- **运镜方式**：镜头如何跟随主体
- **氛围变化**：光线、天气、环境如何变化

**示例**：

- 图片：一只橘猫的照片
- ❌ 错误 Prompt：`an orange cat sitting on a sofa, looking around`（重复描述猫）
- ✅ 正确 Prompt：`slowly turns head to look around, soft natural lighting, gentle camera pan following the movement`（只描述运动和运镜）

### 第三步：构建专业 Prompt

使用电影/视频行业专业术语优化 Prompt，提升生成质量。

#### 核心术语分类

| 类别         | 常用术语                                             | 效果说明         |
| ------------ | ---------------------------------------------------- | ---------------- |
| **镜头类型** | extreme close-up, close-up, medium shot, wide shot   | 根据主体大小选择 |
| **运镜方式** | tracking shot, dolly in/out, pan, handheld, static   | 控制画面动态     |
| **视角角度** | low angle, high angle, eye level, overhead           | 营造心理感受     |
| **光线效果** | golden hour, rim light, soft light, volumetric light | 塑造氛围         |
| **色彩风格** | cinematic tone, teal and orange, high contrast       | 确定整体调性     |
| **特效**     | slow motion, motion blur, lens flare, bokeh          | 增强视觉冲击     |
| **画质**     | 8K resolution, highly detailed, sharp focus          | 保证专业品质     |

#### Prompt 构建公式

```
[主体描述], [动作/运动], [场景环境], [镜头类型], [运镜方式],
[光线条件], [色彩风格], [特效/氛围], [画质要求]
```

**示例**：

- 基础描述：`一个人在海边走路`
- 专业 Prompt：`a person walking along the coastline, tracking shot following from behind, golden hour lighting with warm orange tones, cinematic color grading, shallow depth of field with bokeh, motion blur on waves, highly detailed, 8K resolution`

### 第四步：调用生成脚本

**文生视频**（默认无声）：

```bash
python {baseDir}/scripts/generate_video.py --prompt "专业 Prompt" --duration 8
```

**文生视频**（带声音）：

```bash
python {baseDir}/scripts/generate_video.py --prompt "专业 Prompt" --duration 8 --audio
```

**图生视频**（支持本地路径或 URL，默认无声）：

```bash
python {baseDir}/scripts/generate_video.py --prompt "专业 Prompt" -i "C:\path\to\image.jpg" --duration 8
python {baseDir}/scripts/generate_video.py --prompt "专业 Prompt" -i "https://example.com/image.jpg" --duration 8
```

**参数说明**：
| 参数 | 说明 |
|------|------|
| `--prompt` | 视频描述（建议使用专业术语） |
| `-i`, `--image` | 参考图片：**本地路径**或**URL**均可（图生视频时可选） |
| `--duration` | 视频时长（秒），Pro 模型支持 4-12s，Fast 模型支持 2-12s |
| `--model` | 模型选择，默认 `doubao-seedance-1-5-pro-251215` |
| `--audio` | 生成带声音的视频（默认**无声**，需要声音时添加此参数） |

**支持的模型**：

- `doubao-seedance-1-5-pro-251215`（默认，质量优先）
- `doubao-seedance-1-0-pro-fast-251015`（速度优先）

### 第五步：下载视频

生成完成后，脚本会输出视频下载 URL。调用下载脚本：

```bash
python {baseDir}/scripts/download_video.py "视频 URL" -o "输出路径.mp4"
```

**参数说明**：
| 参数 | 说明 |
|------|------|
| `url` | 视频下载链接（必填） |
| `-o, --output` | 保存路径（默认：`~/Downloads/generated_video_时间戳.mp4`） |

---

## 完整示例

### 示例 1：文生视频 - 海边漫步

**用户输入**：`生成一个人在海边走路的视频`

**优化后的 Prompt**：

```
a person walking along the coastline at sunset, tracking shot following from behind,
golden hour lighting with warm orange and purple tones, cinematic color grading,
shallow depth of field with bokeh background, gentle motion blur on ocean waves,
highly detailed textures, 8K resolution, film-like atmosphere
```

**执行命令**：

```bash
python {baseDir}/scripts/generate_video.py --prompt "a person walking along the coastline at sunset, tracking shot following from behind, golden hour lighting with warm orange and purple tones, cinematic color grading, shallow depth of field with bokeh background, gentle motion blur on ocean waves, highly detailed textures, 8K resolution, film-like atmosphere" --duration 8
```

### 示例 2：图生视频 - 产品展示（本地图片）

**用户输入**：上传了一张耳机产品图 + 描述`让耳机旋转展示`

**优化后的 Prompt**：

```
white wireless earbuds floating in clean minimal background, smooth 360 degree rotation,
close-up showing product details, rim light outlining shape, soft blue LED glow,
minimalist composition, high contrast with deep blacks, sharp focus on product,
shallow depth of field, 8K resolution, tech product showcase
```

**执行命令**：

```bash
python {baseDir}/scripts/generate_video.py --prompt "white wireless earbuds floating in clean minimal background, smooth 360 degree rotation, close-up showing product details, rim light outlining shape, soft blue LED glow, minimalist composition, high contrast with deep blacks, sharp focus on product, shallow depth of field, 8K resolution, tech product showcase" -i "C:\Users\CF\Desktop\earbuds.jpg" --duration 6
```

---

## 专业术语速查表

### 镜头类型 (Shot Types)

| 术语             | 含义   | 适用场景               |
| ---------------- | ------ | ---------------------- |
| extreme close-up | 极特写 | 产品细节、珠宝切面     |
| close-up         | 特写   | 人物表情、产品纹理     |
| medium shot      | 中景   | 人物半身、产品使用场景 |
| wide shot        | 全景   | 环境展示、大场景       |

### 运镜方式 (Camera Movement)

| 术语          | 含义     | 适用场景           |
| ------------- | -------- | ------------------ |
| tracking shot | 跟随拍摄 | 移动主体、运动场景 |
| dolly in/out  | 推拉镜头 | 强调细节或展现场景 |
| pan           | 平移     | 展示宽度、环绕主体 |
| handheld      | 手持感   | 真实感、纪录片风格 |
| static        | 固定机位 | 稳定展示、科技产品 |

### 光线与色彩 (Lighting & Color)

| 术语            | 含义     | 效果               |
| --------------- | -------- | ------------------ |
| golden hour     | 黄金时刻 | 温暖柔和，日出日落 |
| blue hour       | 蓝调时刻 | 冷峻神秘，黎明黄昏 |
| rim light       | 轮廓光   | 勾勒主体边缘       |
| soft light      | 柔光     | 均匀照明，人像美妆 |
| hard light      | 硬光     | 强烈阴影，强调质感 |
| cinematic tone  | 电影色调 | 专业电影感         |
| teal and orange | 青橙色调 | 好莱坞风格         |

### 特效与氛围 (Effects)

| 术语           | 含义     | 效果               |
| -------------- | -------- | ------------------ |
| slow motion    | 慢动作   | 强调瞬间，液体飞溅 |
| motion blur    | 动态模糊 | 速度感             |
| lens flare     | 镜头光晕 | 科技感、阳光感     |
| bokeh          | 背景光斑 | 虚化背景，突出主体 |
| depth of field | 景深     | 前景清晰背景虚化   |
| film grain     | 胶片颗粒 | 复古质感           |

---

## 黄金法则

1. **拒绝模糊形容词**：不用"好看""炫酷""漂亮"，改用 `cinematic` `high contrast` `rim light`
2. **镜头先行**：先确定 shot type，再描述内容
3. **光影定调**：光线决定 80% 的氛围
4. **动态为王**：描述主体如何运动（rotation/tracking/pan）
5. **图生视频**：描述图片中元素的运动方式，而非重新描述画面内容
6. **优先图生视频**：需要 consistency 时，用图片锁定视觉，文字控制动态

---

## 注意事项

- **时长限制**：Pro 模型 4-12 秒，Fast 模型 2-12 秒
- **生成时间**：通常需要 3-5 分钟，请提前告知用户等待
- **消耗积分**：使用 EasyClaw 用户积分进行生成
- **网络稳定**：生成过程中请保持网络连接稳定
- **音频设置**：默认生成**无声视频**，如需声音请添加 `--audio` 参数
  - 无声视频更适合后期配音、添加背景音乐
  - 带声音视频由 AI 自动生成与画面对应的音效
- **图片格式**：支持 JPG、PNG 等常见格式，超 256 万像素会自动压缩

---

## 文件位置

| 文件     | 路径                                  |
| -------- | ------------------------------------- |
| 生成脚本 | `{baseDir}/scripts/generate_video.py` |
| 下载脚本 | `{baseDir}/scripts/download_video.py` |

> `{baseDir}` = skill 所在目录（如 `~/.easyclaw/skills/video-gen`）
