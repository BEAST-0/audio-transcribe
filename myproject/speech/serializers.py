from rest_framework import serializers
from .models import CustomUser, Meeting, MeetingTranscription
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = '__all__'

class MeetingTranscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeetingTranscription
        fields = ["id", "speaker", "text","roomid"] 

class MeetingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meeting
        fields = ['title', 'roomid', 'createdat']