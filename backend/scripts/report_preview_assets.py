"""Build a self-contained HTML and optional PDF from captured pilot evidence."""

import argparse
import base64
import html
import io
import json
import textwrap
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def state_image(title, detail):
    image = Image.new("RGB", (800, 600), "#eef2f6")
    painter = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("Arial.ttf", 24)
        small = ImageFont.truetype("Arial.ttf", 20)
    except OSError:
        font = ImageFont.load_default(size=24)
        small = ImageFont.load_default(size=20)
    painter.text((40, 220), title, fill="#25364b", font=font)
    painter.multiline_text(
        (40, 270), textwrap.fill(detail, 57)[:420], fill="#526174", font=small, spacing=10
    )
    return image


def image_bytes(path, title, detail):
    if path and Path(path).is_file():
        with Image.open(path) as source:
            image = source.convert("RGBA")
            background = Image.new("RGBA", image.size, "#f5f7fa")
            background.alpha_composite(image)
            image = background.convert("RGB")
            image.thumbnail((800, 600))
    else:
        image = state_image(title, detail)
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=90)
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pdf", action="store_true")
    args = parser.parse_args()
    rows = json.loads(args.report.read_text())
    current = {row["id"]: row for row in json.loads(args.current.read_text())}
    args.output.mkdir(parents=True, exist_ok=True)
    statuses = Counter(row["manifest"]["status"] for row in rows)
    thumbs = Counter(row["manifest"]["thumbnail_status"] for row in rows)
    summary = (
        f"{len(rows)} fixed pilot records. Processing ready: {statuses['ready']}; "
        f"thumbnail ready: {thumbs['ready']}. These are processing outcomes, "
        "not a collection-wide success rate or completed browser acceptance."
    )
    cards, evidence = [], []
    for number, row in enumerate(rows, 1):
        manifest = row["manifest"]
        before = current.get(row["id"], {})
        cells = []
        for name, label in [
            ("thumbnail", "Current thumbnail"),
            ("coverage", "Current location map"),
        ]:
            item = before.get(name, {})
            message = item.get("error") or before.get("error") or "No captured asset"
            if name == "thumbnail" and message == "No current asset URL":
                message = (
                    "No content thumbnail supplied by the public API; "
                    "family fallback remains available."
                )
            cells.append(
                (label, image_bytes(item.get("path"), "Current asset unavailable", message))
            )
        thumb_path = (
            args.assets / manifest["thumbnail_key"] if manifest.get("thumbnail_key") else None
        )
        review_key = manifest.get("metrics", {}).get("review_thumbnail_key")
        if review_key and not thumb_path:
            thumb_path = args.assets / review_key
        retained = before.get("thumbnail", {}).get("path") if not thumb_path else None
        detail = manifest.get("detail") or "No defensible content thumbnail was published."
        label = (
            "Prepared thumbnail"
            if thumb_path
            else ("Retained current thumbnail" if retained else "Thumbnail outcome")
        )
        if review_key:
            label = "Review candidate (not published)"
        elif thumb_path and before.get("thumbnail", {}).get("path"):
            label = "Prepared candidate; current asset retained"
        cells.append(
            (
                label,
                image_bytes(thumb_path or retained, manifest["thumbnail_status"].upper(), detail),
            )
        )
        coverage_path = (
            args.assets / manifest["coverage_key"] if manifest.get("coverage_key") else None
        )
        cells.append(
            (
                "Prepared location map",
                image_bytes(
                    coverage_path,
                    "Location unavailable",
                    manifest.get("metrics", {}).get("coverage_error")
                    or "No verified or metadata geography was rendered.",
                ),
            )
        )
        metrics = manifest.get("metrics", {})
        text = (
            f"Preview processing: {manifest['status']} | "
            f"Thumbnail: {manifest['thumbnail_status']} | "
            f"Scope: {manifest['scope']} | {metrics.get('seconds', '?')} s | "
            f"Read {metrics.get('bytes_read', 0):,} bytes | "
            f"Stored assets {row.get('stored_asset_bytes', metrics.get('output_bytes', 0)):,} bytes"
        )
        review = (
            f"Browser: {row.get('browser_review', 'not-run')} | "
            f"Visual: {row.get('visual_review', 'not-run')}"
        )
        source = (
            manifest.get("source_url")
            or next(iter(row.get("sources", [])), None)
            or "No usable source selected; see source attempts in the manifest."
        )
        imgs = "".join(
            f"<figure><figcaption>{html.escape(label)}</figcaption>"
            f'<img alt="{html.escape(label)}" '
            f'src="data:image/jpeg;base64,{base64.b64encode(data).decode()}"></figure>'
            for label, data in cells
        )
        cards.append(
            f'<article id="record-{number}"><h2>{number:02d}. {html.escape(row["title"])}</h2>'
            f'<p class="id">{html.escape(row["id"])} · {html.escape(row.get("family") or "")}</p>'
            f'<div class="grid">{imgs}</div><p>{html.escape(text)}</p>'
            f"<p>{html.escape(review)}</p>"
            f'<p class="detail">{html.escape(manifest.get("detail") or "")}</p>'
            "<details><summary>Source and full processing evidence</summary>"
            f"<pre>{html.escape(json.dumps(manifest, indent=2))}</pre></details></article>"
        )
        evidence.append((row, cells, text, review, source))
    document = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Shared preview assets — actual 40-record pilot</title><style>
