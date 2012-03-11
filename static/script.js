// *************************************************************
// * Connection Management:                                    *
// *************************************************************            
connection = null;
connectionErrors = 0;
MAX_CONNECTION_ERRORS = 1;
gameOver = false;
            
$(document).ready(function()
{
  // Reduce the animation framerate to ~33FPS for performance.
  jQuery.fx.interval = 30
  
  function connect()
  {
    connection = $.post(url='/request',
                        data={ gameId : gameId, userId : userId },
                        success=receive);         
  }  

  maybeUnload = false
  $(window).bind('beforeunload', function()
  {
    maybeUnload = true
    
    // If we're still on this page in 30 seconds, we're probably not unloading. 
    setTimeout(function() { maybeUnload = false }, 30000)
    
    if (connection)
    {
      // TODO return "Are you sure you want to leave? This will end the current game!"
    }
  });

  actualUnload = false
  // Ok, we're actually unloading.
  $(window).unload(function() 
  {
    actualUnload = true
    
    if (connection)
    {
      disconnect();
    }
  });

  function lostConnection()
  {
    if (!actualUnload)
    {
      if (connectionErrors < MAX_CONNECTION_ERRORS)
      {
        connectionErrors += 1
        reconnect();
      }
      else
      {
        onGameOver("Sorry, we lost the server...")
      }
    }
  }
 
  $(document).ajaxError(function(event, request, settings)
	{
		// We closed the connection. This was intentional, we don't want to
		// overthink it here.
		if (request.statusText == "abort") return;
		
		// Timeouts, eh. We can deal with timeouts; try again.
		else if (request.statusText == "timeout")
		{
			reconnect();
		}
		
		// The connection was dropped/server error/page missing (should *never* happen)
		// Regardless, we've lost our place, it's all very messy, accept defeat and
		// disconnect and move on.
		else if (request.status == 0 || request.status == 500 || request.status == 404)
		{
			// Maybe unload is only set for a short time after the user tried to navigate away
			// from the page (we can't tell if that's what dropped this connection, yet).
			if (maybeUnload)
			{
				// If we might be unloading, wait a second, to give the actual unload event a chance
				// to stop the dropped connection messages from happening, if we're actually unloading.
				setTimeout(lostConnection, 1000)
			}
			// Otherwise, this is unexpected. Minor timeout anyway, just to hedge bets (perhaps 
			// they idled for ages on the 'leave this page?' dialog and we assumed they'd said no?).
			else
			{
				setTimeout(lostConnection, 100)
			}
		}
		return;
	});            
  
  // Wait a little bit before connecting. Useful to make sure the game is set up
  // server-side.
  setTimeout(function () {
    connect();
  }, 500);
});

function reconnect()
{
  if (connection && connection.readyState == 1)
  {
    console.log('Reconnecting while connection still live!')
    console.trace()
  }
  connection = $.post(url='/request',
                      data={ gameId : gameId, userId : userId, alreadyJoined : true },
                      success=receive);
}

