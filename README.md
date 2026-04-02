# video-gen

视频生成 skill，现已拆分为两条执行链：

- **短期兼容链**：`scripts/generate_video_easyclaw.py`
  - 保留原有 EasyClaw 网关逻辑
  - 继续依赖 `uid/token`
- **官方直连链**：`scripts/generate_video_ark.py`
  - 直连火山引擎 Ark / Seedance 官方接口
  - 使用 `ARK_API_KEY`
  - 本地图片通过独立适配层转成公网 URL
- **任务查询工具**：`scripts/query_video_task_ark.py`
  - 使用任务 ID 单独查询任务状态
  - 适合排查轮询问题或补查最终结果

---

## 目录结构

```text
video-gen/
├─ .env
├─ SKILL.md
├─ README.md
└─ scripts/
   ├─ download_video.py
   ├─ generate_video.py              # 当前旧版入口（EasyClaw）
   ├─ generate_video_easyclaw.py     # 兼容保留版
   ├─ generate_video_ark.py          # 官方 Ark 直连版
   └─ image_url_adapter.py           # 本地图 -> 公网 URL 适配层
```

---

## 环境变量

放在：

`C:\Users\Administrator\.openclaw\skills\video-gen\.env`

示例：

```env
# 官方 Ark / Seedance
ARK_API_KEY=your_ark_api_key
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3

# 本地图上传适配（短期默认使用 KieAI）
KIEAI_API_KEY=your_kieai_api_key
KIEAI_BASE_URL=https://kieai.redpandaai.co
IMAGE_UPLOAD_PROVIDER=kieai
IMAGE_UPLOAD_PATH=images/video-gen
```

说明：

- `ARK_API_KEY`：官方直连必填
- `ARK_BASE_URL`：可不填，默认官方北京区 v3 地址
- `KIEAI_API_KEY`：仅当你要把**本地图片路径**自动转成公网 URL 时才需要
- `IMAGE_UPLOAD_PROVIDER`：
  - `kieai`：允许自动上传本地图
  - `none`：禁止上传，本地路径将直接报错，只接受公网 URL

---

## 短期方案：先跑通官方直连

### 文生视频

```bash
uv run python scripts/generate_video_ark.py \
  --prompt "a cinematic drone flight through futuristic city lights" \
  --duration 5
```

### 图生视频（公网 URL）

```bash
uv run python scripts/generate_video_ark.py \
  --prompt "slow camera push in, subtle wind motion, cinematic lighting" \
  --image "https://example.com/demo.jpg" \
  --duration 5
```

### 图生视频（本地图片自动上传）

```bash
uv run python scripts/generate_video_ark.py \
  --prompt "smooth 360 degree product rotation, rim light, dark premium background" \
  --image "C:\\path\\to\\product.png" \
  --duration 5
```

### 只预览 payload（不提交任务）

```bash
uv run python scripts/generate_video_ark.py \
  --prompt "a dragon emerges from a sketchbook" \
  --image "C:\\path\\to\\dragon.png" \
  --duration 5 \
  --dry-run
```

### 按任务 ID 补查状态

```bash
uv run python scripts/query_video_task_ark.py cgt-xxxxxxxxxxxxxxxx
```

逻辑：

1. 如果 `--image` 是 `http/https URL`，直接传给 Ark
2. 如果 `--image` 是本地路径，则交给 `image_url_adapter.py`
3. `image_url_adapter.py` 按 `.env` 中的 `IMAGE_UPLOAD_PROVIDER` 处理
4. 当前默认 provider 为 `kieai`

---

## 中期方案：解耦上传层

当前本地图转公网 URL 的逻辑已经被抽离到：

- `scripts/image_url_adapter.py`

下一步建议：

1. 新增更多 provider（如 catbox / 自建 OSS / S3 / R2）
2. 给 adapter 增加：
   - 文件大小限制
   - 允许格式白名单
   - 更严格的返回结构校验
3. 将 `generate_video_ark.py` 保持为“只关心模型调用，不关心上传细节”

---

## 长期方案：彻底去掉临时图床依赖

更理想的长期结构：

1. 本地图先上传到你自己的稳定对象存储
2. 再把稳定 URL 提供给 Ark
3. 上传层和模型层彻底解耦
4. `generate_video.py` 最终可以变成统一入口，内部按 provider 分发

长期目标不是“隐藏 uid/token”，而是：

- 不再读取 `.easyclaw` 身份文件
- 不再发 `X-AUTH-UID` / `X-AUTH-TOKEN`
- 不再依赖 `aibot-srv.easyclaw.cn`
- 不再依赖 EasyClaw 的 payload 兼容行为
- 只保留：官方模型 + 官方 endpoint + Bearer Key

---

## 下载视频

两条链都可复用：

```bash
uv run python scripts/download_video.py "<video_url>" -o "C:\\path\\to\\output.mp4"
```

---

## 注意事项

1. `generate_video_easyclaw.py` 是保留兼容，不是未来主线
2. `generate_video_ark.py` 才是你现在要逐步迁移到的主线
3. 如果 Ark 官方后续对 `generate_audio`、图片格式、返回结构有变化，以官方接口文档为准
4. 当前 `.env` 中有真实 key，建议后续避免在对话、日志、README 中直接暴露
