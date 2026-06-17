from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Ұстаз — басқару"
admin.site.site_title = "Ұстаз"
admin.site.index_title = "Контент және пайдаланушылар"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls", namespace="core")),
    path("accounts/", include("accounts.urls", namespace="accounts")),
    path("courses/", include("courses.urls", namespace="courses")),
    path("assessments/", include("assessments.urls", namespace="assessments")),
    path("ai/", include("aitutor.urls", namespace="aitutor")),
    path("g/", include("gamification.urls", namespace="gamification")),
    path("s/", include("social.urls", namespace="social")),
    path("certificates/", include("certificates.urls", namespace="certificates")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
