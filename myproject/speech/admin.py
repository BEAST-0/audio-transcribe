from django.contrib import admin
# Register your models here.
from .models import Meeting, MeetingTranscription, CustomUser

admin.site.register(Meeting)
admin.site.register(MeetingTranscription)
admin.site.register(CustomUser)