function disconnect()
{
  console.log('Disconnecting...')
  send({'type' : 'quit'});
  $.post(url='/request',
         data={ gameId : gameId, 
                userId : userId, 
                alreadyJoined : true, 
                messages : $.toJSON([{'type' : 'quit'}]),
                async : false },
         success=receive);
  connection = null;
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
 
// Major function. How do we react to each + every time of server message:
function receive(data)
{
  if (!connection || gameOver) return;
  
  // Not much we can do without any data. Try again? Might be a server failure, in
  // which case reconnecting should crash and give us more, or might just be a blip
  // somewhere that we can ignore...
  if (!data)
  {
    reconnect();
    return;
  }
  
  data = $.parseJSON(data); 

  switch(data['type'])
  {
    // A definitive list of players currently in the game.
    case 'playerList':
      for (i in data['players'])
      {
        var p = data['players'][i]
        playerJoined(p['name'], p['position'])
      }
      break;
      
    // A new player has joined the game.
    case 'joined':
      playerJoined(data['name'], data['position'])
      break;
      
    // IT BEGIN
    case 'startGame':
      startGame(data['leadPosition'])
      break;
    
    // This is what's in your hand.
    case 'hand':
      setHand(data['hand'])
      break;
      
    // Somebody bid something.
    case 'bid':
      setBid(data['position'], data['bid'])
      bidsMade += 1
      
      // If there's still more bids to go, start waiting for the next person.
      if (bidsMade < 4)
      {
        setBid((data['position'] + 1) % 4, '?')
      }
      
      // If we're done bidding, we're waiting for somebody to play. (person
      // to the right of the last bidder)
      else if (data['position'] != 3)
      {
        setStatus("Waiting for "+players[data['position'] + 1]+" to play")
      }
      // (That person could be us)
      else
      {
        setStatus("Your Turn")
      }
      break;
      
    // A card was played.
    case 'card':
      cardPlayed(data['position'], data['card'])
      break;
      
    // 4 cards have been played, the trick's been won! Clear away, prep for the next.
    case 'winner':
      clearCards(data['winner'])
      setLeader(data['winner'])
      
      if (data['winner'] != 0) setStatus("Waiting for "+players[data['winner']]+" to play")
      else setStatus('Your Turn')
      
      // Reset the invalid cards; all equal again now.
      $.each($('.lowlightedCard'), function()
      {
        $(this).removeClass('.lowlightedCard')
      });      
      break;
      
    // Round over; update the scores.
    case 'scores':
      $('#youScore').text(data['scores']['you'])
      $('#themScore').text(data['scores']['them'])
      $('#scores').show()
      $('.trickCountNum').text('0')
      $('.trickCount').hide()
      $('.cardInHand').remove()
      $('#hand').hide()
      $('.target').hide()
      break;
    
    // Server is waiting for you to answer a question:
    case 'question':
      switch (data['question'])
      {
        // Do you want to bid 00?
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
          
        // You don't want to bid 00 eh? What *do* you want to bid?
        case 'bid?':
          $('#showHand').hide()
          $('#bid00').hide()
          $('.bidWindow').show()
          break;
          
        // Your turn to play a card
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
      
    case 'gameOver':
      onGameOver(data['message'])
      break;
      
    default:
      alert('Recieved unknown message: '+data);
  }

  if (!gameOver) reconnect();
}  





// *************************************************************
// * Player management:                                        *
// *************************************************************
players = ["you"]
currentLeader = null;
canPlayCard = false;

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

function onGameOver(message)
{
  gameOver = true;
  connection = null;
  alert("Game over: "+message)
  setStatus("Game Over.")
  
  $('#leadArrow').fadeOut(2000)
  
  setTimeout(function() {
    $(window.location).attr('href', '/');
  }, 2000);
}





// *********************************************************
// * Bidding                                               *
// *********************************************************
bidsMade = 0
bidButtonValue = 1

$(function()
{  
  // Register bid events:
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
      send({'type' : 'hand'})
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
})

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




//*********************************************************
//* Playing and showing cards                             *
//*********************************************************
leadSuit = null;

suits = [ 'c', 'd', 'h', 's' ]
values = [ '02', '03', '04', '05', '06', '07', '08',
            '09', '10', 'j', 'q', 'k', 'a']

// Register general card event handlers
// (Note: event handler for clicking cards is set in setHand)
$(function()
{
  $(window).resize(function()
  {
    spreadHandEvenly(false)
  })
})

function setHand(hand)
{
  $('#hand').empty();
    
  for (i in hand)
  {
    var card = hand[i]
    var cardImage = suits[parseInt(card['suit'])] + "_" + 
                    values[parseInt(card['value'])] + ".png"
    var cardElement = $("<div href='#' class='cardInHand'><img class='card' src='/static/cards/" + 
                        cardImage + "' /></div>")  
    $('#hand').append(cardElement);
    
    // Write down the value of this card.
    cardElement.data('suit', card['suit'])
    cardElement.data('value', card['value'])
  }
  
  // Register card events:  
  
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
  
  // If that's not the end of the trick, point at the next person in line.
  if ($('body > .card').length < 4)
  {
    // Point the arrow at the next person.
    setLeader(1)  
    setStatus("Waiting for "+players[1]+" to play")
  }                    
  else
  {
    setStatus("Deciding Winner...")
  }
                    
  canPlayCard = false;  
}

function cardPlayed(position, card)
{  
  // We already know about any cards we played.
  if (position == 0) return;
  
  // < 4 cards on the table, look at the next person whose turn it is.
  if ($('body > .card').length < 4)
  {
    // Point the arrow at them.
    setLeader((position + 1) % 4)  
    setStatus("Waiting for "+players[(position + 1) % 4]+" to play")
  }
  else
  {
    setStatus("Deciding Winner...")
  }  

  // Work out the suit situation so we know what cards are valid.
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
  
  // Show the played card.
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
  
  var cardImage = suits[parseInt(card['suit'])] + "_" + 
                  values[parseInt(card['value'])] + ".png"
  var cardElement = $("<img class='card' style='z-index: -2; position:absolute; "+
                      position+"' src='/static/cards/"+cardImage+"' />")
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
