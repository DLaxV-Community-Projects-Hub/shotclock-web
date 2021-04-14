import asyncio
import datetime
import random
import websockets
from threading import Thread

startTime = 30
rooms = {}

async def time(websocket, path):
  room = path[1:]
  if room not in rooms:
    rooms[room] = { 'time': startTime, 'running': False, 'clients': set() }
  rooms[room]['clients'].add(websocket)
  await sendTimeToClient(websocket, room)

  print(getName(websocket) + ' joined ' + room)
  try:
    while True:
      async for message in websocket:
        print(getName(websocket) + '@' + room + ': ' + message)
        if message == 'start':
          await startTimer(room)
        elif message == 'stop':
          stopTimer(room)
        elif message == 'reset':
          await resetTimer(room)
  except:
    disconnected(websocket, room)

def getName(ws):
  if ws.request_headers['X-Real-IP']:
    return ws.request_headers['X-Real-IP']
  return websocket.remote_address[0]

def disconnected(ws, room):
  print(getName(ws) + ' left ' + room)
  clients = rooms[room]['clients'].copy()
  clients.remove(ws)
  rooms[room]['clients'] = clients
  if len(rooms[room]['clients']) == 0:
    del(rooms[room])
    print(room + ' closed')

async def startTimer(room):
  rooms[room]['running'] = True
  thread = Thread(target=asyncio.run, args=(timerThread(room),))
  thread.start()

async def timerThread(room):
  while room in rooms and rooms[room]['running'] and rooms[room]['time'] > 0:
    rooms[room]['time'] = rooms[room]['time'] - 1
    await sendTimeToClients(room)
    await asyncio.sleep(1)

def stopTimer(room):
  rooms[room]['running'] = False

async def resetTimer(room):
  rooms[room]['time'] = startTime
  await sendTimeToClients(room)

async def sendTimeToClients(room):
  for ws in rooms[room]['clients']:
    await sendTimeToClient(ws, room)

async def sendTimeToClient(ws, room):
  try:
    time = rooms[room]['time']
    await ws.send('time:' + str(time))
  except:
    disconnected(ws, room)

start_server = websockets.serve(time, "localhost", 5678)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()