import io
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from courses.models import Enrollment, Lesson, LessonProgress

from .models import Certificate


def is_eligible(user, course) -> tuple[bool, int]:
    """Returns (eligible, final_score_pct)."""
    enrollment = Enrollment.objects.filter(user=user, course=course).first()
    if not enrollment:
        return False, 0
    total_lessons = Lesson.objects.filter(module__course=course).count()
    if total_lessons == 0:
        return False, 0
    done = LessonProgress.objects.filter(
        user=user, lesson__module__course=course, completed_at__isnull=False
    ).count()
    if done < total_lessons:
        return False, 0
    # Find final exam attempt
    from assessments.models import Attempt, Quiz
    final = Quiz.objects.filter(course=course, kind=Quiz.Kind.FINAL).first()
    if not final:
        return True, 100
    best = (
        Attempt.objects.filter(user=user, quiz=final, status=Attempt.Status.SUBMITTED)
        .order_by("-score_pct").first()
    )
    if not best or best.score_pct < course.final_exam_pass_pct:
        return False, best.score_pct if best else 0
    return True, best.score_pct


def issue_certificate_if_eligible(user, course) -> Certificate | None:
    ok, score = is_eligible(user, course)
    if not ok:
        return None
    cert, created = Certificate.objects.get_or_create(
        user=user, course=course,
        defaults={
            "final_score_pct": score,
            "full_name_snapshot": user.get_full_name() or user.username,
        },
    )
    if created or not cert.pdf:
        pdf_bytes = render_certificate_pdf(cert)
        cert.pdf.save(f"cert-{cert.uid}.pdf", ContentFile(pdf_bytes), save=True)
        # mark enrollment completed
        Enrollment.objects.filter(user=user, course=course).update(
            completed_at=timezone.now()
        )
        from gamification.services import award_xp
        award_xp(user, "course_complete", 500, ref=f"course:{course.id}")
    return cert


_FONTS_REGISTERED = False


def _register_unicode_fonts():
    """Register DejaVu Sans (supports Cyrillic + Kazakh special chars)."""
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from django.conf import settings

    fonts_dir = settings.BASE_DIR / "static" / "fonts"
    pdfmetrics.registerFont(TTFont("UstazSans", str(fonts_dir / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("UstazSans-Bold", str(fonts_dir / "DejaVuSans-Bold.ttf")))
    from reportlab.pdfbase.pdfmetrics import registerFontFamily
    registerFontFamily("UstazSans", normal="UstazSans", bold="UstazSans-Bold")
    _FONTS_REGISTERED = True


def render_certificate_pdf(cert: Certificate) -> bytes:
    """Generate an A4 landscape certificate via ReportLab with Cyrillic/Kazakh support."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas

    _register_unicode_fonts()
    FONT_REG = "UstazSans"
    FONT_BOLD = "UstazSans-Bold"

    page = landscape(A4)
    width, height = page
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=page)

    # Background — warm cream
    c.setFillColorRGB(0.973, 0.984, 1.0)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # Decorative gradient strip on top
    c.setFillColorRGB(0.145, 0.388, 0.922)  # primary blue
    c.rect(0, height - 16, width, 16, fill=1, stroke=0)
    c.setFillColorRGB(0.984, 0.439, 0.314)  # coral
    c.rect(width * 0.6, height - 16, width * 0.4, 16, fill=1, stroke=0)

    # Inner border
    c.setStrokeColorRGB(0.145, 0.388, 0.922)
    c.setLineWidth(2)
    c.rect(35, 35, width - 70, height - 90, fill=0)

    # Brand mark
    c.setFillColorRGB(0.145, 0.388, 0.922)
    c.circle(width / 2, height - 100, 28, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(FONT_BOLD, 32)
    c.drawCentredString(width / 2, height - 112, "Ұ")

    # Title
    c.setFillColorRGB(0.043, 0.118, 0.247)
    c.setFont(FONT_BOLD, 36)
    c.drawCentredString(width / 2, height - 170, "СЕРТИФИКАТ")
    c.setFont(FONT_REG, 14)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawCentredString(width / 2, height - 195, "Ұстаз академиясының курсын аяқтағаны туралы")

    # Awarded to
    c.setFont(FONT_REG, 13)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawCentredString(width / 2, height - 245, "Осы сертификат")

    # Name
    c.setFont(FONT_BOLD, 30)
    c.setFillColorRGB(0.043, 0.118, 0.247)
    c.drawCentredString(width / 2, height - 285, cert.full_name_snapshot)

    # Course line
    c.setFont(FONT_REG, 13)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawCentredString(width / 2, height - 320, "келесі курсты сәтті аяқтағанын растайды:")

    # Course title
    c.setFont(FONT_BOLD, 20)
    c.setFillColorRGB(0.984, 0.439, 0.314)
    c.drawCentredString(width / 2, height - 360, f"«{cert.course.title}»")

    # Score / date row
    c.setFont(FONT_REG, 13)
    c.setFillColorRGB(0.043, 0.118, 0.247)
    c.drawCentredString(
        width / 2, height - 405,
        f"Қорытынды балл: {cert.final_score_pct}%       Берілген күні: {cert.issued_at:%d.%m.%Y}",
    )

    # QR with verify URL
    try:
        import qrcode
        from reportlab.lib.utils import ImageReader

        verify_url = f"https://ustaz.local{cert.get_verify_url()}"
        qr = qrcode.make(verify_url)
        img = ImageReader(qr.get_image())
        c.drawImage(img, width - 170, 65, 100, 100, mask="auto")
        c.setFont(FONT_REG, 8)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.drawCentredString(width - 120, 55, "Тексеру")
    except Exception:
        pass

    # ID / verify URL bottom-left
    c.setFont(FONT_REG, 9)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(55, 75, f"ID: {cert.uid}")
    c.drawString(55, 60, f"Тексеру: /certificates/verify/{cert.uid}/")

    c.showPage()
    c.save()
    return buf.getvalue()
