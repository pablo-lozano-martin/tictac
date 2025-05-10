from flask import Flask, render_template, request, redirect, url_for, session, flash
from game import TicTacToe
from ollama_client import get_ai_move

app = Flask(__name__)
app.secret_key = 'your_very_secret_key'  # Important for session management!

PLAYER_X = 'X'
PLAYER_O = 'O'

# Define player type options
PLAYER_X_OPTIONS = [
    'human',
    'ai_llama3.2',
    'ai_qwen3',     # renamed default Qwen3
    'ai_qwen3:4b',
    'ai_qwen3:1.7b',
    'ai_qwen3:0.6b'
]
PLAYER_O_OPTIONS = [
    'human',
    'ai_llama3.2',
    'ai_qwen3',     # renamed default Qwen3
    'ai_qwen3:4b',
    'ai_qwen3:1.7b',
    'ai_qwen3:0.6b'
]

# Define AI model capabilities (True if it's a "thinking" model)
AI_MODEL_CONFIG = {
    'llama3.2':    {'is_thinking_model': False},
    'qwen3':    {'is_thinking_model': True},   # updated key
    'qwen3:4b':    {'is_thinking_model': True},
    'qwen3:1.7b':  {'is_thinking_model': True},
    'qwen3:0.6b':  {'is_thinking_model': True},
}

def get_player_type_display_name(player_type_code):
    if player_type_code == 'human':
        return 'Human'
    elif player_type_code == 'ai_llama3.2':
        return 'Llama 3.2'
    elif player_type_code == 'ai_qwen3':
        return 'Qwen3 8B'   # updated label
    elif player_type_code == 'ai_qwen3:4b':
        return 'Qwen3 4B'
    elif player_type_code == 'ai_qwen3:1.7b':
        return 'Qwen3 1.7B'
    elif player_type_code == 'ai_qwen3:0.6b':
        return 'Qwen3 0.6B'
    return 'Unknown'

def get_game():
    session.setdefault('player_X_type', PLAYER_X_OPTIONS[0])
    session.setdefault('player_O_type', PLAYER_O_OPTIONS[0])

    if 'board' not in session:
        session['board'] = [[' ' for _ in range(3)] for _ in range(3)]
        session['current_player'] = PLAYER_X
        session['winner'] = None
        session['game_over'] = False
        # Clear previous thinking logs
        session.pop('ai_thinking_X', None)
        session.pop('ai_thinking_O', None)
        # Initialize thinking history
        session['ai_history_X'] = []
        session['ai_history_idx_X'] = -1
        session['ai_history_O'] = []
        session['ai_history_idx_O'] = -1
    
    game = TicTacToe()
    game.board = session['board']
    game.current_winner = session.get('winner')
    return game

def save_game(game_instance, current_player_turn, game_over=False):
    session['board'] = game_instance.board
    session['winner'] = game_instance.current_winner
    session['current_player'] = current_player_turn
    session['game_over'] = game_over
    session.modified = True


@app.route('/', methods=['GET'])
def menu():
    # Ensure player types are initialized in session if not present
    session.setdefault('player_X_type', PLAYER_X_OPTIONS[0])
    session.setdefault('player_O_type', PLAYER_O_OPTIONS[0])

    player_x_type_code = session['player_X_type']
    player_o_type_code = session['player_O_type']
    
    player_x_display = get_player_type_display_name(player_x_type_code)
    player_o_display = get_player_type_display_name(player_o_type_code)
    
    return render_template('menu.html',
                           player_X_type=player_x_display,
                           player_O_type=player_o_display)

@app.route('/toggle_player_type/<player_symbol>', methods=['GET'])
def toggle_player_type(player_symbol):
    if player_symbol == PLAYER_X:
        options = PLAYER_X_OPTIONS
        session_key = 'player_X_type'
    elif player_symbol == PLAYER_O:
        options = PLAYER_O_OPTIONS
        session_key = 'player_O_type'
    else:
        flash("Invalid player symbol.", "error")
        return redirect(url_for('menu')) # Redirect to menu

    current_type = session.get(session_key, options[0])
    try:
        current_index = options.index(current_type)
        next_index = (current_index + 1) % len(options)
        session[session_key] = options[next_index]
    except ValueError:
        session[session_key] = options[0]
    
    session.modified = True
    return redirect(url_for('menu')) # Redirect to menu

