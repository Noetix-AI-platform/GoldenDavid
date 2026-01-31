# GoldenDavid - 线条编织发光头像工具

把一张图片转成发光线条编织动画，并导出：
- 帧序列（PNG）
- WebM 视频
- 可直接打开的内嵌 HTML（`data:video/webm;base64,...`）

## Demo



https://github.com/<user>/<repo>/raw/main/demo.mp4



## 1. 环境要求

- Python 3.10+（建议）
- FFmpeg（可选，但建议安装，用于生成 `webm`）
- Playwright（用于无头渲染）
- OpenCV（用于图片边缘点提取）

## 2. 安装依赖

### 2.1 Python 依赖

```bash
python -m pip install opencv-python numpy playwright
```

### 2.2 安装 Playwright 浏览器

```bash
python -m playwright install
```

### 2.3 安装 FFmpeg（可选）

如果你希望生成 `out_xxx/david_effect.webm`，需要系统里能找到 `ffmpeg`。

验证：
```bash
ffmpeg -version
```

## 3. 一键运行（推荐）

> 输入任意图片，自动：提取边缘点 -> 生成效果 JS -> 无头渲染 -> 导出 frames/webm/embed.html。

```bash
python generate.py --img path/to/your_image.png --out out_effect --render --lossless --dpr 2 --alpha
```

运行成功后你会得到：
- `out_effect/precomputed_data.json`
- `out_effect/david_effect_generated.js`
- `out_effect/frames/frame_00000.png ...`
- `out_effect/david_effect.webm`
- `out_effect/david_effect_embed.html`

直接双击打开：
- `out_effect/david_effect_embed.html`

## 4. 常用参数

### 4.1 点提取（影响“像不像/密度/耗时”）

- `--max-dim`：默认 520，越大越细，但更慢、数据更大
- `--threshold`：默认 95，越小点越多
- `--sample-rate`：默认 2，越小点越多
- `--max-points`：默认 50000，限制点数量
- `--seed`：默认 123，裁点时随机种子（保证可复现）

### 4.2 渲染导出（影响“清晰度/速度/文件体积”）

- `--width/--height`：输出画面尺寸
- `--fps`：默认 30
- `--max-frames`：最多导出多少帧
- `--dpr`：默认 2，清晰度关键参数
- `--lossless`：VP9 无损
- `--alpha`：导出带 alpha 的 VP9（通常能减少“视频比单帧略粗/晕染”的观感差异）

## 5. 只有生成数据（不渲染）

```bash
python generate.py --img path/to/your_image.png --out out_effect
```

产物：
- `out_effect/precomputed_data.json`
- `out_effect/david_effect_generated.js`

## 6. 常见问题

### 6.1 找不到 `david_effect.js`

`generate.py` 会把 `--template-js` 指定的模板 JS 作为基础，生成 `david_effect_generated.js`。

如果仓库里没有 `david_effect.js`：
- 确保你本地有一份模板（比如从历史版本/备份恢复）
- 或者把模板文件路径通过 `--template-js` 传进去

示例：
```bash
python generate.py --img a.png --out out_effect --template-js path/to/template_david_effect.js --render
```

### 6.2 运行很慢

渲染阶段是无头浏览器逐帧截图，正常会比实时播放慢。
你可以：
- 降低 `--max-frames`
- 降低 `--dpr`
- 提高 `--threshold` 或提高 `--sample-rate` 降低点数

