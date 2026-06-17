from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render

from .models import Certificate


def verify(request, uid):
    cert = Certificate.objects.filter(uid=uid).select_related("user", "course").first()
    return render(
        request,
        "certificates/verify.html",
        {"cert": cert, "valid": cert is not None},
    )


def detail(request, uid):
    cert = get_object_or_404(
        Certificate.objects.select_related("user", "course"), uid=uid
    )
    return render(request, "certificates/detail.html", {"cert": cert})


def download(request, uid):
    cert = get_object_or_404(Certificate, uid=uid)
    if not cert.pdf:
        raise Http404
    return FileResponse(
        cert.pdf.open("rb"),
        as_attachment=True,
        filename=f"ustaz-{cert.course.slug}-{cert.uid}.pdf",
    )
