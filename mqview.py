import time
import cPickle as pickle
from greenlet import greenlet

from game.model import *

from stormed import Connection, Message
import tornado.ioloop

class MQView:
  """
  A view for the game that lets it communicate with the comet clients, via RabbitMQ.
  Pretends to be a normal blocking interface for this purpose, acts completely
  synchronous.
  """
  
  def __init__(self, playerId, position, otherPlayers, onQuit = None):
    # Acking for messages. You cannot send a message until the previous 
    # message has been ack'd (in a message, not just ack'd to the MQ). This
    # guarantees message order, which RabbitMQ does not otherwise do.
    self.waitlet = None
    self.waitingForAck = False
    self.blockingForAck = False
    self.messages = []
    self.playerId = playerId
    self.inQueue = "from-%s" % playerId
    self.outQueue = "to-%s" % playerId    
    
    # Number of messages we've recieved. Used to track whether the client has
    # stopped talking to us.
    self.msgCount = 0
    
    # Callback -- If we lose the player, call this with our position.
    self.onQuit = onQuit
    
    # If we've seen our hand we can't bid double nil. We (MQView) have to guarantee 
    # this, since we get given the hand before 00 bidding time. 
    self.seenHand = False
    
    self.position = position    
    self.otherPlayers = dict((self._getRelPosition(position), name) for (position, name) in otherPlayers)
    
    # Connect to the MQ.
    self.mq = None
    self.mqConn = Connection(host='localhost')
    self.mqConn.connect(self._onConnect)
  
  # Every single position that goes out from here should be relative to
  # the player we represent.
  def _getRelPosition(self, position):
    return (position - self.position) % 4
    
  def playerJoined(self, name, position):
    self.otherPlayers[self._getRelPosition(position)] = name
    self._send({'type' : 'joined', 
               'name' : name, 
               'position' : self._getRelPosition(position)}, async=True)
               
  def playerQuit(self, position):
    self.otherPlayers[self._getRelPosition(position)] = None  
    self._send({'type' : 'quit',
                'position' : self._getRelPosition(position)}, async=True)
               
  def startRound(self, leadPosition):
    self._send({'type' : 'startGame', 
                'leadPosition' : self._getRelPosition(leadPosition),
                'playerList' : map(lambda (position, name) : {
                         'name' : name, 
                         'position' : position
                }, self.otherPlayers.items())})  
    
  def setHand(self, hand):
    self.hand = hand
    self.seenHand = False

  def goDoubleNil(self):
    if self.seenHand:
      return False
      
    else:
      self._send({'type' : 'question', 'question' : 'bid00?'})
      result = self._recv()
      result = result['00']
      if result is True and self.seenHand:
        print "* Player attempted to bid 00 after having looked at their hand!"
        return False
        
      return result
      
  def showHand(self):
    if not self.seenHand:
      self.sendHand()
    
  def bidSomethingSensible(self):
    self._send({'type' : 'question', 'question' : 'bid?'})
    return self._recv()['bid']
    
  def sendHand(self, async=False):
    msg = {'type' : 'hand', 'hand' : self.hand}
  
    self._send(msg, async)
    self.seenHand = True
    
  def playerBid(self, position, bid):
    self._send({'type' : 'bid', 
    'position' : self._getRelPosition(position), 
    'bid' : bid})
       
  def playACard(self):
    self._send({'type' : 'question', 'question' : 'card'})
    card = self._recv()['card']
    self.hand.remove(card)
    return card
    
  def playerPlayed(self, position, card):
    self._send({'type' : 'card', 
                'position' : self._getRelPosition(position), 
                'card': card})
    
  def winnerWas(self, playerId):
    self._send({'type' : 'winner', 'winner' : self._getRelPosition(playerId)})
    
  def scores(self, scores):
    self._send({'type' : 'scores', 'scores' : 
      dict(map(lambda (ps, s) : ('you' if filter(lambda p: p.view is self, ps) 
                            else 'them', s), scores.items()))})
    
  def gameOver(self, message):
    self._send({'type' : 'gameOver', 'message' : message}, async=True)
    
    # We can't do this right now, or some of the messages might not get through
    # to the comet end in time. Wait 30 seconds. 
    tornado.ioloop.IOLoop.instance().add_timeout(time.time() + 30, self._disconnectMQ)
    
    if self._pingTimeout:
      tornado.ioloop.IOLoop.instance().remove_timeout(self._pingTimeout)
      self._pingTimeout = None
    
    # If we're blocking waiting for something, stop it, it's not coming.
    if self.waitlet:
      self.waitlet.throw()
         
  # Message Queue utility functions:
    
  def _onConnect(self):
    self.mq = self.mqConn.channel()
    self.mq.queue_declare(queue = self.inQueue)
    self.mq.queue_declare(queue = self.outQueue)        
    
    # Tell the client who else is currently in-game.
    self._send({ 
      'type' : 'playerList',
      'players' : map(lambda (position, name) : {
                         'name' : name, 
                         'position' : position
      }, self.otherPlayers.items())
    })
   
    # Start listening to the client.
    self.mq.consume(self.inQueue, self._onRecv, no_ack=True)    
    
    # The client has to respond to us within 15 seconds, or we'll be *angry*.
    self._pingTimeout = tornado.ioloop.IOLoop.instance().add_timeout(time.time() + 15, self._timeout)
    
    # If the game thread is waiting to use this MQ connection, yield back to it
    if self.waitlet:      
      self.waitlet.switch()
    
  def _onRecv(self, msg):
    msg = pickle.loads(msg.body)
    self.lastPingTime = time.time()
    
    # Cancel the previous timeout, set a new one, later.
    if self._pingTimeout:
      tornado.ioloop.IOLoop.instance().remove_timeout(self._pingTimeout)
    self._pingTimeout = tornado.ioloop.IOLoop.instance().add_timeout(time.time() + 15, self._timeout)
       
    # We handle acks ourselves, unblocking the send process.
    if 'ack' in msg and msg['ack'] is True:
      assert self.waitingForAck
      self.waitingForAck = False
      if self.blockingForAck:
        self.waitlet.switch()
        
    elif 'type' in msg and msg['type'] == 'ping':
      return        
    
    # Async messages are those that the game won't have blocked for, such as
    # sending chat messages, exiting, or otherwise making requests of the server.
    elif 'async' in msg and msg['async'] is True:
      if msg['type'] == 'quit':
        if self.onQuit:
          self.onQuit(self.position)
        
      elif msg['type'] == 'hand':
        self.sendHand(async=True)
    
    # All other messages get passed onward (probably to a waiting _recv call)
    else:
      if self.waitlet:
        self.waitlet.switch(msg)        
      else:
        self.messages.append(msg) 
        
  def _ensureConnectedToMQ(self):
    """
    Checks the an MQ connection is available, or yields until it is. Should only be
    called from the game thread.
    """
    if not self.mq:
      self.waitlet = greenlet.getcurrent()
      # Yield until MQ is ready.
      self.waitlet.parent.switch()
      self.waitlet = None
    
  def _recv(self):
    """
    Blocking recieve call. Waits until something is available on the message
    queue, and returns it. If nothing is available now, it yields execution at
    this point as a greenlet (self.waitlet), only continuing when a message arrives.
    Must be called from the game thread itself.
    """
    self._ensureConnectedToMQ()
    
    if len(self.messages) > 0:
      message = self.messages.pop(0)
      
    else:
      self.waitlet = greenlet.getcurrent()
      # Wait until another event comes back to here, with the message we're waiting for.
      message = self.waitlet.parent.switch()
      self.waitlet = None
    
    self.msgCount += 1
    return message
            
  def _send(self, msg, async=False):
    """
    Sends a message to the client. If there is an outstanding un-ack'd message, blocks
    until it has been ack'd. Must be called from the game thread itself.    
    """
    # print "%s sending %s%s" % (self.position, msg, " (async)" if async else "")
    
    # Async means ignoring the proper synchronous play of normal games, so we don't want
    # to interrupt whatever continuations (greenlets) are about, and we just want to
    # try and push, ignoring failures or acks of whatever.
    if async:
      try:
        msg['async'] = True
        self.mq.publish(Message(pickle.dumps(msg)), exchange = '', routing_key=self.outQueue)
      except Exception, e:
        raise Exception("Error sending message from MQView: "+e)
      return
      
    self._ensureConnectedToMQ()   
   
    # We refuse to send the next message until we've heard back that the previous message
    # reached the client a-ok.
    if self.waitingForAck:
      self.waitlet = greenlet.getcurrent()
      self.blockingForAck = True
      self.waitlet.parent.switch()
      self.blockingForAck = False  
      self.waitlet = None
      
    self.mq.publish(Message(pickle.dumps(msg)), exchange = '', routing_key=self.outQueue)
    self.waitingForAck = True

  def _timeout(self, timeout = 15):
    """
    This function gets endlessly scheduled and re-scheduled, as new messages come in
    and confirm that the client is definitely still connected. If it ever gets run,
    it means we haven't re-scheduled, which means we've timed out, and lost the client.
    """
    self._pingTimeout = None
    print ("* Connection to player %s timed out" % self.playerId)
    if self.onQuit:
      self.onQuit(self.position)
      
  def _disconnectMQ(self):
    if self.mqConn:
      self.mq.queue_delete(self.inQueue)
      self.mq.queue_delete(self.outQueue)
      self.mqConn.close()
      self.mqConn = None      