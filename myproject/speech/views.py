from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from dotenv import load_dotenv
import requests
import os
import json
from deepgram import Deepgram
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

from speech.models import Meeting, MeetingTranscription

load_dotenv()

#Deepgram API Key
DEEPGRAM_API_KEY = os.environ.get('DEEPGRAM_API_KEY')

#Trello API Credentials
TRELLO_API_KEY = os.environ.get('TRELLO_API_KEY')
TRELLO_TOKEN = os.environ.get('TRELLO_TOKEN')
TRELLO_LIST_ID = os.environ.get('TRELLO_LIST_ID')
OPENAI_API_KEY="YOUR_OPENAI_API_KEY"

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

def create_transcript(output_json, output_transcript, meetingId):
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
        MeetingTranscription.objects.create(speaker=word_speaker,meeting=Meeting.objects.get(id=meetingId), text=curr_line)
        curr_line = ' ' + word
    lines.append(TAG + str(curr_speaker) + ':' + curr_line)
    with open(output_transcript, 'w') as f:
      for line in lines:
        f.write(line)
        f.write('\n')
  return

DIRECTORY = '.'

def print_transcript(meetingId):
    os.makedirs("transcriptions", exist_ok=True)
    for filename in os.listdir(DIRECTORY):
        if filename.endswith('.json'):
            json_path = os.path.join(DIRECTORY, filename)
            output_transcript = os.path.join("transcriptions", os.path.splitext(filename)[0] + '.txt')
            create_transcript(json_path, output_transcript, meetingId)  # Process the file
            os.remove(json_path)

@csrf_exempt
def upload_audio(request):
    print("fafdsafdas",DEEPGRAM_API_KEY)
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=405)

    if "file" not in request.FILES:
        return JsonResponse({"error": "No file uploaded"}, status=400)

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

        meeting = Meeting.objects.create(userid=1, title="Project started")
        
        print_transcript(meeting.id)

        return JsonResponse({
            "message": "Transcription saved and task created successfully",
            "trello_response": trello_response
        })

    except requests.exceptions.RequestException as e:
        return JsonResponse({"error": f"Failed to transcribe: {str(e)}"}, status=500)

    except Exception as e:
        return JsonResponse({"error": f"Unexpected error: {str(e)}"}, status=500)

@csrf_exempt
@require_POST
def ask_question(request):
    try:
        data = json.loads(request.body)
        question = data.get('question')

        if not question:
            return JsonResponse({"error": "Please provide a 'question' in the JSON body."}, status=400)

        openai_api_key = os.getenv("OPENAI_API_KEY")

        if not openai_api_key:
            print("Error: OpenAI API key not found in environment variables.")
            return JsonResponse({"error": "OpenAI API key not configured."}, status=500)

        try:
            llm = ChatOpenAI(
                openai_api_key=openai_api_key,
                model="gpt-4o-mini",  # Update model name
                temperature=0.7
            )

            prompt_template = PromptTemplate(
                input_variables=["question"],
                template="Answer the following question: {question}"
            )

            chain = LLMChain(llm=llm, prompt=prompt_template)
            answer = chain.run(question=question)

            print(f"Question: {question}")
            print(f"Answer: {answer}")

            return JsonResponse({"answer": answer})

        except Exception as e:
            print(f"Error during Langchain processing: {e}")
            return JsonResponse({"error": str(e)}, status=500)

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON in request body."}, status=400)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
