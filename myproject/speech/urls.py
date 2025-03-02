from django.urls import path
from .views import assign_trello_tasks_from_meeting, get_all_meetings, get_summary, get_user_details, upload_audio, create_trello_task, ask_question, checking, LiveKitTokenView  
from .views import UserCreateView, get_meeting_transcriptions, upload_audio, meeting_end_alert, get_meeting_details_by_username,save_meeting_users

urlpatterns = [
    path("upload_audio/", upload_audio),
    path('api/create-task/', create_trello_task, name='create_task'), 
    path('ask-gpt/', ask_question, name='ask_question'),
    path("users/", UserCreateView.as_view(), name="user-create"),
    path("testing/", checking, name="checking"),  
    path('transcripts/<str:room_id>/', get_meeting_transcriptions, name='get_meeting_transcriptions'),
    path("livekit/token/", LiveKitTokenView.as_view(), name="livekit-token"), 
    path('summary_and_action/<str:room_id>/<str:username>/', get_summary, name='get_summary'),
    path('meetings/<str:username>', get_all_meetings, name='get_all_meetings'),
    path('assign-trello-tasks/', assign_trello_tasks_from_meeting, name='assign_trello_tasks'),
    path('get-user-details/', get_user_details, name='get_user_details'),
    path('meeting-end-alert/', meeting_end_alert, name='meeting_end_alert'),
    path('get-meeting-details/', get_meeting_details_by_username, name='get_meeting_details'),
    path('save_meeting_users/', save_meeting_users, name='save_meeting_users'),
]


