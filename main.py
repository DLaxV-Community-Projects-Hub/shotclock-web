import asyncio
from datetime import datetime
import random
import websockets
import time as timing
from threading import Thread
from threading import Timer

shotclockStart = 30
rooms = {}

async def time(websocket, path):
  room = path[1:]
  if room not in rooms:
    rooms[room] = { 'game': 0, 'shotclock': shotclockStart, 'running': False, 'clients': set(), 'active': True }
  elif not rooms[room]['active']:
    rooms[room]['active'] = True
    log(room + " reactivated")
  rooms[room]['clients'].add(websocket)
  await sendTimeToClient(websocket, room)

  log(getName(websocket) + ' joined ' + room)
  try:
    while True:
      async for message in websocket:
        log(getName(websocket) + '@' + room + ': ' + message)
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
  log(getName(ws) + ' left ' + room)
  clients = rooms[room]['clients'].copy()
  clients.remove(ws)
  rooms[room]['clients'] = clients
  if len(rooms[room]['clients']) == 0 and rooms[room]['active']:
    rooms[room]['active'] = False
    log(room + ' deactivated')
    Timer(300.0, deleteRoom, (room,)).start()

def deleteRoom(room):
  if not rooms[room]['active']:
    del(rooms[room])
    log(room + ' deleted')
  else:
    log('Skipping delete for ' + room)

async def startTimer(room):
  if not rooms[room]['running']:
    rooms[room]['running'] = True
    thread = Thread(target=asyncio.run, args=(timerThread(room),))
    thread.start()

async def timerThread(room):
  while room in rooms and rooms[room]['running']:
    t1 = timing.time()
    rooms[room]['game'] = rooms[room]['game'] + 1
    if rooms[room]['shotclock'] > 0:
      rooms[room]['shotclock'] = rooms[room]['shotclock'] - 1
    await sendTimeToClients(room)
    t2 = timing.time()
    diff = t2 - t1
    await asyncio.sleep(1 - diff)

def stopTimer(room):
  rooms[room]['running'] = False

async def resetTimer(room):
  rooms[room]['shotclock'] = shotclockStart
  await sendTimeToClients(room)

async def sendTimeToClients(room):
  for ws in rooms[room]['clients']:
    await sendTimeToClient(ws, room)

async def sendTimeToClient(ws, room):
  try:
    shotclock = rooms[room]['shotclock']
    game = rooms[room]['game']
    await ws.send('g' + str(game) + ';s' + str(shotclock))
  except:
    disconnected(ws, room)

def log(msg):
  print(str(datetime.now()) + ": " + msg)

start_server = websockets.serve(time, "localhost", 5678)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()