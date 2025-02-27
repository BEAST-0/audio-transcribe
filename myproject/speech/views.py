# Standard library imports
import os
import re
import json
import requests

# Django imports
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

# Third-party package imports
from dotenv import load_dotenv
from deepgram import Deepgram
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.permissions import AllowAny

# Local imports
from speech.models import MeetingTranscription
from .serializers import MeetingTranscriptionSerializer, UserSerializer
from livekit.api import AccessToken, VideoGrants

load_dotenv()

#Deepgram API Key
DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')

#Trello API Credentials
TRELLO_API_KEY = os.getenv('TRELLO_API_KEY')
TRELLO_TOKEN = os.getenv('TRELLO_TOKEN')
TRELLO_LIST_ID = os.getenv('TRELLO_LIST_ID')



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

TAG = "SPEAKER "

def create_transcript(json_path, room_id,username):
    with open(json_path, "r") as file:
        words = json.load(file)["results"]["channels"][0]["alternatives"][0]["words"]
    if not words:
        return []
    lines = []
    bulk_objects = []
    curr_speaker, curr_line = words[0]["speaker"], ""
    for word_struct in words:
        word, word_speaker = word_struct["punctuated_word"], word_struct["speaker"]
        if word_speaker == curr_speaker:
            curr_line += " " + word
        else:
            full_line = f"{TAG}{curr_speaker}: {curr_line.strip()}"
            lines.append(full_line)
            bulk_objects.append(
                MeetingTranscription(
                    speaker=curr_speaker, 
                    roomid=room_id, 
                    text=curr_line.strip(), 
                    username=username
                )
            )    
            curr_speaker, curr_line = word_speaker, word
    if curr_line:
        full_line = f"{TAG}{curr_speaker}: {curr_line.strip()}"
        lines.append(full_line)
        bulk_objects.append(
            MeetingTranscription(
                speaker=curr_speaker, 
                roomid=room_id, 
                text=curr_line.strip(), 
                username=username
            )
        )
    MeetingTranscription.objects.bulk_create(bulk_objects)
    return lines

TRANSCRIPTS_DIRECTORY = './uploads/transcripts'
UPLOADS_DIRECTORY = './uploads/'

def process_transcriptions(room_id,username, audiofilename):
    for filename in os.listdir(TRANSCRIPTS_DIRECTORY):
        if filename == (audiofilename[:-4] + ".json"):
            json_path = os.path.join(TRANSCRIPTS_DIRECTORY, filename)
            audio_path = os.path.join(UPLOADS_DIRECTORY,audiofilename)
            transcription_text = create_transcript(json_path, room_id, username)
            os.remove(json_path)
            os.remove(audio_path)
            return transcription_text

@csrf_exempt
@require_POST
def test_transcription(request, room_id):
    for filename in os.listdir(TRANSCRIPTS_DIRECTORY):
        if filename.endswith(".json"):
            json_path = os.path.join(TRANSCRIPTS_DIRECTORY, filename)
            transcription_text = create_transcript(json_path, room_id)
            # os.remove(json_path)
            return JsonResponse({
            "message": "Transcription saved and task created successfully.",
            "transcription_text": transcription_text,
        })

