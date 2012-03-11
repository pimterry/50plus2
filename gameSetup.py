import uuid, os.path, functools, difflib
import cPickle as pickle

# Tornado -- Web server/framework
import tornado.ioloop
import tornado.web

# Stormed-amqp -- Message Queue system
import stormed

# Greenlet -- Coroutine library.
from greenlet import greenlet

# Rest of the web server stuff.
from mqview import MQView

# The bit that plays cards.
from game.game import Game
from game.model import Player

class GameDirectory(object):
  """
  Keeps track of all games in progress, so that the server can search them, etc. 
  Registers itself as a game directory with the MQ, provides functions so this server
  can search for games. There may be multiple of these, for scalability, but all 
  of them should recieve every game state change, and only one of them will be asked 
  about any single game search.
  
  If the directory is created with alone = false, it will attempt to get information 
  from other directories over AMQP. Until it had done so, ready() will return false. 
  Servers should not start while their directory's ready() returns false, as searches 
  for games that do exist could fail.
  
  If there are no directories up that are ready(), and a directory is started with 
  alone set, it will wait 30 seconds, and then assume that it's ready anyway.
  """

  def __init__(self, alone = True):
    self.gameStates = {}
    # Points to the same game states as self.gameStates, but indexed by name, and
    # doesn't include games which have started.
    self.searchableGames = {}
    self.alone = alone  
    
    if not alone:
      self.waitingForStates = True
      # If nobody gives us game states in the next minute, assume we're alone and there are
      # no other games out there.
      tornado.ioloop.IOLoop.instance().add_timeout(time.time() + 30, functools.partial(self.updateStates, []))
  
    # Wait for messages from the MQ, create players accordingly.
    self.mqConn = stormed.Connection(host='localhost')
    self.mqConn.connect(self.onMQConnect)
    
  def ready(self):
    return self.alone or not self.waitingForStates
    
  def find(self, search, cutoff = 0):
    """
    The important bit. Searches the registered games for games with 'similar' names to the
    search string, and returns a list of GameStates, in order of relevance.
    """
    return [self.searchableGames[match] for match in 
            difflib.get_close_matches(search, self.searchableGames.keys(), n=30, cutoff = cutoff)]
    
  def onMQConnect(self):
    self.mq = self.mqConn.channel()
    self.mq.exchange_declare(exchange = 'gameDirectory', type = 'fanout')
    result = self.mq.queue_declare(exclusive=True, callback=self.onQueueReady)
                  
  def onQueueReady(self, queueInfo):
    self.mq.queue_bind(exchange = 'gameDirectory', queue = queueInfo.queue)
    self.mq.consume(queueInfo.queue, self.onMessage, no_ack=True)
    
    # If there might be other people out there, ask them if they know anything about 
    # games already in progress.
    if not self.alone:
      self.mq.publish(Message(pickle.dumps({'type' : 'statesRequest'})), exchange = 'gameDirectory')
    
  def onMessage(self, msg):
    data = pickle.loads(msg.body)
    
    # New game initialized. 
    if data['type'] == 'newGame':
      self.addGame(data['gameId'], data['gameName'])
    
    if data['type'] == 'gameState':
      self.updateGameState(data['gameId'], data['updateId'], data['players'])
      
    if data['type'] == 'gameStarted':
      self.gameStarted(data['gameId'])      
      
    if data['type'] == 'gameOver':
      self.gameOver(data['gameId'])
      
    # Somebody wants to know what games we think are in progress.
    if data['type'] == 'statesRequest' and not self.waitingForStates:
      self.ch.publish(stormed.Message(pickle.dumps(
      {
        'type' : 'states',
        'states' : self.gameStates
      })), exchange='gameDirectory')
      
    # Unless we just asked for states list, we don't want to look at this.
    if data['type'] == 'states' and not self.waitingForStates:
      self.waitingForStates = False      
    
  def addGame(self, gameId, gameName):
    state = GameState(gameId, gameName)
    self.gameStates[gameId] = state
    self.searchableGames[gameName] = state
    
  def updateGameState(self, gameId, updateId, players):
    if (gameId in self.gameStates):
      self.gameStates[gameId].update(updateId, players)
    else:
      pass # TODO: Build partial gamestates, update later when somebody tells us the
           #       name etc of this game. Might not be necessary...
      
  def gameStarted(self, gameId):
    game = self.gameStates[gameId]
    game.started = True
    del self.searchableGames[game.gameName]
  
  def gameOver(self, gameId):
    try:
      game = self.gameStates[gameId]
      del self.gameStates[gameId]
      
      if not game.started:
        del self.searchableGames[game.gameName]
      
    except KeyError:
      pass    
      
  def updateStates(self, states):
    self.waitingForStates = False
    
    for gameState in states:      
      if gameState.gameId not in self.gameStates:
        self.gameStates[gameState.gameId] = gameState
        self.searchableGames[gameState.gameName] = gameState
        
      else:   
        assert gameState.gameName == self.gameStates[gameState.gameId].gameName        
        self.updateGameState(gameId, gameState.updateId, gameState.players)


