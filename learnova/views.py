from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login,authenticate,logout
from django.contrib import messages
from .forms import RegistrationForm, ProfileForm
from .models import Profile
import requests
import threading
from django.db import close_old_connections
from pypdf import PdfReader


import os
from io import BytesIO

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from .forms import StudyMaterialForm
from .models import StudyMaterial

import requests
import json
import urllib.request
import urllib.error
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import JsonResponse, StreamingHttpResponse
from django.contrib.admin.views.decorators import staff_member_required


def register(request):

    if request.method == 'POST':
        form = RegistrationForm(request.POST)

        if form.is_valid():

            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()

            Profile.objects.create(user=user)

            return redirect('home')

    else:
        form = RegistrationForm()

    return render(request, 'register.html', {
        'form': form
    })



def user_login(request):

    if request.method == 'POST':

        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:

            login(request, user)

            return redirect('home')

        else:

            messages.error(
                request,
                'Invalid username or password.'
            )

    return render(request, 'login.html')

def home(request):
    return render(request, 'home.html')


from django.contrib.auth.decorators import login_required


@login_required
def profile(request):

    profile = request.user.profile

    return render(request, 'profile.html', {
        'profile': profile
    })


# Edit Profile
@login_required
def edit_profile(request):

    profile = request.user.profile

    if request.method == 'POST':

        form = ProfileForm(
            request.POST,
            instance=profile
        )

        if form.is_valid():
            form.save()
            return redirect('profile')

    else:

        form = ProfileForm(
            instance=profile
        )

    return render(request, 'edit_profile.html', {
        'form': form
    })

def user_logout(request):
    logout(request)
    return redirect('login')





@login_required
def study_materials(request):

    if request.method == "POST":
        form = StudyMaterialForm(request.POST, request.FILES)

        if form.is_valid():
            material = form.save(commit=False)
            material.uploaded_by = request.user
            material.save()

            messages.success(
                request,
                "Study material uploaded successfully!"
            )
            return redirect("study_materials")

    else:
        form = StudyMaterialForm()

    # Get all materials
    materials = StudyMaterial.objects.all().order_by("-uploaded_at")

    # Read search filters
    query = request.GET.get("q", "").strip()
    subject = request.GET.get("subject", "").strip()
    topic = request.GET.get("topic", "").strip()

    # Search by title, subject, topic, or description
    if query:
        materials = materials.filter(
            Q(title__icontains=query)
            | Q(subject__icontains=query)
            | Q(topic__icontains=query)
            | Q(description__icontains=query)
        )

    if subject:
        materials = materials.filter(subject__iexact=subject)

    if topic:
        materials = materials.filter(topic__iexact=topic)

    # Populate dropdowns from existing database records
    subjects = (
        StudyMaterial.objects.exclude(subject="")
        .values_list("subject", flat=True)
        .distinct()
        .order_by("subject")
    )

    topics = (
        StudyMaterial.objects.exclude(topic="")
        .values_list("topic", flat=True)
        .distinct()
        .order_by("topic")
    )

    context = {
        "form": form,
        "materials": materials,
        "query": query,
        "subject_filter": subject,
        "topic_filter": topic,
        "subjects": subjects,
        "topics": topics,
    }

    return render(request, "study_materials.html", context)


@login_required
def view_pdf(request, pk):
    material = get_object_or_404(StudyMaterial, pk=pk)

    try:
        file_handle = material.pdf_file.open("rb")
        response = FileResponse(
            file_handle,
            content_type="application/pdf"
        )
        response["Content-Disposition"] = (
            f'inline; filename="{os.path.basename(material.pdf_file.name)}"'
        )
        response["X-Content-Type-Options"] = "nosniff"
        return response
    except (OSError, ValueError):
        raise Http404("PDF file not found.")