@csrf_exempt
def upload_audio(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method."}, status=405)

    if "file" not in request.FILES:
        return JsonResponse({"error": "No file uploaded."}, status=400)

    room_id = request.POST.get('room_id')
    if not room_id:
        return JsonResponse({"error": "No meeting id provided."}, status=400)
    
    username = request.POST.get('username')
    if not username:
        return JsonResponse({"error": "No username provided."}, status=400)
    
    audio_file = request.FILES["file"]
    audiofilename = audio_file.name

    #Ensure 'uploads/' folder exists
    upload_folder = "uploads"
    os.makedirs(upload_folder, exist_ok=True)

    #Save file to 'uploads/' directory
    file_path = os.path.join(upload_folder, audiofilename)
    try:
        with open(file_path, "wb") as f:
            for chunk in audio_file.chunks():
                f.write(chunk)
    except Exception as e:
        return JsonResponse({"error": f"File saving failed: {str(e)}"}, status=500)
    

    dg = Deepgram(DEEPGRAM_API_KEY)
    MIMETYPE = 'mp3'
    options = {
        "punctuate": True,
        "diarize": True,
        "model": 'general',
        "tier": 'nova'
    }
    #Send file to Deepgram API for transcription
    try:
        with open(file_path, "rb") as f:
            source = {"buffer": f, "mimetype":'audio/'+MIMETYPE}
            res = dg.transcription.sync_prerecorded(source, options)
            os.makedirs("uploads/transcripts", exist_ok=True)
            with open(f"./uploads/transcripts/{audio_file.name[:-4]}.json", "w") as transcript:
                  json.dump(res, transcript, indent=4)

        deepgram_result = res
        transcription_text = deepgram_result.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "No transcription available")

        #Create Trello Task with transcription details
        task_name = f"Transcription: {audio_file.name}"
        trello_response = create_trello_task(task_name, transcription_text)
        
        processed_transcript = process_transcriptions(room_id,username, audiofilename)


        return JsonResponse({
            "message": "Transcription saved and task created successfully",
            "transcription_text": processed_transcript,
        })

    except requests.exceptions.RequestException as e:
        return JsonResponse({"error": f"Failed to transcribe: {str(e)}"}, status=500)

    except Exception as e:
        return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)


@csrf_exempt
@require_POST
def ask_question(request):
    try:
        transcript = """John: Good morning, everyone. Let's start with the project update. Sarah, can you share the status?  
        Sarah: Sure! We completed the initial UI design, and the dev team will start implementation on March 5th.  
        Mark: That's great. Also, we need the API documentation finalized by March 8th. Who's taking that?  
        David: I can handle the API documentation.  
        John: Perfect. Also, don't forget we have the client presentation on March 10th at 3 PM.  
        Lisa: I'll prepare the presentation slides by March 9th.  
        John: Sounds good. Let's also schedule the next team sync on March 12th at 10 AM.  
        Mark: Noted. Also, Sarah, can you send the updated UI mockups to the team by March 6th?  
        Sarah: Yes, I'll do that.  
        John: Great. That's all for today. Thanks, everyone!"""

        openai_api_key = os.getenv("OPENAI_API_KEY")

        if not openai_api_key:
            return JsonResponse({"error": "OpenAI API key not configured."}, status=500)

        llm = ChatOpenAI(
            openai_api_key=openai_api_key,
            model="gpt-4o-mini",  # Use GPT-4o instead of "gpt-4o-mini" if needed
            temperature=0.7,
            response_format={"type": "json_object"}  # ✅ Use "json_object" instead of "json"
        )

        prompt_template = PromptTemplate(
            input_variables=["transcript"],
            template="""
            You are an AI assistant that processes meeting transcriptions. 
            Analyze the following transcript and extract the following details:

            - **Meeting Notes**: Summarize key discussion points concisely.
            - **Schedules**: Identify any dates, times, or deadlines mentioned.
            - **Action Items**: List tasks assigned to specific individuals, including deadlines.

            Format your response in **valid JSON**:

            {{
                "notes": [
                    {{
                        "topic": "Description of key discussion point"
                    }}
                ],
                "schedules": [
                    {{
                        "date": "YYYY-MM-DD",
                        "time": "HH:MM AM/PM",
                        "event": "Description of scheduled event"
                    }}
                ],
                "action_items": [
                    {{
                        "task": "Description of action item",
                        "assigned_to": "Person's name",
                        "deadline": "YYYY-MM-DD"
                    }}
                ],
                "trello_tasks": [
                    {{
                        "task": "Description of action item",
                        "assigned_to": "Person's name",
                        "deadline": "YYYY-MM-DD",
                        "trello_list": "To Do"
                    }}
                ]
            }}

            **Transcript:**
            {transcript}
            """
        )

        chain = LLMChain(llm=llm, prompt=prompt_template)
        answer = chain.run(transcript=transcript)  # Ensure correct variable mapping

        print(f"Raw Answer: {answer}")

        # Ensure the response is valid JSON
        try:
            json_answer = json.loads(answer)  # This might fail if GPT output is not proper JSON
            notes = json_answer.get("notes", [])
            schedules = json_answer.get("schedules", [])
            action_items = json_answer.get("action_items", [])
            trello_tasks = json_answer.get("trello_tasks", [])

            print(f"trello_tasks: {trello_tasks[0]}")
            # iterate over the trello tasks and create them
            for task in trello_tasks:
                task_name = task.get("task", "No task name")
                task_description = task.get("assigned_to", "No assignee") + " - " + task.get("deadline", "No deadline")
                trello_response = create_trello_task(task_name, task_description)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format in AI response.", "raw_output": answer}, status=500)

        return JsonResponse({"answer": json_answer})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

