from model.cards import *

class SpadesRule:

  def decideWinner(self, trick):
    """
    Decides who won the trick, outputting a winning player id.
    """
    winningCard = trick.values()[0]
    winningPlayer = trick.keys()[0]
    
    for p, c in trick.items():
      if (c.suit is winningCard.suit or c.suit is spades) and c.value > winningCard.value:
        winningCard = c
        winningPlayer = p
        
    return winningPlayer
    
    
