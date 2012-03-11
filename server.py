import uuid, os.path, sys
import cPickle as pickle

# Tornado -- Web server/framework
import tornado.ioloop
import tornado.web

# Rest of the web server stuff.
from comet import CometHandler
from mqview import MQView

from gameSetup import GameDirectory, GameLobby

class MainHandler(tornado.web.RequestHandler):
  """
  Shows the front page, allowing starting/joining of games.
  """
  def get(self):
    self.render('lobby.html')
    
class FindHandler(tornado.web.RequestHandler):
  
  def get(self, gameName):
    self.search(gameName)
    
  def post(self):
    self.search(self.get_argument('name'))
    
  def search(self, name):
    global directory
    games = directory.find(name)
    self.render('search.html', games = games, search = name)

class HostHandler(tornado.web.RequestHandler):
  """
  Shows the game set up page, for the game 'host'.
  """

  @tornado.web.asynchronous
  def post(self):
    gameName = self.get_argument('name')
    gameId = uuid.uuid1().int
    
    self.render('game.html', gameId = gameId)
    
    # Page has been sent; client's disconnected, 
    # we're now just some process running on the server.
    self.game = GameLobby(gameId, gameName)
    self.game.waitForPlayers()

class JoinHandler(tornado.web.RequestHandler):
  """
  Shows the game joining page, for game clients.
  """

  def post(self):
    self.join(self.get_argument('gameId'))

  def join(self, gameId):
    self.render("game.html", gameId = gameId)

application = tornado.web.Application(
  handlers = [
    (r"/", MainHandler),
    (r"/find", FindHandler),
    (r"/find/(.*)", FindHandler),
    (r"/host", HostHandler),
    (r"/join", JoinHandler),
    (r"/request", CometHandler),
    (r"/favicon.ico", None)
  ],
  template_path="./templates",
  static_path="./static",
  debug=True
)

if __name__ == "__main__":
  if len(sys.argv) > 1: 
    port = int(sys.argv[1])
  else:
    port = 8888
  
  directory = GameDirectory()
  
  # Don't start the server till the directory's ready.
  while not directory.ready():
    time.sleep(1)
  
  # Ready to go: rock the fuck out.
  application.listen(port)
  tornado.ioloop.IOLoop.instance().start()