@login_required
def download_pdf(request, pk):
    material = get_object_or_404(StudyMaterial, pk=pk)

    try:
        file_handle = material.pdf_file.open("rb")
        return FileResponse(
            file_handle,
            as_attachment=True,
            filename=os.path.basename(material.pdf_file.name),
            content_type="application/pdf",
        )
    except (OSError, ValueError):
        raise Http404("PDF file not found.")


def _generate_summary(material_id, title, subject, topic, extracted_text):
    try:
        payload = {
            "model": "llama3.2:1b",
            "stream": False,
            "keep_alive": "30m",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a study assistant. Summarize the study material "
                        "in simple English with short headings and bullet points. "
                        "Include key definitions and a 3-point revision list. "
                        "Do not invent facts."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Title: {title}\nSubject: {subject}\nTopic: {topic}\n\n"
                        f"Study material:\n{extracted_text}"
                    ),
                },
            ],
            "options": {"temperature": 0.3, "num_ctx": 2048, "num_predict": 350},
        }

        res = requests.post(
            "http://127.0.0.1:11434/api/chat",
            json=payload,
            timeout=900,
            proxies={"http": None, "https": None},
        )
        res.raise_for_status()

        summary = res.json().get("message", {}).get("content", "").strip()
        if not summary:
            raise ValueError("Empty summary returned.")

        material = StudyMaterial.objects.get(pk=material_id)
        material.summary = summary
        material.save(update_fields=["summary"])
        print("AI SUMMARY DONE for material", material_id)

    except Exception as e:
        print("AI SUMMARY ERROR:", repr(e))
    finally:
        close_old_connections()


@login_required
@require_POST
def summarize_pdf(request, pk):
    material = get_object_or_404(StudyMaterial, pk=pk)

    try:
        with material.pdf_file.open("rb") as pdf:
            reader = PdfReader(pdf)

            if reader.is_encrypted:
                raise ValueError("This PDF is password-protected.")

            text_parts = [(page.extract_text() or "") for page in reader.pages[:10]]
            extracted_text = "\n".join(text_parts).strip()

        if not extracted_text:
            messages.error(
                request,
                "No readable text was found in this PDF. "
                "Scanned PDFs may require OCR."
            )
            return redirect("study_materials")

        extracted_text = extracted_text[:3000]

        threading.Thread(
            target=_generate_summary,
            args=(material.pk, material.title, material.subject,
                  material.topic, extracted_text),
            daemon=True,
        ).start()

        messages.info(
            request,
            "Summary is being generated. This can take 1 to 3 minutes. "
            "Refresh this page later to see it."
        )

    except Exception as e:
        print("AI SUMMARY ERROR:", repr(e))
        messages.error(
            request,
            f"Summary failed: {type(e).__name__}. "
            "Check the VS Code terminal for details."
        )

    return redirect("study_materials")

@login_required
def view_summary(request, pk):
    material = get_object_or_404(StudyMaterial, pk=pk)

    if not material.summary:
        messages.error(request, "No summary yet. Generate one first.")
        return redirect("study_materials")

    return render(request, "summary_view.html", {"material": material})

import json
import re
import logging
import ollama
from django.db.models import Avg, Sum, Max, Count, Q
from .models import StudyMaterial, Quiz, Question, QuizResult
import django.db.transaction as transaction
import time

QUESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "A": {"type": "string"},
                    "B": {"type": "string"},
                    "C": {"type": "string"},
                    "D": {"type": "string"},
                    "answer": {"type": "string", "enum": ["A", "B", "C", "D"]},
                },
                "required": ["question", "A", "B", "C", "D", "answer"],
            },
        }
    },
    "required": ["questions"],
}