@app.route('/start_selected_game', methods=['GET'])
def start_selected_game():
    session.pop('board', None)
    session.pop('current_player', None)
    session.pop('winner', None)
    session.pop('game_over', None)
    # Clear thinking logs for both players
    session.pop('ai_thinking_X', None)
    session.pop('ai_thinking_O', None)
    return redirect(url_for('play_game'))


@app.route('/play', methods=['GET'])
def play_game():
    game = get_game() # Ensures board, player types, and current_player are initialized
    message = ""
    trigger_ai_move = False
    show_agi_reset_button = False # Retained for existing logic

    current_player_symbol = session.get('current_player') 
    current_player_type = session.get(f'player_{current_player_symbol}_type', 'human') 

    # Always retrieve the last recorded AI thoughts from the session
    ai_thinking_details_for_template = session.get('ai_thinking_details', "")
    ai_thinker_for_template = session.get('ai_player_who_thought')

    # Retrieve both AIs' last thoughts
    ai_thinking_X = session.get('ai_thinking_X', "")
    ai_thinking_O = session.get('ai_thinking_O', "")

    if session.get('game_over'):
        player_x_is_ai = session.get('player_X_type', 'human').startswith('ai_')
        player_o_is_ai = session.get('player_O_type', 'human').startswith('ai_')
        if player_x_is_ai and player_o_is_ai:
            show_agi_reset_button = True
        
        if session.get('winner'):
            message = f"Game Over. Player {session.get('winner')} won."
        else:
            message = "Game Over. It's a tie."
        # ai_thinking_details_for_template and ai_thinker_for_template are already set from session
    else: # Game is not over
        if current_player_type.startswith('ai_'): # Current player is AI
            message = f"AI ({current_player_symbol}) is thinking..."
            trigger_ai_move = True 
            # The existing ai_thinking_details (from previous player if AI, or this AI's last turn) will be shown.
            # _handle_ai_turn will update session['ai_thinking_details'] and session['ai_player_who_thought']
            # for the *current* AI after it thinks and before the next page render.
            print(f"play_game: AI's turn ({current_player_symbol} type: {current_player_type}). Will render page with meta refresh.")
        elif current_player_type == 'human': # Current player is Human
            message = f"Player {current_player_symbol}'s turn."
            # ai_thinking_details_for_template and ai_thinker_for_template are already set from session (from previous AI move)
    
    # Compute display names for header
    px_code = session.get('player_X_type')
    po_code = session.get('player_O_type')
    from app import get_player_type_display_name  # ensure function is accessible
    player_X_display = get_player_type_display_name(px_code)
    player_O_display = get_player_type_display_name(po_code)

    # Compute history context for both AIs
    history_X = session.get('ai_history_X', [])
    idx_X     = session.get('ai_history_idx_X', -1)
    history_O = session.get('ai_history_O', [])
    idx_O     = session.get('ai_history_idx_O', -1)

    return render_template('index.html', 
                           board=game.board, 
                           message=message, 
                           game_over=session.get('game_over', False),
                           trigger_ai_move=trigger_ai_move,
                           show_agi_reset_button=show_agi_reset_button,
                           ai_thinking_details=ai_thinking_details_for_template,
                           ai_thinker_symbol_for_display=ai_thinker_for_template,
                           ai_thinking_X=ai_thinking_X,
                           ai_thinking_O=ai_thinking_O,
                           PLAYER_X=PLAYER_X, # Pass PLAYER_X for template logic
                           PLAYER_O=PLAYER_O,  # Pass PLAYER_O for template logic
                           player_X_display=player_X_display,
                           player_O_display=player_O_display,
                           history_X=history_X,
                           idx_X=idx_X,
                           history_len_X=len(history_X),
                           can_prev_X=(idx_X > 0),
                           can_next_X=(idx_X < len(history_X)-1),
                           history_O=history_O,
                           idx_O=idx_O,
                           history_len_O=len(history_O),
                           can_prev_O=(idx_O > 0),
                           can_next_O=(idx_O < len(history_O)-1))

