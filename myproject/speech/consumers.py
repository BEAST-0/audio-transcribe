import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
import os
from datetime import datetime

UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

class SpeechConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.metadata = None  # Store metadata separately

    async def disconnect(self, close_code):
        pass

    async def receive(self, bytes_data=None, text_data=None):
        if text_data:
            # Handle metadata
            try:
                self.metadata = json.loads(text_data)  # Store metadata for later
                print(f"Received metadata: {self.metadata}")
                await self.send(text_data=json.dumps({"response": "Metadata received"}))
            except json.JSONDecodeError:
                print(f"Received invalid JSON: {text_data}")

        if bytes_data:
            # Handle binary audio data
            print(f"Received audio chunk: {len(bytes_data)} bytes")

            # Generate unique filename
            audio_name = f"audio_chunk.wav"
            file_path = os.path.join(UPLOAD_FOLDER, audio_name)

            # Save the audio file
            try:
                with open(file_path, "wb") as f:
                    f.write(bytes_data)
                print(f"Saved audio file: {file_path}")
            except Exception as e:
                print(f"Error saving file: {str(e)}")
                return await self.send(text_data=json.dumps({"error": "File saving failed"}))

            # Process the saved audio file
            try:
                from speech.views import process_audio
                ares = await sync_to_async(process_audio)(file_path,self.metadata)  # Process audio
                
                # Include metadata in the response
                response_data = {
                    "response": f"Processed: {audio_name}",
                    "transcription_text": ares,
                    "metadata": self.metadata  # Send metadata back
                }

                await self.send(text_data=json.dumps(response_data))

            except Exception as e:
                print(f"Error processing audio: {str(e)}")
                await self.send(text_data=json.dumps({"error": "Processing failed"}))

class SpeechConsumerv2(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, bytes_data=None, text_data=None):
        print("hehfdhkjf")
        await self.send(text_data=json.dumps({"response": "Processed"}))