import json
import os
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional

from backend.database import init_db, get_db
from backend.schemas import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    GameResponse,
    GameListItem,
    MoveRequest,
)
from backend.auth import hash_password, verify_password, create_access_token, get_current_user
from backend.game import (
    create_board,
    make_move,
    check_winner,
    get_ai_move,
    get_result_for_player,
)

app = FastAPI(title="Tic-Tac-Toe API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Path to frontend static files
FRONTEND_STATIC = Path(__file__).resolve().parent.parent / "frontend" / "static"


# Serve static assets (CSS, JS) at /static/
if FRONTEND_STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_STATIC)), name="static")
else:
    # Create a placeholder so the app still works without frontend
    FRONTEND_STATIC.mkdir(parents=True, exist_ok=True)


@app.get("/")
def serve_index():
    """Serve the main SPA HTML page."""
    index_path = FRONTEND_STATIC / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Backend is running. Frontend not yet deployed."}


@app.on_event("startup")
def on_startup():
    """Initialize the database on application startup."""
    init_db()


# ─── Auth Endpoints ───────────────────────────────────────────────────────────


@app.post("/api/register", response_model=UserResponse, status_code=status.HTTP_200_OK)
def register(body: UserCreate):
    """Register a new user."""
    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM users WHERE username = ?", (body.username,)
        ).fetchone()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )

        password_hash = hash_password(body.password)
        cursor = db.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (body.username, password_hash),
        )
        user_id = cursor.lastrowid

    return UserResponse(id=user_id, username=body.username)


@app.post("/api/login", response_model=TokenResponse)
def login(body: UserLogin):
    """Authenticate a user and return a JWT token."""
    with get_db() as db:
        user = db.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (body.username,),
        ).fetchone()

        if not user or not verify_password(body.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        token = create_access_token(user["id"], user["username"])

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(id=user["id"], username=user["username"]),
    )


@app.get("/api/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user)):
    """Get the currently authenticated user's info."""
    with get_db() as db:
        user = db.execute(
            "SELECT id, username FROM users WHERE id = ?",
            (int(current_user["sub"]),),
        ).fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

    return UserResponse(id=user["id"], username=user["username"])


# ─── Game Endpoints ───────────────────────────────────────────────────────────


@app.post("/api/games", response_model=GameResponse, status_code=status.HTTP_201_CREATED)
def create_game(current_user: dict = Depends(get_current_user)):
    """Create a new game against the computer."""
    user_id = int(current_user["sub"])
    username = current_user["username"]
    board = create_board()
    board_json = json.dumps(board)

    with get_db() as db:
        cursor = db.execute(
            """INSERT INTO games (player_x_id, player_o, status, board, current_turn)
               VALUES (?, 'computer', 'in_progress', ?, 'X')""",
            (user_id, board_json),
        )
        game_id = cursor.lastrowid

    return GameResponse(
        id=game_id,
        board=board,
        status="in_progress",
        current_turn="X",
        winner=None,
        player_x=username,
        player_o="computer",
    )


@app.get("/api/games", response_model=list[GameListItem])
def list_games(current_user: dict = Depends(get_current_user)):
    """List all games for the current user with results."""
    user_id = int(current_user["sub"])

    with get_db() as db:
        rows = db.execute(
            """SELECT id, status, board, player_x_id, created_at
               FROM games WHERE player_x_id = ?
               ORDER BY created_at DESC""",
            (user_id,),
        ).fetchall()

    games = []
    for row in rows:
        board = json.loads(row["board"])
        result = get_result_for_player(board, row["player_x_id"], user_id)
        games.append(
            GameListItem(
                id=row["id"],
                status=row["status"],
                result=result,
                opponent="computer",
                created_at=row["created_at"],
            )
        )

    return games


@app.get("/api/games/{game_id}", response_model=GameResponse)
def get_game(game_id: int, current_user: dict = Depends(get_current_user)):
    """Get the state of a specific game."""
    user_id = int(current_user["sub"])

    with get_db() as db:
        row = db.execute(
            """SELECT g.id, g.board, g.status, g.current_turn, g.winner,
                      g.player_x_id, g.player_o, u.username as player_x_name
               FROM games g
               JOIN users u ON g.player_x_id = u.id
               WHERE g.id = ?""",
            (game_id,),
        ).fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found",
            )

        if row["player_x_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this game",
            )

    board = json.loads(row["board"])
    return GameResponse(
        id=row["id"],
        board=board,
        status=row["status"],
        current_turn=row["current_turn"] if row["status"] == "in_progress" else "",
        winner=row["winner"],
        player_x=row["player_x_name"],
        player_o=row["player_o"],
    )