@app.route('/execute_ai_move', methods=['GET'])
def execute_ai_move():
    game = get_game() # Get current game state
    current_player_symbol = session.get('current_player')
    current_player_type = session.get(f'player_{current_player_symbol}_type', 'human')

    if not session.get('game_over') and current_player_type.startswith('ai_'): # Check for any AI type
        print(f"execute_ai_move: AI's turn ({current_player_symbol} type: {current_player_type}). Calling _handle_ai_turn.")
        return _handle_ai_turn(game, current_player_symbol)
    else:
        # Should not happen if called correctly via meta refresh
        print(f"execute_ai_move: Called inappropriately. Game over: {session.get('game_over')}, Player: {current_player_symbol}, Type: {current_player_type}.")
        return redirect(url_for('play_game'))


def _handle_ai_turn(game, ai_player_symbol):
    print(f"--- AI Turn ({ai_player_symbol}) ---")
    
    # Use the new JSON string method for the board state
    board_json_for_ai = game.get_board_as_json_string()
    available_moves_for_ai = game.available_moves()

    # Determine the next player's symbol regardless of AI's success for saving game state
    next_player_symbol_after_ai = PLAYER_O if ai_player_symbol == PLAYER_X else PLAYER_X

    if not available_moves_for_ai: # Check if any moves are possible
        if not game.current_winner: # No moves left, but no winner yet means draw
            session['game_over'] = True
            flash("It's a tie! (No moves left for AI)", "info")
        # Even if game is over, save state with a designated next player (for consistency)
        save_game(game, next_player_symbol_after_ai, game_over=True)
        return redirect(url_for('play_game'))

    print(f"Board state (JSON for AI) ({ai_player_symbol}):\n{board_json_for_ai}")
    
    # Determine which AI model to use
    ai_player_type_code = session.get(f'player_{ai_player_symbol}_type')
    model_to_use = "llama3.2" # Default model
    if ai_player_type_code == 'ai_llama3.2':
        model_to_use = "llama3.2"
    elif ai_player_type_code == 'ai_qwen3':
        model_to_use = "qwen3" # Or the exact name you pulled with ollama, e.g., "qwen:latest" or "qwen:7b"
    
    is_thinking_model = AI_MODEL_CONFIG.get(model_to_use, {}).get('is_thinking_model', False)
    
    print(f"AI ({ai_player_symbol}) using model: {model_to_use}, Is thinking model: {is_thinking_model}")
    # Pass the JSON board string and thinking status to get_ai_move
    ai_move_coords, ai_response_details = get_ai_move(board_json_for_ai, available_moves_for_ai, model_to_use, ai_player_symbol, is_thinking_model)
    # Save per-player thinking and update history
    key_think = 'ai_thinking_X' if ai_player_symbol == PLAYER_X else 'ai_thinking_O'
    key_hist  = 'ai_history_X'  if ai_player_symbol == PLAYER_X else 'ai_history_O'
    key_idx   = 'ai_history_idx_X' if ai_player_symbol == PLAYER_X else 'ai_history_idx_O'
    session[key_think] = ai_response_details
    hist = session[key_hist]
    hist.append(ai_response_details)
    session[key_hist] = hist
    session[key_idx] = len(hist)-1
    print(f"AI ({ai_player_symbol}) suggested move coordinates: {ai_move_coords}")

    if ai_move_coords and game.board[ai_move_coords[0]][ai_move_coords[1]] == ' ':
        print(f"AI ({ai_player_symbol}) making move at: {ai_move_coords}")
        game.make_move(ai_move_coords, ai_player_symbol)
        if game.current_winner:
            session['winner'] = ai_player_symbol
            session['game_over'] = True
            flash(f"Player {ai_player_symbol} (AI) wins!", "success")
        elif game.empty_squares() == 0:
            session['game_over'] = True
            flash("It's a tie!", "info")
    else: # AI failed to provide a valid move or get_ai_move returned None
        print(f"AI ({ai_player_symbol}) failed to provide a valid move or suggested an invalid one: {ai_move_coords}. Game stopped.")
        flash(f"AI ({ai_player_symbol} using {model_to_use}) failed to make a valid move. Game stopped.", "error")
        session['game_over'] = True
        # No winner is set. The game is simply over due to AI failure.
    
    # Save game with the next player's turn, and current game_over state
    save_game(game, next_player_symbol_after_ai, game_over=session.get('game_over', False))
    print(f"--- End AI Turn ({ai_player_symbol}). Next player: {next_player_symbol_after_ai} ---")
    return redirect(url_for('play_game')) # Redirect to play_game, which will handle next turn


