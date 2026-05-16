import json
import random
from typing import Optional


def create_board() -> list[str]:
    """Create an empty 3x3 board."""
    return [""] * 9


def make_move(board: list[str], position: int, player: str) -> list[str]:
    """Place a player's mark on the board at the given position."""
    if board[position] != "":
        raise ValueError(f"Position {position} is already occupied")
    if player not in ("X", "O"):
        raise ValueError("Player must be 'X' or 'O'")
    new_board = list(board)
    new_board[position] = player
    return new_board


def check_winner(board: list[str]) -> Optional[str]:
    """Check the board for a winner.

    Returns:
        'X' if X wins,
        'O' if O wins,
        'draw' if board is full with no winner,
        None if game is still in progress.
    """
    win_patterns = [
        (0, 1, 2),
        (3, 4, 5),
        (6, 7, 8),  # rows
        (0, 3, 6),
        (1, 4, 7),
        (2, 5, 8),  # columns
        (0, 4, 8),
        (2, 4, 6),  # diagonals
    ]

    for a, b, c in win_patterns:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]

    if all(cell != "" for cell in board):
        return "draw"

    return None


def get_ai_move(board: list[str]) -> Optional[int]:
    """Get a move for the AI player.

    For 'easy' difficulty (default), picks a random empty cell.
    For 'medium', uses minimax algorithm.
    """
    # Easy difficulty: random empty cell
    empty_positions = [i for i, cell in enumerate(board) if cell == ""]
    if not empty_positions:
        return None
    return random.choice(empty_positions)


def minimax(board: list[str], is_maximizing: bool) -> int:
    """Minimax algorithm for Tic-Tac-Toe.

    AI plays as 'O' (minimizing), player plays as 'X' (maximizing).
    Returns the score of the board state.
    """
    result = check_winner(board)
    if result == "X":
        return -10
    elif result == "O":
        return 10
    elif result == "draw":
        return 0

    empty_positions = [i for i, cell in enumerate(board) if cell == ""]

    if is_maximizing:
        best_score = -float("inf")
        for pos in empty_positions:
            board[pos] = "X"
            score = minimax(board, False)
            board[pos] = ""
            best_score = max(score, best_score)
        return best_score
    else:
        best_score = float("inf")
        for pos in empty_positions:
            board[pos] = "O"
            score = minimax(board, True)
            board[pos] = ""
            best_score = min(score, best_score)
        return best_score


def get_ai_move_medium(board: list[str]) -> Optional[int]:
    """Get the best move for AI (O) using minimax."""
    empty_positions = [i for i, cell in enumerate(board) if cell == ""]
    if not empty_positions:
        return None

    best_score = float("inf")
    best_move = None
    for pos in empty_positions:
        board[pos] = "O"
        score = minimax(board, True)
        board[pos] = ""
        if score < best_score:
            best_score = score
            best_move = pos
    return best_move


def get_result_for_player(
    board: list[str], player_x_id: int, user_id: int
) -> Optional[str]:
    """Determine game result from the perspective of the given user.

    Returns:
        'win' if the user won,
        'lose' if the user lost,
        'draw' if the game is a draw,
        None if the game is still in progress.
    """
    winner = check_winner(board)
    if winner is None:
        return None
    if winner == "draw":
        return "draw"
    # Player X is always the human user
    if user_id == player_x_id:
        return "win" if winner == "X" else "lose"
    else:
        return "lose" if winner == "X" else "win"
