from enum import Enum
import re
from .util import Memoize, OrderedDict

TrickState = OrderedDict
BidState = OrderedDict

suits = ['Clubs', 'Diamonds', 'Hearts', 'Spades']

values = ['Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 
          'Ten', 'Jack', 'Queen', 'King', 'Ace']

class Card:
  __metaclass__ = Memoize  

  def __init__(self, suit, value):
    assert suit in range(len(suits))
    assert value in range(len(values))
    
    self.suit = suit
    self.value = value
    
  def __str__(self):
    return "%s of %s" % (values[self.value], suits[self.suit])
    
  def __repr__(self):
    return self.__str__()
    
  def __eq__(self, other):
    return self.suit == other.suit and self.value == other.value
            
  def __neq__(self, other):
    return not self.__eq__(other)

deck = [Card(s, v) for s in range(len(suits)) for v in range(len(values))]

class Bid:

  def __init__(self, bid):
    if isinstance(bid, str):      
      bid = bid.lower()      
      if re.match(bid, 'double.?nil') or bid == '00':
        bid = -1
      elif bid == 'nil':
        bid = 0
      elif bid.isdigit():
        bid = int(bid)
    
    if not isinstance(bid, int) or bid < -1 or bid > 13:
      raise Exception("Instancing invalid bid!")
    else:
      self.value = bid
      
  @property
  def points(self):
    if self.isDoubleNil():
      return 200
    elif self.value == 0:
      return 100
    else:
      return self.value * 10
  
  @property
  def target(self):
    if self.isDoubleNil():
      return 0
    else:
      return self.value
      
  def isDoubleNil(self):
    return self.value == -1
    
  def __str__(self):
    if self.value is 0:
      return 'nil'
    elif self.value is -1:
      return 'double-nil'
    else:
      return str(self.value)
      
class Player:

  def __init__(self, name, seat, view):
    self.name = name
    self.seat = seat
    self.view = view
    
    self.tricks = 0
    self.bid = None
    
  def __str__(self):
    return self.name
    
   
class Partnership:
  """
  A set of players with a shared score.
  """

  def __init__(self, players):
    self.players = players      
    self.score = 0
    
  def __str__(self):
    return "%s and %s" % (self.players[0], self.players[1])      
    
def setupPartnership(*players):
  partnership = Partnership(players)
  for p in players:
    p.partnership = partnership    
