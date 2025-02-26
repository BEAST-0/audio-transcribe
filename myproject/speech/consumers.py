import json
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
import asyncio

class SpeechConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, bytes_data=None, text_data=None):
        print("Received data", bytes_data, text_data)
        if bytes_data:
            # Handle binary audio data
            print(f"Received audio chunk: {len(bytes_data)} bytes")

            # Example: Save audio chunk to a file
            with open("audio_chunk.wav", "ab") as f:
                f.write(bytes_data)

            # Example: Send confirmation
            await self.send(text_data="Audio chunk received")

        elif text_data:
            # Handle text data (e.g., JSON)
            try:
                text_data_json = json.loads(text_data)
                message = text_data_json['message']
                print(f"Received text message: {message}")

                # Example: Process the message
                from speech.views import socket_checking

                # Call socket_checking using sync_to_async
                result = await sync_to_async(socket_checking)(message)

                # Example: Send a response
                await self.send(text_data=json.dumps({"response": f"Processed: {'fsfsdf'}"}))

            except json.JSONDecodeError:
                print(f"Received invalid JSON: {text_data}")

        else:
            print("Received unknown data type")