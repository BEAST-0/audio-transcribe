from django.db import models
from django.utils.timezone import now

class Meeting(models.Model):
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=255)
    createdat = models.DateTimeField(auto_now_add=True)
    updatedat = models.DateTimeField(auto_now=True)
    title = models.CharField(max_length=255)
    airesponse = models.JSONField()
    roomid = models.CharField(max_length=255)
    trello_created = models.BooleanField(default=False)
    duration = models.IntegerField(null=True)

    def __str__(self):

        return self.title
    
class MeetingTranscription(models.Model):
    id = models.AutoField(primary_key=True)
    speaker = models.CharField(max_length=255)
    text = models.TextField()
    roomid = models.CharField(max_length=255)
    username = models.CharField(max_length=255)
    order_no = models.IntegerField()
    createdat = models.DateTimeField(auto_now=True)
    updatedat = models.DateTimeField(auto_now=True) 

    def __str__(self):
        return str(self.id)

class CustomUser(models.Model):  
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=30, unique=True)
    email = models.EmailField(unique=True)
    token = models.CharField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email
# new table for meeting_user

class MeetingUser(models.Model):
    id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=255)
    roomid = models.CharField(max_length=255)
    createdat = models.DateTimeField(auto_now_add=True)
    updatedat = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username