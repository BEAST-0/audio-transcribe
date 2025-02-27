from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path("ws/speech/", consumers.SpeechConsumer.as_asgi()),
    path("ws/speechv2/", consumers.SpeechConsumerv2.as_asgi()),
]