import uuid, sys, json, time
import cPickle as pickle

import tornado.web
import tornado.ioloop
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
    
    self._pingTimeout = None
    
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
      
    # We need the MQView to know that we're connected, either by us pinging it
    # or by us sending actual relevant messages:
    if len(self.messagesToSend) > 0:    
      for message in self.messagesToSend:
        self._send(message)
        
      # If we're still here in 14 seconds, make sure the MQView knows that we 
      # haven't disconnected.
      self._pingTimeout = tornado.ioloop.IOLoop.instance().add_timeout(time.time() + 14, 
                                                                       self._ping)
    
    # If we don't have any messages to send, just starting pinging instead (sooner, since
    # we don't know when the last message was)
    else:
      self._pingTimeout = tornado.ioloop.IOLoop.instance().add_timeout(time.time() + 5, 
                                                                       self._ping)
    
  def _send(self, msg):      
    # These messages are not going to be expected, and the MQView needs
    # do deal with them now.
    if 'type' in msg and (msg['type'] == 'quit' or msg['type'] == 'hand'):
      msg['async'] = True
  
    if 'bid' in msg:
      msg['bid'] = Bid(msg['bid'])
      
    if 'card' in msg:
      msg['card'] = Card(msg['card']['suit'], msg['card']['value'])
      
    self.mq.publish(Message(pickle.dumps(msg)), exchange = '', routing_key=self.outQueue)
    
  def _ping(self):
    self._pingTimeout = None
    
    if not self.request.connection.stream.closed() and not self.cancelled:
      self._send({'type' : 'ping'})
      self._pingTimeout = tornado.ioloop.IOLoop.instance().add_timeout(time.time() + 14, 
                                                                       self._ping)   
    
  def on_connection_close(self):
    self.stopConsuming()
    
  def _onRecv(self, msg):  
    if self.cancelled:
      # Don't print this, it happens quite a lot, not an issue unless we start getting
      # messages out of order again (should be fixed by our 'ack' messages.
      #   print "* Cancelled comet got message! (%s)" % self.userId
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
    if self._pingTimeout:
      tornado.ioloop.IOLoop.instance().remove_timeout(self._pingTimeout)

    
