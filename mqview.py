from threading import Lock
import cPickle as pickle
from greenlet import greenlet

from game.model.cards import *
from game.model.game_state import Bid  

from stormed import Connection, Message

class MQView:
  """
  A view for the game that lets it communicate with the comet clients, via RabbitMQ. Pretends to be
  a normal blocking interface for this purpose, acts completely synchronous.
  """
  
  def __init__(self, playerId, position, otherPlayers):
    print "MQView for player %s built" % playerId
    self.msgLock = Lock()
    self.waitlet = None
    self.waitingForAck = False
    self.blockingForAck = False
    self.messages = []
    
    self.seenHand = False
    
    self.inQueue = "from-%s" % playerId
    self.outQueue = "to-%s" % playerId
    self.position = position    
    self.otherPlayers = list(otherPlayers)
    
    self.mq = None
    self.mqConn = Connection(host='localhost')
    self.mqConn.connect(self._onConnect)
    self._send({ 
      'type' : 'playerList',
      'players' : map(lambda (position, name) : {
                         'name' : name, 
                         'position' : self._getRelPosition(position)
                       }, self.otherPlayers)
    })
    
  def _getRelPosition(self, position):
    return (position - self.position) % 4
    
  def playerJoined(self, name, position):
    self._send({'type' : 'joined', 
               'name' : name, 
               'position' : self._getRelPosition(position)})
               
  def startRound(self, leadPosition):
    self._send({'type' : 'startGame', 
               'leadPosition' : self._getRelPosition(leadPosition)})  
    
  def _onConnect(self):
    print "MQView connected to MQ"
    self.msgLock.acquire()
    self.mq = self.mqConn.channel()
    self.mq.queue_declare(queue = self.inQueue)
    self.mq.queue_declare(queue = self.outQueue)    
    self.mq.consume(self.inQueue, self._onRecv, no_ack=True)
    
    # If the game thread is waiting to use this MQ connection, yield back to it
    if self.waitlet:      
      self.msgLock.release()
      self.waitlet.switch()
    else:
      self.msgLock.release()
    
  def _onRecv(self, msg):
    msg = pickle.loads(msg.body)
    print "MQ %s received message: %s" % (self.position, str(msg))
    
    self.msgLock.acquire()
    # We handle acks ourselves, unblocking the send process.
    if 'ack' in msg and msg['ack'] is True:
      assert self.waitingForAck
      self.waitingForAck = False
      self.msgLock.release()      
      if self.blockingForAck:
        self.waitlet.switch()
    
    # Async messages are those that the game won't have blocked for, such as
    # sending chat messages, exiting, or otherwise making requests of the server.
    elif 'async' in msg and msg['async'] is True:
      self.msgLock.release()
      if msg['type'] == 'quit':
        pass
      elif msg['type'] == 'hand':
        self.sendHand(async=True)
    
    # All other messages get passed onward (probably to a waiting _recv call)
    else:
      if self.waitlet:
        self.msgLock.release()
        self.waitlet.switch(msg)        
      else:
        self.messages.append(msg)
        self.msgLock.release()      
        
  def ensureConnectedToMQ(self):
    """
    Checks the an MQ connection is available, or yields until it is. Should only be
    called from the game thread.
    """
    self.msgLock.acquire()
    if not self.mq:
      print "MQ unavailable in MQView, waiting"
      self.waitlet = greenlet.getcurrent()
      self.msgLock.release()
      # Yield until MQ is ready.
      self.waitlet.parent.switch()
      self.waitlet = None
    else:
      self.msgLock.release()
    
  def _recv(self):
    """
    Blocking recieve call. Waits until something is available on the message
    queue, and returns it. If nothing is available now, it yields execution at
    this point as a greenlet (self.waitlet), only continuing when a message arrives.
    Must be called from the game thread itself.
    """
    print "MQ %s getting message" % self.position
    self.ensureConnectedToMQ()
    
    self.msgLock.acquire()
    if len(self.messages) > 0:
      print "Message available, grabbing"
      self.msgLock.release()
      message = self.messages.pop(0)
      
    else:
      print "No message available, waiting"
      self.waitlet = greenlet.getcurrent()
      self.msgLock.release()
      # Wait until another event comes back to here, with the message we're waiting for.
      message = self.waitlet.parent.switch()
      self.waitlet = None
    
    print "MQ %s got message %s" % (self.position, str(message))
    return message
            
  def _send(self, msg, async=False):
    """
    Sends a message to the client. If there is an outstanding un-ack'd message, blocks
    until it has been ack'd. Must be called from the game thread itself.    
    """
    print "%s sending %s%s" % (self.position, msg, " (async)" if async else "")
    
    # Async means ignoring the proper synchronous play of normal games, so we don't want
    # to interrupt whatever continuations (greenlets) are about, and we just want to
    # try and push, ignoring failures or acks of whatever.
    if async:
      try:
        msg['async'] = True
        self.mq.publish(Message(pickle.dumps(msg)), exchange = '', routing_key=self.outQueue)
      except Exception, e:
        print "* Exception on async message push: %s" % (e, )
      return
      
    self.ensureConnectedToMQ()    
    self.msgLock.acquire()
   
    # We refuse to send the next message until we've heard back that the previous message
    # reached the client a-ok.
    if self.waitingForAck:
      print "%s tried to send %s, but still waiting for ack" % (self.position, msg)    
      self.waitlet = greenlet.getcurrent()
      self.blockingForAck = True
      self.msgLock.release()
      self.waitlet.parent.switch()
      print "%s got their ack"
      self.blockingForAck = False
      self.msgLock.acquire()      
      self.waitlet = None
      
    self.mq.publish(Message(pickle.dumps(msg)), exchange = '', routing_key=self.outQueue)
    self.waitingForAck = True
    print "%s waiting for ack" % (self.position)
    self.msgLock.release()
    
  def setIds(self, playerId, partnerId):
    self.playerId = playerId
    
  def setHand(self, hand):
    self.hand = hand
    self.seenHand = False

  def goDoubleNil(self):
    if self.seenHand:
      return False
      
    else:
      print "MQ sending 00 question"
      self._send({'type' : 'question', 'question' : 'bid00?'})
      result = self._recv()['00']
      if result is True and self.seenHand:
        print "* Attempt to bid 00 after having looked at their hand!"
        return False
        
      return result
      
  def showHand(self):
    if not self.seenHand:
      self.sendHand()
    
  def bidSomethingSensible(self):
    print "MQ sending sensible bid question (question)"
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
    
  def gameOver(self):
    self._send({'type' : 'gameOver'})
    self.mq.queue_delete(self.inQueue)
    self.mq.queue_delete(self.outQueue)
    self.mqConn.close()