@login_required
def quiz_list(request):
    # Only show the logged-in user's uploaded materials.
    materials = StudyMaterial.objects.filter(
        uploaded_by=request.user
    ).order_by("subject", "-uploaded_at")

    # Group uploaded materials by subject.
    subjects = {}

    for material in materials:
        subject_name = material.subject.strip() or "Other"
        subjects.setdefault(subject_name, []).append(material)

    # Show quizzes created by the current user.
    quizzes = Quiz.objects.filter(
        created_by=request.user
    ).select_related("study_material").order_by("-created_at")

    # Show completed attempts for quiz history.
    results = QuizResult.objects.filter(
        student=request.user
    ).select_related("quiz").order_by("-completed_at")

    return render(request, "quiz_list.html", {
        "subjects": subjects,
        "quizzes": quizzes,
        "results": results,
    })

def _clean_question(item):
    """Return a validated question dict, or None if it is bad."""
    if not isinstance(item, dict):
        return None

    question_text = str(item.get("question", "")).strip()
    options = {k: str(item.get(k, "")).strip() for k in ("A", "B", "C", "D")}
    answer = str(item.get("answer", "")).strip().upper()

    if not question_text or any(not v for v in options.values()):
        return None
    if answer not in ("A", "B", "C", "D"):
        return None

    return {
        "question_text": question_text,
        "option_a": options["A"],
        "option_b": options["B"],
        "option_c": options["C"],
        "option_d": options["D"],
        "correct_answer": answer,
    }


def _ask_for_questions(material, text, count):
    prompt = f"""Write {count} multiple-choice questions from the study material below.
Use only the material. Keep each question and option short (under 15 words).

Subject: {material.subject}
Topic: {material.topic}

Study material:
{text}
"""
    res = requests.post(
        "http://127.0.0.1:11434/api/generate",
        json={
            "model": "llama3.2:1b",
            "prompt": prompt,
            "stream": False,
            "format": QUESTION_SCHEMA,
            "keep_alive": "30m",
            "options": {"temperature": 0.3, "num_ctx": 2048, "num_predict": 500},
        },
        timeout=300,
        proxies={"http": None, "https": None},
    )
    res.raise_for_status()
    return json.loads(res.json()["response"]).get("questions", [])

def _build_quiz_background(material_id, user_id, extracted_text):
    try:
        material = StudyMaterial.objects.get(pk=material_id)
        validated_questions = []
        seen = set()

        for attempt in range(4):
            needed = 5 - len(validated_questions)
            if needed <= 0:
                break

            start = time.time()

            

            try:
                items = _ask_for_questions(material, extracted_text, min(3, needed))
            except Exception as e:
                print("QUIZ ERROR:", repr(e))
                continue

            for item in items:
                cleaned = _clean_question(item)
                if cleaned and cleaned["question_text"].lower() not in seen:
                    seen.add(cleaned["question_text"].lower())
                    validated_questions.append(cleaned)

            print(f"QUIZ: attempt {attempt + 1} took {time.time() - start:.0f}s, "
          f"now have {len(validated_questions)}/5")
            
        validated_questions = validated_questions[:5]

        if len(validated_questions) < 5:
            print(f"QUIZ FAILED: only {len(validated_questions)} valid questions")
            return

        with transaction.atomic():
            quiz = Quiz.objects.create(
                title=f"{material.title} - Quiz",
                subject=material.subject,
                topic=material.topic,
                study_material=material,
                created_by_id=user_id,
            )
            Question.objects.bulk_create([
                Question(quiz=quiz, **item) for item in validated_questions
            ])

        print("QUIZ DONE for material", material_id)

    except Exception as e:
        print("QUIZ ERROR:", repr(e))
    finally:
        close_old_connections()
