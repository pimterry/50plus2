class Player:

  def __init__(self, name, id, hand, view):
    self.name = name
    self.id = id
    self.hand = hand
    self.view = view
    
    self.tricks = 0
    self.bid = None
    
  def __str__(self):
    return self.name
    
class Partnership:

  def __init__(self, *players):
    self.players = players
    
    for p in players:
      p.partnership = self
      
    self.score = 0
    
  def __str__(self):
    # TODO Properly, for possible later biggering.
    return "Team of %s and %s" % (self.players[0], self.players[1])
