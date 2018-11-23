import eventlet
eventlet.monkey_patch()

import os
os.environ['EVENTLET_NO_GREENDNS'] = 'yes'

from flask import Flask, request, jsonify, json
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId, Timestamp
from flask_socketio import SocketIO, send, emit


import isodate
import json
import requests
import datetime
import threading
import time


version = '0.200'

youtubeAPIKey = 'AIzaSyD7edp0KrX7oft2f-zL2uEnQFhW4Uj5OvE'
isSomeoneDJing = False

currentDJ = ''
currentVideoStartTime = None
currentVideoId = None
delayTime = 1.0
currentVideoTitle = ''

videoTimer = None

clients = []
djQueue = []
unfinishedClients = []

wooters = []
mehers = []
grabbers = []

# https://git.heroku.com/plug-dj-clone-api.git

# thebigcluster-x0vu6.mongodb.net
# mongodb+srv://walker:onesouth@thebigcluster-x0vu6.mongodb.net/test?retryWrites=true
DBURL = "mongodb+srv://walker:onesouth@thebigcluster-x0vu6.mongodb.net/test?retryWrites=true"
# DBURL = 'localhost'

app = Flask(__name__)
app.config['SECRET_KEY'] = 'onesouth'
socketio = SocketIO(app)
CORS(app)


@app.route('/getPlaylists')
def getPlaylists():
    client = MongoClient(DBURL + ":27017")
    db = client.PlugDJClone

    collection = db['playlists']

    playlist = collection.find_one({'username': request.args['username']})

    if(playlist != None):
        return JSONEncoder().encode(playlist)
    else:
        return JSONEncoder().encode([])


@app.route('/addVideoToPlaylist', methods=['POST'])
def addVideoToPlaylist():

    username = request.json['username']
    playlistTitle = request.json['playlistTitle']
    videoId = request.json['videoId']
    videoTitle = request.json['videoTitle']

    # If the user that just added a video doesn't have an entry in the playlist db, change the playlist title to default
    if(playlistTitle is ''):
        playlistTitle = 'default'

    # Connect to database and get instance of the DB
    client = MongoClient(DBURL + ":27017")
    db = client.PlugDJClone

    # Get instance of the playlist collection
    collection = db['playlists']

    newVideo = {'videoId': videoId, 'videoTitle': videoTitle}

    # print(videoTitle)

    doesUserExist = collection.find_one({'username': username})

    # If the user doesn't exist in the playlists db, make a new entry for them
    if(not doesUserExist):
        result = collection.insert_one({'username': username, 'playlists': [
                                       {'playlistTitle': playlistTitle, 'playlistVideos': []}]})

    # # Try to find a document that has the requested username
    result = collection.update_one(
        {'$and': [{'playlists.playlistTitle': playlistTitle},
                  {'username': username}]},
        {'$push': {'playlists.$.playlistVideos': newVideo}},
        upsert=True)

    return JSONEncoder().encode(result.raw_result)


@app.route('/setPlaylist', methods=['POST'])
def setPlaylist():

    playlistVideos = request.json['playlistVideos']
    playlistTitle = request.json['playlistTitle']
    username = request.json['username']

    # Connect to database and get instance of the DB
    client = MongoClient(DBURL + ":27017")
    db = client.PlugDJClone

    # Get instance of the playlist collection
    collection = db['playlists']

    # Check if user exists yet
    doesUserExist = collection.find_one({'username': username})

    # If user doesn't exist, make a new document for them
    if(not doesUserExist):
        playlist = {'playlistTitle': playlistTitle, 'playlistVideos': playlistVideos}
        result = collection.insert_one({'username': username, 'playlists': [playlist], 'currentPlaylist': playlist})
        return JSONEncoder().encode(result.acknowledged)

    else: # If user exist, just set the playlist like normal
        doesPlaylistExist = collection.find_one({'$and': [{'playlists.playlistTitle': playlistTitle}, {'username': username}]})
        # print(doesPlaylistExist)
        result = None

        if(doesPlaylistExist == None):
            newPlaylist = {'playlistTitle': playlistTitle,
                        'playlistVideos': playlistVideos}
            result = collection.update_one(
                {'username': username},
                {'$push': {'playlists': newPlaylist}})

        else:
            result = collection.update_one(
                {'$and': [{'playlists.playlistTitle': playlistTitle},{'username': username}]},
                {'$set': {'playlists.$.playlistVideos': playlistVideos}},
                upsert=True)

        return JSONEncoder().encode(result.raw_result)

    


