import requests
import json
import re

OLLAMA_API_URL = "http://localhost:11434/api/generate" # Default Ollama API URL
MAX_RETRIES = 5
REQUEST_TIMEOUT = 180 # Increased timeout to 180 seconds

def get_ai_move(board_json_string, available_moves_list, model_name, player_symbol='O', is_thinking_model=False):
    if not available_moves_list:
        print("Warning: get_ai_move called with no available moves.")
        return None, "No available moves."
        
    formatted_available_moves = ", ".join([f"({r},{c})" for r, c in available_moves_list])
    
    # Ensure model_name is exactly as listed in `ollama list`
    # For example, if `ollama list` shows `qwen:7b-chat-q4_0`, then model_name should be that.
    # The value "qwen3" used in app.py might need to be more specific.
    print(f"Attempting to use model: '{model_name}'. Verify this matches 'ollama list'.")

    # Always instruct the model to use <think> tags for its thought process.
    # The is_thinking_model flag is still used for response parsing.
    prompt_instruction = f"""
First, think step-by-step within <think></think> tags.
Analyze the board, consider your opponent's potential moves, and strategize to win or draw.
After your thought process inside the <think></think> tags, you MUST output your chosen move.
Output only the chosen coordinates in the format (row,col). For example: (0,1)
Do not provide any other explanation or text outside the <think></think> tags or after the final move.
"""

    # System prompt to explain coordinate system
    system_instructions = """
Coordinate system for moves:
• Coordinates are given as (row,col).
• Rows are numbered 0 (top) to 2 (bottom).
• Columns are numbered 0 (left) to 2 (right).
Examples:
- Top-left corner is (0,0)
- Top-right corner is (0,2)
- Bottom-left corner is (2,0)
- Bottom-right corner is (2,2)
- Center is (1,1)
"""
    current_prompt = f"""
{system_instructions}
You are an expert Tic Tac Toe player. You are playing as '{player_symbol}'.
The current board state is represented by the following JSON object:
{board_json_string}
In the JSON, " " denotes an empty cell.

Your available moves are: [{formatted_available_moves}].
You MUST choose exactly one move from this list of available moves.
{prompt_instruction}
Your move:
"""

    ai_response_details = ""  # To store AI's thinking process
    for attempt in range(MAX_RETRIES):
        print(f"AI ({player_symbol} using {model_name}) attempt {attempt + 1}/{MAX_RETRIES}")
        payload = {
            "model": model_name, 
            "prompt": current_prompt,
            "stream": False,
            # "options": {"temperature": 0.3} # Optional: Add model options if needed
        }
        
        try:
            print(f"Sending prompt to Ollama for AI ({player_symbol} with {model_name}). API: {OLLAMA_API_URL}")
            print(f"Payload: {json.dumps(payload, indent=2)}") # Log the exact payload
            response = requests.post(OLLAMA_API_URL, json=payload, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            
            response_data = response.json()
            print(f"Raw AI Response Data (Attempt {attempt + 1}): {response_data}")

            full_response_content = response_data.get("response", "").strip()
            ai_response_details += f"Attempt {attempt + 1}: {full_response_content}\n"  # Append AI response details
            
            if not full_response_content:
                print(f"AI response content is empty (Attempt {attempt + 1}).")
                current_prompt = f"""Your previous response was empty. Please try again.
You are playing Tic Tac Toe. You are '{player_symbol}'.
The current board is:
{board_json_string}
Your available moves are: [{formatted_available_moves}].
You MUST choose exactly one move from this list.
Output only the chosen coordinates in the format (row,col). For example: (0,1)
Your move:"""
                continue

            print(f"AI Response Content (Attempt {attempt + 1}): '{full_response_content}'")

            # Find all occurrences of (row,col)
            all_matches = list(re.finditer(r'\((\d+),(\d+)\)', full_response_content))
            
            parsed_move = None
            
            if is_thinking_model:
                think_end_tag = "</think>"
                if think_end_tag in full_response_content:
                    content_after_think = full_response_content.split(think_end_tag, 1)[-1].strip()
                    # Find all matches *after* the </think> tag
                    matches_after_think = list(re.finditer(r'\((\d+),(\d+)\)', content_after_think))
                    if matches_after_think:
                        # Get the last match after </think>
                        last_match_after_think = matches_after_think[-1]
                        row, col = int(last_match_after_think.group(1)), int(last_match_after_think.group(2))
                        parsed_move = (row, col)
                        print(f"AI (thinking model) found move {parsed_move} after </think> tag.")
                    else:
                        print(f"AI (thinking model) used </think> tag but no move found after it. Checking entire response for last move.")
                else:
                    print(f"AI (thinking model) did not use </think> tag. Checking entire response for last move.")
            
            # If not a thinking model, or if a thinking model didn't provide a clear move after <think>
            if parsed_move is None and all_matches:
                # Get the last match from the entire response
                last_match = all_matches[-1]
                row, col = int(last_match.group(1)), int(last_match.group(2))
                parsed_move = (row, col)
                print(f"Using last found move {parsed_move} from the entire response.")
            
            if parsed_move:
                if parsed_move in available_moves_list:
                    print(f"AI parsed valid move: {parsed_move} (Attempt {attempt + 1})")
                    return parsed_move, ai_response_details
                else:
                    print(f"AI returned a move {parsed_move} NOT in available list {available_moves_list} (Attempt {attempt + 1}).")
                    current_prompt = f"""Your previous move {parsed_move} was not in the list of available moves.
You are playing Tic Tac Toe. You are '{player_symbol}'.
The current board is:
{board_json_string}
Your available moves are: [{formatted_available_moves}].
You MUST choose exactly one move from this list.
Output only the chosen coordinates in the format (row,col).
Your move:"""
            else:
                print(f"Could not parse AI move (r,c) from response: '{full_response_content}' (Attempt {attempt + 1}).")
                current_prompt = f"""Your previous response '{full_response_content}' was not in the correct format (row,col).
You are playing Tic Tac Toe. You are '{player_symbol}'.
The current board is:
{board_json_string}
Your available moves are: [{formatted_available_moves}].
You MUST choose exactly one move from this list.
Output only the chosen coordinates in the format (row,col).
Your move:"""

        except requests.exceptions.Timeout:
            print(f"Error communicating with Ollama: Request timed out after {REQUEST_TIMEOUT} seconds (Attempt {attempt + 1}).")
            ai_response_details += f"Attempt {attempt + 1}: Timeout error.\n"
        except requests.exceptions.RequestException as e:
            print(f"Error communicating with Ollama: {e} (Attempt {attempt + 1}).")
            ai_response_details += f"Attempt {attempt + 1}: Request error - {e}.\n"
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON response from Ollama: {e} (Attempt {attempt + 1}).")
            ai_response_details += f"Attempt {attempt + 1}: JSON decode error.\n"
        except Exception as e:
            print(f"An unexpected error occurred in get_ai_move: {e} (Attempt {attempt + 1}).")
            ai_response_details += f"Attempt {attempt + 1}: Unexpected error - {e}.\n"
    
    print(f"AI failed to provide a valid move after {MAX_RETRIES} attempts.")
    ai_response_details += "AI failed to provide a valid move after maximum attempts.\n"
    return None, ai_response_details
