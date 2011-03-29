connection = null;

players = ["you"]
currentLeader = null;
leadSuit = null;
bidsMade = 0
bidButtonValue = 1
canPlayCard = false
gameOver = false;

suits = [ 'c', 'd', 'h', 's' ]
values = [ '02', '03', '04', '05', '06', '07', '08',
            '09', '10', 'j', 'q', 'k', 'a']

$(document).ready(function()
{  
  $('#bid00').click(function()
  {
    send({'00' : true});
    $('#showHand').hide()
    $('#bid00').hide()    
    return false;
  });
  
  $('#showHand').click(function()
  {
    if ($('#bid00').is(":visible"))
    {
      send({'00' : false});
    }
    else
    {
      send({'async' : true,
            'type' : 'hand'})
    }
    $('#showHand').hide()
    $('#bid00').hide()    
    return false;    
  });
  
  $('#bid0').click(function()
  {
    send({'bid' : 0});
    $('.bidWindow').hide()
    return false;    
  });  
  
  $('#incBid').click(function()
  {
    if (bidButtonValue < 13)
    {
      bidButtonValue += 1
    }
    $('#bidButtonValue').text(bidButtonValue)
    $('#bidPointsValue').text(bidButtonValue * 10)
    return false;    
  });
  
  $('#decBid').click(function()
  {
    if (bidButtonValue > 1)
    {
      bidButtonValue -= 1      
    }
    $('#bidButtonValue').text(bidButtonValue)
    $('#bidPointsValue').text(bidButtonValue * 10)
    return false;
  });    
  
  $('#bidButton').click(function()
  {
    send({'bid' : bidButtonValue})
    bidButtonValue = 1
    $('#bidButtonValue').text(bidButtonValue)
    $('.bidWindow').hide()
    return false;    
  });            
  
  setTimeout(function () {
    connect();
  }, 200);
});

$(window).bind('beforeunload', function()
{
  if (!gameOver)
  {
    // TODO return "Are you sure you want to leave? This will end the current game!"
  }
});

$(window).unload(function() 
{  
  if (connection)
  {
    disconnect();
  }
});

function connect()
{
  connection = $.post(url='/request',
                      data={ gameId : gameId, userId : userId },
                      success=receive);
}

function reconnect()
{
  connection = $.post(url='/request',
                      data={ gameId : gameId, userId : userId, alreadyJoined : true },
                      success=receive);
}

function disconnect()
{
  send({'async' : true, 'type' : 'quit'});
  connection.abort()
}

function send(msg, type)
{
  data = {
      gameId : gameId,
      userId : userId,
      messages : $.toJSON([msg]),
      alreadyJoined : true
  };

  connection.abort();
  connection = $.post(url='/request', data = data, success = receive);
}

function receive(data)
{
  data = $.parseJSON(data); 

  switch(data['type'])
  {
    case 'playerList':
      for (i in data['players'])
      {
        var p = data['players'][i]
        playerJoined(p['name'], p['position'])
      }
      break;
    case 'joined':
      playerJoined(data['name'], data['position'])
      break;
    case 'startGame':
      startGame(data['leadPosition'])
      break;
    case 'hand':
      setHand(data['hand'])
      break;
    case 'bid':
      setBid(data['position'], data['bid'])
      bidsMade += 1
      if (bidsMade < 4)
      {
        setBid((data['position'] + 1) % 4, '?')
      }
      else if (data['position'] != 3)
      {
        setStatus("Waiting for "+players[data['position'] + 1]+" to play")
      }
      else
      {
        setStatus("Your Turn")
      }
      break;      
    case 'card':
      cardPlayed(data['position'], data['card'])
      if ($('body > .card').length < 4)
      {
        setLeader((data['position'] + 1) % 4)
      }
      if (data['position'] != 3)
      {
        setStatus("Waiting for "+players[data['position'] + 1]+" to play")
      }
      else
      {
        setStatus("Your Turn")
      }
      break;
    case 'winner':
      clearCards(data['winner'])
      setLeader(data['winner'])
      
      if (data['winner'] != 0) setStatus("Waiting for "+players[data['winner']]+" to play")
      else setStatus('Your Turn')
      
      $.each($('.lowlightedCard'), function()
      {
        $(this).removeClass('.lowlightedCard')
      });      
      break;
    case 'scores':
      $('#youScore').text(data['scores']['you'])
      $('#themScore').text(data['scores']['them'])
      $('#scores').show()
      $('.trickCountNum').text('0')
      $('.trickCount').hide()
      $('.target').hide()
      break;
    case 'question':
      switch (data['question'])
      {
        case 'bid00?':
          if ($('.cardInHand').length == 0)
          {
            $('#showHand').removeClass('wide')
            $('#showHand').show()
            $('#bid00').show()
          }
          else
          {
            alert("Server asked us if we want to go double-nil, but we've "+
                  "seen our hand!")
          } break;
        case 'bid?':
          $('#showHand').hide()
          $('#bid00').hide()
          $('.bidWindow').show()
          break;
        case 'card':
          canPlayCard = true;
          $.each($('.cardInHand'), function()
          {
            if (!isValidCard(leadSuit, $(this).data()['suit']))
            {
              $(this).removeClass('highlightedCard')
            }
            else
            {
              $(this).css('cursor', 'pointer')
            }
          });
          setLeader(0)
          setStatus('Your Turn')
          break;
        default:
          alert('Unknown question '+data['question'])
      } break;
    default:
      alert('Recieved unknown message: '+data);
  }

  reconnect();
}

