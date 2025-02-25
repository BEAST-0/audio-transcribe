from django.db import models
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
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE)
    text = models.TextField()

    def __str__(self):
        return f"{self.speaker} - {self.meeting.title}"
