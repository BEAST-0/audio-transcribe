from django.urls import path
from .views import upload_audio
from .views import upload_audio, create_trello_task  # Import your views

urlpatterns = [
    path("upload_audio/", upload_audio),
      path('api/create-task/', create_trello_task, name='create_task'), 
]