function playerJoined(name, position)
{
  players[position] = name
  getPlayer(position).find('.statusBox').text(name);
}

function getPlayer(position)
{
  switch (position)
  {
    case 0:
      return $('#playerBottom');
    case 1:
      return $('#playerLeft');
    case 2:
      return $('#playerTop');
    case 3:
      return $('#playerRight');
  }  
  alert('Trying to get player from invalid position '+position);
}

function startGame(leadPosition)
{
  currentLeader = leadPosition
  bidsMade = 0
  setLeader(leadPosition)
  
  $('.target').hide()
  $('.trickCount').hide()  

  setBid(leadPosition, '?')
  $('#showHand').show()  
  $('#showHand').addClass('wide')
}

function getAngleFor(position)
{
  return (180 + position * 90) % 360
}

function setLeader(leadPosition)
{
  if (!$('#leadArrow').is(":visible"))
  {
    $('#leadArrow').show()  
    $('#leadArrow').rotate(getAngleFor(leadPosition))
  }
  else
  {
    $('#leadArrow').rotate({animateTo: getAngleFor(leadPosition), duration:500})
  }

  $('#bidLeaderArrow').show()
  $('#bidLeaderArrow').rotate(getAngleFor(leadPosition))
  
  if (leadPosition == 0)
  {
    $('#leader').text("Your")
  }
  else
  {
    $('#leader').text(players[leadPosition]+"'s")
  }
}

function setStatus(status)
{
  getPlayer(0).find('.statusBox').text(status)
}

function setBid(position, value)
{
  var target;
  var targetNum;

  if (position == 0)
  {
    target = $('#localTarget')
    targetNum = $('#localTarget > .targetNum')
  }
  else
  {
    target = getPlayer(position).find('.target')
    targetNum = getPlayer(position).find('.targetNum')
  }   
  
  target.show()
  targetNum.text(value)

  if (value == '?')
  {
    if (position == 0)
    {
      setStatus('Your Bid')
    }
    else
    {
      setStatus('Waiting for '+players[position]+' to bid')
    }
    
    // Question mark blink (have to do it by hand, new browsers have blocked
    // blinking, for some mad reason :-P)
    var blink = function()
    {
      targetNum.toggle()
    
      if (targetNum.text() == '?')
      {
        setTimeout(blink, 500)
      }
      else
      {
        targetNum.show()
      }
    }
    blink()
  }
}

function setHand(hand)
{
  $('#hand').empty();
    
  for (i in hand)
  {
    var card = hand[i]
    var cardImage = suits[parseInt(card['suit'])] + "_" + values[parseInt(card['value'])] + ".png"
    var cardElement = $("<a href='#' class='cardInHand'><img class='card' src='/static/cards/"+cardImage+"' /></a>")  
    $('#hand').append(cardElement);
    
    // Write down the value of this card.
    cardElement.data('suit', card['suit'])
    cardElement.data('value', card['value'])
  }
  
  $('.cardInHand').mouseenter(function()
  {
    var suit = $(this).data('suit')
    var value = $(this).data('value')
    
    if ($('.cardInHand').index(this) == $('.cardInHand').length - 1)
    {
      $(this).css('paddingRight', '3%')
    }

    $('.highlightedCard').removeClass('highlightedCard');
    $(this).addClass('highlightedCard');
    
    var hand = $('#hand')
    var cards = $('.cardInHand')
    cards.css('width', '200px')  

    // If we have so much space that the cards are no longer overlapping
    // then stop moving them left and up, and instead just go up.
    var gapWidth = ($('#hand').width() / $('.cardInHand').length) - 200
    if (gapWidth > 0)
    {
      $('.highlightedCard').css('marginLeft', 0)
      $('.highlightedCard').css('paddingRight', 0)
    }    
  });    
  
  $('.cardInHand').mouseleave(function(e)
  {
    $('.highlightedCard').removeClass('highlightedCard')
    $(this).css('paddingRight', '0')    
  });
  
  $('.cardInHand').click(function()
  {  
    var suit = $(this).data('suit')
    var value = $(this).data('value')
        
    if (isValidCard(leadSuit, suit))
    {
      playCard($(this));
    }
  });        
  
  spreadHandEvenly(false);  
    
  $('#hand').show()
}

function isValidCard(leadSuit, suit)
{
  if (leadSuit != null && suit != leadSuit)
  {
    var ok = true;
  
    // Check the rest of their hand for legit cards.
    $.each($('.cardInHand'), function()
    {        
      // Found? Refuse to play.
      if ($(this).data('suit') == leadSuit)
      {
        ok = false;
      }
    });
    
    if (!ok) return false;
  }  
  return true;
}