class UserCreateView(APIView):
    def post(self, request):
        serializer =UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "User created successfully.", "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# get request
@csrf_exempt
def checking(request):
    return JsonResponse({"message": "Hello1, World!"})

def socket_checking(message):
    return {"message": "Socket response" + message}

@api_view(['GET'])
def get_meeting_transcriptions(request, room_id):
    transcriptions = MeetingTranscription.objects.filter(roomid=room_id).order_by("id")
    serializer = MeetingTranscriptionSerializer(transcriptions, many=True)
    return Response(serializer.data)

def process_audio(file_path):
    """Process an audio file using Deepgram API."""
    
    dg = Deepgram(DEEPGRAM_API_KEY)
    MIMETYPE = "mp3"
    options = {
        "punctuate": True,
        "diarize": True,
        "model": "general",
        "tier": "nova"
    }

    # Send file to Deepgram API for transcription
    try:
        with open(file_path, "rb") as f:
            source = {"buffer": f, "mimetype": f"audio/{MIMETYPE}"}
            res = dg.transcription.sync_prerecorded(source, options)
            
            # Save transcription result as JSON
            transcription_path = file_path.replace(".wav", ".json")
            with open(transcription_path, "w") as transcript_file:
                json.dump(res, transcript_file, indent=4)

        # Extract transcription text
        deepgram_result = res
        transcription_text = deepgram_result.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "No transcription available")

        return transcription_text

    except Exception as e:
        return f"Transcription failed: {str(e)}"

class LiveKitTokenView(APIView):
    permission_classes = [AllowAny]  # Adjust permissions as needed

    def post(self, request):
        user_identity = request.data.get("user_identity", "guest")  # Unique identifier
        room_name = request.data.get("room_name", "default-room")  # Room to join

        # LiveKit credentials from settings or environment variables
        LIVEKIT_API_KEY = os.getenv('LIVEKITAPIKEY')
        LIVEKIT_SECRET_KEY = os.getenv('LIVEKITAPISECRET')

        if not LIVEKIT_API_KEY or not LIVEKIT_SECRET_KEY:
            return Response({"error": "LiveKit API credentials are missing"}, status=500)

        try:
            # Import datetime for proper time handling
            import datetime
            
            # Create token with properly formatted expiration time
            token = AccessToken(
                api_key=LIVEKIT_API_KEY,
                api_secret=LIVEKIT_SECRET_KEY
            )
            
            # Use the grants
            grants = VideoGrants(
                room_join=True,
                room=room_name
            )
            
            # Try to set the grants
            if hasattr(token, 'with_grants'):
                token.with_grants(grants)
            elif hasattr(token, 'video_grant'):
                token.video_grant = grants
            
            # Try to set identity
            if hasattr(token, 'identity'):
                token.identity = user_identity
                
            # Set expiration using datetime objects instead of integers
            if hasattr(token, 'set_expires'):
                # Set expiration to current time + 1 hour
                expiration = datetime.datetime.now() + datetime.timedelta(hours=1)
                token.set_expires(expiration)
            elif hasattr(token, 'expires'):
                expiration = datetime.datetime.now() + datetime.timedelta(hours=1)
                token.expires = expiration
                
            # Generate token
            token_jwt = token.to_jwt()
            return Response({"token": token_jwt})
            
        except Exception as e:
            import traceback
            return Response({
                "error": f"Failed to generate token: {str(e)}",
                "traceback": traceback.format_exc()
            }, status=500)