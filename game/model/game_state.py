from random import shuffle, randint
from enum import Enum
import re
from game.util import OrderedDict
from game.rules import SpadesRule
from player import Player, Partnership
from cards import *

TrickState = OrderedDict
BidState = OrderedDict

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
    
class Game:

  def __init__(self, playerNames, playerViews):
    self.ruleStack = [SpadesRule()]
  
    ids = range(len(playerNames))
    self.players = map(lambda (n, i, v) : Player(n, i, None, v), zip(playerNames, ids, playerViews))
    
    Partnership(*self.players[0::2])
    Partnership(*self.players[1::2])    
    
    for p in self.players:
      p.view.setIds(p.id, (p.id + 2) % 4)
        
  def runRound(self, dealerIndex = None):      
    # Deal the cards
    self.deck = deck[:]
    shuffle(self.deck)
    hands = [self.deck[i::4] for i in range(len(self.players))]
    
    for hand in hands:
      hand.sort(key=lambda c : ([diamonds, clubs, hearts, spades].index(c.suit), c.value))
    
    for p in self.players:
      p.tricks = 0
      p.bid = None
      p.hand = hands.pop()
      # The view needs to know what their hand is, but it guarantees that it
      # won't let them bid 00 if they actually get this information.      
      p.view.setHand(p.hand[:])
    
    # Map from player ids to bids
    bids = BidState()
    
    # Ask each player for a bid
    for i in range(dealerIndex, dealerIndex + 4):
      p = self.players[i % len(self.players)]
      
      # Ask if they want to go double nil.      
      doubleNil = p.view.goDoubleNil()
      p.view.showHand()      
      
      if doubleNil:
        bid = Bid('00')
        print "Player %s bid 00" % i
        
      # No? Now they've seen their cards, ask again.
      else:
        bid = p.view.bidSomethingSensible()
        print "Player %s bid %s" % (i, bid)
        if bid.isDoubleNil():
          raise Exception("Can't bid double-nil after looking at your cards! Jeez.")
          
      bids[p.id] = bid
      p.bid = bid
      
      for p2 in self.players:
        p2.view.playerBid(i, bid)
        
    leader = dealerIndex
    
    # Play some damn tricks.
    for trick in (TrickState() for t in range(13)):      
      # Ask each player to play a card
      for i in range(leader, leader + 4):
        p = self.players[i % 4]
        card = p.view.playACard()
        
        p.hand.remove(card)
        
        if i is leader:
          ledSuit = card.suit
        else:
          if card.suit.index is not ledSuit.index and \
             any(map(lambda c : c.suit.index is ledSuit.index, p.hand)):
            raise Exception("%s played %s on %s, but their hand is %s!" % 
                            (p.name, card, ledSuit, map(str,p.hand)))
        
        # Record this card in the current trick.
        trick[i % 4] = card
        
        # Tell everybody what they played.
        for p2 in self.players:
          p2.view.playerPlayed(i, card)
      
      # Go through the rules in order, until one of them knows who won the trick.
      # TODO Consider inverse order, passing previous result to each Rule en route up.
      for rule in self.ruleStack:
        candidate = rule.decideWinner(trick)
        if candidate is not None:
          winner = candidate
          break
         
      self.players[winner].tricks += 1
      
      for p in self.players:
        p.view.winnerWas(winner)
        
      # Winner of each trick leads the next.
      leader = winner        
        
    # Round over, count points, update scores.
    for p in self.players:
      print "Player %s made %s aiming for %s" % (p, p.tricks, p.bid.target)    
      # If you bid 0/00, you must make exactly 0. If you bid anything else,
      # you have to make that or more.
      if (p.bid.target == 0 and p.tricks == 0) or \
         (p.bid.target != 0 and p.tricks >= p.bid.target):
        overtricks = p.tricks - p.bid.target
        
        # If your overtrick total goes past 10, lose 100 points.
        if overtricks + (p.partnership.score % 10) >= 10:
          p.partnership.score -= 100
      
        p.partnership.score += p.bid.points + overtricks
        
      else:
        p.partnership.score -= p.bid.points      
  
  def run(self):
    # Randomly select a dealer
    dealerIndex = randint(0, len(self.players))
    gameOver = False
    partnerships = set(map(lambda p : p.partnership, self.players))
    
    while not gameOver:
      for player in self.players:
        player.view.startRound(dealerIndex)      
      
      self.runRound(dealerIndex)
      dealerIndex = (dealerIndex + 1) % len(self.players)
      
      for p in partnerships:
        if p.score > 500 or p.score < -500:
          gameOver = True
          
      scores = dict(map(lambda p : (p.players, p.score), partnerships))
       
      for p in self.players:
        p.view.scores(scores)
        
    for p in self.players:
      p.view.gameOver()    
