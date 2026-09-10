"""把源图处理成网页头像（正方形、等比缩放、白底居中，不裁切主体）。

用法：
    python tools/make_avatar.py                     # 默认 pics/QB.webp -> web/qb.png
    python tools/make_avatar.py 源图 输出 尺寸        # 自定义（尺寸默认 256）

说明：源图可能是 WebP 却带着 .jpg 扩展名，脚本按内容识别格式，不依赖扩展名。
"""
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent


def make_avatar(src: Path, dst: Path, size: int = 256) -> None:
    im = Image.open(src)                      # 按内容识别（WebP/JPEG/PNG 均可）
    im = im.convert("RGBA")
    # 等比缩放到 (size, size) 之内，不裁切；再把透明像素压到白底上
    im.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    canvas.paste(im, ((size - im.width) // 2, (size - im.height) // 2), im)
    canvas.convert("RGB").save(dst, "PNG", optimize=True)
    print(f"已生成 {dst.relative_to(ROOT)}：{canvas.size[0]}x{canvas.size[1]}，"
          f"{dst.stat().st_size} 字节（源：{src.name}，{im.width}x{im.height}）")


if __name__ == "__main__":
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "pics" / "QB.webp"
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "web" / "qb.png"
    size = int(sys.argv[3]) if len(sys.argv) > 3 else 256
    if not src.exists():
        raise SystemExit(f"找不到源图：{src}")
    make_avatar(src, dst, size)
