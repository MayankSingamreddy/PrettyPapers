import fitz  # PyMuPDF
from PIL import Image, ImageFilter
import io, numpy as np
import math

# ---------- helper functions ----------
def int_to_rgb_float(color_int):
    """Converts an integer color (like 0xFF0000 for red) to a (r, g, b) tuple with values 0-1."""
    if color_int is None:
        return (1.0, 1.0, 1.0) # Default to white
    blue = (color_int & 255) / 255.0
    green = ((color_int >> 8) & 255) / 255.0
    red = ((color_int >> 16) & 255) / 255.0
    return (red, green, blue)

def apply_blur_and_grain(pil_img, blur_radius=10, grain_strength=0.20):
    """Gaussian-blur the bg + add film grain."""
    blurred = pil_img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    grain = np.random.normal(
        loc=128, scale=30,
        size=(blurred.height, blurred.width, 3)
    ).clip(0, 255).astype(np.uint8)
    grain_img = Image.fromarray(grain, "RGB")
    return Image.blend(blurred, grain_img, alpha=grain_strength)

def map_font(pdf_font_name: str):
    """Very coarse mapping from embedded names → built-in Times family."""
    f = pdf_font_name.lower()
    if "bold" in f and ("italic" in f or "oblique" in f):
        return "Times-BoldItalic"
    if "bold" in f:
        return "Times-Bold"
    if "italic" in f or "oblique" in f:
        return "Times-Italic"
    return "Times-Roman"

# ---------- main transform ----------
def stylise_pdf(pdf_path, bg_path, out_path):
    src = fitz.open(pdf_path)
    bg  = Image.open(bg_path).convert("RGB")
    dst = fitz.open()                       # fresh doc

    for pnum, page in enumerate(src):
        w, h = page.rect.width, page.rect.height
        npg   = dst.new_page(width=w, height=h)

        # 1. background (underlay)
        bg_resized = apply_blur_and_grain(bg.resize((int(w), int(h))))
        buf = io.BytesIO()
        bg_resized.save(buf, format="PNG")
        npg.insert_image(page.rect, stream=buf.getvalue(), overlay=False)

        text_blocks   = page.get_text("dict")["blocks"]
        drawing_items = page.get_drawings()
        images_on_pg  = page.get_images(full=True)

        # 2. raster images (graph bitmaps etc.)  - keep z-order UNDER shapes/text
        for b in text_blocks:
            if b.get("type") == 1:                      # 1 == image block
                xref  = b.get("xref")
                if not xref:        # sometimes missing – fall back to first page image with same bbox
                    continue
                base  = src.extract_image(xref)
                npg.insert_image(
                    fitz.Rect(b["bbox"]),
                    stream=base["image"],
                    overlay=True                      # image above bg, below vectors/text
                )

        # 3. vector drawings (rectangles, lines, polygons, bezier)
        for d in drawing_items:
            # Use drawing-level color and width
            color_val = d.get("color")
            if color_val is None:
                draw_color = (1.0, 1.0, 1.0)
            elif isinstance(color_val, (tuple, list)):
                draw_color = tuple(color_val)
            elif isinstance(color_val, int):
                draw_color = int_to_rgb_float(color_val)
            else:
                draw_color = (1.0, 1.0, 1.0)
            draw_width = d.get("width", d.get("linewidth", 1.0))
            for item in d["items"]:
                typ = item[0] if len(item) > 0 else None
                pts = item[1] if len(item) > 1 else []
                if typ in ("l", "L") and isinstance(pts, (list, tuple)) and len(pts) >= 2:
                    p1, p2 = fitz.Point(pts[0]), fitz.Point(pts[1])
                    npg.draw_line(p1, p2, color=draw_color, width=draw_width)
                elif typ == "re" and isinstance(pts, (list, tuple)):
                    try:
                        npg.draw_rect(fitz.Rect(pts), color=draw_color,
                                      fill=None, width=max(0.5, draw_width))
                    except Exception:
                        pass
                elif typ in ("qu", "p") and isinstance(pts, (list, tuple)):
                    try:
                        pts_list = [fitz.Point(p) for p in pts]
                        npg.draw_polyline(pts_list, color=draw_color, width=draw_width)
                    except Exception:
                        pass
                elif typ in ("c", "be", "b") and isinstance(pts, (list, tuple)):
                    try:
                        pts_list = [fitz.Point(p) for p in pts]
                        npg.draw_bezier(pts_list, color=draw_color, width=draw_width)
                    except Exception:
                        pass
                # ignore other drawing commands

        # detect hyperlinks on this page
        page_links = [fitz.Rect(lk["from"]) for lk in page.get_links() if "from" in lk]

        # 4. text – keep original style
        for blk in text_blocks:
            for line in blk.get("lines", []):
                for span in line.get("spans", []):
                    text  = span["text"]               # keep original glyphs
                    size  = span["size"]
                    font  = map_font(span["font"])
                    # determine original color
                    orig_color = int_to_rgb_float(span.get("color", 0))

                    # Treat near-zero as black; threshold ~2%
                    epsilon = 5.0 / 255.0
                    is_non_black = any(ch > epsilon for ch in orig_color)

                    # choose color: white if original was black/default, otherwise keep original color
                    if is_non_black:
                        color = orig_color
                    else:
                        color = (1.0, 1.0, 1.0) # Force to white

                    # point where span *starts*
                    origin = fitz.Point(*span["origin"])
                    matrix = span.get("matrix", [1, 0, 0, 1, 0, 0])

                    # detect rotation: matrix[1] ≠ 0 ⇔ 90° or –90°
                    if abs(matrix[1]) > 1e-3:
                        # create a bbox, rotate around its centre
                        rect = fitz.Rect(span["bbox"])
                        angle = 90 if matrix[1] > 0 else -90
                        npg.insert_textbox(
                            rect, text, fontname=font, fontsize=size,
                            color=color, rotate=angle, align=fitz.TEXT_ALIGN_LEFT
                        )
                    else:
                        # regular horizontal span
                        npg.insert_text(
                            origin, text,
                            fontname=font, fontsize=size, color=color
                        )

    dst.save(out_path, deflate=True, clean=True, garbage=4)
    for d in (src, dst):
        d.close()
    bg.close()

# ---------- run ----------
stylise_pdf(
    pdf_path="overthinking.pdf",
    bg_path="background.jpg",
    out_path="overthinking_refactored.pdf",
)
