# video-gen

视频生成 skill，现已拆分为三块：

- **短期兼容链**：`scripts/generate_video_easyclaw.py`
  - 保留原有 EasyClaw 网关逻辑
  - 继续依赖 `uid/token`
- **官方直连链**：`scripts/generate_video_ark.py`
  - 直连火山引擎 Ark / Seedance 官方接口
  - 使用 `ARK_API_KEY`
  - 支持本地图片自动上传为公网 URL
  - 支持生成成功后自动下载视频
  - 支持可选 JSON 结果输出
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
   ├─ generate_video.py              # 旧版入口（EasyClaw）
   ├─ generate_video_easyclaw.py     # 兼容保留版
   ├─ generate_video_ark.py          # 官方 Ark 直连版
   ├─ query_video_task_ark.py        # Ark 任务查询脚本
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

# 本地图上传适配
KIEAI_API_KEY=your_kieai_api_key
KIEAI_BASE_URL=https://kieai.redpandaai.co
IMAGE_UPLOAD_PROVIDER=catbox
IMAGE_UPLOAD_PATH=images/video-gen
IMAGE_UPLOAD_MAX_MB=20
```

说明：

- `ARK_API_KEY`：官方直连必填
- `ARK_BASE_URL`：可不填，默认官方北京区 v3 地址
- `KIEAI_API_KEY`：仅当 provider 为 `kieai` 时才需要
- `IMAGE_UPLOAD_PROVIDER`：
  - `kieai`：允许自动上传本地图（需 KIEAI_API_KEY）
  - `catbox`：允许自动上传本地图（免费、无需 API key）
  - `none`：禁止上传，本地路径将直接报错，只接受公网 URL
- `IMAGE_UPLOAD_PATH`：KieAI 上传路径
- `IMAGE_UPLOAD_MAX_MB`：本地图片上传大小限制，默认 20MB

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
- 结果：
  - `generate_video_ark.py --auto-download` 单脚本闭环成功
  - 不再需要依赖“任务成功后手动补查再单独下载”的补救流程

补充说明：

- 早期版本曾出现“任务已成功但轮询阶段提前退出 code 1”的问题
- 当前版本已增加轮询容错与补查提示
- `query_video_task_ark.py` 仍保留，作为排障兜底工具

---

## 典型用法

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

### 指定使用 catbox 上传本地图

```bash
uv run python scripts/generate_video_ark.py \
  --prompt "ink dragon emerges from a drawing" \
  --image "C:\\path\\to\\dragon.png" \
  --upload-provider catbox \
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

### 生成成功后自动下载视频

```bash
uv run python scripts/generate_video_ark.py \
  --prompt "a dragon emerges from a sketchbook" \
  --image "C:\\path\\to\\dragon.png" \
  --upload-provider catbox \
  --duration 5 \
  --auto-download \
  --download-output "C:\\path\\to\\output.mp4"
```

### 输出最终成功结果为 JSON

```bash
uv run python scripts/generate_video_ark.py \
  --prompt "a dragon emerges from a sketchbook" \
  --image "C:\\path\\to\\dragon.png" \
  --duration 5 \
  --auto-download \
  --download-output "C:\\path\\to\\output.mp4" \
  --json
```

成功时会额外输出类似结果：

```json
{
  "task_id": "cgt-xxxxxxxxxxxxxxxx",
  "status": "succeeded",
  "model": "doubao-seedance-1-5-pro-251215",
  "duration": 5,
  "video_url": "https://...mp4",
  "local_path": "C:\\path\\to\\output.mp4",
  "query_payload": {"...": "..."}
}
```

### 控制轮询容错

```bash
uv run python scripts/generate_video_ark.py \
  --prompt "a dragon emerges from a sketchbook" \
  --duration 5 \
  --max-polls 120 \
  --max-query-failures 6
```

### 按任务 ID 补查状态

```bash
uv run python scripts/query_video_task_ark.py cgt-xxxxxxxxxxxxxxxx
```

---

## 当前逻辑

1. 如果 `--image` 是 `http/https URL`，直接传给 Ark
2. 如果 `--image` 是本地路径，则交给 `image_url_adapter.py`
3. `image_url_adapter.py` 按 `.env` 或 `--upload-provider` 选择 provider
4. 当前支持：`kieai` / `catbox` / `none`
5. 任务成功后如果开启 `--auto-download`，会自动调用 `download_video.py` 的下载逻辑
6. 如果轮询阶段发生短暂查询异常，会自动重试；只有连续失败超过 `--max-query-failures` 才会退出，并打印任务补查命令
7. 如果传入 `--json`，成功完成后会额外打印结构化结果，方便其他脚本或 skill 继续消费

---

## 中期方案：解耦上传层

当前本地图转公网 URL 的逻辑已经被抽离到：

- `scripts/image_url_adapter.py`

下一步建议：

1. 新增更多 provider（如自建 OSS / S3 / R2）
2. 补充更严格的 MIME / 格式 / 文件大小校验
3. 继续保持 `generate_video_ark.py` 只关心模型调用，不关心上传细节

---

## 长期方案：彻底去掉临时图床依赖

更理想的长期结构：

1. 本地图先上传到你自己的稳定对象存储
2. 再把稳定 URL 提供给 Ark
3. 上传层和模型层彻底解耦
4. `generate_video.py` 最终变成统一入口，内部按 provider 分发

长期目标不是“隐藏 uid/token”，而是：

- 不再读取 `.easyclaw` 身份文件
- 不再发送 `X-AUTH-UID` / `X-AUTH-TOKEN`
- 不再依赖 `aibot-srv.easyclaw.cn`
- 不再依赖 EasyClaw 的 payload 兼容行为
- 只保留：官方模型 + 官方 endpoint + Bearer Key

---

## 注意事项

1. `generate_video_easyclaw.py` 是兼容保留，不是未来主线
2. `generate_video_ark.py` 才是当前主线
3. Catbox 适合测试和轻量桥接，不适合作长期正式素材库
4. 当前 `.env` 中有真实 key，不要提交到 GitHub
