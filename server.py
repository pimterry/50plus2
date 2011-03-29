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

from game.model.game_state import Game

class MainHandler(tornado.web.RequestHandler):
  """
  Shows the front page, allowing starting/joining of games.
  """

  def get(self):
    self.render('index.html')

class HostHandler(tornado.web.RequestHandler):
  """
  Shows the game set up page, for the game 'host'.
  """

  @tornado.web.asynchronous
  def get(self, gameId):
    self.host(gameId)

  def post(self):
    self.host(self.get_argument('gameId'))

  def host(self, gameId):
    print 'hosting'
    self.render('game.html', gameId = gameId)

    self.gamelet = greenlet(self.startGame)
    self.gamelet.switch()

    # Start listening for more messages (to begin with, for more joining people)

    def withMQ():
      print 'withMQ'
      def onMessage(msg):
        data = pickle.loads(msg.body)
        print "Host (game %s) recieved message: %s" % (gameId, data)

        # TODO Deal with unwanted extra players.
        if data['type'] == 'join' and self.waitingForPlayers:
          self.gamelet.switch(data['name'], data['id'])

        # If anybody quits, shut down everything.
        # TODO Tidy this up, other players will probably recreate the queue
        # on their way out.
        elif data['type'] == 'quit':
          ch.queue_delete(gameId)
          mq.close()

        else:
          print "Unknown message type %s!" % data['type']

      ch = mq.channel()
      ch.queue_declare(gameId)

      # Clear any old messages.
      ch.queue_purge(gameId)
      ch.consume(gameId, onMessage, no_ack=True)

    # Wait for messages from the MQ, create players accordingly.
    mq = Connection(host='localhost')
    mq.connect(withMQ)

  def startGame(self):
    views = []
    names = []

    self.waitingForPlayers = True
    for i in range(4):
      # Yield till a parent joins
      name, playerId = self.gamelet.parent.switch()
      for view in views:
        view.playerJoined(name, i)
      views.append(MQView(playerId, i, enumerate(names)))
      names.append(name)

    self.waitingForPlayers = False

    # Wait one second, then start the game
    game = Game(names, views)
    game.run()

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