@app.route('/deleteVideoInPlaylist', methods=['POST'])
def deleteVideoInPlaylist():

    username = request.json['username']
    playlistTitle = request.json['playlistTitle']
    videoId = request.json['videoId']
    videoTitle = request.json['videoTitle']

    # Connect to database and get instance of the DB
    client = MongoClient(DBURL + ":27017")
    db = client.PlugDJClone

    # Get instance of the playlist collection
    collection = db['playlists']

    video = {'videoId': videoId, 'videoTitle': videoTitle}

    print(videoTitle)

    # # Try to find a document that has the requested username
    result = collection.update_one(
        {'$and': [{'playlists.playlistTitle': playlistTitle},
                  {'username': username}]},
        {'$pull': {'playlists.$.playlistVideos': video}},
        upsert=False)

    return JSONEncoder().encode(result.raw_result)


@app.route('/setCurrentPlaylist', methods=['POST'])
def setCurrentPlaylist():
    playlist = request.json['newCurrentPlaylist']
    username = request.json['username']

    # print(playlist)

    # Connect to database and get instance of the DB
    client = MongoClient(DBURL + ":27017")
    db = client.PlugDJClone

    # Get instance of the playlist collection
    collection = db['playlists']

    currentPlaylist = collection.find_one({'username': username})

    if(currentPlaylist != None):
        res = collection.update_one(
            {'username': username},
            {'$set': {'currentPlaylist': playlist}})

        return JSONEncoder().encode(res.raw_result)
    else:
        return "User doesn't exist yet"

@app.route('/setAllPlaylist', methods=['POST'])
def setAllPlaylist():
    username = request.json['username']
    playlists = request.json['playlists']

    # Connect to database and get instance of the DB
    client = MongoClient(DBURL + ":27017")
    db = client.PlugDJClone

    # Get instance of the playlist collection
    collection = db['playlists']

    # Check if user exists yet
    doesUserExist = collection.find_one({'username': username})

    if(doesUserExist):
        res = collection.update_one(
            {'username': username},
            {'$set': {'playlists': playlists}})

        return JSONEncoder().encode(res.raw_result)
    else:
        return "User not in database"

@app.route('/deletePlaylistDocument', methods=['POST'])
def deletePlaylistDocument():
    username = request.json['username']

    # Connect to database and get instance of the DB
    client = MongoClient(DBURL + ":27017")
    db = client.PlugDJClone

    # Get instance of the playlist collection
    collection = db['playlists']

    res = collection.delete_one({'username': username})

    return JSONEncoder().encode(res.deleted_count)

@app.route('/login', methods=['POST'])
def login():
    username = request.json['username']
    password = request.json['password']

    if(len(username) > 32 or len(password) > 128 or 'accounts' in username or 'accounts' in password or 'playlist' in username or 'playlist' in password):
        return 'fuck you'

    # Connect to database and get instance of the DB
    client = MongoClient(DBURL + ":27017")
    db = client.PlugDJClone

    # Get instance of the playlist collection
    collection = db['accounts']

    doesUsernameExist = collection.find_one({'username': username})
    # print(JSONEncoder().encode(doesUsernameExist))

    # print("logging in...")

    # The username does not exist, make a new entry in the accounts DB
    if(doesUsernameExist == None):
        result = collection.insert_one({'username': username, 'password': password})

        # To make things easier down the line, generate a new playlists record in the db
        # generateNewPlaylistRecord(username)
        return 'success'

    else:
        if(doesUsernameExist['password'] == password):
            # print("***** Right Password ******")
            return 'success'
        else:
            # print("***** Wrong Password ******")
            return 'failure'