body{{font:15px/1.5 system-ui;background:#edf1f6;color:#182b40;margin:0}}
header,article{{background:white;padding:26px 32px;margin:22px auto;max-width:1400px;
border-radius:12px}}
h1{{font-size:30px}}
h2{{font-size:21px;margin:0}}
.id{{color:#637489;font-size:13px}}
.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:15px}}
figure{{margin:0;background:#f5f7fa}}
figcaption{{padding:10px;font-weight:650}}
img{{display:block;width:100%;height:260px;object-fit:contain}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.4 monospace}}
.detail{{color:#8b432b}}
@media(max-width:900px){{.grid{{grid-template-columns:1fr 1fr}}
}}
@media print{{article{{break-before:page}}
details{{display:none}}
}}

</style></head><body><header><h1>Current assets → prepared preview assets</h1>
<p>{html.escape(summary)}</p>
<p>Actual source data, captured current images, and explicit failure states.
No illustrative replacement imagery.
Original downloads and working curated assets remain authoritative.</p>
<p>Conversion, thumbnail quality, visual review, and browser acceptance are separate outcomes.
A ready processing status alone is not approval for rollout. Review notes below identify
remaining failures and incomplete acceptance checks.</p>
</header>{"".join(cards)}</body></html>"""
    (args.output / "index.html").write_text(document)
    (args.output / "pilot-results.json").write_text(json.dumps(rows, indent=2))
    if args.pdf:
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas
        from reportlab.platypus import Paragraph

        pdf = canvas.Canvas(str(args.output / "preview-pilot-comparison.pdf"), pagesize=(612, 792))
        normal = ParagraphStyle(
            "text", fontName="Helvetica", fontSize=9, leading=12, textColor="#25364b"
        )
        title_style = ParagraphStyle(
            "title", parent=normal, fontName="Helvetica-Bold", fontSize=15, leading=18
        )

        def paragraph(text, x, y, width, style=normal):
            text = text.encode("ascii", "replace").decode()
            para = Paragraph(html.escape(text), style)
            _, height = para.wrap(width, 1000)
            para.drawOn(pdf, x, y - height)
            return y - height

        for number, (row, cells, stats, review, source) in enumerate(evidence, 1):
            pdf.setFillColorRGB(0.08, 0.16, 0.25)
            pdf.rect(0, 750, 612, 42, fill=1, stroke=0)
            pdf.setFillColorRGB(1, 1, 1)
            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(28, 766, "SHARED PREVIEW ASSETS | ACTUAL PILOT")
            y = paragraph(f"{number:02d}. {row['title']}", 28, 733, 556, title_style)
            paragraph(row["id"], 28, y - 5, 556)
            # Current assets on the first row, prepared assets on the second.
            for i, (label, data) in enumerate(cells):
                x = 28 + (i % 2) * 286
                top = 660 - (i // 2) * 216
                paragraph(
                    label,
                    x,
                    top,
                    270,
                    ParagraphStyle("label", parent=normal, fontName="Helvetica-Bold"),
                )
                pdf.setFillColorRGB(0.96, 0.97, 0.98)
                pdf.rect(x, top - 198, 270, 178, fill=1, stroke=0)
                pdf.drawImage(
                    ImageReader(io.BytesIO(data)),
                    x,
                    top - 198,
                    width=270,
                    height=178,
                    preserveAspectRatio=True,
                    anchor="c",
                )
            y = paragraph(stats, 28, 218, 556)
            y = paragraph(review, 28, y - 6, 556)
            detail = (
                row["manifest"].get("detail")
                or "Actual prepared outputs; original assets remain authoritative."
            )
            y = paragraph(detail[:420], 28, y - 6, 556)
            paragraph("Source: " + source[:300], 28, y - 6, 556)
            pdf.setFont("Helvetica", 8)
            pdf.setFillColorRGB(0.35, 0.4, 0.48)
            pdf.drawString(
                28,
                25,
                "Processing status is not browser acceptance. See embedded HTML evidence.",
            )
            pdf.drawRightString(584, 25, f"{number} / {len(evidence)}")
            pdf.showPage()
        pdf.save()
    print(
        json.dumps(
            {
                "records": len(rows),
                "embedded_images": len(rows) * 4,
                "processing": statuses,
                "thumbnails": thumbs,
            }
        )
    )


if __name__ == "__main__":
    main()
