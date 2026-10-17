import io
import qrcode
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def build_pdf(cert):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    navy = colors.HexColor('#102A43')
    c.setFillColor(navy); c.rect(0, h - 38 * mm, w, 38 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont('Helvetica-Bold', 22); c.drawString(20 * mm, h - 22 * mm, 'MediCore')
    c.setFont('Helvetica', 11); c.drawString(20 * mm, h - 30 * mm, cert.doctor.polyclinic.name)
    c.setFillColor(navy); c.setFont('Helvetica-Bold', 18)
    c.drawString(20 * mm, h - 58 * mm, f'MA\'LUMOTNOMA  No {cert.number}')
    rows = [('Bemor', cert.patient.user.full_name), ('Tug\'ilgan sana', str(cert.patient.birth_date or '-')),
            ('Turi', cert.get_kind_display()), ('Shifokor', cert.doctor.user.full_name),
            ('Mutaxassislik', cert.doctor.specialization.name),
            ('Holati', cert.get_status_display()),
            ('Amal qiladi', str(cert.valid_until or '-'))]
    y = h - 75 * mm
    c.setFont('Helvetica', 11)
    for k, v in rows:
        c.setFillColor(colors.grey); c.drawString(20 * mm, y, k)
        c.setFillColor(navy); c.drawString(65 * mm, y, v); y -= 8 * mm
    y -= 4 * mm
    c.setFont('Helvetica-Bold', 12); c.drawString(20 * mm, y, 'Xulosa'); y -= 7 * mm
    c.setFont('Helvetica', 11)
    for line in (cert.conclusion or '-').splitlines():
        c.drawString(20 * mm, y, line[:95]); y -= 6 * mm
    if cert.signed_at:
        c.setFont('Helvetica', 9); c.setFillColor(colors.grey)
        c.drawString(20 * mm, 55 * mm, f'Elektron imzo: {cert.signature_serial}  ({cert.signed_at:%Y-%m-%d %H:%M})')
    url = f'{settings.PUBLIC_BASE_URL}/api/verify/{cert.qr_token}/'
    img = qrcode.make(url)
    ib = io.BytesIO(); img.save(ib, format='PNG'); ib.seek(0)
    c.drawImage(ImageReader(ib), w - 55 * mm, 25 * mm, 35 * mm, 35 * mm)
    c.setFont('Helvetica', 8); c.setFillColor(colors.grey)
    c.drawString(20 * mm, 22 * mm, 'Haqiqiyligini tekshirish uchun QR kodni skanerlang.')
    c.drawString(20 * mm, 18 * mm, url)
    c.showPage(); c.save()
    return buf.getvalue()
