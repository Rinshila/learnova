
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Profile, StudyMaterial, Quiz, Question

User = get_user_model()


# Show student profile details
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "age", "gender")
    search_fields = ("user__username", "user__email", "phone")
    list_filter = ("gender",)


# Show uploaded study materials
@admin.register(StudyMaterial)
class StudyMaterialAdmin(admin.ModelAdmin):
    list_display = ("id", "__str__")
    search_fields = ("id",)
    ordering = ("-id",)


# Show quizzes
@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("id", "__str__")
    search_fields = ("id",)
    ordering = ("-id",)


# Show quiz questions
@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "__str__")
    search_fields = ("id",)
    ordering = ("-id",)


# Configure registered users
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_active",
        "date_joined",
    )

    list_filter = ("is_staff", "is_active", "date_joined")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("-date_joined",)
