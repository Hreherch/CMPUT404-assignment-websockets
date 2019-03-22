#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
import os

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()
        
    def add_socket_listener(self, listener):
        self.listeners.append( listener )

    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners( entity )

    def set(self, entity, data):
        self.space[entity] = data
        self.tell_socket_listeners_about( entity )

    def clean_sockets(self):
        open_sockets = list()
        for listener in self.listeners:
            if not listener.closed:
                open_sockets.append(listener)
        self.listeners = open_sockets

    def tell_socket_listeners_about(self, entity):
        '''update the set of listeners'''
        entMsg = {}
        entMsg[entity] = self.get(entity)
        entMsg = json.dumps(entMsg)
        self.clean_sockets()
        for listener in self.listeners:
            listener.send(entMsg)

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity,dict())
    
    def world(self):
        return self.space

myWorld = World()
        
@app.route('/')
def hello():
    '''Return something coherent here.. perhaps redirect to /static/index.html '''
    resp = flask.Response(status=302)
    resp.headers["location"] = "/static/index.html"
    return resp

def read_ws(ws,client=None):
    '''A greenlet function that reads from the websocket and updates the world'''
    while not ws.closed:
        data = ws.receive()
        if not data: continue
        data = json.loads(data)
        #print("read_ws", data)
        for entity in data: # hopefully
            myWorld.set(entity, data[entity])
    return None

@sockets.route('/subscribe')
def subscribe_socket(ws):
    '''Fufill the websocket URL of /subscribe, every update notify the
       websocket and read updates from the websocket '''
    myWorld.add_socket_listener(ws)
    ws.send(json.dumps(myWorld.world()))
    read_ws(ws) # start reading the websocket
    return None


# I give this to you, this is how you get the raw body/data portion of a post in flask
# this should come with flask but whatever, it's not my project.
def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data.decode("utf8") != u''):
        return json.loads(request.data.decode("utf8"))
    else:
        return json.loads(request.form.keys()[0])

@app.route("/entity/<entity>", methods=['POST','PUT'])
def update(entity):
    '''update the entities via this interface'''
    body = flask_post_json()
    myWorld.set(entity,body)
    return get_entity(entity)

@app.route("/world", methods=['POST','GET'])    
def world():
    '''you should probably return the world here'''
    world = myWorld.world()
    body = json.dumps(world)
    resp = flask.Response(response=body, status=200, content_type="application/json")
    return resp

@app.route("/entity/<entity>")    
def get_entity(entity):
    '''This is the GET version of the entity interface, return a representation of the entity'''
    entity = myWorld.get(entity)
    body = json.dumps(entity)
    resp = flask.Response(response=body, status=200, content_type="application/json")
    return resp

@app.route("/clear", methods=['POST','GET'])
def clear():
    '''Clear the world out!'''
    myWorld.clear()
    return world()

if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
