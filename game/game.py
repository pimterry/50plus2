from random import shuffle, randint

from .rules import SpadesRule
from .model import *

class Game:
  """
  The definition of the flow of a game of spaodes. Build it with some players,
  call run(). It can also be built with an optional callback for when it's finished.
  """

  def __init__(self, players, onGameOver = None):
    self.ruleStack = [SpadesRule()]
    self.players = players

    self.onGameOver = onGameOver
    for player in self.players:
      player.view.onQuit = self.playerQuit

    # Every player should have a seat id that accurately describes where 
    # they're sitting.
    assert all(i == p.seat for i, p in enumerate(self.players))

    # Set up partnerships between opposite players
    setupPartnership(*self.players[0::2])
    setupPartnership(*self.players[1::2])

  def runRound(self, dealerIndex = None):
    # Deal the cards
    self.deck = deck[:]
    shuffle(self.deck)
    hands = [self.deck[i::len(self.players)] for i in range(len(self.players))]

    for hand in hands:
      hand.sort(key = lambda c : ([1, 0, 2, 3].index(c.suit), c.value))

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
      # Regardless of the response, they get to see their hand now.
      p.view.showHand()

      if doubleNil:
        bid = Bid('00')

      else:
        # No? Now they've seen their cards, ask again.
        bid = p.view.bidSomethingSensible()
        if bid.isDoubleNil():
          raise Exception("Can't bid double-nil after looking at your cards! Jeez.")

      bids[p.seat] = bid
      p.bid = bid

      for p2 in self.players:
        p2.view.playerBid(p.seat, bid)

    # The person who dealt leads, initially.
    leader = dealerIndex

    # Play some damn tricks.
    for trick in (TrickState() for t in range(13)):
      # Ask each player to play a card
      for i in range(leader, leader + 4):
        p = self.players[i % 4]
        card = p.view.playACard()
        p.hand.remove(card)

        if i is leader:
          leadSuit = card.suit

        else:
          # Check the card played was legal (either they followed suit, or
          # they had none of the lead suit)
          if card.suit != leadSuit and any(c for c in p.hand if c.suit == leadSuit):
            raise Exception("%s played %s on %s, but their hand is %s!" %
                            (p.name, card, leadSuit, map(str, p.hand)))

        # Record this card in the current trick.
        trick[p.seat] = card

        # Tell everybody what they played.
        for p2 in self.players:
          p2.view.playerPlayed(p.seat, card)

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

      # TODO: Deal with both teams winning/losing a round at the same time.
      for p in partnerships: # TODO fix scores here
        if p.score > 500:
          gameOverMessage = "%s won with %s points." % (p, p.score)
          gameOver = True
        elif p.score < -500:
          gameOverMessage = "%s lost, falling to %s points." % (p, p.score)
          gameOver = True

      scores = dict(map(lambda p : (p.players, p.score), partnerships))

      for p in self.players:
        p.view.scores(scores)

    self.announceGameOver(gameOverMessage)

  def playerQuit(self, position):
    """
    Views have to call this if their player quits, so we can tell the others and
    close down nicely. We set it as the onQuit method on each view so they can do so.
    """
    self.announceGameOver("%s left the game." % self.players[position].name)

  def announceGameOver(self, message = ""):
    for p in self.players:
      p.view.gameOver(message)

    if self.onGameOver:
      self.onGameOver()
