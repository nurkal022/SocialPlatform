# Ұстаз — болашақ ұстаздарға арналған цифрлық академия

Django-based online education platform for Kazakh pedagogy students. Single language (Kazakh-first), MVP scope: 1 published course, modular lesson player, tests, AI-graded case studies, gamification, certificates.

## Stack

- **Django 5.x** + Django templates + HTMX + Alpine.js
- **SQLite** (WAL mode) — single-file dev DB
- **OpenAI API** — tutor chat, case grading, short answer checks, practice generation
- **ReportLab + qrcode** — PDF certificates
- No background workers in MVP — streaming via SSE, AI calls run inside request

## Apps

| app | what |
|---|---|
| `accounts` | Custom user with profile, university/region/specialty, password reset |
| `courses` | Course → Module → Lesson with block-based JSON content, enrollment, progress, notes |
| `assessments` | Quizzes (7 question types), case studies with AI grading |
| `aitutor` | OpenAI wrapper, streaming tutor, case grader, short answer judge, practice generator |
| `gamification` | XP, 50 levels, badges, streaks (with 2 monthly freezes), leaderboards |
| `social` | Comments, course reviews, reports, best-solutions wall |
| `certificates` | Eligibility check, PDF generation, verification URL with QR |
| `core` | Landing, dashboard, shared templatetags |

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env       # edit and add OPENAI_API_KEY if you want AI features

python manage.py migrate
python manage.py seed_course        # creates the «Жалпы педагогика негіздері» course + cases + badges
python manage.py createsuperuser    # for admin access

python manage.py runserver
# open http://127.0.0.1:8000
```

## Without an OpenAI key

The platform fully works without `OPENAI_API_KEY`. AI features (tutor, case grading, practice questions) will surface a friendly "ИИ қолжетімсіз" message; case submissions are still saved and gradable later.

## URL map (top-level)

- `/` — landing / dashboard
- `/courses/` — catalog
- `/courses/<slug>/` — course detail + syllabus
- `/courses/<slug>/m<id>/<lesson>/` — lesson player
- `/assessments/cases/` — case bank
- `/assessments/quiz/<id>/start/` — start a quiz attempt
- `/ai/tutor/<lesson_id>/` — chat panel in lesson context
- `/g/leaderboard/`, `/g/badges/`, `/g/me/`
- `/s/best/` — best public case solutions
- `/certificates/verify/<uuid>/` — public verification page
- `/admin/` — methodist back office (Django admin)

## Scaling notes

- SQLite holds up to ~500 active writers. Past that, switch to Postgres; Django ORM stays identical.
- AI calls are synchronous. Add Celery once you start seeing >2s p95 on grading endpoints.
- For RAG over the whole course (cross-lesson tutor), add pgvector + chunk-and-embed pipeline after the Postgres migration.

## Tests

`python manage.py test` runs a few grading + scoring tests in `assessments/tests.py`.
