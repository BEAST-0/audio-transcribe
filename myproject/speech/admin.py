from django.contrib import admin

# Register your models here.
from .models import Meeting, MeetingTranscription

admin.site.register(Meeting)
admin.site.register(MeetingTranscription)