@login_required
@require_POST
def generate_quiz(request, material_id):
    material = get_object_or_404(
        StudyMaterial,
        pk=material_id,
        uploaded_by=request.user
    )

    try:
        with material.pdf_file.open("rb") as pdf_file:
            reader = PdfReader(pdf_file)

            if reader.is_encrypted:
                messages.error(request, "This PDF is password-protected.")
                return redirect("quiz_list")

            extracted_text = "\n".join(
                page.extract_text() or "" for page in reader.pages[:20]
            ).strip()

        if not extracted_text:
            messages.error(
                request,
                "No readable text found in this PDF. "
                "Scanned PDFs may need OCR."
            )
            return redirect("quiz_list")

        extracted_text = extracted_text[:2000]

        threading.Thread(
            target=_build_quiz_background,
            args=(material.pk, request.user.pk, extracted_text),
            daemon=True,
        ).start()

        messages.info(
            request,
            "Your quiz is being generated. This can take 3 to 8 minutes. "
            "Refresh this page later to see it in your quizzes."
        )

    except Exception:
        logging.exception("Learnova quiz generation failed")
        messages.error(request, "Quiz generation failed. Check the terminal.")

    return redirect("quiz_list")


@login_required
def take_quiz(request, quiz_id):
    quiz = get_object_or_404(
        Quiz,
        pk=quiz_id,
        created_by=request.user
    )

    questions = quiz.questions.all()

    if questions.count() != 5:
        messages.error(
            request,
            "This quiz does not contain 5 valid questions."
        )
        return redirect("quiz_list")

    return render(request, "take_quiz.html", {
        "quiz": quiz,
        "questions": questions,
    })


@login_required
@require_POST
def submit_quiz(request, quiz_id):
    quiz = get_object_or_404(
        Quiz,
        pk=quiz_id,
        created_by=request.user
    )

    questions = list(quiz.questions.all())

    if len(questions) != 5:
        messages.error(request, "This quiz is incomplete.")
        return redirect("quiz_list")

    answers = {}
    score = 0

    for question in questions:
        selected = request.POST.get(
            f"question_{question.id}", ""
        ).upper()

        if selected not in ("A", "B", "C", "D"):
            selected = ""

        answers[str(question.id)] = selected

        if selected == question.correct_answer:
            score += 1

    percentage = round((score / 5) * 100, 2)

    result = QuizResult.objects.create(
        student=request.user,
        quiz=quiz,
        score=score,
        total_questions=5,
        percentage=percentage,
        answers=answers,
    )

    return redirect("quiz_result", result_id=result.id)


@login_required
def quiz_result(request, result_id):
    result = get_object_or_404(
        QuizResult.objects.select_related("quiz"),
        pk=result_id,
        student=request.user
    )

    review = []

    for question in result.quiz.questions.all():
        selected = result.answers.get(str(question.id), "")

        review.append({
            "question": question,
            "selected": selected,
            "correct": question.correct_answer,
            "is_correct": selected == question.correct_answer,
        })

    return render(request, "quiz_result.html", {
        "result": result,
        "review": review,
    })




@login_required
def ai_assistant(request):
    return render(request, "ai_assistant.html")


@login_required
@require_POST
def ai_chat_api(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request. Please try again."}, status=400)

    message = data.get("message", "").strip()

    if not message:
        return JsonResponse({"error": "Please enter your question."}, status=400)

    if len(message) > 4000:
        return JsonResponse({"error": "Your question is too long."}, status=400)

    payload = {
        "model": "llama3.2:1b",
        "stream": True,
        "keep_alive": "30m",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Learnova AI Study Assistant, a friendly tutor. "
                    "Explain in simple English with a short example. "
                    "Keep answers under 150 words unless the student asks for more."
                ),
            },
            {"role": "user", "content": message},
        ],
        "options": {
            "temperature": 0.5,
            "num_predict": 250,
            "num_ctx": 2048,
        },
    }

    def stream():
        try:
            with requests.post(
                "http://127.0.0.1:11434/api/chat",
                json=payload,
                stream=True,
                timeout=300,
                proxies={"http": None, "https": None},
            ) as res:
                res.raise_for_status()
                for line in res.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line.decode("utf-8"))
                    yield chunk.get("message", {}).get("content", "")
        except requests.exceptions.Timeout:
            yield "\n[The AI took too long. Please try again.]"
        except requests.exceptions.RequestException:
            yield "\n[Cannot connect to Ollama. Please make sure it is running.]"
        except Exception:
            yield "\n[Something went wrong. Please try again.]"

    return StreamingHttpResponse(stream(), content_type="text/plain; charset=utf-8")

