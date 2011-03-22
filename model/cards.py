from enum import Enum
from util import memoize

Suits = Enum('Clubs', 'Hearts', 'Diamonds', 'Spades')
clubs = Suits.Clubs
hearts = Suits.Hearts
diamonds = Suits.Diamonds
spades = Suits.Spades

Values = Enum('Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 
              'Ten', 'Jack', 'Queen', 'King', 'Ace')

class Card:

  def __init__(self, suit, value):
    assert suit in Suits
    assert value in Values
    
    self.suit = suit
    self.value = value
    
  def __str__(self):
    return "%s of %s" % (self.value, self.suit)

deck = [Card(s, v) for s in Suits for v in Values]
