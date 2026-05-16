# Tic-Tac-Toe Game

A full-stack Tic-Tac-Toe web application with a **FastAPI** backend and a single-page application (SPA) frontend. Players can register, log in, play against an AI opponent, and review their game history.

## Modules

### Backend: FastAPI + SQLite + JWT Auth + Game Logic

The backend is a Python-based REST API built with FastAPI. It provides:

- **User Authentication**: Register and log in with username/password. Passwords are hashed with bcrypt, and authenticated sessions use JWT (JSON Web Tokens).
- **Game Management**: Create new games, make moves, and retrieve game state and history. Each game is played against an AI opponent.
- **AI Opponent**: The computer player uses a configurable AI strategy — random move selection (easy) or minimax algorithm (medium).
- **Database**: SQLite with WAL mode for concurrent access. Tables for `users` and `games` are auto-initialized on startup.
- **Static File Serving**: The backend serves the frontend SPA assets (HTML, CSS, JS) at the `/static/` path and provides a catch-all route for SPA client-side routing.
- **CORS**: Enabled for all origins during development.

**API Endpoints:**

| Method | Path                     | Description                          | Auth Required |
|--------|--------------------------|--------------------------------------|---------------|
| POST   | `/api/register`          | Register a new user                  | No            |
| POST   | `/api/login`             | Log in and receive a JWT token       | No            |
| GET    | `/api/me`                | Get current authenticated user info  | Yes           |
| POST   | `/api/games`             | Create a new game vs computer        | Yes           |
| GET    | `/api/games`             | List all games for current user      | Yes           |
| GET    | `/api/games/{game_id}`   | Get a specific game state            | Yes           |
| POST   | `/api/games/{game_id}/move` | Make a move in a game (player X), AI responds automatically (O) | Yes |

### Frontend: HTML + CSS + JavaScript (SPA)

The frontend is a single-page application (SPA) built with vanilla JavaScript. It features:

- **Login Screen**: Username/password form with error handling.
- **Registration Screen**: Create a new account with password confirmation and client-side validation.
- **Dashboard**: Shows the user's game history in a sortable table with results (win/lose/draw) and provides a button to start a new game.
- **Game Screen**: Interactive 3×3 board where the player (X) plays against the computer (O). Winning cells are highlighted with an animated pulse effect. Game status and results are displayed with color-coded messages.
- **Responsive Design**: Adapts to different screen sizes with clean, modern styling.
- **Russian UI**: The interface is localized in Russian.

**Frontend files are located in `frontend/static/` and are served by the FastAPI backend at `/static/`.**

## Project Structure

```
.
├── backend/
│   ├── __init__.py          # Python package marker
│   ├── auth.py              # JWT creation/verification, bcrypt password hashing
│   ├── database.py          # SQLite setup, connection pooling via context manager
│   ├── game.py              # Board logic, win detection, AI moves (random + minimax)
│   ├── main.py              # FastAPI app: routes, CORS, static file serving, startup
│   └── schemas.py           # Pydantic models for request/response validation
├── frontend/
│   └── static/
│       ├── app.js           # SPA client logic: authentication, API calls, board rendering
│       ├── index.html       # Main HTML page with login, register, dashboard, and game screens
│       └── styles.css       # All styles: forms, buttons, board, responsive layout
├── requirements.txt         # Python dependencies (fastapi, uvicorn, pyjwt, bcrypt, python-multipart)
├── run.sh                   # Convenience script to install deps and start the server
├── .gitignore               # Git ignore rules
└── .gitkeep                 # Placeholder to keep the directory in git
```

## How to Run

### Prerequisites

- Python 3.10 or later
- pip (Python package manager)

### Backend + Frontend (Full Stack)

The backend serves both the API and the frontend static files. To run everything:

```bash
# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Or use the convenience script:

```bash
chmod +x run.sh
./run.sh
```

The application will be available at [http://localhost:8000](http://localhost:8000).

### Running Tests (Backend)

```bash
# You can test the API endpoints using curl or any HTTP client.
# Example: Register a new user
curl -X POST http://localhost:8000/api/register \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "test1234"}'

# Example: Log in
curl -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "test1234"}'

# Example: Create a new game (with token from login response)
curl -X POST http://localhost:8000/api/games \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"

# Example: Make a move
curl -X POST http://localhost:8000/api/games/1/move \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"position": 0}'
```

### Frontend Only

The frontend is a standard SPA. To develop it separately from the backend, you can serve the `frontend/static/` directory with any static file server:

```bash
# Using Python's built-in HTTP server (for development only)
cd frontend/static && python3 -m http.server 8080
```

Note: When served separately, the frontend expects the backend API at `window.location.origin` (set in `app.js` via the `API_BASE` constant). Adjust this if your backend runs on a different port.

## How They Connect

1. The **FastAPI backend** mounts the `frontend/static/` directory at the `/static/` URL path and serves `index.html` at the root (`/`).
2. When a user visits `http://localhost:8000`, the backend returns `index.html`, which loads `app.js` and `styles.css` from `/static/`.
3. The **frontend SPA** makes API calls (via `fetch()`) to the backend at `http://localhost:8000/api/*` with JWT tokens stored in `localStorage` for authenticated requests.
4. The backend processes game logic (validates moves, computes AI responses) and returns updated game state as JSON.
5. For any unmatched GET request, the backend falls back to serving `index.html`, enabling client-side routing in the SPA.

## Tech Stack

- **Backend**: Python, FastAPI, SQLite, PyJWT, bcrypt, Uvicorn
- **Frontend**: HTML5, CSS3, Vanilla JavaScript (ES6+)
- **Authentication**: JWT (JSON Web Tokens) with Bearer scheme
- **Database**: SQLite with WAL mode
