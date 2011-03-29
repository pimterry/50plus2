from enum import Enum
from game.util import Memoize

Suits = Enum('Clubs', 'Diamonds', 'Hearts', 'Spades')
clubs = Suits.Clubs
hearts = Suits.Hearts
diamonds = Suits.Diamonds
spades = Suits.Spades

Values = Enum('Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 
              'Ten', 'Jack', 'Queen', 'King', 'Ace')

class Card:
  __metaclass__ = Memoize  

  def __init__(self, suit, value):
    assert suit in Suits
    assert value in Values
    
    self.suit = suit
    self.value = value
    
  def __str__(self):
    return "%s of %s" % (self.value, self.suit)
    
  def __repr__(self):
    return self.__str__()
    
  def __eq__(self, other):
    return (self.suit.index == other.suit.index and
            self.value.index == other.value.index)
            
  def __neq__(self, other):
    return not self.__eq__(other)

deck = [Card(s, v) for s in Suits for v in Values]
