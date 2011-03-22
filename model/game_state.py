from random import shuffle, randint
from enum import Enum
from util import OrderedDict
from player import Player
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
    
    for p in self.players:
      p.view.setIds(p.id, (p.id + 2) % 4)
        
  def runRound(self, dealerIndex = None):      
    # Deal the cards
    shuffle(deck)
    hands = [deck[i::4] for i in range(len(self.players))]
    
    # Map from player ids to bids
    bids = BidState()
    
    # Ask each player for a bid
    for i, p in enumerate(self.players):
      p.hand = hands[i]    
      
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
      
      for p2 in self.players:
        p2.view.playerBid(bids)
        
    leader = dealerIndex
    
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
          leader = i
          break
      
      for p in self.players:
        p.view.winnerWas(leader)
    
  def start(self):
    # Randomly select a dealer
    dealerIndex = randint(0, len(self.players))
    gameOver = False
    
    while not gameOver:
      self.runRound(dealerIndex)
      gameOver = True
    

