# Standard library imports
from datetime import date
import os
import json
import requests

# Django imports
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

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
from speech.models import CustomUser, Meeting, MeetingTranscription
from .serializers import MeetingTranscriptionSerializer, UserSerializer, MeetingSerializer
from livekit.api import AccessToken, VideoGrants

load_dotenv()

#Deepgram API Key
DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')

#Trello API Credentials
TRELLO_API_KEY = os.getenv('TRELLO_API_KEY')
TRELLO_TOKEN = os.getenv('TRELLO_TOKEN')
TRELLO_LIST_ID = os.getenv('TRELLO_LIST_ID')
created_by_ai_label_id = os.getenv("TRELLO_AI_LABEL_ID") 


def create_trello_task(task_name, task_description):
    """Function to create a new task in Trello."""
    if not all([TRELLO_API_KEY, TRELLO_TOKEN, TRELLO_LIST_ID]):
        return {"error": "Trello API credentials are missing"}

    url = "https://api.trello.com/1/cards"
    params = {
        "key": TRELLO_API_KEY,
        "token": TRELLO_TOKEN,
        "idList": TRELLO_LIST_ID,
        "idLabels": created_by_ai_label_id,
        "name": task_name,
        "desc": task_description
    }

    try:
        response = requests.post(url, params=params)
        response.raise_for_status()  # Raise an error if request fails
        trello_card = response.json()

      # Extract the Trello card URL
        return {
            "id": trello_card.get("id"),
            "name": trello_card.get("name"),
            "trello_card_url": trello_card.get("shortUrl"),
        }
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


@api_view(['GET'])
def get_summary(request, room_id, username):
    if not room_id:
        return JsonResponse({"error": "No meeting id provided."}, status=400)
    summaries = Meeting.objects.filter(roomid=room_id, username=username).order_by("id").values_list("airesponse", flat = True)
    if len(summaries) == 1:
        # Parse the JSON string into a Python dict
        parsed_summary = json.loads(summaries[0])
        return Response(parsed_summary)
    else:
        # Handle multiple summaries if needed
        parsed_summaries = [json.loads(summary) for summary in summaries]
        return Response(parsed_summaries)

@api_view(['GET'])
def get_all_meetings(request, username):
    if not username:
        return JsonResponse({"error": "No username provided."}, status=400)
    meetings = Meeting.objects.filter(username=username).order_by("id")
    serialized_meetings = MeetingSerializer(meetings, many=True)
    return Response(serialized_meetings.data)

