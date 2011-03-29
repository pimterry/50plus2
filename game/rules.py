from model.cards import *

class SpadesRule:

  def decideWinner(self, trick):
    """
    Decides who won the trick, outputting a winning player id.
    """
    winningCard = trick.values()[0]
    winningPlayer = trick.keys()[0]
    
    for p, c in trick.items():
      if ((c.suit.index == winningCard.suit.index and c.value.index > winningCard.value.index) or 
          (c.suit.index == spades.index and winningCard.suit.index != spades.index)):
        winningCard = c
        winningPlayer = p
        
    return winningPlayer
    
    