def generateNewPlaylistRecord(username):
    client = MongoClient(DBURL + ":27017")
    db = client.PlugDJClone

    # Get instance of the playlist collection
    collection = db['playlists']

    document = {"username":username, "playlists":[], "currentPlaylist":{"playlistTitle":"default", "playlistVideos":[]}}

    result = collection.insert_one(document)

    print("Generating new playlist record result")
    print(result)


@app.route('/getCurrentVideo', methods=['GET'])
def getCurrentVideoPlaying():
    global currentVideoStartTime
    global currentVideoId
    global currentDJ
    global currentVideoTitle

    if(currentVideoId != None):
        currentTime = time.time()
        timeElapsed = int(currentTime - currentVideoStartTime)


        videoData = {'videoId': currentVideoId, 'startTime': timeElapsed, 'currentDJ': currentDJ, 'currentVideoTitle': currentVideoTitle}
        return json.dumps(videoData)
    else:
        # No video is playing
        return 'No one playing'

@app.route('/getYoutubePlaylist', methods=['GET'])
def getYoutubePlaylist():
    playlistId = request.args['playlistId']
    playlist = createYoutubePlaylistObject(playlistId)

    return JSONEncoder().encode(playlist)

@app.route('/createPlugDJPlaylistFromYoutubePlaylist', methods=['POST'])
def createPlugDJPlaylistFromYoutubePlaylist():
    playlistId = request.json['playlistId']
    newPlaylistTitle = request.json['newPlaylistTitle']
    username = request.json['username']

    # Create playlist Object from YouTube data
    newPlaylistVideos = createYoutubePlaylistObject(playlistId)

    newPlaylist = {'playlistVideos': newPlaylistVideos, 'playlistTitle': newPlaylistTitle}

    # Connect to database and get instance of the DB
    client = MongoClient(DBURL + ":27017")
    db = client.PlugDJClone

    # Get instance of the playlist collection
    collection = db['playlists']

    doesUserExist = collection.find_one({'username': username})

    # User doesn't exist yet in the playlists collection
    if(not doesUserExist):
        result = collection.insert_one({'username': username, 'playlists': [newPlaylist], 'currentPlaylist': newPlaylist})
        return JSONEncoder().encode(result.acknowledged)
    else:
        res = collection.update_one({'username': username}, {'$push': {'playlists': newPlaylist}})
        return JSONEncoder().encode(res.raw_result)


def createYoutubePlaylistObject(playlistId):
    numOfResults = 50
    pageToken = ''
    finished = False
    playlist = []

    while(not finished):
        # Get json data for the next 50 videos in the playlist
        res = executeRequest(playlistId, numOfResults, pageToken)
        
        # If nextPageToken is not in the response, then we have received all of the videos and can now finish our requests
        if('nextPageToken' not in res):
            finished = True
        else:
            pageToken = res['nextPageToken']

        # Extract the data that we want from the response and add it to a playlist list
        for item in res['items']:
            videoId = item['snippet']['resourceId']['videoId']
            videoTitle = item['snippet']['title']

            video = {'videoTitle': videoTitle, 'videoId': videoId}
            playlist.append(video)


    return playlist
    

def executeRequest(playlistId, numOfResults, nextPageToken=''):
    url = 'https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId=' + playlistId + '&key=' + youtubeAPIKey + '&maxResults=' + str(numOfResults) + '&pageToken=' + nextPageToken
    r = requests.get(url)
    return json.loads(r.text)

@app.route('/getCurrentVersion', methods=['GET'])
def getCurrentVersion():
    global version

    return json.dumps({'version': version})

@app.route('/getCurrentVideoMetrics', methods=['GET'])
def getCurrentVideoMetrics():
    global wooters
    global mehers
    global grabbers

    return json.dumps({'wooters': wooters, 'mehers': mehers, 'grabbers': grabbers})




@socketio.on('Event_userConnected')
def handleConnection(user):
    print(user + ' is connecting')

    clients.append({'user': user, 'clientId': request.sid})

    # if someone is playing a video, the new connection must be added to the unfinished clients
    if(isSomeoneDJing):
        unfinishedClients.append({'user': user, 'clientId': request.sid})

    print("clients")
    print(clients)

    data = {'user': user, 'clients': clients}

    socketio.emit('Event_userConnecting', data, broadcast=True)


