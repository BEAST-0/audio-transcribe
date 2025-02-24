from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import requests
import os
import json
from speech.utils.pretty_table import save_transcription_as_table  

# 🔹 Deepgram API Key
DEEPGRAM_API_KEY = "9a4289e9696cbc1c365b468bbfe94967753aaa66"

# 🔹 Trello API Credentials (Use environment variables in production)
TRELLO_API_KEY = "dc36fb2ca97154c01365ecc3f19fe31e"
TRELLO_TOKEN = "ATTA712974522a014c9faab55dc6eecdc6eac4aa3cf9203bffe4fc05913ddef895f01277FAC8"
TRELLO_LIST_ID = "67bbf8f4b5d90f817ea62ba8"

def create_trello_task(task_name, task_description):
    """Function to create a new task in Trello."""
    if not all([TRELLO_API_KEY, TRELLO_TOKEN, TRELLO_LIST_ID]):
        return {"error": "Trello API credentials are missing"}

    url = "https://api.trello.com/1/cards"
    params = {
        "key": TRELLO_API_KEY,
        "token": TRELLO_TOKEN,
        "idList": TRELLO_LIST_ID,
        "name": task_name,
        "desc": task_description
    }

    try:
        response = requests.post(url, params=params)
        response.raise_for_status()  # Raise an error if request fails
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": f"Trello API request failed: {str(e)}"}

@csrf_exempt
def upload_audio(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    if "file" not in request.FILES:
        return JsonResponse({"error": "No file uploaded"}, status=400)

    audio_file = request.FILES["file"]

    # ✅ Ensure 'uploads/' folder exists
    upload_folder = "uploads"
    os.makedirs(upload_folder, exist_ok=True)

    # ✅ Save file to 'uploads/' directory
    file_path = os.path.join(upload_folder, audio_file.name)
    try:
        with open(file_path, "wb") as f:
            for chunk in audio_file.chunks():
                f.write(chunk)
    except Exception as e:
        return JsonResponse({"error": f"File saving failed: {str(e)}"}, status=500)

    # ✅ Send file to Deepgram API for transcription
    deepgram_url = "https://api.deepgram.com/v1/listen"
    headers = {
        "Authorization": f"Token {DEEPGRAM_API_KEY}",
        "Content-Type": "audio/wav"
    }
    try:
        with open(file_path, "rb") as f:
            response = requests.post(deepgram_url, headers=headers, data=f)
            response.raise_for_status()  # Raise an error if Deepgram API fails

        deepgram_result = response.json()
        transcription_text = deepgram_result.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "No transcription available")

        # ✅ Save formatted transcription using PrettyTable
        transcription_file = save_transcription_as_table(transcription_text, f"{audio_file.name}.txt")

        # ✅ Create Trello Task with transcription details
        task_name = f"Transcription: {audio_file.name}"
        trello_response = create_trello_task(task_name, transcription_text)

        return JsonResponse({
            "message": "Transcription saved and task created successfully",
            "transcription_file": transcription_file,
            "trello_response": trello_response
        })

    except requests.exceptions.RequestException as e:
        return JsonResponse({"error": f"Failed to transcribe: {str(e)}"}, status=500)

    except Exception as e:
        return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)
