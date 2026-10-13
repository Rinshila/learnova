from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):

    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
        ('Other', 'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    phone = models.CharField(max_length=15, blank=True)
    age = models.PositiveIntegerField(null=True, blank=True)
    gender = models.CharField(
        max_length=10,
        choices=GENDER_CHOICES,
        blank=True
    )

    def __str__(self):
        return self.user.username

class StudyMaterial(models.Model):
    title = models.CharField(max_length=200)
    subject = models.CharField(max_length=150)
    topic = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    pdf_file = models.FileField(upload_to="study_materials/")

    summary = models.TextField(blank=True)

    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="study_materials"
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["-uploaded_at"]





from django.db import models
from django.contrib.auth.models import User


class Quiz(models.Model):
    title = models.CharField(max_length=200)
    subject = models.CharField(max_length=150)
    topic = models.CharField(max_length=200, blank=True)

    study_material = models.ForeignKey(
        "StudyMaterial",
        on_delete=models.CASCADE,
        related_name="quizzes"
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_quizzes"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Question(models.Model):
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="questions"
    )

    question_text = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500)

    correct_answer = models.CharField(
        max_length=1,
        choices=[
            ("A", "A"),
            ("B", "B"),
            ("C", "C"),
            ("D", "D"),
        ]
    )

    def __str__(self):
        return self.question_text[:80]


class QuizResult(models.Model):
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="quiz_results"
    )

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="results"
    )

    score = models.PositiveIntegerField()
    total_questions = models.PositiveIntegerField(default=15)
    percentage = models.FloatField(default=0)
    answers = models.JSONField(default=dict)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-completed_at"]

    def __str__(self):
        return f"{self.student.username} - {self.quiz.title}"

