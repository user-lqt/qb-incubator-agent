"""把背景原图处理成网页背景（限制宽度、压缩体积）。

用法：
    python tools/make_background.py                      # pics/bg-src.* -> web/bg.jpg
    python tools/make_background.py 源图 web/bg.jpg 1600
"""
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def make_background(src: Path, dst: Path, max_width: int = 1600, quality: int = 78) -> None:
    im = Image.open(src)                     # 按内容识别格式
    fmt, size = im.format, im.size
    im = im.convert("RGB")
    if im.width > max_width:
        im = im.resize((max_width, round(im.height * max_width / im.width)), Image.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, "JPEG", quality=quality, optimize=True, progressive=True)
    try:
        shown = dst.relative_to(ROOT)
    except ValueError:
        shown = dst
    print(f"已生成 {shown}：{im.size[0]}x{im.size[1]}，{dst.stat().st_size} 字节"
          f"（源：{src.name}，{fmt} {size[0]}x{size[1]}）")


if __name__ == "__main__":
    src = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "pics" / "bg-src.jpg"
    dst = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else ROOT / "web" / "bg.jpg"
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 1600
    if not src.exists():
        raise SystemExit(f"找不到源图：{src}")
    make_background(src, dst, width)