#saves gpt answer to db. only hit this api once per meeting.
@csrf_exempt
@require_POST
def ask_question(request): 
    try:
        current_date = date.today().strftime('%Y-%m-%d')

        room_id = request.POST.get('room_id')
        if not room_id:
            return JsonResponse({"error": "No meeting id provided."}, status=400)
    
        username = request.POST.get('username')
        if not username:
            return JsonResponse({"error": "No username provided."}, status=400)

        transcriptions = MeetingTranscription.objects.filter(roomid=room_id, username=username).order_by("id").values("text")
        transcript = " "
        for transcription in transcriptions:
            transcript += transcription["text"] + " "

        # transcript = """SPEAKER 0: Hello. My name is Jeevan."
        # "SPEAKER 1: Hello. Hi. Good evening.",
        # "SPEAKER 0: Good evening, mister Navin. Welcome to you today's session."
        # "SPEAKER 1: Thank you. How are you?"
        # "SPEAKER 0: I'm doing really well. I hope I'm loud and clear to you."
        # "SPEAKER 1: Yeah. Your voice is very clear."
	    # "SPEAKER 0: You should submit the document tomorrow at 10:00 AM."
	    # "SPEAKER 1: Sure."""

        openai_api_key = os.getenv("OPENAI_API_KEY")

        if not openai_api_key:
            return JsonResponse({"error": "OpenAI API key not configured."}, status=500)

        llm = ChatOpenAI(
            openai_api_key=openai_api_key,
            model="gpt-4o-mini",
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        prompt_template = PromptTemplate(
            input_variables=["meeting_transcription", "current_date"],
            template="""
            You are an AI assistant that processes meeting transcriptions where speakers are not explicitly identified.
            
            Analyze the following transcript and extract the following details:
            - **Speaker Identification**: Identify different speakers based on conversational flow, pronouns used, questions asked and answers given.
            - **Meeting Notes**: Summarize key discussion points concisely.
            - **Schedules**: Identify any dates, times, or deadlines mentioned.
            - **Action Items**: List tasks assigned to specific individuals, including deadlines.
            
            Speaker identification guidelines:
            1. Pay attention to shifts in perspective (e.g., "I will" vs "you should")
            2. Track question-answer pairs to identify different speakers
            3. Look for names mentioned in third-person vs first-person references
            4. Consider the context of who would likely assign tasks vs who would accept them
            5. Watch for confirmation responses that indicate a different speaker
            
            Format your response in **valid JSON**:
            {{
                "summary": "Brief but comprehensive summary of the meeting capturing all key points, decisions, deadlines, and action items in an easy-to-understand format",
                "speakers": [
                    {{
                        "speaker_id": "SPEAKER_1",
                        "identified_name": "Name identified from transcript or role description if name unknown"
                    }}
                ],
                "notes": [
                    {{
                        "topic": "Description of key discussion point",
                        "speaker": "Identified name or role of speaker"
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
                        "assigned_to": "Person's identified name or role",
                        "assigned_by": "Person who assigned the task",
                        "deadline": "YYYY-MM-DD"
                    }}
                ],
                "trello_tasks": [
                    {{
                        "task": "Description of action item",
                        "assigned_to": "Person's identified name or role",
                        "assigned_by": "Person who assigned the task",
                        "deadline": "YYYY-MM-DD",
                        "trello_list": "To Do"
                    }}
                ]
            }}
            
            IMPORTANT: For all deadlines and schedules, convert relative time references to actual dates based on today's date ({current_date}):
            - "tomorrow" = the day after {current_date}
            - "next week" = 7 days after {current_date}
            - "next month" = the same day in the following month
            - "in X days/weeks/months" = calculate the specific date accordingly.
            
            SPEAKER IDENTIFICATION STRATEGY:
            1. First, segment the transcript by identifying natural breaks in conversation
            2. Look for names mentioned directly (e.g., "Naveen, can you...")
            3. Analyze question-answer patterns to separate speakers
            4. Track pronoun usage changes (I/you/we) to detect speaker changes
            5. For task assignments, the person accepting the task is typically the assignee
            6. Confirmations like "Ok fine" usually indicate a return to the original speaker

            **Transcript:**
            {transcript}
            """
        )

        chain = LLMChain(llm=llm, prompt=prompt_template)
        answer = chain.run(transcript=transcript, current_date=current_date)

        try:
            json_answer = json.loads(answer)  # This might fail if GPT output is not proper JSON
            notes = json_answer.get("notes", [])
            schedules = json_answer.get("schedules", [])
            action_items = json_answer.get("action_items", [])
            trello_tasks = json_answer.get("trello_tasks", [])

            trello_responses = []
            for task in trello_tasks:
                task_name = task.get("task", "No task name")
                task_description = (
                    f"Task Details:\n"
                    f"- Assigned to: {task.get('assigned_to', 'Unassigned')}\n"
                    f"- Deadline: {task.get('deadline', 'No deadline specified')}\n"
                    f"\n"
                    f"Task Context:\n"
                    f"This task was identified from a meeting conversation between {', '.join([speaker.get('identified_name', speaker.get('original_id', 'Unknown')) for speaker in json_answer.get('speakers', [])])}\n"
                    f"\n"
                    f"Related Meeting Notes:\n"
                    f"- {' '.join([f'{note.get('topic', 'Unknown topic')} (mentioned by {note.get('speaker', 'Unknown speaker')})' for note in notes])}\n"
                    f"\n"
                    f"Additional Information:\n"
                    f"- Created on: {current_date}\n"
                    f"- Extracted automatically from meeting transcript"
                )
                
                trello_response = create_trello_task(task_name, task_description)
                trello_responses.append(trello_response)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format in AI response.", "raw_output": answer}, status=500)
        
        Meeting.objects.filter(roomid=room_id).update(airesponse=json.dumps(json_answer))

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
        LIVEKIT_SERVER_URL = os.getenv('LIVEKITSERVERURL', 'wss://your-livekit-server.com')  # Get your LiveKit server URL

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
            
            # Generate meeting sharing information
            meeting_url = f"{LIVEKIT_SERVER_URL}/room/{room_name}?token={token_jwt}"
            sharing_code = room_name  # You might want to generate a custom code
            
            # Return token and meeting info
            return Response({
                "token": token_jwt,
                "meeting_info": {
                    "room_name": room_name,
                    "meeting_url": meeting_url,
                    "sharing_code": sharing_code,
                    "host": user_identity,
                    "expires_at": expiration.isoformat() if 'expiration' in locals() else None
                }
            })
            
        except Exception as e:
            import traceback
            return Response({
                "error": f"Failed to generate token: {str(e)}",
                "traceback": traceback.format_exc()
            }, status=500)

@csrf_exempt
@require_POST
def assign_trello_tasks_from_meeting(request):
    """
    Fetches the meeting summary from the database, extracts Trello tasks, and creates Trello cards.
    
    Args:
        room_id (str): The room ID of the meeting.
        username (str): The username associated with the meeting.
    
    Returns:
        JsonResponse: A response containing the results of the Trello card creation process.
    """
    try:
        # Parse JSON data from the request body
        data = json.loads(request.body)
        
        # Extract room_id and username from the parsed JSON data
        room_id = data.get("room_id")
        username = data.get("username")
        # Fetch the meeting summary from the database
        summaries = Meeting.objects.filter(roomid=room_id, username=username).order_by("id").values_list("airesponse", flat=True)
    
        if not summaries:
            return JsonResponse({"error": "No meeting summary found for the given room ID and username."}, status=404)
        
        # Parse the first summary (assuming only one summary is needed)
        meeting_summary = json.loads(summaries[0])
        
        # Extract Trello tasks from the meeting summary
        trello_tasks = meeting_summary.get("trello_tasks", [])
        
        if not trello_tasks:
            return JsonResponse({"error": "No Trello tasks found in the meeting summary."}, status=404)
        
        # Create Trello cards for each task
        trello_responses = []
        for task in trello_tasks:
            task_name = task.get("task", "No task name")
            task_description = (
                f"Task Details:\n"
                f"- Assigned to: {task.get('assigned_to', 'Unassigned')}\n"
                f"- Deadline: {task.get('deadline', 'No deadline specified')}\n"
                f"\n"
                f"Task Context:\n"
                f"This task was identified from a meeting conversation between {', '.join([speaker.get('identified_name', speaker.get('original_id', 'Unknown')) for speaker in meeting_summary.get('speakers', [])])}\n"
                f"\n"
                f"Related Meeting Notes:\n"
                f"- {' '.join([f'{note.get('topic', 'Unknown topic')} (mentioned by {note.get('speaker', 'Unknown speaker')})' for note in meeting_summary.get('notes', [])])}\n"
                f"\n"
                f"Additional Information:\n"
                f"- Created on: {date.today().strftime('%Y-%m-%d')}\n"
                f"- Extracted automatically from meeting transcript"
            )
            
            # Create the Trello task
            trello_response = create_trello_task(task_name, task_description)
            trello_responses.append(trello_response)
        
        # Return the results
        return JsonResponse({
            "message": "Trello tasks created successfully.",
            "trello_responses": trello_responses
        }, status=200)
    
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
@csrf_exempt
def get_user_details(request):
    """
    API endpoint to fetch user details based on username.
    
    Args:
        request (HttpRequest): The HTTP request object containing the `username` as a query parameter.
    
    Returns:
        JsonResponse: A response containing the user details or an error message.
    """
    try:
        # Extract username from the query parameters
        username = request.GET.get("username")
        print("Received username:", username)  # Debugging: Print the received username
        
        # Validate the username
        if not username:
            return JsonResponse({"error": "Username is required."}, status=400)
        
        # Fetch the user details from the database
        user = CustomUser.objects.filter(username=username).first()
        
        if not user:
            return JsonResponse({"error": "User not found."}, status=404)
        
        # Prepare the user details to return
        user_details = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else None,
            # Add other fields as needed
        }
        
        # Return the user details
        return JsonResponse({"user": user_details}, status=200)
    
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)