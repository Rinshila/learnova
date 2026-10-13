from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login,authenticate,logout
from django.contrib import messages
from .forms import RegistrationForm, ProfileForm
from .models import Profile


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


import os
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from pypdf import PdfReader
from openai import OpenAI

from .forms import StudyMaterialForm
from .models import StudyMaterial


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


@login_required
@require_POST
def summarize_pdf(request, pk):
    material = get_object_or_404(StudyMaterial, pk=pk)

    api_key = os.environ.get("OPENAI_API_KEY")

    if not api_key:
        messages.error(
            request,
            "AI summarization is not configured yet. "
            "Please configure your AI API key."
        )
        return redirect("study_materials")

    try:
        with material.pdf_file.open("rb") as pdf:
            reader = PdfReader(pdf)

            if reader.is_encrypted:
                raise ValueError("This PDF is password-protected.")

            text_parts = []

            # Limit processing to 50 pages to control cost and memory.
            for page in reader.pages[:50]:
                text_parts.append(page.extract_text() or "")

            extracted_text = "\n".join(text_parts).strip()

        if not extracted_text:
            messages.error(
                request,
                "No readable text was found in this PDF. "
                "Scanned PDFs may require OCR."
            )
            return redirect("study_materials")

        # Keep the input within a reasonable size.
        extracted_text = extracted_text[:40000]

        client = OpenAI(api_key=api_key)

        result = client.responses.create(
            model="gpt-4o-mini",
            instructions=(
                "You are a helpful study assistant for students. "
                "Summarize the supplied study material in simple English. "
                "Use clear headings, short paragraphs, bullet points, "
                "important definitions, key concepts, and a short revision "
                "section. Preserve important facts and formulas. "
                "Do not invent information not present in the source. "
                "Mention if the supplied text appears incomplete."
            ),
            input=(
                f"Title: {material.title}\n"
                f"Subject: {material.subject}\n"
                f"Topic: {material.topic}\n\n"
                f"Study material:\n{extracted_text}"
            ),
        )

        material.summary = result.output_text
        material.save(update_fields=["summary"])

        messages.success(
            request,
            "Your study summary has been generated!"
        )

    
    except Exception as e:
        print("AI SUMMARY ERROR:", repr(e))

        messages.error(
            request,
            f"Summary failed: {type(e).__name__}. "
            "Check the VS Code terminal for details."
        )

    return redirect("study_materials")

import json
import re
import logging
import ollama
from django.db.models import Avg,Count
from .models import StudyMaterial, Quiz, Question, QuizResult
import django.db.transaction as transaction


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


@login_required
@require_POST
def generate_quiz(request, material_id):
    # A user cannot generate a quiz from someone else's PDF.
    material = get_object_or_404(
        StudyMaterial,
        pk=material_id,
        uploaded_by=request.user
    )

    try:
        # Extract readable text from the uploaded PDF.
        with material.pdf_file.open("rb") as pdf_file:
            reader = PdfReader(pdf_file)

            if reader.is_encrypted:
                messages.error(
                    request,
                    "This PDF is password-protected."
                )
                return redirect("quiz_list")

            extracted_text = "\n".join(
                page.extract_text() or ""
                for page in reader.pages[:40]
            ).strip()

        if not extracted_text:
            messages.error(
                request,
                "No readable text found in this PDF. "
                "Scanned PDFs may need OCR."
            )
            return redirect("quiz_list")

        # Limit input length for local AI generation.
        extracted_text = extracted_text[:18000]

        prompt = f"""
Create exactly 15 multiple-choice questions using ONLY
the study material provided below.

Subject: {material.subject}
Topic: {material.topic}
Title: {material.title}

Requirements:
- Exactly 15 distinct questions.
- Four options for every question: A, B, C, D.
- Exactly one correct answer per question.
- Questions and answers must be supported by the PDF.
- Use clear language suitable for students.
- Do not repeat questions.
- Return valid JSON only, without Markdown.

Required JSON structure:
{{
  "questions": [
    {{
      "question": "Question text",
      "A": "Option A",
      "B": "Option B",
      "C": "Option C",
      "D": "Option D",
      "answer": "A"
    }}
  ]
}}

Study material:
{extracted_text}
"""

        response = ollama.generate(
            model="llama3.2",
            prompt=prompt,
            format="json",
            options={"temperature": 0.2}
        )

        data = json.loads(response["response"])
        generated_questions = data.get("questions", [])

        if (
            not isinstance(generated_questions, list)
            or len(generated_questions) != 15
        ):
            messages.error(
                request,
                "The AI did not generate exactly 15 questions. "
                "Please try again."
            )
            return redirect("quiz_list")

        validated_questions = []

        for item in generated_questions:
            if not isinstance(item, dict):
                raise ValueError("Invalid question format.")

            question_text = str(
                item.get("question", "")
            ).strip()

            options = {
                key: str(item.get(key, "")).strip()
                for key in ("A", "B", "C", "D")
            }

            correct_answer = str(
                item.get("answer", "")
            ).strip().upper()

            if (
                not question_text
                or any(not value for value in options.values())
                or correct_answer not in ("A", "B", "C", "D")
            ):
                raise ValueError("Invalid question or options.")

            validated_questions.append({
                "question_text": question_text,
                "option_a": options["A"],
                "option_b": options["B"],
                "option_c": options["C"],
                "option_d": options["D"],
                "correct_answer": correct_answer,
            })

        # Save the quiz and all 15 questions together.
        with transaction.atomic():
            quiz = Quiz.objects.create(
                title=f"{material.title} - Quiz",
                subject=material.subject,
                topic=material.topic,
                study_material=material,
                created_by=request.user,
            )

            Question.objects.bulk_create([
                Question(quiz=quiz, **item)
                for item in validated_questions
            ])

        messages.success(
            request,
            "Your 15-question quiz is ready!"
        )

        return redirect("take_quiz", quiz_id=quiz.id)

    except Exception:
        logging.exception("Learnova quiz generation failed")
        messages.error(
            request,
            "Quiz generation failed. Check that Ollama is running, "
            "llama3.2 is installed, and the PDF is readable."
        )
        return redirect("quiz_list")


