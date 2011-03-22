from random import shuffle, randint
from enum import Enum
from util import OrderedDict
from player import Player, Partnership
from cards import *
from rules import SpadesRule
import re

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
    shuffle(deck)
    hands = [deck[i::4] for i in range(len(self.players))]
    
    for p in self.players:
      p.tricks = 0
      p.bid = None
    
    # Map from player ids to bids
    bids = BidState()
    
    # Ask each player for a bid
    for i in range(dealerIndex, dealerIndex + 4):
      p = self.players[i % len(self.players)]
      p.hand = hands[i % len(hands)]    
      
      # Before we give them their hand, ask if they want to go double nil.
      doubleNil = p.view.goDoubleNil(bids)
      if doubleNil:
        bid = Bid('00')
        # Madness. Show them their cards anyway.
        p.view.youCrazyBitchHeresYourHand(p.hand[:])
        
      # No? Show them the cards, ask again.
      else:
        bid = p.view.bidSomethingSensible(bids, p.hand[:])
        if bid.isDoubleNil():
          raise Exception("Can't bid double-nil after looking at your cards! Jeez.")
          
      bids[p.id] = bid
      p.bid = bid
      
      for p2 in self.players:
        p2.view.playerBid(bids)
        
    leader = dealerIndex
    
    # Play some damn tricks.
    for trick in (TrickState() for t in range(13)):      
      # Ask each player to play a card
      for i in range(leader, leader + 4):
        p = self.players[i % 4]
        card = p.view.playACard(trick)
        p.hand.remove(card)
        
        if i is leader:
          ledSuit = card.suit
        else:
          if card.suit is not ledSuit and any(map(lambda c : c.suit is ledSuit, p.hand)):
            raise Exception("%s played %s on %s, but their hand is %s!" % 
                            (p.name, card, ledSuit, p.hand))
            
        
        trick[p.id] = card
        
        # Tell everybody what they played.
        for p2 in self.players:
          p2.view.playerPlayed(trick)
      
      # Go through the rules in order, until one of them knows who won the trick.
      # TODO Consider inverse order, passing previous result to each Rule en route up.
      for rule in self.ruleStack:
        candidate = rule.decideWinner(trick)
        if candidate is not None:
          winner = candidate
          break
          
      # Rules return player ids, we need to find the corresponding id in the list of players
      for i, p in enumerate(self.players):
        if p.id is winner:
          p.tricks += 1
          leader = i
          break
      
      for p in self.players:
        p.view.winnerWas(leader)
        
    # Round over, count points, update scores.
    for p in self.players:    
      if p.tricks >= p.bid.target:
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
      self.runRound(dealerIndex)
      dealerIndex = (dealerIndex + 13) % len(self.players)
      
      for p in partnerships:
        if p.score > 500 or p.score < -500:
          gameOver = True      
          
      scores = dict(map(lambda p : (str(p), p.score), partnerships))
       
      for p in self.players:
        p.view.scores(scores)
        
    for p in self.players:
      p.view.gameOver()
      

