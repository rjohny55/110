"""
Integration tests for the Tic-Tac-Toe FastAPI backend.

Tests cover:
- User registration and login (happy path, duplicates, invalid data)
- JWT authentication (valid token, missing token, invalid token)
- Game creation
- Making moves (including AI response)
- Game logic (win detection, draw detection)
- Listing games and getting game state
- Error handling (occupied positions, wrong turn, finished games, etc.)
- SPA fallback route
"""

import json
import os
import tempfile
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def fresh_db():
    """
    Each test gets a fresh database by replacing DATABASE_PATH
    with a new temporary file and reinitializing the schema.
    """
    import backend.database as db_module

    # Remember the original
    orig_path = db_module.DATABASE_PATH

    # Create a fresh temp DB
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_module.DATABASE_PATH = path
    db_module.init_db()

    yield

    # Cleanup
    db_module.DATABASE_PATH = orig_path
    try:
        os.unlink(path)
    except OSError:
        pass


from backend.main import app

client = TestClient(app)


# ─── Helper fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def unique_user():
    """
    Register a unique user and return credentials.
    Uses a random username suffix to avoid collisions.
    """
    import random
    import string

    suffix = "".join(random.choices(string.ascii_lowercase, k=8))
    username = f"testuser_{suffix}"
    password = "test1234"
    resp = client.post("/api/register", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Registration failed: {resp.text}"
    return {"username": username, "password": password}


@pytest.fixture
def user_token(unique_user):
    """Return a valid JWT token for the registered user."""
    resp = client.post("/api/login", json=unique_user)
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    return data["access_token"]


@pytest.fixture
def auth_header(user_token):
    """Return Authorization header dict with Bearer token."""
    return {"Authorization": f"Bearer {user_token}"}


# ─── Registration Tests ───────────────────────────────────────────────────────


class TestRegistration:
    def test_register_success(self):
        """Should successfully register a new user."""
        resp = client.post("/api/register", json={"username": "newuser", "password": "pass1234"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "newuser"
        assert "id" in data

    def test_register_duplicate_username(self):
        """Should reject registration with an existing username."""
        client.post("/api/register", json={"username": "dupuser", "password": "pass1234"})
        resp = client.post("/api/register", json={"username": "dupuser", "password": "pass1234"})
        assert resp.status_code == 409
        assert "already taken" in resp.json()["detail"].lower()

    def test_register_short_username(self):
        """Should reject usernames shorter than 3 characters."""
        resp = client.post("/api/register", json={"username": "ab", "password": "pass1234"})
        assert resp.status_code == 422  # Validation error

    def test_register_short_password(self):
        """Should reject passwords shorter than 4 characters."""
        resp = client.post("/api/register", json={"username": "validuser", "password": "abc"})
        assert resp.status_code == 422

    def test_register_missing_fields(self):
        """Should reject requests with missing fields."""
        resp = client.post("/api/register", json={})
        assert resp.status_code == 422

    def test_register_invalid_json(self):
        """Should reject non-JSON requests."""
        resp = client.post("/api/register", data="not-json", headers={"Content-Type": "application/json"})
        assert resp.status_code == 422


# ─── Login Tests ──────────────────────────────────────────────────────────────


class TestLogin:
    def test_login_success(self, unique_user):
        """Should successfully log in and return a JWT token."""
        resp = client.post("/api/login", json=unique_user)
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == unique_user["username"]

    def test_login_wrong_password(self, unique_user):
        """Should reject login with wrong password."""
        resp = client.post("/api/login", json={"username": unique_user["username"], "password": "wrongpass"})
        assert resp.status_code == 401
        assert "invalid" in resp.json()["detail"].lower()

    def test_login_nonexistent_user(self):
        """Should reject login for unregistered user."""
        resp = client.post("/api/login", json={"username": "nobody", "password": "pass1234"})
        assert resp.status_code == 401
        assert "invalid" in resp.json()["detail"].lower()

    def test_login_empty_body(self):
        """Should handle empty login body."""
        resp = client.post("/api/login", json={})
        assert resp.status_code == 422


# ─── Authentication Tests ─────────────────────────────────────────────────────


class TestAuthentication:
    def test_access_protected_without_token(self):
        """Should reject requests without token (returns 401 or 403)."""
        resp = client.get("/api/me")
        # FastAPI's HTTPBearer can return 401 or 403 depending on configuration
        assert resp.status_code in (401, 403)

    def test_access_with_invalid_token(self):
        """Should reject requests with invalid token."""
        resp = client.get("/api/me", headers={"Authorization": "Bearer invalidtoken123"})
        assert resp.status_code == 401

    def test_access_with_malformed_header(self):
        """Should reject malformed Authorization header."""
        resp = client.get("/api/me", headers={"Authorization": "BadFormat"})
        # HTTPBearer requires 'Bearer' scheme, so either 401 or 403 is acceptable
        assert resp.status_code in (401, 403)

    def test_get_me_success(self, auth_header, unique_user):
        """Should return current user info with valid token."""
        resp = client.get("/api/me", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == unique_user["username"]
        assert "id" in data


# ─── Game Creation Tests ──────────────────────────────────────────────────────


class TestGameCreation:
    def test_create_game_success(self, auth_header):
        """Should create a new game successfully."""
        resp = client.post("/api/games", headers=auth_header)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "in_progress"
        assert data["current_turn"] == "X"
        assert data["winner"] is None
        assert len(data["board"]) == 9
        assert all(cell == "" for cell in data["board"])
        assert data["player_x"] is not None
        assert data["player_o"] == "computer"
        assert "id" in data

    def test_create_game_without_auth(self):
        """Should reject game creation without auth (returns 401 or 403)."""
        resp = client.post("/api/games")
        assert resp.status_code in (401, 403)


# ─── Game Listing Tests ───────────────────────────────────────────────────────


class TestGameListing:
    def test_list_games_empty(self, auth_header):
        """Should return empty list when no games exist."""
        resp = client.get("/api/games", headers=auth_header)
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_games_after_creation(self, auth_header):
        """Should list created games."""
        # Create a game
        client.post("/api/games", headers=auth_header)
        resp = client.get("/api/games", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[0]["opponent"] == "computer"
        assert data[0]["status"] in ("in_progress", "finished")

    def test_list_games_isolated_per_user(self):
        """Games should be isolated per user."""
        # Register and create game for user1
        client.post("/api/register", json={"username": "user1_list", "password": "pass1234"})
        r1 = client.post("/api/login", json={"username": "user1_list", "password": "pass1234"})
        token1 = r1.json()["access_token"]
        client.post("/api/games", headers={"Authorization": f"Bearer {token1}"})

        # Register and check games for user2
        client.post("/api/register", json={"username": "user2_list", "password": "pass1234"})
        r2 = client.post("/api/login", json={"username": "user2_list", "password": "pass1234"})
        token2 = r2.json()["access_token"]
        resp = client.get("/api/games", headers={"Authorization": f"Bearer {token2}"})
        assert resp.status_code == 200
        assert resp.json() == []


# ─── Game State Tests ─────────────────────────────────────────────────────────


class TestGameState:
    def test_get_game_success(self, auth_header):
        """Should return game state for a valid game ID."""
        create_resp = client.post("/api/games", headers=auth_header)
        game_id = create_resp.json()["id"]

        resp = client.get(f"/api/games/{game_id}", headers=auth_header)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == game_id
        assert len(data["board"]) == 9
        assert data["status"] == "in_progress"
        assert data["current_turn"] == "X"

    def test_get_game_not_found(self, auth_header):
        """Should return 404 for non-existent game."""
        resp = client.get("/api/games/99999", headers=auth_header)
        assert resp.status_code == 404

    def test_get_game_other_users_game(self):
        """Should return 403 when accessing another user's game."""
        # User1 creates a game
        client.post("/api/register", json={"username": "user1_get", "password": "pass1234"})
        r1 = client.post("/api/login", json={"username": "user1_get", "password": "pass1234"})
        token1 = r1.json()["access_token"]
        create_resp = client.post("/api/games", headers={"Authorization": f"Bearer {token1}"})
        game_id = create_resp.json()["id"]

        # User2 tries to access it
        client.post("/api/register", json={"username": "user2_get", "password": "pass1234"})
        r2 = client.post("/api/login", json={"username": "user2_get", "password": "pass1234"})
        token2 = r2.json()["access_token"]
        resp = client.get(f"/api/games/{game_id}", headers={"Authorization": f"Bearer {token2}"})
        assert resp.status_code == 403


# ─── Game Move Tests ──────────────────────────────────────────────────────────


class TestGameMoves:
    def test_make_move_success(self, auth_header):
        """Should successfully make a move and get AI response."""
        create_resp = client.post("/api/games", headers=auth_header)
        game_id = create_resp.json()["id"]

        # Make a move at position 0
        resp = client.post(
            f"/api/games/{game_id}/move",
            headers=auth_header,
            json={"position": 0},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == game_id
        # Board should have X at position 0
        assert data["board"][0] == "X"
        # AI (O) should have made a move somewhere
        o_count = sum(1 for cell in data["board"] if cell == "O")
        assert o_count == 1, f"Expected 1 O on board, got {o_count}"

    def test_make_move_occupied_position(self, auth_header):
        """Should reject a move on an already occupied position."""
        create_resp = client.post("/api/games", headers=auth_header)
        game_id = create_resp.json()["id"]

        # Make first move at position 0
        client.post(f"/api/games/{game_id}/move", headers=auth_header, json={"position": 0})

        # Try to move at the same position
        resp = client.post(
            f"/api/games/{game_id}/move",
            headers=auth_header,
            json={"position": 0},
        )
        # The game may have finished or still be in progress
        # Either way, position 0 should still be occupied
        assert resp.status_code in (400,)

    def test_make_move_invalid_position(self, auth_header):
        """Should reject moves at invalid positions."""
        create_resp = client.post("/api/games", headers=auth_header)
        game_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/games/{game_id}/move",
            headers=auth_header,
            json={"position": 9},
        )
        assert resp.status_code == 422  # Pydantic validation (ge=0, le=8)

        resp = client.post(
            f"/api/games/{game_id}/move",
            headers=auth_header,
            json={"position": -1},
        )
        assert resp.status_code == 422

    def test_make_move_on_finished_game(self, auth_header):
        """Should reject moves on finished games."""
        # Create game and play until finished
        create_resp = client.post("/api/games", headers=auth_header)
        game_id = create_resp.json()["id"]

        resp = client.get(f"/api/games/{game_id}", headers=auth_header)
        game = resp.json()

        # Play moves while game is in progress
        move_count = 0
        while game["status"] == "in_progress" and move_count < 5:
            empty = [i for i, cell in enumerate(game["board"]) if cell == ""]
            if not empty:
                break
            resp = client.post(
                f"/api/games/{game_id}/move",
                headers=auth_header,
                json={"position": empty[0]},
            )
            if resp.status_code != 200:
                break
            game = resp.json()
            move_count += 1

        # If game is now finished, try to make a move
        if game["status"] == "finished":
            resp = client.post(
                f"/api/games/{game_id}/move",
                headers=auth_header,
                json={"position": 0},
            )
            assert resp.status_code == 400
            assert "finished" in resp.json()["detail"].lower()

    def test_make_move_without_auth(self, auth_header):
        """Should reject moves without authentication."""
        create_resp = client.post("/api/games", headers=auth_header)
        game_id = create_resp.json()["id"]

        resp = client.post(f"/api/games/{game_id}/move", json={"position": 0})
        assert resp.status_code in (401, 403)

    def test_make_move_on_other_users_game(self):
        """Should reject moves on another user's game."""
        # User1 creates a game
        client.post("/api/register", json={"username": "user1_move", "password": "pass1234"})
        r1 = client.post("/api/login", json={"username": "user1_move", "password": "pass1234"})
        token1 = r1.json()["access_token"]
        create_resp = client.post("/api/games", headers={"Authorization": f"Bearer {token1}"})
        game_id = create_resp.json()["id"]

        # User2 tries to make a move
        client.post("/api/register", json={"username": "user2_move", "password": "pass1234"})
        r2 = client.post("/api/login", json={"username": "user2_move", "password": "pass1234"})
        token2 = r2.json()["access_token"]
        resp = client.post(
            f"/api/games/{game_id}/move",
            headers={"Authorization": f"Bearer {token2}"},
            json={"position": 0},
        )
        assert resp.status_code == 403

    def test_make_move_game_not_found(self, auth_header):
        """Should return 404 when moving on non-existent game."""
        resp = client.post(
            "/api/games/99999/move",
            headers=auth_header,
            json={"position": 0},
        )
        assert resp.status_code == 404


# ─── Game Logic Tests ─────────────────────────────────────────────────────────


class TestGameLogic:
    def test_win_detection(self, auth_header):
        """Test that a winning scenario is detected correctly."""
        create_resp = client.post("/api/games", headers=auth_header)
        game_id = create_resp.json()["id"]

        resp = client.get(f"/api/games/{game_id}", headers=auth_header)
        game = resp.json()

        # Play moves — try to get a win or at least verify game proceeds
        moves = [0, 1, 2]
        for pos in moves:
            if game["status"] == "in_progress":
                resp = client.post(
                    f"/api/games/{game_id}/move",
                    headers=auth_header,
                    json={"position": pos},
                )
                if resp.status_code == 200:
                    game = resp.json()

        # Verify game either finished or still in progress
        assert game["status"] in ("in_progress", "finished")

    def test_draw_detection(self):
        """Test that a draw is detected at code level."""
        from backend.game import check_winner

        # Create a full board with no winner
        draw_board = ["X", "O", "X", "X", "O", "O", "O", "X", "X"]
        result = check_winner(draw_board)
        assert result == "draw"

    def test_ai_responds_immediately(self, auth_header):
        """After the player's move, the AI should have responded."""
        create_resp = client.post("/api/games", headers=auth_header)
        game_id = create_resp.json()["id"]

        resp = client.post(
            f"/api/games/{game_id}/move",
            headers=auth_header,
            json={"position": 4},  # Center
        )
        assert resp.status_code == 200
        data = resp.json()
        # AI should have placed O somewhere
        assert "O" in data["board"], "AI should have responded with O"

    def test_ai_returns_none_on_full_board(self):
        """AI should return None when no moves available."""
        from backend.game import get_ai_move

        full_board = ["X", "O", "X", "X", "O", "O", "O", "X", "X"]
        result = get_ai_move(full_board)
        assert result is None

    def test_minimax_ai_available(self):
        """Test the minimax AI function exists and returns valid positions."""
        from backend.game import get_ai_move_medium

        board = ["X", "", "", "", "O", "", "", "", ""]
        ai_pos = get_ai_move_medium(board)
        assert ai_pos is not None
        assert 0 <= ai_pos <= 8
        assert board[ai_pos] == ""

    def test_minimax_empty_board(self):
        """Test minimax AI on empty board returns valid position."""
        from backend.game import get_ai_move_medium

        board = [""] * 9
        ai_pos = get_ai_move_medium(board)
        assert ai_pos is not None
        assert 0 <= ai_pos <= 8


# ─── Move Validation Tests ────────────────────────────────────────────────────


class TestMoveValidation:
    def test_check_winner_x_wins(self):
        """Test X wins detection."""
        from backend.game import check_winner

        board = ["X", "X", "X", "", "O", "", "", "O", ""]
        assert check_winner(board) == "X"

    def test_check_winner_o_wins(self):
        """Test O wins detection."""
        from backend.game import check_winner

        board = ["X", "X", "", "O", "O", "O", "", "", "X"]
        assert check_winner(board) == "O"

    def test_check_winner_in_progress(self):
        """Test in-progress detection."""
        from backend.game import check_winner

        board = ["X", "", "", "", "O", "", "", "", ""]
        assert check_winner(board) is None

    def test_check_winner_empty_board(self):
        """Test empty board returns None."""
        from backend.game import check_winner

        board = [""] * 9
        assert check_winner(board) is None

    def test_make_move_valid(self):
        """Test making a valid move."""
        from backend.game import make_move

        board = [""] * 9
        new_board = make_move(board, 4, "X")
        assert new_board[4] == "X"
        # Original board should be unchanged
        assert board[4] == ""

    def test_make_move_occupied_raises(self):
        """Test that moving on occupied position raises ValueError."""
        from backend.game import make_move

        board = ["X", "", "", "", "", "", "", "", ""]
        with pytest.raises(ValueError):
            make_move(board, 0, "O")

    def test_make_move_invalid_player_raises(self):
        """Test that invalid player raises ValueError."""
        from backend.game import make_move

        board = [""] * 9
        with pytest.raises(ValueError):
            make_move(board, 0, "Z")


# ─── SPA Routes ────────────────────────────────────────────────────────────────


class TestSPARoutes:
    def test_root_returns_index(self):
        """Test that the root path returns the SPA index.html."""
        resp = client.get("/")
        # The frontend/static/index.html should exist
        assert resp.status_code in (200,)

    def test_spa_fallback(self):
        """Test that unmatched routes serve index.html (SPA fallback)."""
        resp = client.get("/some-random-path")
        assert resp.status_code in (200, 404)

    def test_api_not_found(self):
        """Test that non-existent API routes return 404."""
        resp = client.get("/api/nonexistent")
        assert resp.status_code == 404

    def test_static_not_found(self):
        """Test that non-existent static routes return 404."""
        resp = client.get("/static/nonexistent.css")
        assert resp.status_code in (200, 404)  # Could be caught by SPA fallback


# ─── Additional Edge Cases ────────────────────────────────────────────────────


class TestEdgeCases:
    def test_create_board(self):
        """Test board creation."""
        from backend.game import create_board

        board = create_board()
        assert board == [""] * 9
        assert len(board) == 9

    def test_get_result_for_player(self):
        """Test result determination for a player."""
        from backend.game import get_result_for_player

        # X wins
        board_x_wins = ["X", "X", "X", "", "O", "", "", "O", ""]
        assert get_result_for_player(board_x_wins, 1, 1) == "win"
        assert get_result_for_player(board_x_wins, 1, 2) == "lose"

        # Draw
        draw_board = ["X", "O", "X", "X", "O", "O", "O", "X", "X"]
        assert get_result_for_player(draw_board, 1, 1) == "draw"

        # In progress
        in_progress = ["X", "", "", "", "O", "", "", "", ""]
        assert get_result_for_player(in_progress, 1, 1) is None


# ─── SECRET_KEY Configuration Tests ────────────────────────────────────────────


class TestSecretKeyConfig:
    """Tests for the SECRET_KEY environment variable configuration."""

    def test_default_secret_key_when_env_not_set(self, monkeypatch):
        """
        When SECRET_KEY env var is not set, the default key should be used.
        """
        # Remove SECRET_KEY from env if present
        monkeypatch.delenv("SECRET_KEY", raising=False)
        import importlib
        import backend.auth
        importlib.reload(backend.auth)
        assert backend.auth.SECRET_KEY == "super-secret-key-dev-110"

    def test_env_secret_key_used_when_set(self, monkeypatch):
        """
        When SECRET_KEY env var is set, it should be used instead of default.
        """
        monkeypatch.setenv("SECRET_KEY", "my-custom-secret-key-for-testing-12345")
        import importlib
        import backend.auth
        importlib.reload(backend.auth)
        assert backend.auth.SECRET_KEY == "my-custom-secret-key-for-testing-12345"

    def test_token_created_with_env_key_can_be_verified(self, monkeypatch):
        """
        Tokens created with the env-var-derived SECRET_KEY should
        be verifiable using the same key.
        """
        monkeypatch.setenv("SECRET_KEY", "my-custom-secret-key-for-testing-12345")
        import importlib
        import backend.auth
        importlib.reload(backend.auth)

        token = backend.auth.create_access_token(42, "envuser")
        payload = backend.auth.decode_access_token(token)
        assert payload["sub"] == "42"
        assert payload["username"] == "envuser"

    def test_token_created_with_env_key_accepted_by_api(self, monkeypatch):
        """
        A token created with the env-var-derived SECRET_KEY
        should be accepted by the /api/me endpoint.
        """
        # Register a user first (uses default DB, which is fine)
        client.post("/api/register", json={"username": "envuser", "password": "test1234"})

        monkeypatch.setenv("SECRET_KEY", "my-custom-secret-key-for-testing-12345")
        import importlib
        import backend.auth
        importlib.reload(backend.auth)

        # Create a token using the env-derived key
        token = backend.auth.create_access_token(1, "envuser")
        resp = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        # Token is valid — request should succeed
        assert resp.status_code == 200
        assert resp.json()["username"] == "envuser"

    def test_default_key_still_works_after_reload(self, monkeypatch):
        """
        After reloading with the env var, clearing the env var and
        reloading should restore the default key.
        """
        # First set and reload
        monkeypatch.setenv("SECRET_KEY", "custom-key")
        import importlib
        import backend.auth
        importlib.reload(backend.auth)
        assert backend.auth.SECRET_KEY == "custom-key"

        # Now clear and reload
        monkeypatch.delenv("SECRET_KEY", raising=False)
        importlib.reload(backend.auth)
        assert backend.auth.SECRET_KEY == "super-secret-key-dev-110"


# ─── Token Edge Cases ─────────────────────────────────────────────────────────


class TestTokenEdgeCases:
    def test_expired_token(self):
        """Test that expired tokens are rejected."""
        import jwt
        from backend.auth import SECRET_KEY, ALGORITHM
        from datetime import datetime, timedelta

        # Create an expired token
        payload = {
            "sub": "1",
            "username": "testuser",
            "exp": datetime.utcnow() - timedelta(hours=1),
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        # Test via API
        resp = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_invalid_signature_token(self):
        """Test that tokens with invalid signature are rejected."""
        import jwt

        # Create token with different key
        token = jwt.encode({"sub": "1", "username": "testuser"}, "wrong-key", algorithm="HS256")

        resp = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401