@app.post("/api/games/{game_id}/move", response_model=GameResponse)
def make_player_move(
    game_id: int,
    body: MoveRequest,
    current_user: dict = Depends(get_current_user),
):
    """Make a move in a game. After the player's move, the AI automatically moves."""
    user_id = int(current_user["sub"])
    position = body.position

    with get_db() as db:
        # Fetch game
        row = db.execute(
            """SELECT g.*, u.username as player_x_name
               FROM games g
               JOIN users u ON g.player_x_id = u.id
               WHERE g.id = ?""",
            (game_id,),
        ).fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Game not found",
            )

        if row["player_x_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this game",
            )

        if row["status"] != "in_progress":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Game is already finished",
            )

        board = json.loads(row["board"])
        current_turn = row["current_turn"]

        # Must be player's turn (X)
        if current_turn != "X":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Not your turn",
            )

        # Make player's move
        if board[position] != "":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Position already occupied",
            )

        board = make_move(board, position, "X")
        winner = check_winner(board)

        if winner is not None:
            # Game over
            status_val = "finished"
            if winner == "draw":
                winner_str = "draw"
            else:
                winner_str = winner
            db.execute(
                """UPDATE games SET board = ?, status = ?, winner = ?, finished_at = datetime('now')
                   WHERE id = ?""",
                (json.dumps(board), status_val, winner_str, game_id),
            )
        else:
            # AI's turn (O)
            ai_position = get_ai_move(board)
            if ai_position is not None:
                board = make_move(board, ai_position, "O")
                winner = check_winner(board)

                if winner is not None:
                    status_val = "finished"
                    if winner == "draw":
                        winner_str = "draw"
                    else:
                        winner_str = winner
                    current_turn = ""
                else:
                    status_val = "in_progress"
                    winner_str = None
                    current_turn = "X"

                db.execute(
                    """UPDATE games SET board = ?, status = ?, current_turn = ?, winner = ?,
                          finished_at = CASE WHEN ? = 'finished' THEN datetime('now') ELSE NULL END
                       WHERE id = ?""",
                    (
                        json.dumps(board),
                        status_val,
                        current_turn,
                        winner_str,
                        status_val,
                        game_id,
                    ),
                )
            else:
                # No empty positions (shouldn't happen if not winner, but just in case)
                status_val = "finished"
                winner_str = "draw"
                db.execute(
                    """UPDATE games SET board = ?, status = ?, winner = ?, finished_at = datetime('now')
                       WHERE id = ?""",
                    (json.dumps(board), status_val, winner_str, game_id),
                )

    # Return final state
    with get_db() as db:
        row = db.execute(
            """SELECT g.*, u.username as player_x_name
               FROM games g
               JOIN users u ON g.player_x_id = u.id
               WHERE g.id = ?""",
            (game_id,),
        ).fetchone()

    board = json.loads(row["board"])
    return GameResponse(
        id=row["id"],
        board=board,
        status=row["status"],
        current_turn=row["current_turn"] if row["status"] == "in_progress" else "",
        winner=row["winner"],
        player_x=row["player_x_name"],
        player_o=row["player_o"],
    )


# Catch-all route for SPA: serve index.html for any unmatched GET request
# that is not an API route or static file
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve index.html for any unmatched path (SPA fallback)."""
    if full_path.startswith("api/") or full_path.startswith("static/"):
        raise HTTPException(status_code=404, detail="Not found")
    index_path = FRONTEND_STATIC / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    raise HTTPException(status_code=404, detail="Not found")
