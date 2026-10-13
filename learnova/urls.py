
from django.urls import path
from  .import views

urlpatterns = [
    path('',views.home,name='home'),
    path('register/',views.register,name='register'),
    path('login/',views.user_login,name='login'),
    path('profile/',views.profile,name='profile'),
    path('edit_profile/',views.edit_profile,name='edit_profile'),
    path('logout/', views.user_logout, name='logout'),
    path(
        "study-materials/",
        views.study_materials,
        name="study_materials"
    ),
    path(
        "study-materials/<int:pk>/view/",
        views.view_pdf,
        name="view_pdf"
    ),
    path(
        "study-materials/<int:pk>/download/",
        views.download_pdf,
        name="download_pdf"
    ),
    path(
        "study-materials/<int:pk>/summarize/",
        views.summarize_pdf,
        name="summarize_pdf"
    ),


    path(
        "quizzes/",
        views.quiz_list,
        name="quiz_list"
    ),

    path(
        "quizzes/generate/<int:material_id>/",
        views.generate_quiz,
        name="generate_quiz"
    ),

    path(
        "quizzes/<int:quiz_id>/",
        views.take_quiz,
        name="take_quiz"
    ),

    path(
        "quizzes/<int:quiz_id>/submit/",
        views.submit_quiz,
        name="submit_quiz"
    ),

    path(
        "quiz-results/<int:result_id>/",
        views.quiz_result,
        name="quiz_result"
    ),

    path(
        "ai-assistant/",
        views.ai_assistant,
        name="ai_assistant"
    ),

    path(
        "ai-assistant/chat/",
        views.ai_chat_api,
        name="ai_chat_api"
    ),




    ]