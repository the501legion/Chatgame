#!/usr/bin/python
# -*- coding: utf-8 -*-

import httplib2
import os
import sys
import re
import string
import dateutil.parser
import threading
import random
import urllib2
import requests
import urllib
import json
import sys
import base64
import hashlib
import MySQLdb

from thread import *
from apiclient.discovery import build
from apiclient.errors import HttpError
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow

import time
from datetime import datetime
from pytz import timezone
from datetime import datetime, timedelta
from requests.auth import HTTPDigestAuth

encoding = "utf-8" 

CLIENT_SECRETS_FILE = "client_secret.json"

YOUTUBE_READ_WRITE_SCOPE = "https://www.googleapis.com/auth/youtube"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

MISSING_CLIENT_SECRETS_MESSAGE = """
WARNING: Please configure OAuth 2.0

To make this sample run you will need to populate the client_secrets.json file
found at:

   %s

with information from the Developers Console
https://console.developers.google.com/

For more information about the client_secrets.json file format, please visit:
https://developers.google.com/api-client-library/python/guide/aaa_client_secrets
""" % os.path.abspath(os.path.join(os.path.dirname(__file__),
                                   CLIENT_SECRETS_FILE))

VALID_BROADCAST_STATUSES = ("all", "active", "completed", "upcoming",)

LAST_MSG = 0
FIRST = 0
FIRST_MSGS = 0
COOLDOWN = 1
NEXTMSG = 0
CHAT_ID = ""
READING = 0
ID_LIST = []

def get_authenticated_service(args):
  flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE,
    scope=YOUTUBE_READ_WRITE_SCOPE,
    message=MISSING_CLIENT_SECRETS_MESSAGE)

  storage = Storage("%s-oauth2.json" % sys.argv[0])
  credentials = storage.get()

  if credentials is None or credentials.invalid:
    credentials = run_flow(flow, storage, args)

  return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
    http=credentials.authorize(httplib2.Http()))

