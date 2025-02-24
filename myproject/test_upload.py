import requests

file_path = "test_audio.wav"  # Replace with your actual audio file
django_api_url = "http://127.0.0.1:8000/api/upload_audio/"  # Your Django API endpoint

# Open the file and send it to Django (which forwards it to Colab)
files = {"file": open(file_path, "rb")}
response = requests.post(django_api_url, files=files)

# Print the transcription result
print(response.json())  # This should return the transcribed text
