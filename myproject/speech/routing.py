from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path("ws/speech/", consumers.SpeechConsumer.as_asgi())
]