function spreadHandEvenly(animate)
{
  var hand = $('#hand')
  var cards = $('.cardInHand')
  cards.css('width', '200px')  
  
  var spacePerCard = hand.width() / cards.length
  
  for (i = 0; i < cards.length; i++)
  {
    var target = {'position' : 'absolute',
                  'left' : (i + 0.5) * spacePerCard - 100 + 'px'}
    if (animate) $(cards[i]).animate(target)
    else $(cards[i]).css(target)
  }
}

function playCard(card)
{ 
  if (!canPlayCard) return;
  
  $('.cardInHand').css('cursor', 'default')  
  
  var suit = card.data('suit')
  var value = card.data('value')
  
  if (leadSuit == null)
  {  
    leadSuit = suit
  }
   
  // N.B. VERY dependent on current page structure, might need work.
  var position = card.offset()
  var x = position.left + 100
  var y = position.top
  
  card.unbind('mouseenter')
  card.trigger('mouseexit')
  card.unbind('mouseexit')
    
  // Strip off the outer <a> tag.
  var cardImage = $(card.children()[0]).detach()
  card.remove()
  spreadHandEvenly(true)
  
  // Push the card from the hand into the body itself, absolutely positioned 
  $('body').append(cardImage)
  cardImage.css({'position': 'absolute', 'zIndex': -1,
            'top': y, 'left': x, 'marginLeft': '-100px'})
            
  // Have to use absolute px positions here not %s because chrome breaks
  // with percentages. No idea why, but I don't think I care.
  cardImage.animate({'top': $(window).height() * 0.52 + 'px', 
                     'left': $(window).width() / 2 + 'px'}, 
                    duration = 500,
                    complete = function() {
                      // Put every card back to normal -- unlowlighted, not cursor'd.
                      $.each($('.cardInHand'), function()
                      {
                        $(this).removeClass('lowlightedCard')
                        $(this).css('pointer', 'default')
                      })                      
                      send({'card' : { 'suit' : suit, 'value' : value }}) 
                    })
  
  canPlayCard = false;  
}

function cardPlayed(position, card)
{  
  // We already know about any cards we played.
  if (position == 0) return;
  
  if (leadSuit == null)
  {
    leadSuit = card['suit']
    $.each($('.cardInHand'), function()
    {
      if (!isValidCard(leadSuit, $(this).data('suit')))
      {
        $(this).addClass('lowlightedCard')
        $(this).css('pointer', 'default')
      }
    })
  }
  
  var width = $(window).width()
  var height = $(window).height()
  switch(position)
  {
    case 1:
      position = 'top: '+(height * 0.3)+'px; left:'+(width * 0.3)+'px;'
      break;
    case 2:
      position = 'top:'+(width * 0.1)+'px; left:'+(width * 0.5)+'px; margin-left: -100px;'
      break;
    case 3:
      position = 'top:'+(height * 0.3)+'px; right: '+(width * 0.3)+'px;'
      break;
  }  
  
  var cardImage = suits[parseInt(card['suit'])] + "_" + values[parseInt(card['value'])] + ".png"
  var cardElement = $("<img class='card' style='position:absolute; "+position+"' src='/static/cards/"+cardImage+"' />")
  $('body').append(cardElement);
}

// Sweep the cards off the board toward the winner, and mark them
// as having won a trick.
function clearCards(winner)
{
  leadSuit = null;
  
  // Get every card object that's just floating around over the board.
  var playedCards = $('body > .card')
    
  // Update shown trick totals.
  var winnerTrickDisplay  
  if (winner != 0) winnerTrickDisplay = getPlayer(winner).find('.trickCountNum')
  else winnerTrickDisplay = $('#localTrickCountNum')
  
  var winnerTrickTotal = parseInt(winnerTrickDisplay.text()) + 1

  winnerTrickDisplay.text(winnerTrickTotal)
  winnerTrickDisplay.parent().show()    
  
  // Change each cards position so that it's measured purely in terms of top and left.
  $.each(playedCards, function()
  {
    $(this).css({ 'top' : $(this).offset().top, 
                 'left' : $(this).offset().left, 
                 'right' : 'auto', 
                 'bottom' : 'auto',
                 'marginLeft' : 0 })
  });
  
  var x;
  var y;
  
  switch(winner)
  {
    case 0:
      y = $(window).height() + 500
      break;
    case 1:
      x = -500
      break;
    case 2:
      y = -500
      break;
    case 3:
      x = $(window).width() + 500
      break;
  }
  
  var target = { }
  if (y) target['top'] = y
  if (x) target['left'] = x  
  
  setTimeout(function()
  {    
    playedCards.css('zIndex', -5)
    playedCards.animate(target, duration = 600, easing = 'linear')
  }, 800)
  
  setTimeout(function()
  {
    playedCards.remove()
    delete playedCards
  }, 1500)
}
