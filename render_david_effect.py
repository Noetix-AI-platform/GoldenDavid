import argparse
import base64
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _run_ffmpeg(frames_dir: Path, fps: int, out_path: Path, lossless: bool, alpha: bool) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False

    in_pattern = str(frames_dir / "frame_%05d.png")

    cmd = [ffmpeg, "-y", "-framerate", str(fps), "-i", in_pattern]

    if lossless:
        cmd += [
            "-c:v",
            "libvpx-vp9",
            "-lossless",
            "1",
            "-pix_fmt",
            "yuva420p" if alpha else "yuv444p",
        ]
        if alpha:
            cmd += [
                "-metadata:s:v:0",
                "alpha_mode=1",
                "-auto-alt-ref",
                "0",
            ]
    else:
        cmd += [
            "-c:v",
            "libvpx-vp9",
            "-b:v",
            "0",
            "-crf",
            "18",
            "-row-mt",
            "1",
            "-pix_fmt",
            "yuva420p" if alpha else "yuv444p",
        ]
        if alpha:
            cmd += [
                "-metadata:s:v:0",
                "alpha_mode=1",
                "-auto-alt-ref",
                "0",
            ]

    cmd += [str(out_path)]

    try:
        subprocess.check_call(cmd)
        return True
    except subprocess.CalledProcessError:
        return False


def _write_embed_html(video_bytes: bytes, out_html: Path) -> None:
    b64 = base64.b64encode(video_bytes).decode("ascii")
    html = (
        "<!doctype html>\n"
        "<html lang=\"zh-CN\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\" />\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
        "  <title>david_effect 内嵌动画</title>\n"
        "  <style>html,body{height:100%;margin:0;background:#000}body{display:flex;align-items:center;justify-content:center}video{display:block;max-width:100vw;max-height:100vh;width:auto;height:auto}</style>\n"
        "</head>\n"
        "<body>\n"
        f"  <video autoplay loop muted playsinline src=\"data:video/webm;base64,{b64}\"></video>\n"
        "</body>\n"
        "</html>\n"
    )
    out_html.write_text(html, encoding="utf-8")


def render_david_effect(
    david_effect_js: Path,
    out_dir: Path,
    width: int,
    height: int,
    fps: int,
    max_frames: int,
    dpr: float,
    lossless: bool,
    alpha: bool,
) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:
        raise RuntimeError(
            "未安装 playwright。请先执行：\n"
            "  python -m pip install playwright\n"
            "  python -m playwright install\n"
        ) from e

    out_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    html_template = (
        "<!doctype html>\n"
        "<html lang=\"zh-CN\">\n"
        "<head>\n"
        "  <meta charset=\"utf-8\" />\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />\n"
        "  <style>html,body{{margin:0;background:transparent;width:{w}px;height:{h}px;overflow:hidden}}canvas{{display:block;width:{w}px;height:{h}px}}</style>\n"
        "</head>\n"
        "<body>\n"
        "  <canvas id=\"c\" width=\"{w}\" height=\"{h}\"></canvas>\n"
        "  <script src=\"{js_url}\"></script>\n"
        "  <script>window.initDavidEffect('c');</script>\n"
        "</body>\n"
        "</html>\n"
    )

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        html_path = td_path / "render.html"

        js_url = david_effect_js.resolve().as_uri()
        html_path.write_text(html_template.format(w=width, h=height, js_url=js_url), encoding="utf-8")

        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
            except Exception:
                browser = None
                for ch in ("chrome", "msedge"):
                    try:
                        browser = p.chromium.launch(headless=True, channel=ch)
                        break
                    except Exception:
                        browser = None
                if browser is None:
                    raise
            page = browser.new_page(viewport={"width": width, "height": height, "device_scale_factor": dpr})
            page.add_init_script(
                "window.__DAVID_EFFECT_CAPTURE_MODE = true;"
                f"Object.defineProperty(window, 'devicePixelRatio', {{ get: () => {dpr} }});"
            )
            page.goto(html_path.resolve().as_uri())

            interval_ms = int(1000 / max(1, fps))

            last_frame = page.evaluate("() => Number(window.__davidEffectFrame || 0)")

            for i in range(max_frames):
                page.evaluate("() => { window.__davidEffectAwait = false; }")
                page.wait_for_function(
                    "(last) => Number(window.__davidEffectFrame || 0) > last",
                    arg=last_frame,
                    timeout=5000,
                )
                last_frame = page.evaluate("() => Number(window.__davidEffectFrame || 0)")

                data_url = page.evaluate(
                    """() => {
                        const c = document.getElementById('c');
                        return c.toDataURL('image/png');
                    }"""
                )
                if not isinstance(data_url, str) or "," not in data_url:
                    raise RuntimeError("无法从 canvas 读取 dataURL")

                _, b64 = data_url.split(",", 1)
                png_bytes = base64.b64decode(b64)
                (frames_dir / f"frame_{i:05d}.png").write_bytes(png_bytes)

                done = page.evaluate("() => Boolean(window.__davidEffectDone)")
                if done:
                    break

                page.wait_for_timeout(interval_ms)

            browser.close()

    webm_path = out_dir / "david_effect.webm"
    ok = _run_ffmpeg(frames_dir=frames_dir, fps=fps, out_path=webm_path, lossless=lossless, alpha=alpha)
    if ok:
        _write_embed_html(webm_path.read_bytes(), out_dir / "david_effect_embed.html")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--js", default="david_effect.js")
    parser.add_argument("--out", default="out_david_effect")
    parser.add_argument("--width", type=int, default=800)
    parser.add_argument("--height", type=int, default=800)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--max-frames", type=int, default=600)
    parser.add_argument("--dpr", type=float, default=2.0)
    parser.add_argument("--lossless", action="store_true")
    parser.add_argument("--alpha", action="store_true")

    args = parser.parse_args()

    js_path = Path(args.js)
    if not js_path.exists():
        print(f"Error: js not found: {js_path}", file=sys.stderr)
        return 2

    out_dir = Path(args.out)
    render_david_effect(
        david_effect_js=js_path,
        out_dir=out_dir,
        width=args.width,
        height=args.height,
        fps=args.fps,
        max_frames=args.max_frames,
        dpr=args.dpr,
        lossless=args.lossless,
        alpha=args.alpha,
    )

    print(f"Frames: {out_dir / 'frames'}")
    if (out_dir / 'david_effect.webm').exists():
        print(f"WebM: {out_dir / 'david_effect.webm'}")
        print(f"Embed HTML: {out_dir / 'david_effect_embed.html'}")
    else:
        print("未检测到 ffmpeg，已输出帧序列（frames）。如需 webm，请安装 ffmpeg 后再运行一次。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
