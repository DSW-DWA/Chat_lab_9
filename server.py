import asyncio
import tornado.ioloop
import tornado.web
import tornado.websocket
import aioredis
import json
import os
from dotenv import load_dotenv

class WebSocketHandler(tornado.websocket.WebSocketHandler):
    clients = set()
    room = "default"

    def check_origin(self, origin):
        return True

    async def open(self):
        self.clients.add(self)
        self.redis = await aioredis.from_url(os.getenv("REDIS_URL"))
        self.pubsub = self.redis.pubsub()
        await self.pubsub.subscribe(self.room)
        asyncio.create_task(self.listen_to_redis())

    async def on_message(self, obj):
        data = json.loads(obj)
        event = data.get("connectEvent", False)
        room = data.get("roomId")
        if (room == ""):
            room = self.room
        text = data.get("message")
        name = data.get("name")
        if (event):
            await self.pubsub.unsubscribe(self.room)
            self.room = room
            await self.pubsub.subscribe(self.room)
            await self.redis.publish(self.room, f'{name} connect to chat ({self.room})')
        else:
            await self.redis.publish(self.room, f'{name} type in chat ({self.room}):{text}')

    async def on_close(self):
        self.clients.remove(self)
        await self.pubsub.unsubscribe(self.room)
        await self.pubsub.close()

    async def listen_to_redis(self):
        async for message in self.pubsub.listen():
            if message["type"] == "message":
                self.write_message(message["data"].decode("utf-8"))

def make_app():
    return tornado.web.Application([
        (r"/ws", WebSocketHandler),
        (r"/", tornado.web.RedirectHandler, {"url": "/static/index.html"}),
        (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": "./static"}),
    ])

if __name__ == "__main__":
    load_dotenv()
    app = make_app()
    app.listen(8888)
    print("Server started at http://localhost:8888")
    tornado.ioloop.IOLoop.current().start()
