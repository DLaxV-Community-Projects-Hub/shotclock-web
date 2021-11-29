import asyncio
from datetime import datetime
import random
import websockets
from websockets.protocol import State
import time as timing
from threading import Thread
from threading import Timer

shotclockStart = 30
rooms = {}

async def time(websocket, path):
  room = path[1:]
  if room not in rooms:
    rooms[room] = { 
      'active': True,
      'running': False,
      'gameTime': 0,
      'shotclock': shotclockStart,
      'penalties': [],
      'score': [0, 0],
      'clients': set()
    }
  elif not rooms[room]['active']:
    rooms[room]['active'] = True
    log(room + " reactivated")
  rooms[room]['clients'].add(websocket)
  await sendTimeToClient(websocket, room)
  await sendScoreToClient(websocket, room)

  log(getName(websocket) + ' joined ' + room)
  try:
    while True:
      if websocket.state == State.CLOSED:
        disconnected(websocket, room)
        break
      async for message in websocket:
        log(getName(websocket) + '@' + room + ': ' + message)
        if message == 'start':
          await startTimer(room)
        elif message == 'stop':
          stopTimer(room)
        elif message == 'startstop':
          if rooms[room]['running']:
            stopTimer(room)
          else:
            await startTimer(room)
        elif message == 'reset':
          await resetTimer(room)
        elif message == 'goalH+':
          rooms[room]['score'][0] = rooms[room]['score'][0] + 1
          await sendScoreToClients(room)
        elif message == 'goalA+':
          rooms[room]['score'][1] = rooms[room]['score'][1] + 1
          await sendScoreToClients(room)
        elif message == 'goalH-':
          rooms[room]['score'][0] = max(rooms[room]['score'][0] - 1, 0)
          await sendScoreToClients(room)
        elif message == 'goalA-':
          rooms[room]['score'][1] = max(rooms[room]['score'][1] - 1, 0)
          await sendScoreToClients(room)
        elif message.startswith("p"):
          pData = message.split(";")
          team = int(pData[1])
          player = int(pData[2])
          time = int(pData[3])
          await addPenalty(room, team, player, time)
  except:
    disconnected(websocket, room)

def getName(ws):
  if ws.request_headers['X-Real-IP']:
    return ws.request_headers['X-Real-IP']
  return websocket.remote_address[0]

def disconnected(ws, room):
  if ws in rooms[room]['clients']:
    log(getName(ws) + ' left ' + room)
    clients = rooms[room]['clients'].copy()
    clients.remove(ws)
    rooms[room]['clients'] = clients
    if len(rooms[room]['clients']) == 0 and rooms[room]['active']:
      stopTimer(room)
      rooms[room]['active'] = False
      log(room + ' deactivated')
      Timer(86400.0, deleteRoom, (room,)).start()

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
    # Startzeit für Lautzeitmessung dieser Methode speichern
    t1 = timing.time()

    # Spielzeit +1 Sek
    rooms[room]['gameTime'] = rooms[room]['gameTime'] + 1
    
    # Wenn Shotclock nicht abgelaufen
    if rooms[room]['shotclock'] > 0:
      # Shotclock -1 Sek
      rooms[room]['shotclock'] = rooms[room]['shotclock'] - 1
    
    # Alle Penalties iterieren
    for p in rooms[room]['penalties']:
      # Penalty -1 Sek
      p['time'] = p['time'] - 1
    # Abgelaufene Penalties löschen
    rooms[room]['penalties'][:] = [p for p in rooms[room]['penalties'] if p['time'] >= -5]

    # Neue Zeiten senden
    await sendTimeToClients(room)

    # Laufzeit dieser Methode berechnen
    t2 = timing.time()
    diff = t2 - t1
    # Eine Sekunde minus Methodenlaufzeit bis zum nächsten Aufruf
    await asyncio.sleep(1 - diff)

def stopTimer(room):
  rooms[room]['running'] = False

async def resetTimer(room):
  rooms[room]['shotclock'] = shotclockStart
  await sendTimeToClients(room)

async def addPenalty(room, team, player, time):
  rooms[room]['penalties'].append({
    "team": team,
    "player": player,
    "time": time
  })
  await sendTimeToClients(room)

async def sendTimeToClients(room):
  for ws in rooms[room]['clients']:
    await sendTimeToClient(ws, room)

async def sendScoreToClients(room):
  for ws in rooms[room]['clients']:
    await sendScoreToClient(ws, room)

async def sendTimeToClient(ws, room):
  try:
    shotclock = rooms[room]['shotclock']
    game = rooms[room]['gameTime']
    await ws.send('t;' + str(game) + ';' + str(shotclock))
    await sendPenaltiesToClient(ws, room)
  except:
    disconnected(ws, room)

async def sendPenaltiesToClient(ws, room):
  try:
    penalties = rooms[room]['penalties']
    if len(penalties) > 0:
      msg = 'p'
      # Wenn min. einer drin ist, der nicht abläuft
      if any(p['time'] > -5 for p in penalties):
        for p in penalties:
          msg = msg + ';' + str(p['team']) + ':' + str(p['player']) + ':' + str(max(p['time'], 0))
      await ws.send(msg)
  except:
    disconnected(ws, room)

async def sendScoreToClient(ws, room):
  try:
    await ws.send('s;' + str(rooms[room]['score'][0]) + ';' + str(rooms[room]['score'][1]))
  except:
    disconnected(ws, room)

def log(msg):
  print(str(datetime.now()) + ": " + msg)

start_server = websockets.serve(time, "localhost", 5678)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()