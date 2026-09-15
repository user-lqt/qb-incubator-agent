"""把 16:9 的成图处理成项目用的 8:5 背景（1920x1200 → 1600x1000 那条链的前半段）。

输入：任意比例的图
输出：
    bg-master-8x5.png          裁成 8:5 的无损母版（原分辨率）
    bg-candidate-1600x1000.jpg 网页用成品（q80，与现有 web/bg.jpg 同规格）

顺带把左下角作品 logo 与右下角版权小字做「羽化模糊」处理，避免它们出现在界面里。
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else None
OUT_DIR = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
TARGET_RATIO = 8 / 5            # 1.6

if not SRC or not SRC.exists():
    raise SystemExit("用法: python crop_to_8x5.py <源图> [输出目录]")

im = Image.open(SRC).convert("RGB")
src_w, src_h = im.size
print(f"源图: {src_w}x{src_h}  比例 {src_w / src_h:.4f}")

# 1) 裁成 8:5（优先保留高度，裁两侧）
target_w = round(src_h * TARGET_RATIO)
if target_w > src_w:                   # 图太窄：改为裁上下，保住宽度
    target_h = round(src_w / TARGET_RATIO)
    top = (src_h - target_h) // 2
    box = (0, top, src_w, top + target_h)
    note = f"上下各裁 {top}px / {src_h - target_h - top}px"
else:
    left = (src_w - target_w) // 2
    box = (left, 0, left + target_w, src_h)
    note = f"左右各裁 {left}px / {src_w - target_w - left}px"

im = im.crop(box)
w, h = im.size
print(f"裁切: {w}x{h}  比例 {w / h:.4f}  （{note}）")

# 2) 羽化模糊掉两个角上的水印区（比例定位，换图也能用）
boxes = [
    (0, int(0.900 * h), int(0.140 * w), h),            # 左下：作品 logo
    (int(0.880 * w), int(0.940 * h), w, h),            # 右下：版权小字
]
blur = im.filter(ImageFilter.GaussianBlur(radius=max(8, h // 48)))
mask = Image.new("L", im.size, 0)
draw = ImageDraw.Draw(mask)
for b in boxes:
    draw.rectangle(b, fill=255)
mask = mask.filter(ImageFilter.GaussianBlur(radius=max(6, h // 60)))
im = Image.composite(blur, im, mask)

# 3) 输出母版 + 网页成品
out_master = OUT_DIR / "bg-master-8x5.png"
im.save(out_master)
web_w = 1600
web = im.resize((web_w, round(im.height * web_w / im.width)), Image.LANCZOS)
out_web = OUT_DIR / "bg-candidate-1600x1000.jpg"
web.save(out_web, quality=80, optimize=True, progressive=True)

for p in (out_master, out_web):
    print(f"已生成 {p.name}: {Image.open(p).size[0]}x{Image.open(p).size[1]}  "
          f"{p.stat().st_size / 1024:.0f} KB")