@app.route('/move/<int:row>/<int:col>', methods=['GET'])
def player_move(row, col):
    game = get_game()
    player_making_the_move = session.get('current_player', PLAYER_X)

    if session.get('game_over', False):
        flash("Game is over. Please reset to play again.", "info")
        return redirect(url_for('play_game'))

    # Crucially, check if it's actually a human's turn based on session player types
    if session.get(f'player_{player_making_the_move}_type') != 'human':
        flash("It's not a human player's turn to click.", "warning")
        return redirect(url_for('play_game'))

    if game.board[row][col] != ' ':
        flash("Invalid move. Cell already taken.", "warning")
        return redirect(url_for('play_game'))

    # Human player makes their move
    game.make_move((row, col), player_making_the_move)
    if game.current_winner:
        session['winner'] = player_making_the_move
        session['game_over'] = True
        flash(f"Player {player_making_the_move} wins!", "success")
        # Determine next player just for save_game consistency, though game is over
        next_player_after_win = PLAYER_O if player_making_the_move == PLAYER_X else PLAYER_X
        save_game(game, next_player_after_win, game_over=True)
        return redirect(url_for('play_game'))
    elif game.empty_squares() == 0:
        session['game_over'] = True
        flash("It's a tie!", "info")
        next_player_after_tie = PLAYER_O if player_making_the_move == PLAYER_X else PLAYER_X
        save_game(game, next_player_after_tie, game_over=True)
        return redirect(url_for('play_game'))

    # Switch to the next player
    next_player_symbol = PLAYER_O if player_making_the_move == PLAYER_X else PLAYER_X
    save_game(game, next_player_symbol) # Game is not over, save state for next player

    # If the next player is AI, handle AI's turn
    next_player_type = session.get(f'player_{next_player_symbol}_type', 'human')
    if not session.get('game_over') and next_player_type.startswith('ai_'): # Check for any AI type
        # Instead of calling _handle_ai_turn directly, redirect to play_game.
        # play_game will then detect it's AI's turn and call _handle_ai_turn.
        # This keeps the control flow consistent.
        print(f"Human move done. Next player {next_player_symbol} is AI (type: {next_player_type}). Redirecting to play_game.")
        return redirect(url_for('play_game'))


    return redirect(url_for('play_game'))


@app.route('/reset', methods=['GET'])
def reset_game():
    session.pop('board', None)
    session.pop('current_player', None)
    session.pop('winner', None)
    session.pop('game_over', None)
    # Clear thinking logs
    session.pop('ai_thinking_X', None)
    session.pop('ai_thinking_O', None)
    flash("Game has been reset. Board cleared, player selections kept.", "info")
    return redirect(url_for('play_game')) # Redirect back to the game page to start fresh

@app.route('/navigate_history/<player_symbol>/<direction>', methods=['GET'])
def navigate_history(player_symbol, direction):
    key_hist  = 'ai_history_X'     if player_symbol==PLAYER_X else 'ai_history_O'
    key_idx   = 'ai_history_idx_X' if player_symbol==PLAYER_X else 'ai_history_idx_O'
    hist      = session.get(key_hist, [])
    idx       = session.get(key_idx, -1)
    if direction=='prev' and idx>0:
        session[key_idx] = idx-1
    if direction=='next' and idx < len(hist)-1:
        session[key_idx] = idx+1
    return redirect(url_for('play_game'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)
