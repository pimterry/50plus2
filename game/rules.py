from .model import *

class SpadesRule:

  def decideWinner(self, trick):
    """
    Decides who won the trick, outputting a winning player id.
    """
    winningCard = trick.values()[0]
    winningPlayer = trick.keys()[0]
    spades = suits.index('Spades')
    
    for p, c in trick.items():
      if (c.suit == winningCard.suit and c.value > winningCard.value) or \
          (c.suit == spades and winningCard.suit != spades):
        winningCard = c
        winningPlayer = p
        
    return winningPlayer
    
    
# TODO: PySandbox