def get_messages(youtube, pagetoken = ""):
  global LAST_MSG
  global FIRST
  global FIRST_MSGS
  global COOLDOWN
  global NEXTMSG
  global CHAT_ID
  global READING
  global ID_LIST

  maxRes = 0
  if FIRST == 0:
    maxRes = 200
  else:
    maxRes = 2000
  
  if pagetoken != "":
    message_request = youtube.liveChatMessages().list(
      liveChatId=CHAT_ID,
      part="id,snippet,authorDetails",
      pageToken=pagetoken,
      maxResults=maxRes
    )
  else:
    message_request = youtube.liveChatMessages().list(
      liveChatId=CHAT_ID,
      part="id,snippet,authorDetails",
      maxResults=maxRes
    )

  try:
    message_response = message_request.execute()
  except Exception as e:
    print e
    get_messages(youtube, pagetoken)
    return

  try:
    totalResults = message_response["pageInfo"]["totalResults"]
    resultsPerPage = message_response["pageInfo"]["resultsPerPage"]
    if totalResults == 0:
        print "Finished"
        READING = 1
        return
  except Exception as e:
      print e
      get_messages(youtube)
      return

  time.localtime()


  if FIRST == 0:
    message_response.get("items", [])[0]

    date = dateutil.parser.parse(message_response.get("items", [])[0]["snippet"]["publishedAt"].encode('utf_8'))
    timeString = str(date)
    timeString = timeString.split('.')[0]
    timeString = timeString.split('+')[0]
    unix = time.mktime(datetime.strptime(timeString, "%Y-%m-%d %H:%M:%S").timetuple())

  for message in message_response.get("items", []):
    chatID = message["id"]

    if chatID in ID_LIST:
      continue
    ID_LIST.append(chatID)

    msgType = message["snippet"]["type"]
    publishedTime = message["snippet"]["publishedAt"].encode('utf_8')

    # Zeit in Unix Timestamp umwandeln
    date = dateutil.parser.parse(publishedTime)
    timeString = str(date)
    timeString = timeString.split('.')[0]
    timeString = timeString.split('+')[0]
    unix = time.mktime(datetime.strptime(timeString, "%Y-%m-%d %H:%M:%S").timetuple())
    
    # Zeit in lesbares Format umwandeln
    date = date + timedelta(hours=2)
    day = '%s' % date.strftime('%Y-%m-%d')
    month = '%s' % date.strftime('%Y-%m')
    date = str(date)
    date = date.split('.')[0]

    if LAST_MSG >= unix and FIRST == 0:
      continue
    LAST_MSG = unix

    name = message["authorDetails"]["displayName"].encode('utf_8')
    user = message["snippet"]["authorChannelId"].encode('utf_8')
    msg = message["snippet"]["displayMessage"].encode('utf_8')
    channel = message["authorDetails"]["channelUrl"].encode('utf_8')
    isVerified = message["authorDetails"]["isVerified"]
    isChatOwner = message["authorDetails"]["isChatOwner"]
    isChatSponsor = message["authorDetails"]["isChatSponsor"]
    isChatModerator = message["authorDetails"]["isChatModerator"]

    if msgType == 'tombstone':
      continue
    
    oldName = name
    name = string.replace(name, '/', '&#47;')

    if len(msg) > 2 and FIRST_MSGS == 1:
      if user == "UCMGaBiEGSEre_nvgZsq3qJw":
        continue

      live = isLive(yesterday="")
      if live == 0:
        postFunction(youtube, "Die aktuelle Show ist eine Wiederholung!")
      elif live == 1:
        postFunction(youtube, "Die aktuelle Show ist live!")
      elif live == 2:
        postFunction(youtube, "Die aktuelle Show ist eine Premiere!")
      elif live == 3:
        postFunction(youtube, "Error!")

      now = time.mktime(datetime.now().timetuple())

      #command
      if msg[0] == "?" and (now - COOLDOWN > 5):
        COOLDOWN = now
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
              result = cur.fetchone()[0]
              result = result.replace("%name%", name)
              postFunction(youtube, result)
        except Exception as e:
          print e

  FIRST_MSGS = 1
  FIRST = 1
  NEXTMSG = time.time() + message_response["pollingIntervalMillis"] / 1000

  sleep = message_response["pollingIntervalMillis"] / 1000
  print "Sleep %d sec" % (sleep)
  time.sleep(sleep)

  if message_response["nextPageToken"] == "":
    get_messages(youtube, "")
    return
  else:
    get_messages(youtube, message_response["nextPageToken"])
    return

def postFunction(youtube, msg):
  global CHAT_ID

  try:
    sendeplan_response = youtube.liveChatMessages().insert(
      part="snippet",
      body=dict(
        snippet=dict(
          liveChatId=CHAT_ID,
          type="textMessageEvent",
          textMessageDetails=dict(
            messageText=msg
          )
        ),
      )
    ).execute()
  except Exception as e:
    print e

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
      print "Skip"
      continue
    
    if "live" in group['type']:
      print "Live"
      live = 1
    elif "premiere" in group['type']:
      print "Premiere"
      live = 2
    else:
      print "Wiederholung"
      live = 0
    break
  return live

def main():
  global READING
  global LAST_MSG
  global CHAT_ID

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
    cur.execute("UPDATE settings SET youtubeChatID = %s", (CHAN,))
  else:
    cur.execute("SELECT youtubeChatID FROM settings")
    CHAT_ID = cur.fetchone()[0]


  reload(sys)
  sys.setdefaultencoding('utf8')
  args = argparser.parse_args()
  youtube = get_authenticated_service(args)

  LAST_MSG = time.time() - 3600

  get_messages(youtube)

  while (True):
    timestamp = time.time()
    next_timestamp = timestamp + 1
    time.sleep(next_timestamp - timestamp)
    timestamp = next_timestamp

    if READING == 1:
      READING = 0
      get_messages(youtube)

if __name__ == "__main__":
  main()
