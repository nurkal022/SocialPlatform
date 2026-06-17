from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .forms import LoginForm, ProfileForm, SignupForm
from .models import User


def signup(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Ұстаз академиясына қош келдіңіз!")
            return redirect("accounts:edit_profile")
    else:
        form = SignupForm()
    return render(request, "accounts/signup.html", {"form": form})


class UstazLoginView(LoginView):
    form_class = LoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class UstazLogoutView(LogoutView):
    next_page = "core:landing"


@login_required
def edit_profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль жаңартылды.")
            return redirect("accounts:profile", username=request.user.username)
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/edit_profile.html", {"form": form})


def profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    if not profile_user.is_profile_public and profile_user != request.user:
        return render(request, "accounts/profile_private.html", {"profile_user": profile_user})
    enrollments = list(
        profile_user.enrollments.select_related("course").all()
    )
    badges = list(profile_user.badges.select_related("badge").all()[:12]) if hasattr(profile_user, "badges") else []

    # Activity timeline (last 10 events: lessons completed, cases graded, quizzes passed)
    from datetime import timedelta
    from django.utils import timezone
    from courses.models import LessonProgress
    from assessments.models import Attempt, CaseSubmission
    timeline = []
    for p in LessonProgress.objects.filter(
        user=profile_user, completed_at__isnull=False
    ).select_related("lesson__module__course").order_by("-completed_at")[:6]:
        timeline.append({
            "when": p.completed_at, "icon": "📖",
            "title": f"Сабақ аяқталды: {p.lesson.title}",
            "course": p.lesson.module.course.title,
        })
    for a in Attempt.objects.filter(
        user=profile_user, status="submitted"
    ).select_related("quiz__course").order_by("-submitted_at")[:4]:
        timeline.append({
            "when": a.submitted_at, "icon": "📝",
            "title": f"Тест: {a.quiz.title} — {a.score_pct}%",
            "course": a.quiz.course.title,
        })
    for s in CaseSubmission.objects.filter(
        user=profile_user, status="graded"
    ).select_related("case__course").order_by("-submitted_at")[:4]:
        timeline.append({
            "when": s.submitted_at, "icon": "📋",
            "title": f"Кейс: {s.case.title} — {s.score}/100",
            "course": s.case.course.title,
        })
    timeline.sort(key=lambda x: x["when"], reverse=True)
    timeline = timeline[:10]

    # Cert count
    cert_count = profile_user.certificates.count()

    # Streak / gprofile shortcuts
    gprofile = getattr(profile_user, "gprofile", None)
    streak = getattr(profile_user, "streak", None)

    return render(
        request,
        "accounts/profile.html",
        {
            "profile_user": profile_user,
            "enrollments": enrollments,
            "badges": badges,
            "timeline": timeline,
            "cert_count": cert_count,
            "gprofile": gprofile,
            "streak": streak,
        },
    )


# -------- Impersonation (staff-only quick role switcher) --------

IMPERSONATE_KEY = "impersonate_original_id"


def _can_impersonate(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


@login_required
def become(request, username):
    """Staff or original-staff impersonator becomes another user.

    Original superuser id is stored in session so they can return.
    """
    is_currently_impersonating = bool(request.session.get(IMPERSONATE_KEY))
    if not (_can_impersonate(request.user) or is_currently_impersonating):
        return HttpResponseForbidden("Тек staff/superuser үшін")

    target = get_object_or_404(User, username=username)
    # Remember original only on the first hop
    if not is_currently_impersonating:
        request.session[IMPERSONATE_KEY] = request.user.id

    original_id = request.session[IMPERSONATE_KEY]
    # Hard guard: only an originally-staff user can keep hopping
    original = User.objects.filter(pk=original_id).first()
    if not (original and (original.is_staff or original.is_superuser)):
        request.session.pop(IMPERSONATE_KEY, None)
        return HttpResponseForbidden("Сессия жарамсыз")

    # log in as target (preserve impersonation session key)
    saved = request.session[IMPERSONATE_KEY]
    login(request, target, backend="django.contrib.auth.backends.ModelBackend")
    request.session[IMPERSONATE_KEY] = saved
    messages.info(request, f"Енді сіз {target.display_name} аккаунтындасыз.")
    return redirect(request.GET.get("next") or "core:dashboard")


@login_required
def exit_become(request):
    original_id = request.session.pop(IMPERSONATE_KEY, None)
    if not original_id:
        messages.warning(request, "Сіз ешкімді имитациялаған жоқсыз.")
        return redirect("core:dashboard")
    original = get_object_or_404(User, pk=original_id)
    login(request, original, backend="django.contrib.auth.backends.ModelBackend")
    messages.success(request, "Өзіңіздің аккаунтыңызға қайттыңыз.")
    return redirect("core:dashboard")
