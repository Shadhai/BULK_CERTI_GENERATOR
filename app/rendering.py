import hashlib
import io
from datetime import date

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


class RenderError(Exception):
    """Raised when a certificate cannot be rendered."""


TEMPLATE = {
    "page_size": landscape(A4),
    "bg": HexColor("#fdfaf3"),
    "accent": HexColor("#b8860b"),
    "ink": HexColor("#1a1a1a"),
    "title": "Certificate of Completion",
    "subtitle": "This certificate is proudly presented to",
    "body": "for successfully completing the course",
}


def render_certificate(
    *,
    recipient_name: str,
    course_name: str | None = None,
    issue_date: date | None = None,
    template: dict | None = None,
) -> bytes:
    """
    Pure function: bytes in -> PDF bytes out. No shared state, safe to parallelize
    with one Canvas per call.
    """
    if not recipient_name or not recipient_name.strip():
        raise RenderError("recipient_name is required for rendering")

    tpl = {**TEMPLATE, **(template or {})}
    page_size = tpl["page_size"]
    width, height = page_size

    buf = io.BytesIO()
    try:
        # invariant=1 makes the PDF byte-for-byte deterministic (no timestamps in metadata),
        # which is what makes the sha256 checksum meaningful.
        c = canvas.Canvas(buf, pagesize=page_size, invariant=1, pageCompression=1)

        c.setFillColor(tpl["bg"])
        c.rect(0, 0, width, height, stroke=0, fill=1)

        c.setStrokeColor(tpl["accent"])
        c.setLineWidth(3)
        c.rect(15 * mm, 15 * mm, width - 30 * mm, height - 30 * mm, stroke=1, fill=0)
        c.setLineWidth(0.5)
        c.rect(18 * mm, 18 * mm, width - 36 * mm, height - 36 * mm, stroke=1, fill=0)

        c.setFillColor(tpl["accent"])
        c.setFont("Helvetica-Bold", 30)
        c.drawCentredString(width / 2, height - 50 * mm, tpl["title"])

        c.setFillColor(tpl["ink"])
        c.setFont("Helvetica", 14)
        c.drawCentredString(width / 2, height - 70 * mm, tpl["subtitle"])

        c.setFillColor(tpl["accent"])
        c.setFont("Helvetica-Bold", 34)
        c.drawCentredString(width / 2, height - 95 * mm, recipient_name)

        c.setStrokeColor(tpl["accent"])
        c.setLineWidth(1)
        line_y = height - 105 * mm
        c.line(width / 2 - 80 * mm, line_y, width / 2 + 80 * mm, line_y)

        if course_name:
            c.setFillColor(tpl["ink"])
            c.setFont("Helvetica", 14)
            c.drawCentredString(width / 2, height - 120 * mm, tpl["body"])
            c.setFont("Helvetica-Bold", 18)
            c.drawCentredString(width / 2, height - 132 * mm, course_name)

        if issue_date:
            c.setFillColor(tpl["ink"])
            c.setFont("Helvetica", 11)
            c.drawCentredString(width / 2, 30 * mm, f"Issued on {issue_date.isoformat()}")

        c.showPage()
        c.save()
    except Exception as exc:
        raise RenderError(f"rendering failed: {exc}") from exc

    return buf.getvalue()


def checksum(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()