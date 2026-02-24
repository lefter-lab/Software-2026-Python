# -*- coding: utf-8 -*-
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import struct
import argparse
import sys

import img2pdf
from pypdf import PdfReader, PdfWriter


def get_pdf_page_size_pt(pdf_path: Path) -> tuple[float, float]:
    r = PdfReader(str(pdf_path), strict=False)
    p0 = r.pages[0]
    box = getattr(p0, "cropbox", None) or p0.mediabox
    return float(box.width), float(box.height)


def get_jpeg_size(path: Path) -> tuple[int, int]:
    # Fast JPEG dimension read (no PIL)
    with path.open("rb") as f:
        data = f.read(2)
        if data != b"\xFF\xD8":
            raise ValueError("Файлът не е JPEG (липсва SOI маркер).")

        while True:
            b = f.read(1)
            if not b:
                break
            if b != b"\xFF":
                continue

            marker = f.read(1)
            if not marker:
                break

            # Skip padding FFs
            while marker == b"\xFF":
                marker = f.read(1)
                if not marker:
                    break

            m = marker[0]

            # SOF markers contain size
            if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                seglen = struct.unpack(">H", f.read(2))[0]
                _precision = f.read(1)
                h = struct.unpack(">H", f.read(2))[0]
                w = struct.unpack(">H", f.read(2))[0]
                return w, h

            # Markers without length
            if m in (0xD8, 0xD9):
                continue

            seglen_bytes = f.read(2)
            if len(seglen_bytes) != 2:
                break
            seglen = struct.unpack(">H", seglen_bytes)[0]
            f.seek(seglen - 2, 1)

    raise ValueError("Не успях да прочета размерите на JPEG.")


def estimate_fill_crop_fraction(img_w: int, img_h: int, page_w: float, page_h: float) -> float:
    # If we use fill, scale = max(page_w/img_w, page_h/img_h). Anything beyond page dims is cropped.
    s = max(page_w / img_w, page_h / img_h)
    scaled_w = img_w * s
    scaled_h = img_h * s

    crop_w = max(0.0, (scaled_w - page_w) / scaled_w)  # fraction cropped horizontally
    crop_h = max(0.0, (scaled_h - page_h) / scaled_h)  # fraction cropped vertically
    return max(crop_w, crop_h)


def add_cover_auto(
    cover_jpg: Path,
    input_pdf: Path,
    output_pdf: Path,
    crop_threshold: float = 0.02,  # 2% threshold
):
    if not cover_jpg.exists():
        raise FileNotFoundError(f"Не намирам снимката: {cover_jpg}")
    if not input_pdf.exists():
        raise FileNotFoundError(f"Не намирам PDF-а: {input_pdf}")

    page_w, page_h = get_pdf_page_size_pt(input_pdf)
    img_w, img_h = get_jpeg_size(cover_jpg)

    crop_frac = estimate_fill_crop_fraction(img_w, img_h, page_w, page_h)

    # Auto decision
    if crop_frac > crop_threshold:
        fit_mode = img2pdf.FitMode.into  # no crop
    else:
        fit_mode = img2pdf.FitMode.fill  # tiny crop acceptable

    layout = img2pdf.get_layout_fun(pagesize=(page_w, page_h), fit=fit_mode)

    cover_pdf_bytes = img2pdf.convert(cover_jpg.read_bytes(), layout_fun=layout)
    cover_reader = PdfReader(BytesIO(cover_pdf_bytes), strict=False)
    main_reader = PdfReader(str(input_pdf), strict=False)

    writer = PdfWriter()
    writer.add_page(cover_reader.pages[0])
    for p in main_reader.pages:
        writer.add_page(p)

    try:
        if main_reader.metadata:
            writer.add_metadata(dict(main_reader.metadata))
    except Exception:
        pass

    with output_pdf.open("wb") as f:
        writer.write(f)

    mode_name = "into (без рязане)" if fit_mode == img2pdf.FitMode.into else "fill (пълни страницата)"
    print(f"Готово. Auto избра: {mode_name}. Crop estimate: {crop_frac*100:.2f}%.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Auto add JPG cover to PDF with minimal crop.")
    parser.add_argument("cover", nargs="?", default="Древното сърце заглавна.jpg", help="cover image (jpg)")
    parser.add_argument("input_pdf", nargs="?", default="Древното сърце Избрано от Елеазар Хараш и Старците.pdf", help="input PDF")
    parser.add_argument("output_pdf", nargs="?", default="Древното сърце Избрано от Елеазар Хараш и Старците Загл Auto.pdf", help="output PDF")
    parser.add_argument("--crop-threshold", type=float, default=0.02, help="fraction threshold to switch to 'into' (default 0.02)")
    args = parser.parse_args(argv)

    add_cover_auto(Path(args.cover), Path(args.input_pdf), Path(args.output_pdf), crop_threshold=args.crop_threshold)


if __name__ == "__main__":
    main()
