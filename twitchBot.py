#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import MySQLdb
import irc.bot
import requests
from thread import *
import time
from datetime import datetime
import urllib2
import json
import dateutil.parser
import config
import csv

HOST = "irc.twitch.tv"              # the Twitch IRC server
PORT = 6667                         # always use port 6667!
NICK = config.TWITCH_NICK           # your Twitch username, lowercase
PASS = config.TWITCH_PASS           # your Twitch OAuth token
CHAN = ""                           # = loaded from db
CLIENT_ID = config.TWITCH_CLIENT
STARTED = True
MSG_LIST = []
MSG_AMOUNT = 0
COOLDOWN = 0

#https://github.com/twitchdev/chat-samples/blob/master/python/chatbot.py
class TwitchBot(irc.bot.SingleServerIRCBot):
  def __init__(self, username, client_id, token, channel):
    self.client_id = client_id
    self.token = token
    self.channel = '#' + channel

    # Get the channel id, we will need this for v5 API calls
    url = 'https://api.twitch.tv/kraken/users?login=' + channel
    headers = {'Client-ID': client_id, 'Accept': 'application/vnd.twitchtv.v5+json'}
    r = requests.get(url, headers=headers).json()
    self.channel_id = r['users'][0]['_id']

    # Create IRC bot connection
    server = 'irc.chat.twitch.tv'
    port = 6667
    print 'Connecting to ' + server + ' on port ' + str(port) + '...'
    irc.bot.SingleServerIRCBot.__init__(self, [(server, port, 'oauth:'+token)], username, username)
      

  def on_welcome(self, c, e):
    print 'Joining ' + self.channel
    c.cap('REQ', ':twitch.tv/membership')
    c.cap('REQ', ':twitch.tv/tags')
    c.cap('REQ', ':twitch.tv/commands')
    c.join(self.channel)

  def on_pubmsg(self, c, e):
    global MSG_LIST
    global MSG_AMOUNT
    global COOLDOWN

    msgID = " "
    username = "Anonymous"
    msg = "Clear message"
    timestamp = time.time() + 18000
    date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    moderator = False
    broadcaster = False
    subscriber = False
    partner = False
    emotes = ""

    print "_______________________"
    print e
    print "-------------"

    msg = e.arguments[0]
    oldMsg = msg

    for tag in e.tags:
      if tag['key'] == "badges":
        if tag['value'] != None:
          if "subscriber" in tag['value']:
            subscriber = True
          if "moderator" in tag['value']:
            moderator = True

      if tag['key'] == "display-name":
        username = tag['value']

      if tag['key'] == "id":
        msgID = tag['value']

      if tag['key'] == "emotes":
        if tag['value'] != None:
          emotes = tag['value']
          emotes = emotes.split("/")
          toAdd = 0

          for emote in emotes:
            emoteID = emote.split(":")[0]
            pos = emote.split(":")[1]
            poses = pos.split(",")

            for p in poses:
              posBegin = int(p.split("-")[0]) + toAdd
              posEnd = int(p.split("-")[1]) + toAdd + 1

              subStr = "<img src='http://static-cdn.jtvnw.net/emoticons/v1/%s/1.0' width='22'>" % (emoteID)
              msg = msg.replace(msg[posBegin:posEnd], subStr, 1)
              toAdd = toAdd + len(subStr) - (posEnd - posBegin)

    emotes = ""
    message = "msg///0///%s///%s///%s///%s///%s///%s///%s///%s///%s///%s" % (msgID, username, username, msg, date, moderator, broadcaster, subscriber, partner, emotes)
    MSG_LIST.append(message)
    MSG_AMOUNT = MSG_AMOUNT + 1

    live = isLive(yesterday="")
    if live == 0:
      c.privmsg(self.channel, "Die aktuelle Show ist eine Wiederholung!")
    elif live == 1:
      c.privmsg(self.channel, "Die aktuelle Show ist live!")
    elif live == 2:
      c.privmsg(self.channel, "Die aktuelle Show ist eine Premiere!")
    elif live == 3:
      c.privmsg(self.channel, "Error!")
    else:
      c.privmsg(self.channel, "Error 2!")

    now = time.mktime(datetime.now().timetuple())
    delta = now - COOLDOWN
    c.privmsg(self.channel, "Abstand zwischen den letzten Befehlen: %d Sekunden" % delta)
      
    #command
    if msg[0] == "?" and (delta > 5):
      COOLDOWN = now
      c.privmsg(self.channel, "Befehl registriert")
      try:
        db = MySQLdb.connect(host=config.DB_HOST,
                        user=config.DB_USER,
                        charset='utf8',
                        use_unicode=True,
                        passwd=config.DB_PASSWD,
                        db=config.DB_DB)
        cur = db.cursor()
        db.autocommit(True)
        print(msg.lower()[1:])

        if "regieuhr " in msg.lower()[1:]:
          if "regieuhr <Std:Min>" == msg.lower()[1:]:
            return

          if "regieuhr Budikopf" not in msg.lower()[1:]:
            clock = msg.lower().split( )[1]
            current = datetime.now()
            hour = current.hour + 1
            if hour > 24:
              hour = 1
            minute = current.minute

            if hour < 10:
              hour = "0%d" % (hour)
            if minute < 10:
              minute = "0%d" % (minute)

            if clock == (hour + ":" + minute):
              msg = "?Regieuhr <std:min> (aktuelle uhrzeit)"

        #cur.execute("SELECT result FROM cmd_brighton WHERE cmd = %s", (msg.lower()[1:],))
        cur.execute("SELECT result FROM cmd_hq WHERE cmd = %s", (msg.lower()[1:],))
        count = cur.rowcount
              
        if count > 0:
            c.privmsg(self.channel, "Antwort gefunden")
            result = cur.fetchone()[0]
            result = result.replace("%name%", username)

            c.privmsg(self.channel, result)
            return
      except Exception as e:
        print e
    return

