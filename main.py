from random import randint

from model.game_state import Game
from views import *

if __name__ == "__main__":
  playerViews = []
  playerNames = []
  
  human = randint(0, 3)
  
  for ii in range(0, 4):
    if ii is human:
      playerViews.append(ConsoleView())
      playerNames.append("You")
    else:
      playerViews.append(BadAIView())
      playerNames.append("Player %s" % ii)
    
  g = Game(playerNames, playerViews)
  g.start()
    
  
    
  
