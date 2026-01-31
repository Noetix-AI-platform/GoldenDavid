import cv2
import numpy as np
import json
import math
import argparse
import subprocess
import sys
from pathlib import Path


def _extract_precomputed_data(
    img_path: Path,
    max_dim: int,
    threshold: float,
    sample_rate: int,
    max_points: int,
    seed: int | None,
) -> dict:
    if not img_path.exists():
        raise FileNotFoundError(f"Image not found: {img_path}")

    img = cv2.imread(str(img_path))
    if img is None:
        raise RuntimeError("Failed to load image")

    # 缩放图片以减少计算量和数据大小 (类似前端逻辑)
    h, w = img.shape[:2]
    scale = min(max_dim / w, max_dim / h, 1.0)
    new_w, new_h = int(w * scale), int(h * scale)
    
    if scale < 1.0:
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    
    # 2. 边缘提取 (Sobel)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 计算梯度
    scale_factor = 1
    delta = 0
    ddepth = cv2.CV_32F
    
    grad_x = cv2.Sobel(gray, ddepth, 1, 0, ksize=3, scale=scale_factor, delta=delta, borderType=cv2.BORDER_DEFAULT)
    grad_y = cv2.Sobel(gray, ddepth, 0, 1, ksize=3, scale=scale_factor, delta=delta, borderType=cv2.BORDER_DEFAULT)
    
    # 计算 magnitude
    mag = cv2.magnitude(grad_x, grad_y)

    # 提取点
    points = []
    
    rows, cols = mag.shape
    for y in range(1, rows - 1, sample_rate):
        for x in range(1, cols - 1, sample_rate):
            m = float(mag[y, x])
            if m > threshold:
                gx = float(grad_x[y, x])
                gy = float(grad_y[y, x])
                # 归一化梯度方向
                inv = 1.0 / m if m > 0 else 0
                nx = gx * inv
                ny = gy * inv
                
                # 保留两位小数减少体积
                points.append({
                    "x": x,
                    "y": y,
                    "nx": round(nx, 3),
                    "ny": round(ny, 3),
                    "mag": int(m) # magnitude 不需要太高精度
                })

    # 限制最大点数
    if len(points) > max_points:
        if seed is not None:
            np.random.seed(seed)
        np.random.shuffle(points)
        points = points[:max_points]

    return {"w": new_w, "h": new_h, "points": points}


def _write_json(data: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def _generate_david_effect_js(template_js: Path, out_js: Path, precomputed: dict) -> None:
    src = template_js.read_text(encoding="utf-8")
    anchor = "window.initDavidEffect"
    idx = src.find(anchor)
    if idx < 0:
        raise RuntimeError(f"模板 JS 未找到锚点：{anchor}")

    precomputed_js = json.dumps(precomputed, ensure_ascii=False, separators=(",", ":"))
    prefix = "(function() {\nconst PRECOMPUTED_DATA = " + precomputed_js + ";\n\n"
    suffix = src[idx:]
    out_js.parent.mkdir(parents=True, exist_ok=True)
    out_js.write_text(prefix + suffix, encoding="utf-8")


def _run_render(
    render_py: Path,
    effect_js: Path,
    out_dir: Path,
    width: int,
    height: int,
    fps: int,
    max_frames: int,
    dpr: float,
    lossless: bool,
    alpha: bool,
) -> None:
    cmd = [
        sys.executable,
        str(render_py),
        "--js",
        str(effect_js),
        "--out",
        str(out_dir),
        "--width",
        str(width),
        "--height",
        str(height),
        "--fps",
        str(fps),
        "--max-frames",
        str(max_frames),
        "--dpr",
        str(dpr),
    ]
    if lossless:
        cmd.append("--lossless")
    if alpha:
        cmd.append("--alpha")

    subprocess.check_call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--img", required=True, help="输入图片路径")
    parser.add_argument("--out", default="out_effect", help="输出目录")
    parser.add_argument("--max-dim", type=int, default=520)
    parser.add_argument("--threshold", type=float, default=95)
    parser.add_argument("--sample-rate", type=int, default=2)
    parser.add_argument("--max-points", type=int, default=50000)
    parser.add_argument("--seed", type=int, default=123)

    parser.add_argument("--template-js", default="david_effect.js")
    parser.add_argument("--out-js", default="david_effect_generated.js")
    parser.add_argument("--out-json", default="precomputed_data.json")

    parser.add_argument("--render", action="store_true")
    parser.add_argument("--render-py", default="render_david_effect.py")
    parser.add_argument("--width", type=int, default=800)
    parser.add_argument("--height", type=int, default=800)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--max-frames", type=int, default=600)
    parser.add_argument("--dpr", type=float, default=2.0)
    parser.add_argument("--lossless", action="store_true")
    parser.add_argument("--alpha", action="store_true")

    args = parser.parse_args()

    img_path = Path(args.img)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    precomputed = _extract_precomputed_data(
        img_path=img_path,
        max_dim=args.max_dim,
        threshold=args.threshold,
        sample_rate=args.sample_rate,
        max_points=args.max_points,
        seed=args.seed,
    )

    _write_json(precomputed, out_dir / args.out_json)
    out_js_path = out_dir / args.out_js
    _generate_david_effect_js(Path(args.template_js), out_js_path, precomputed)

    print(f"Precomputed JSON: {out_dir / args.out_json}")
    print(f"Effect JS: {out_js_path}")

    if args.render:
        _run_render(
            render_py=Path(args.render_py),
            effect_js=out_js_path,
            out_dir=out_dir,
            width=args.width,
            height=args.height,
            fps=args.fps,
            max_frames=args.max_frames,
            dpr=args.dpr,
            lossless=args.lossless,
            alpha=args.alpha,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