def twitchBot():
  global CHAN
  global NICK
  global CLIENT_ID
  global PASS

  bot = TwitchBot(NICK, CLIENT_ID, PASS, CHAN)
  bot.start()

def isLive(yesterday = ""):
  live = -1
  now = datetime.now()
  url = "https://api.rocketbeans.tv/v1/schedule/normalized?startDay=%d" % (time.mktime(now.timetuple()))
  if yesterday != "":
    url = yesterday
  hdr = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
       'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
       'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
       'Accept-Encoding': 'none',
       'Accept-Language': 'en-US,en;q=0.8',
       'Connection': 'keep-alive'}
  req = urllib2.Request(url, headers=hdr)
  response = urllib2.urlopen(req)
  data = json.loads(response.read())

  results = 0

  for group in data['data'][0]['elements']:
    timeEnd = dateutil.parser.parse(group['timeEnd'])

    delta = time.mktime(timeEnd.timetuple()) - time.mktime(now.timetuple())

    if delta < 0:
      continue

    
    if "live" in group['type']:
      #print "Live"
      live = 1
    elif "premiere" in group['type']:
      #print "Premiere"
      live = 2
    else:
      #print "Wiederholung"
      live = 0
    break
  return live

def readFile(path):
  file = open(path)
  data = csv.reader(file, delimiter="\t")

  db = MySQLdb.connect(host=config.DB_HOST,
                  user=config.DB_USER,
                  charset='utf8',
                  use_unicode=True,
                  passwd=config.DB_PASSWD,
                  db=config.DB_DB)
  cur = db.cursor()
  db.autocommit(True)
      
  for row in data:
    if len(row) == 2:
      if len(row[0]) == 0:
        continue
      if row[0][0] != "?":
        continue
      print("------2-------")
      print(row[0])
      print(row[1])
      row[1] = row[1].replace('"', "\"")
      cur.execute("INSERT INTO cmd_hq (`prefix`, `cmd`, `result`) VALUES (%s, %s, %s);", ('?', row[0].lower()[1:], row[1], ))

def main():
  global CHAN
  global STARTED
  db = MySQLdb.connect(host=config.DB_HOST,
                        user=config.DB_USER,
                        charset='utf8',
                        use_unicode=True,
                        passwd=config.DB_PASSWD,
                        db=config.DB_DB)
  cur = db.cursor()
  db.autocommit(True)

  if len(sys.argv) == 2:
    CHAN = sys.argv[1]
    args = ""
    cur.execute("UPDATE settings SET twitchChannel = %s", (CHAN,))
  else:
    cur.execute("SELECT twitchChannel FROM settings")
    CHAN = cur.fetchone()[0]

  cur.close()
  del cur
  db.close()

  #readFile('hq.tsv')
  start_new_thread(twitchBot ,())
  
  
  try:
    while (STARTED):
      time.sleep(10)
  except Exception as e:
    STARTED = False

if __name__ == '__main__':
  main()
