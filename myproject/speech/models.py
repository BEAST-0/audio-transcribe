from django.db import models
from django.core.validators import RegexValidator

class Meeting(models.Model):
    id = models.AutoField(primary_key=True)
    userid = models.IntegerField()
    createdat = models.DateTimeField(auto_now_add=True)
    updatedat = models.DateTimeField(auto_now=True)
    title = models.CharField(max_length=255)

    def __str__(self):

        return self.title
    
class MeetingTranscription(models.Model):
    id = models.AutoField(primary_key=True)
    speaker = models.CharField(max_length=255)
    text = models.TextField()
    roomid = models.IntegerField()

    def __str__(self):
        return f"{self.speaker} - {self.meeting.title}"

class CustomUser(models.Model):  
    id = models.AutoField(primary_key=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    code = models.CharField(max_length=10, unique=True)
    password = models.CharField(
        max_length=255,
        validators=[
            RegexValidator(
                regex=r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$',
                message="Password must be at least 8 characters long, contain at least one letter, one number, and one special character."
            )
        ]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email
