import json

class TicTacToe:
    def __init__(self):
        self.board = [[' ' for _ in range(3)] for _ in range(3)]
        self.current_winner = None

    def print_board(self):
        for row in self.board:
            print('| ' + ' | '.join(row) + ' |')

    def available_moves(self):
        moves = []
        for i, row in enumerate(self.board):
            for j, spot in enumerate(row):
                if spot == ' ':
                    moves.append((i, j))
        return moves

    def empty_squares(self):
        return self.board_count(' ')

    def board_count(self, char):
        count = 0
        for row in self.board:
            for spot in row:
                if spot == char:
                    count +=1
        return count

    def make_move(self, square, letter):
        if self.board[square[0]][square[1]] == ' ':
            self.board[square[0]][square[1]] = letter
            if self.winner(square, letter):
                self.current_winner = letter
            return True
        return False

    def winner(self, square, letter):
        # Check row
        row_ind = square[0]
        if all([spot == letter for spot in self.board[row_ind]]):
            return True
        # Check column
        col_ind = square[1]
        if all([self.board[i][col_ind] == letter for i in range(3)]):
            return True
        # Check diagonals
        if square[0] == square[1]: # Diagonal from top-left to bottom-right
            if all([self.board[i][i] == letter for i in range(3)]):
                return True
        if square[0] + square[1] == 2: # Diagonal from top-right to bottom-left
            if all([self.board[i][2-i] == letter for i in range(3)]):
                return True
        return False

    def get_board_string(self):
        board_str = ""
        for r_idx, row in enumerate(self.board):
            row_str = []
            for c_idx, spot in enumerate(row):
                # Represent empty spots with a space, otherwise use the player's letter (X or O)
                row_str.append(spot if spot != ' ' else ' ') 
            board_str += " | ".join(row_str) + "\n"
            if r_idx < 2:
                board_str += "---------\n"
        return board_str

    def get_board_as_json_string(self):
        # Returns a JSON string representing the board state.
        # Empty cells are represented by a single space " ".
        return json.dumps({"board": self.board})
    
    def reset(self):
        self.board = [[' ' for _ in range(3)] for _ in range(3)]
        self.current_winner = None
