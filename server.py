import uuid
import cPickle as pickle
import os.path
import time

# Tornado -- Web server/framework
import tornado.ioloop
import tornado.web
# MQ -- Message Queue system
from stormed import Connection, Message
# Greenlet -- Coroutine library, essentially.
from greenlet import greenlet

from comet import CometHandler
from mqview import MQView

from game.game import Game
from game.model import Player

class MainHandler(tornado.web.RequestHandler):
  """
  Shows the front page, allowing starting/joining of games.
  """
  def get(self):
    self.render('index.html')

class GameLobby(object):
  """
  Manages the game lobby, organising all games that are waiting for participants. 
  Registers itself as a lobby manager with the MQ, offers anybody interested a 
  list of all the games currently waiting for participants. There may be multiple
  of these, for scalability, but all of them should recieve every game state change,
  and only one of them should be asked about any single game search.
  """

  def __init__(self):
    self.gameStates = {}  
  
    # Wait for messages from the MQ, create players accordingly.
    mq = Connection(host='localhost')
    mq.connect(self.onMQConnect)
    
  def onMQConnect(self):
    self.ch = mq.channel()
    ch.exchange_declare(exchange = 'lobby', type = 'fanout')
    result = ch.queue_declare(exclusive=True, callback=self.onQueueReady)
                  
  def onQueueReady(self, queueInfo):
    ch.queue_bind(exchange = 'lobby', 
                  queue = queueInfo.queue)
    ch.consume(queueInfo.queue, self.onMessage, no_ack=True)
    
  def onMessage(self, msg):
    pass

class PrestartGame:
  def __init__(self, gameId):
    self.gameId = gameId
    self.started = False
    self.gameState = GameState(self.gameId)
    self.players = [None, None, None, None]
  
  def waitForPlayers(self):
    """ 
    Starts running the setup for this game, waiting for join messages,
    and eventually launching the game proper once enough players have
    been 'collected'.
    """    
    # Start listening for people trying to join.
    def onMQConnect():
      def onMessage(msg):
        data = pickle.loads(msg.body)
        print data

        if data['type'] == 'join' and not self.started:
          self.join(data['name'], data['id'])

        elif data['type'] == 'quit':
          self.quit(data['id'])

        else:
          print "Unknown message type %s!" % data['type']

      ch = mq.channel()
      ch.queue_declare(self.gameId)

      # Clear any old messages.
      ch.queue_purge(self.gameId)
      ch.consume(self.gameId, onMessage, no_ack=True)

    # Wait for messages from the MQ, create players accordingly.
    mq = Connection(host='localhost')
    mq.connect(onMQConnect)          
    
  def join(self, name, playerId):      
    if self.started:
      raise Exception("Player joining game %s, but its already started!" % self.gameId)
      
    # Work out who else is in the game, so we can tell this new guy.
    otherPlayers = [(p.seat, p.name) for p in self.players if p is not None]
    
    # Find the new guy a seat.
    for i, p in enumerate(self.players):
      if p is None:
        newPlayer = Player(name, i, MQView(playerId, i, otherPlayers))
        
        for p2 in self.players:
          if p2 != None:
            p2.view.playerJoined(name, i)
            
        self.players[i] = newPlayer
        
        if all(p != None for p in self.players):
          self.start()
          
        return
    
    # We couldn't find a seat, should never happen.
    raise Exception("Too many players joining game %s!" % self.gameId)
      
  def quit(self, seat):
    self.players[seat] = None

  def start(self):
    # TODO Tell the lobby we're done.
    self.started = True
    game = Game(self.players)
    greenlet(game.run).switch()

class GameState:
  def __init__(self, gameId):
    self.gameId = gameId
    self.playerNum = 0
    self.stateId = 0

class HostHandler(tornado.web.RequestHandler):
  """
  Shows the game set up page, for the game 'host'.
  """

  @tornado.web.asynchronous
  def get(self, gameId):
    self.host(gameId)

  @tornado.web.asynchronous
  def post(self):
    self.host()

  def host(self, gameId = None):
    if not gameId:
      gameId = uuid.uuid1().int
    self.render('game.html', gameId = gameId)
    self.game = PrestartGame(gameId)
    self.game.waitForPlayers()

class JoinHandler(tornado.web.RequestHandler):
  """
  Shows the game joining page, for game clients.
  """

  def get(self, gameId):
    self.join(gameId)

  def post(self):
    self.join(self.get_argument('gameId'))

  def join(self, gameId):
    self.render("game.html", gameId = gameId)

application = tornado.web.Application(
  handlers = [
    (r"/", MainHandler),
    (r"/host", HostHandler),
    (r"/host/([0-9]+)", HostHandler),
    (r"/join", JoinHandler),
    (r"/join/([0-9]+)", JoinHandler),
    (r"/request", CometHandler),
  ],
  template_path="/home/tim/documents/programming/python/spaodes/templates",
  static_path="./static",
  debug=True
)

if __name__ == "__main__":
  application.listen(8888)
  tornado.ioloop.IOLoop.instance().start()
