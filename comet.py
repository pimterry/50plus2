from threading import Semaphore
import uuid
import sys
import cPickle as pickle
import json

import tornado.web
from stormed import Connection, Message
from stormed.channel import Consumer

from game.model import *

class CometHandler(tornado.web.RequestHandler):
  """
  Handles communication between MQView and the Javascript side, acting as the server end of the
  long-polling AJAX connection.
  """
  
  @tornado.web.asynchronous
  def post(self):
    self._handler(self.get_argument('gameId'), 
                  self.get_argument('userId'),
                  self.get_argument('alreadyJoined', False),
                  json.loads(self.get_argument('messages', "[]")))

  def _handler(self, gameId, userId, alreadyJoined = False, messagesToSend=[]):
    self.cancelled = False
    self.gameId = gameId
    self.userId = userId
    self.alreadyJoined = alreadyJoined
    self.messagesToSend = messagesToSend
    
    self.mqConn = Connection(host='localhost')
    self.mqConn.connect(self._onConnect)
    
  def _onConnect(self):
    self.mq = self.mqConn.channel()  
  
    if not self.alreadyJoined:
      joinMessage = Message(pickle.dumps(
        { 
          'type' : 'join',
          'id' : self.userId,
          'name' : 'Tim'
        }
      ))
      self.mq.queue_declare(self.gameId)
      self.mq.publish(joinMessage, exchange = '', routing_key = self.gameId)
    
    self.outQueue = "from-%s" % self.userId
    self.inQueue = "to-%s" % self.userId    
    self.mq.queue_declare(self.inQueue)
    self.mq.queue_declare(self.outQueue)    
    
    self.mq.consume(self.inQueue, self._onRecv)
    
    for message in self.messagesToSend:
      self._send(message)   
    
  def _send(self, msg):  
    print "Message from comet: %s" % str(msg)
  
    if 'bid' in msg:
      msg['bid'] = Bid(msg['bid'])
      
    if 'card' in msg:
      msg['card'] = Card(msg['card']['suit'], msg['card']['value'])
      
    self.mq.publish(Message(pickle.dumps(msg)), exchange = '', routing_key=self.outQueue)    
    
  def on_connection_close(self):
    self.stopConsuming()
    
  def _onRecv(self, msg):
    print "Message ready for player %s: %s" % (self.userId, pickle.loads(msg.body))
  
    if self.cancelled:
      print "* Cancelled comet got message! (%s)" % self.userId
      msg.reject()
      return
           
    data = pickle.loads(msg.body)
    ackRequired = True
    
    if 'async' in data:
      if data['async'] == True:
        ackRequired = False
      del data['async']            
    
    # Turns hands (lists of Card objects) into dictionaries of the cards values
    # Suits are in alphabetical order (0 clubs, 1 diamonds etc), values in 
    # standard order, aces high, all 0 indexed.
    if 'hand' in data:
      data['hand'] = map(lambda c : {'suit' : c.suit, 
                                     'value' : c.value}, data['hand'])
      
    # Turn bids (lists of Bid objects) into lists of numbers, with
    # 0 as nil and -1 as double nil.
    elif 'bid' in data:
      bid = str(data['bid'].value)
      data['bid'] = bid if bid != '-1' else '00'
      
    # Turn individual cards into key'd maps.
    elif 'card' in data:
      data['card'] = {'suit' : data['card'].suit, 
                      'value' : data['card'].value }
      
    # If the connection got dropped, we leave this, and we give it back to the MQ, so we 
    # can resend it out next time.
    if self.request.connection.stream.closed():
      print "* Comet was closed whilst passing on message"
      msg.reject() # Marks the message as not sent.
      return      
    
    self.write(json.dumps(data))
    self.finish()
    
    msg.ack()
    if ackRequired:
      self._send({'ack' : True})
    self.stopConsuming()    

  def stopConsuming(self):
    self.cancelled = True
    self.mqConn.close()

    
