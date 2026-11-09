"""
AgroLink Hero Image Generator
Generates optimized WebP/JPEG copies of the farmer photo for the hero section.
Source: photo/agrilink_photo.jpeg  (547 x 365 px)
Target: static/img/hero/
"""
import base64
import io
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageFilter
except ImportError:
    sys.exit("Pillow not installed – run:  pip install pillow")

ROOT = Path(__file__).resolve().parent.parent
SRC  = ROOT / "photo" / "agrilink_photo.jpeg"
OUT  = ROOT / "static" / "img" / "hero"
OUT.mkdir(parents=True, exist_ok=True)

img = Image.open(SRC).convert("RGB")
orig_w, orig_h = img.size
print(f"Source image: {orig_w} x {orig_h} px  ({SRC.stat().st_size / 1024:.1f} KB)")

MAX_UPSCALE = 1.5
max_w = int(orig_w * MAX_UPSCALE)
print(f"Max allowed width (1.5× src): {max_w} px  → VARIANT A chosen (source < 1600 px)")

# --- helper ---
def save_webp(src_img, out_path, width, quality=82):
    """Resize to width (height auto) and save as WebP."""
    if width > src_img.width:
        width = src_img.width  # never upscale
    h = round(src_img.height * width / src_img.width)
    resized = src_img.resize((width, h), Image.LANCZOS)
    resized.save(out_path, "WEBP", quality=quality, method=6)
    kb = out_path.stat().st_size / 1024
    print(f"  {out_path.name:40s}  {width}×{h}  {kb:6.1f} KB")
    return resized

# Sizes: only up to max_w
sizes = [s for s in [640, 1024, 1600] if s <= max_w]
# Always include at least one size
if not sizes:
    sizes = [orig_w]
# Cap each at orig_w since 1.5× rule – 1024 > 820 so cap at 547
# Actually 547 * 1.5 = 820, so 640 is fine, 1024 and 1600 are beyond – cap them
sizes = [min(s, int(orig_w * MAX_UPSCALE)) for s in [640, 1024, 1600]]
sizes_actual = []

print("\nGenerating WebP sizes:")
for s in sizes:
    fn = OUT / f"farmer-greenhouse-{min(s, orig_w * 2)}.webp"
    # Actually name by requested size for srcset clarity
    fn = OUT / f"farmer-greenhouse-{s}.webp"
    save_webp(img, fn, s)
    sizes_actual.append(s)

# JPEG fallback (original width, quality 80)
jpeg_path = OUT / "farmer-greenhouse.jpeg"
img.save(jpeg_path, "JPEG", quality=80, optimize=True)
print(f"\n  {'farmer-greenhouse.jpeg':40s}  {orig_w}×{orig_h}  {jpeg_path.stat().st_size/1024:.1f} KB  (JPEG fallback)")

# Copy original unchanged
import shutil
orig_copy = OUT / "farmer-greenhouse-orig.jpeg"
shutil.copy2(SRC, orig_copy)
print(f"  {'farmer-greenhouse-orig.jpeg':40s}  {orig_w}×{orig_h}  (original copy)")

# Tiny blurred placeholder ~24px wide
print("\nGenerating blurred placeholder:")
ph_w = 24
ph_h = max(1, round(orig_h * ph_w / orig_w))
placeholder = img.resize((ph_w, ph_h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(2))
buf = io.BytesIO()
placeholder.save(buf, "JPEG", quality=40)
b64 = base64.b64encode(buf.getvalue()).decode()
uri = f"data:image/jpeg;base64,{b64}"
print(f"  Placeholder: {ph_w}×{ph_h}, {len(b64)} base64 chars")

# Write the placeholder URI to a file for pasting
placeholder_file = OUT / "placeholder_b64.txt"
placeholder_file.write_text(uri)
print(f"  Saved to: {placeholder_file.name}")

print("\n✅ All hero images generated successfully.")
print(f"\nAspect ratio (original): {orig_w}:{orig_h} = {orig_w/orig_h:.4f}")
print(f"CSS aspect-ratio value:  {orig_w}/{orig_h}  or  {orig_w/orig_h*100:.2f}% (padding-top trick)")

