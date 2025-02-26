import re
import os
import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from dotenv import load_dotenv
from deepgram import Deepgram
from django.views.decorators.http import require_POST
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from speech.models import MeetingTranscription
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import MeetingTranscriptionSerializer, UserSerializer
from rest_framework.decorators import api_view

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

TAG = 'SPEAKER '

def create_transcript(output_json, output_transcript,room_id):
    lines = []
    with open(output_json, "r") as file:
        words = json.load(file)["results"]["channels"][0]["alternatives"][0]["words"]
        curr_speaker = 0
        curr_line = ''
        for word_struct in words:
            word_speaker = word_struct["speaker"]
            word = word_struct["punctuated_word"]
            if word_speaker == curr_speaker:
                curr_line += ' ' + word
            else:
                tag = TAG + str(curr_speaker) + ':'
                full_line = tag + curr_line + '\n'
                curr_speaker = word_speaker
                lines.append(full_line)
                curr_speaker = word_speaker
                curr_line = ' ' + word
        lines.append(TAG + str(curr_speaker) + ':' + curr_line)
        for line in lines:
            match = re.match(r"SPEAKER (\d+):\s(.+)", line)
            if match:
                speaker_number = int(match.group(1))
                text = match.group(2)
            MeetingTranscription.objects.create(speaker=speaker_number,roomid=room_id, text=text)
    return lines

DIRECTORY = '.'

def print_transcript(room_id):
    os.makedirs("transcriptions", exist_ok=True)
    for filename in os.listdir(DIRECTORY):
        if filename.endswith('.json'):
            json_path = os.path.join(DIRECTORY, filename)
            output_transcript = os.path.join("transcriptions", os.path.splitext(filename)[0] + '.txt')
            transcription_text = create_transcript(json_path, output_transcript, room_id)  # Process the file
            os.remove(json_path)
            return transcription_text

@csrf_exempt
def upload_audio(request):
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    if "file" not in request.FILES:
        return JsonResponse({"error": "No file uploaded"}, status=400)

    room_id = request.POST.get('room_id')
    if not room_id:
        return JsonResponse({"error": "No meeting id provided."}, status=400)
    
    audio_file = request.FILES["file"]

    #Ensure 'uploads/' folder exists
    upload_folder = "uploads"
    os.makedirs(upload_folder, exist_ok=True)

    #Save file to 'uploads/' directory
    file_path = os.path.join(upload_folder, audio_file.name)
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
            with open(f"./{audio_file.name[:-4]}.json", "w") as transcript:
                  json.dump(res, transcript, indent=4)

        deepgram_result = res
        transcription_text = deepgram_result.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "No transcription available")

        #Create Trello Task with transcription details
        task_name = f"Transcription: {audio_file.name}"
        trello_response = create_trello_task(task_name, transcription_text)
        
        processed_transcript = print_transcript(room_id)

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
            return Response({"message": "User created successfully!", "data": serializer.data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# get request
@csrf_exempt
def checking(request):
    return JsonResponse({"message": "Hello1, World!"})

def socket_checking(message):
    return {"message": "From views.socket_checkin" + message}

@api_view(['GET'])
def get_meeting_transcriptions(request, room_id):
    transcriptions = MeetingTranscription.objects.filter(roomid=room_id).order_by("id")
    serializer = MeetingTranscriptionSerializer(transcriptions, many=True)
    return Response(serializer.data)