@socketio.on('Event_userDisconnected')
def handleDisconnection(user):
    global unfinishedClients
    global clients
    global djQueue

    print(user + " has disconnected")
    
    # find user in clients and remove them
    for item in clients:
        if(item['user'] == user):
            clients.remove(item)

    for item in unfinishedClients:
        if(item['user'] == user):
            unfinishedClients.remove(item)

    for item in djQueue:
        if(item == user):
            djQueue.remove(item)


    global currentDJ
    global isSomeoneDJing

    if(user == currentDJ):
        currentDJ = ''
        isSomeoneDJing = False
        stopVideo()
        determineNextVideo()

    


    print("clients")
    print(clients)

    handleChatMessage({'user': 'Server', 'message': user + ' has disconnected'})

    data = {'user': user, 'clients': clients}

    socketio.emit('Event_userDisconnecting', data, broadcast=True)



@socketio.on('Event_joinDJ')
def handleJoinDJ(data):
    print(json.dumps(data))

    global isSomeoneDJing
    global currentDJ

    user = data['user']

    djQueue.append(user)

    print(user + ' has joined the dj queue')
    print(djQueue)
    print('\n')

    if(isSomeoneDJing == False):
        nextDJ = djQueue.pop(0)
        currentDJ = nextDJ
        print('CurrentDJ in handle join dj = ' + currentDJ)
        sendNewVideoToClients(nextDJ)
        isSomeoneDJing = True


    socketio.emit('Event_DJQueueChanging', djQueue, broadcast=True)


@socketio.on('Event_sendChatMessage')
def handleChatMessage(data):
    user = data['user']
    message = data['message']

    # print(user + ' : ' + message)

    emit('Event_receiveChatMessage', {
         'user': user, 'message': message}, broadcast=True)


@socketio.on('Event_leaveDJ')
def handleLeavingDJ(data):
    
    print(json.dumps(data))

    global currentDJ
    global isSomeoneDJing
    global unfinishedClients

    user = data['user']
    print(user + " is leaving the dj queue")

    if(user == currentDJ):
        currentDJ = ''
        isSomeoneDJing = False
        unfinishedClients = []

        determineNextVideo()

    else:
        djQueue.remove(user)
        socketio.emit('Event_DJQueueChanging', djQueue, broadcast=True)


    print("DJ Queue after leaving")
    print(djQueue)
        

@socketio.on('Event_skipCurrentVideo')
def handleSkipRequest(data):
    # for now, i guess just determine the next video
    # TODO count the amount of skip requests and only skip when the majority of people want to skip

    global unfinishedClients

    unfinishedClients = []


    determineNextVideo()

@socketio.on('Event_userFinishedVideo')
def handleUserFinishingVideo(user):
    global unfinishedClients
    global clients

    print(user + ' finishing watching the video')

    for item in unfinishedClients:
        if(item['user'] == user):
            unfinishedClients.remove(item)

    clientsLength = len(clients)
    unfinishedClientsLength = len(unfinishedClients)
    numOfFinishedClients = clientsLength - unfinishedClientsLength

    print('All Clients')
    print(clients)
    print()

    print('Unfinished clients')
    print(unfinishedClients)
    print()

    finishedClientsPercentage = float(numOfFinishedClients / clientsLength)

    print('finishedClientsPercentage = ' + str(finishedClientsPercentage))

    if(finishedClientsPercentage >= .75):
        determineNextVideo()

@socketio.on('Event_Woot')
def handleUserWooting(data):
    global wooters

    if(data['wooting']):
        wooters.append(data['user'])
    else:
        wooters.remove(data['user'])

    data = {'wooters': wooters}

    socketio.emit('Event_wootChanged', data, broadcast=True)

@socketio.on('Event_Meh')
def handleUserMehing(data):
    global mehers

    if(data['mehing']):
        mehers.append(data['user'])
    else:
        mehers.remove(data['user'])

    data = {'mehers': mehers}

    socketio.emit('Event_mehChanged', data, broadcast=True)

