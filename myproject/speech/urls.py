from django.urls import path
from .views import UserCreateView, get_meeting_transcriptions, upload_audio
from .views import upload_audio, create_trello_task,ask_question,checking

urlpatterns = [
    path("upload_audio/", upload_audio),
    path('api/create-task/', create_trello_task, name='create_task'), 
    path('ask-gpt/', ask_question, name='ask_question'),
    path("users/", UserCreateView.as_view(), name="user-create"),
    path("testing/", checking, name="checking"),  
    path('transcripts/<str:room_id>/', get_meeting_transcriptions, name='get_meeting_transcriptions'),
]