class GameState:
  def __init__(self, gameId, gameName):
    self.gameId = gameId
    self.gameName = gameName
    self.players = [None] * 4
    self.updateId = 0
    self.started = False
    
  def update(self, updateId, players):
    # UpdateIds should be unique to the update; conflicting updates should not happen.
    assert not (updateId == self.updateId and players != self.players)
    
    # Only update if this information is newer than what we already have.
    if updateId > self.updateId:
      self.players = players


class GameLobby:
  
  def __init__(self, gameId, gameName):
    self.gameId = gameId
    self.gameName = gameName
    self.started = False
    self.gameState = GameState(gameId, gameName)
    self.gamelet = None
    self.players = [None, None, None, None]
    self.updateCount = 0
  
  def waitForPlayers(self):
    """ 
    Starts running the setup for this game, waiting for join messages,
    and eventually launching the game proper once enough players have
    are ready.
    """    
    # Start listening for people trying to join.
    def onMQConnect():
      def onMessage(msg):
        try:
          print "Got message"
          data = pickle.loads(msg.body)

          if data['type'] == 'join' and not self.started:
            self._join(data['name'], data['id'])
  
          elif data['type'] == 'quit':
            self._quit(data['id'])
  
          else:
            print "Unknown message type %s!" % data['type']
        except Exception, e:
          print e
          
        return

      # Set up a new MQ for this game.
      self.mq = self.mqConn.channel()
      self.mq.queue_declare(str(self.gameId))
      self.mq.queue_purge(str(self.gameId))
      
      # Tell the directory that we are up and waiting for players!
      self.mq.publish(stormed.Message(pickle.dumps({
        'type' : 'newGame',
        'gameId' : self.gameId,
        'gameName' : self.gameName
      })), exchange='gameDirectory')  
      self.updateCount += 1    
      
      self.mq.consume(str(self.gameId), onMessage, no_ack=True)

    # Wait for messages from the MQ, create players accordingly.
    self.mqConn = stormed.Connection(host='localhost')
    self.mqConn.connect(onMQConnect)          
    
  def _join(self, name, playerId):      
    if self.started:
      raise Exception("Player joining game %s, but its already started!" % self.gameId)
      
    # Work out who else is in the game, so we can tell this new guy.
    otherPlayers = [(p.seat, p.name) for p in self.players if p is not None]
    
    # Find the new guy a seat.
    for i, p in enumerate(self.players):
      if p is None:
        newPlayer = Player(name, i, MQView(playerId, i, otherPlayers))
        newPlayer.view.onQuit = self._quit
        
        for p2 in self.players:
          if p2 != None:
            p2.view.playerJoined(name, i)
            
        self.players[i] = newPlayer
        self._updateDirectory()                
        
        if all(p for p in self.players):
          self._start()
          
        return
    
    # We couldn't find a seat, should never happen.
    raise Exception("Too many players joining game %s!" % self.gameId)
      
  def _quit(self, seat):
    if self.started:
      raise Exception("Player quit game %s, but it's already started!" % self.gameId)
    
    self.players[seat] = None    
    self._updateDirectory()
    
    # If the last player has just left, we're done before we even began :-(
    if not any(p for p in self.players):
      self._gameOver()
      
  def _updateDirectory(self):
    print "Updating directory"
    
    self.mq.publish(stormed.Message(pickle.dumps({
      'type' : 'gameState',
      'gameId' : self.gameId,
      'updateId' : self.updateCount,
      'players' : [p.name if p else None for p in self.players]
    })), exchange='gameDirectory')            
    self.updateCount += 1
      
  def _start(self):
    # Tell the directory we're starting.
    self.mq.publish(stormed.Message(pickle.dumps({
      'type' : 'gameStarted',
      'gameId' : self.gameId
    })), exchange='gameDirectory')
    self.started = True
    
    # Close the connection to the MQ, we're not going to need it for
    # quite a while (feasibly hours, probably just many minutes).
    self.mqConn.close()    
    self.mqConn = None
    
    # Go go go.
    game = Game(self.players, onGameOver = self._gameOver)
    self.gamelet = greenlet(game.run)
    self.gamelet.switch()
    
  def _gameOver(self):
    # If the game's running, (and it's not running this function, i.e. it doesn't know
    # that it should be dead now) kill it.
    if self.gamelet and self.gamelet != greenlet.getcurrent():
      self.gamelet.throw()
        
    def shutdownGame():      
      # Tell the directory that the game's finished.
      mqConn.channel().publish(stormed.Message(pickle.dumps({
        'type' : 'gameOver',
        'gameId' : self.gameId
      })), exchange='gameDirectory')  
      mqConn.close()    
    
    if self.mqConn:
      mqConn = self.mqConn
      shutdownGame()
    else:
      mqConn = stormed.Connection(host='localhost')
      mqConn.connect(shutdownGame)   
    
      