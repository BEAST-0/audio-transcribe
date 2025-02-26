import json

from channels.generic.websocket import AsyncWebsocketConsumer

class SpeechConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']  # Assuming your frontend sends a 'message'

        print(f"Received: {message}")

        # Send a response back to the client
        await self.send(text_data=json.dumps({
            'message': f'Received: {message}',
        }))