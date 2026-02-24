# -*- coding: utf-8 -*-
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import sys

import img2pdf
from pypdf import PdfReader, PdfWriter


def get_first_page_size_pt(pdf_path: Path) -> tuple[float, float]:
    r = PdfReader(str(pdf_path), strict=False)
    p0 = r.pages[0]
    mb = p0.mediabox
    w = float(mb.width)
    h = float(mb.height)
    return w, h


def add_cover_match_pdf_size(
    cover_jpg: Path,
    input_pdf: Path,
    output_pdf: Path,
    mode: str = "fill",  # "fill" or "into"
) -> None:
    if not cover_jpg.exists():
        raise FileNotFoundError(f"Не намирам снимката: {cover_jpg}")
    if not input_pdf.exists():
        raise FileNotFoundError(f"Не намирам PDF-а: {input_pdf}")

    page_w, page_h = get_first_page_size_pt(input_pdf)
    pagesize = (page_w, page_h)

    if mode.lower() == "fill":
        fit_mode = img2pdf.FitMode.fill
    elif mode.lower() == "into":
        fit_mode = img2pdf.FitMode.into
    else:
        raise ValueError('mode трябва да е "fill" или "into"')

    layout = img2pdf.get_layout_fun(pagesize=pagesize, fit=fit_mode)

    cover_pdf_bytes = img2pdf.convert(cover_jpg.read_bytes(), layout_fun=layout)
    cover_reader = PdfReader(BytesIO(cover_pdf_bytes), strict=False)

    main_reader = PdfReader(str(input_pdf), strict=False)
    writer = PdfWriter()

    writer.add_page(cover_reader.pages[0])
    for page in main_reader.pages:
        writer.add_page(page)

    try:
        if main_reader.metadata:
            writer.add_metadata(dict(main_reader.metadata))
    except Exception:
        pass

    with output_pdf.open("wb") as f:
        writer.write(f)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Add JPG cover to PDF matching the PDF's first-page size.")
    parser.add_argument("cover", nargs="?", default="Древното сърце заглавна.jpg", help="cover image path (jpg)")
    parser.add_argument("input_pdf", nargs="?", default="Древното сърце Избрано от Елеазар Хараш и Старците.pdf", help="input PDF path")
    parser.add_argument("output_pdf", nargs="?", default="Древното сърце Избрано от Елеазар Хараш и Старците Загл.pdf", help="output PDF path to create")
    parser.add_argument("--mode", choices=("fill", "into"), default="fill", help="fit mode: 'fill' (may crop) or 'into' (no crop, may leave borders)")

    args = parser.parse_args()

    add_cover_match_pdf_size(
        Path(args.cover),
        Path(args.input_pdf),
        Path(args.output_pdf),
        mode=args.mode,
    )

    print(f"Готово: {args.output_pdf}")
