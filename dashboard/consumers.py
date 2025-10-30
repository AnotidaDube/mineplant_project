import json
from channels.generic.websocket import AsyncWebsocketConsumer

class ProdDemandConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = "prod_demand"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # Receive message from group
    async def broadcast_update(self, event):
        # event['payload'] expected to be JSON-serializable
        await self.send(text_data=json.dumps({
            "type": "update",
            "payload": event["payload"]
        }))