@login_required
def take_quiz(request, quiz_id):
    quiz = get_object_or_404(
        Quiz,
        pk=quiz_id,
        created_by=request.user
    )

    questions = quiz.questions.all()

    if questions.count() != 15:
        messages.error(
            request,
            "This quiz does not contain 15 valid questions."
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

    if len(questions) != 15:
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

    percentage = round((score / 15) * 100, 2)

    result = QuizResult.objects.create(
        student=request.user,
        quiz=quiz,
        score=score,
        total_questions=15,
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


import urllib.request
import urllib.error
import requests
from django.http import JsonResponse
from django.views.decorators.http import require_POST

import json
import urllib.request
import urllib.error
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def ai_assistant(request):
    return render(request, "ai_assistant.html")


@login_required
@require_POST
def ai_chat_api(request):
    try:
        data = json.loads(request.body)
        message = data.get("message", "").strip()

        if not message:
            return JsonResponse(
                {"error": "Please enter your question."},
                status=400
            )

        if len(message) > 4000:
            return JsonResponse(
                {"error": "Your question is too long. Use fewer than 4000 characters."},
                status=400
            )

        payload = {
            "model": "llama3.2",
            "stream": False,
            "keep_alive": "30m",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Learnova AI Study Assistant, a friendly tutor. "
                        "Help students clear academic doubts in simple English. "
                        "Explain concepts step by step and use examples when useful. "
                        "For programming questions, provide understandable code "
                        "and explain it. If a question is unclear, ask for clarification. "
                        "Do not invent facts when uncertain."
                    )
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            "options": {
                "temperature": 0.5,
                "num_predict": 300
            }
        }

        res = requests.post(
        "http://127.0.0.1:11434/api/chat",
        json=payload,
        timeout=300,
        proxies={"http": None, "https": None},
        )
        res.raise_for_status()
        result = res.json()

        answer = result.get("message", {}).get("content", "").strip()

        if not answer:
            return JsonResponse(
                {"error": "The AI did not return an answer. Please try again."},
                status=502
            )

        return JsonResponse({"reply": answer})

    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "Invalid request. Please try again."},
            status=400
        )

    except requests.exceptions.Timeout:
        return JsonResponse(
            {"error": "The AI took too long to respond. Please try again."},
            status=504
        )

    except requests.exceptions.RequestException:
        return JsonResponse(
            {
                "error": (
                    "Cannot connect to Ollama. Please start Ollama "
                    "and make sure the llama3.2 model is installed."
                )
            },
            status=503
        )

    except Exception:
        return JsonResponse(
            {"error": "Something went wrong. Please try again."},
            status=500
        )
