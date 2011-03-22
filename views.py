from model.cards import *
from model.game_state import Bid
from random import choice
  
class BadAIView:
    
  def setIds(self, playerId, partnerId):
    self.playerId = playerId
    self.partnerId = partnerId

  def goDoubleNil(self, bidState):
    return False
    
  def bidSomethingSensible(self, bidState, hand):
    self.hand = hand
    return Bid(2)
    
  def youCrazyBitchHeresYourHand(self, hand):
    self.hand = hand
    
  def playerBid(self, bidState):
    pass
       
  def playACard(self, trickState):
    validCards = None
  
    if len(trickState) > 0:
      validCards = filter(lambda c : c.suit is trickState.values()[0].suit, self.hand)
    
    if not validCards:
      validCards = self.hand
      
    card = choice(validCards)
    self.hand.remove(card)
    
    return card
    
  def playerPlayed(self, trickState):
    pass
    
  def winnerWas(self, playerId):
    pass
    
  def scores(self, scores):
    pass
    
  def gameOver(self):
    pass
    
class ConsoleView:

  def setIds(self, playerId, partnerId):
    self.playerId = playerId
    self.partnerId = partnerId
    print "You are %s, your partner is %s" % (playerId, partnerId)

  def goDoubleNil(self, bidState):
    return raw_input("Bid double-nil Y/N? ").lower() == "y"
    
  def bidSomethingSensible(self, bidState, hand):
    print "Your hand is %s" % map(str, hand)
    self.hand = hand
    
    bid = None
    while not bid:
      try:
        bid = Bid(raw_input("What to bid? "))
      except Exception:
        print "Er, what? Try again please."
        bid = None
           
    return bid
    
  def youCrazyBitchHeresYourHand(self, hand):
    print "Your hand is %s" % map(str, hand)
    self.hand = hand
    
  def playerBid(self, bids):
    print "%s bid %s" % bids.items()[-1]
       
  def playACard(self, trick):
    validCards = None
  
    if len(trick) > 0:
      validCards = filter(lambda c : c.suit is trick.values()[0].suit, self.hand)
    
    if not validCards:
      validCards = self.hand
      
    print "You can play one of: %s" % map(str, validCards)
    card = validCards[int(raw_input("Card to play? (0-indexed) "))]
    self.hand.remove(card)    
    return card
    
  def playerPlayed(self, trick):
    print "%s played %s" % trick.items()[-1]
    
  def winnerWas(self, playerId):
    print "%s won the trick" % playerId
    
  def scores(self, scores):
    print "Scores:\n%s" % map(lambda (k, v): "%s = %s" % (k, v), scores.items())
    
  def gameOver(self):
    print "Game over!"