@socketio.on('Event_Grab')
def handleUserGrabbing(data):
    global grabbers

    grabbers.append(data['user'])

    data = {'grabbers': grabbers}

    socketio.emit('Event_grabChanged', data, broadcast=True)



def sendNewVideoToClients(nextUser):
    # Get next video from next DJ
    user = None
    for item in clients:
        if(item['user'] == nextUser):
            user = item

    currentPlaylist = None

    client = MongoClient(DBURL + ":27017")
    db = client.PlugDJClone

    collection = db['playlists']

    playlist = collection.find_one({'username': nextUser})['currentPlaylist']

    if(playlist != None):
        if(len(playlist['playlistVideos']) != 0):
            nextVideo = playlist['playlistVideos'].pop(0)
        else:
            print('Next User doesn\'t have videos in their current playlist. Next User = ' + nextUser)
            determineNextVideo()
            return
    else:
        print('Next User doesn\'t exists. Next User = ' + nextUser)
        determineNextVideo()
        return


    data = {'videoId': nextVideo['videoId'], 'videoTitle': nextVideo['videoTitle'], 'username': nextUser}

    global currentVideoId
    global currentVideoTitle
    currentVideoId = data['videoId']
    currentVideoTitle = data['videoTitle']

    print('\n ****************** \n')

    print("Username = " + str(data['username']))
    print("Video Id = " + str(data['videoId']))
    print("Video Title = " + str(data['videoTitle'].encode("utf-8")))
    global currentDJ
    print("Current DJ = " + str(currentDJ))

    print('\n ****************** \n')

    
    print('emitting to clients \n')
    socketio.emit('Event_nextVideo', data, broadcast=True)

    global unfinishedClients

    # Adding all connected clients to a waiting list
    unfinishedClients.extend(clients)

    global currentVideoStartTime
    global delayTime
    global videoTimer

    duration = getVideoDuration(data['videoId'])

    print('Video Duration = ' + str(duration))
    # videoTimer = threading.Timer(duration + delayTime, determineNextVideo)
    # videoTimer.start()
    currentVideoStartTime = time.time()

    playlist['playlistVideos'].append(nextVideo)

    collection.update_one({'username': nextUser}, {'$set': {'currentPlaylist': playlist}})
    return None


def determineNextVideo():
    # print('timer done ***************')
    global currentDJ
    global currentVideoId
    global isSomeoneDJing

    global wooters
    global mehers
    global grabbers

    wooters = []
    mehers = []
    grabbers = []

    print("** Determining next video **")
    print('Current DJ in determineVideo = ' + currentDJ)

    if(currentDJ != ''):
        print("Adding " + currentDJ + " to queue")
        djQueue.append(currentDJ)

    print("Current DJ Queue")
    print(djQueue)

    if(len(djQueue) != 0):
        nextUser = djQueue.pop(0)
        currentDJ = nextUser
        isSomeoneDJing = True
        sendNewVideoToClients(nextUser)
        
        socketio.emit('Event_DJQueueChanging', djQueue, broadcast=True)
    else:
        currentVideoId = None
        print('No more DJs in queue')
        stopVideo()

def stopVideo():
    # This works but it isn't graceful
    # data = {'videoId': '', 'videoTitle': '', 'username': ''}
    # socketio.emit('Event_nextVideo', data, broadcast=True)
    print("Stopping video")
    # global videoTimer
    # if(videoTimer != None):
    #     videoTimer.cancel()
    #     videoTimer = None

    global unfinishedClients
    unfinishedClients = []
    
    socketio.emit('Event_stopVideo', broadcast=True)
    


def getVideoDuration(videoId):
    url = 'https://www.googleapis.com/youtube/v3/videos?key=' + youtubeAPIKey + '&id=' + str(videoId) + '&part=contentDetails'
    r = requests.get(url)
    res = json.loads(r.text)
    duration = res['items'][0]['contentDetails']['duration']

    duration = isodate.parse_duration(duration).total_seconds()
    return duration




class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId) or isinstance(o, Timestamp) or isinstance(o, bytes):
            return str(o)
        return json.JSONEncoder.default(self, o)


if __name__ == '__main__':
    socketio.run(app, debug=True)