@login_required
def track_progress(request):
    results = QuizResult.objects.filter(student=request.user).select_related("quiz")

    # Overall numbers
    overall = results.aggregate(
        attempts=Count("id"),
        average=Avg("percentage"),
        best=Max("percentage"),
        correct=Sum("score"),
        total=Sum("total_questions"),
    )
    overall = {
        "attempts": overall["attempts"] or 0,
        "average": round(float(overall["average"] or 0)),
        "best": round(float(overall["best"] or 0)),
        "correct": overall["correct"] or 0,
        "total": overall["total"] or 0,
    }

    # Per-subject breakdown
    subject_rows = (
        results.values("quiz__subject")
        .annotate(attempts=Count("id"), average=Avg("percentage"), best=Max("percentage"))
        .order_by("-average")
    )

    subject_stats = []
    for row in subject_rows:
        average = round(float(row["average"] or 0))
        if average >= 80:
            status, label = "strong", "Strong"
        elif average >= 60:
            status, label = "good", "Good"
        else:
            status, label = "weak", "Needs practice"

        subject_stats.append({
            "subject": (row["quiz__subject"] or "").strip() or "Other",
            "attempts": row["attempts"],
            "average": average,
            "best": round(float(row["best"] or 0)),
            "status": status,
            "label": label,
        })

    # Last 10 attempts, oldest to newest, for the bar chart
    recent = list(results.order_by("-completed_at")[:10])[::-1]
    recent_chart = [
        {
            "height": max(round(float(r.percentage)), 4),  # min height so 0% is still visible
            "percentage": round(float(r.percentage)),
            "label": r.completed_at.strftime("%d %b"),
            "title": r.quiz.title,
            "result_id": r.id,
        }
        for r in recent
    ]

    # Trend: compare last 3 attempts with the 3 before them
    trend = None
    if len(recent) >= 4:
        last = [float(r.percentage) for r in recent[-3:]]
        before = [float(r.percentage) for r in recent[:-3][-3:]]
        diff = sum(last) / len(last) - sum(before) / len(before)
        trend = round(diff)

    return render(request, "progress.html", {
        "overall": overall,
        "subject_stats": subject_stats,
        "recent_chart": recent_chart,
        "trend": trend,
        "plan": _study_plan(request.user),   
    })

    

from datetime import date, timedelta
from django.db.models import Avg
from django.utils.dateparse import parse_date

def _subject(name):
    return (name or "").strip() or "Other"


def _study_plan(user):
    # Average score per subject
    averages = {
        _subject(r["quiz__subject"]): float(r["avg"])
        for r in QuizResult.objects.filter(student=user)
        .values("quiz__subject").annotate(avg=Avg("percentage"))
    }

    # Subjects from uploaded materials, weakest first (untested = 50)
    subjects = {_subject(m.subject) for m in StudyMaterial.objects.filter(uploaded_by=user)}
    subjects = sorted(subjects, key=lambda s: averages.get(s, 50))

    # Weak subjects (under 60%) appear twice
    order = []
    for s in subjects:
        order += [s] * (2 if averages.get(s, 100) < 60 else 1)

    plan = []
    for i in range(7 if order else 0):
        subject = order[i % len(order)]
        avg = averages.get(subject)

        if avg is None:
            tip = "Read your material, then generate a quiz."
        elif avg < 60:
            tip = "Re-read slowly, ask the AI Assistant about hard parts, then retake a quiz."
        elif avg < 80:
            tip = "Skim your notes and take a quiz."
        else:
            tip = "Quick revision to stay sharp."

        plan.append({
            "day": i + 1,
            "date": date.today() + timedelta(days=i),
            "subject": subject,
            "avg": round(avg) if avg is not None else None,
            "tip": tip,
        })
    return plan


