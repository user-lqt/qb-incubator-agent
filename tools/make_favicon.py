"""从 QB 原图生成 favicon 与 apple-touch-icon（脸部特写，小尺寸更清楚）。

用法：python tools/make_favicon.py
"""
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "pics" / "QB.webp"


def make(src: Path = SRC) -> None:
    im = Image.open(src).convert("RGBA")
    w, h = im.size
    # 脸部特写：原图 525x455 时脸大致在中心偏上；按比例取一个方形窗口
    side = int(min(w, h) * 0.62)
    cx, cy = int(w * 0.52), int(h * 0.44)
    left = max(0, cx - side // 2)
    top = max(0, cy - side // 2)
    box = (left, top, min(w, left + side), min(h, top + side))
    face = im.crop(box)

    for size, name in [(64, "favicon.png"), (180, "apple-touch-icon.png")]:
        canvas = Image.new("RGBA", (size, size), (255, 255, 255, 255))
        scaled = face.resize((size, size), Image.LANCZOS)
        canvas.paste(scaled, (0, 0), scaled)
        out = ROOT / "web" / name
        canvas.convert("RGB").save(out, "PNG", optimize=True)
        print(f"已生成 {out.relative_to(ROOT)}：{size}x{size}，{out.stat().st_size} 字节"
              f"（源 {src.name} 的裁切区 {box}）")


if __name__ == "__main__":
    make(Path(sys.argv[1]) if len(sys.argv) > 1 else SRC)
