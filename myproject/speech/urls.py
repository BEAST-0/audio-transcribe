from django.urls import path
from .views import UserCreateView, upload_audio
from .views import upload_audio, create_trello_task,ask_question  # Import your views

urlpatterns = [
    path("upload_audio/", upload_audio),
    path('api/create-task/', create_trello_task, name='create_task'), 
    path('ask-gpt/', ask_question, name='ask_question'),
    path("users/", UserCreateView.as_view(), name="user-create"),  # Keep it simple
]


