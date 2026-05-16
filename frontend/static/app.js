// Tic-Tac-Toe SPA - Frontend Logic

const API_BASE = '';
let currentGameId = null;

// ─── Utility Functions ───────────────────────────────────────────────────────

function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(screenId).classList.add('active');
}

function showLoading(show = true) {
    document.getElementById('loading').classList.toggle('hidden', !show);
}

function getToken() {
    return localStorage.getItem('token');
}

function setToken(token) {
    if (token) {
        localStorage.setItem('token', token);
    } else {
        localStorage.removeItem('token');
    }
}

function getUser() {
    const user = localStorage.getItem('user');
    return user ? JSON.parse(user) : null;
}

function setUser(user) {
    if (user) {
        localStorage.setItem('user', JSON.stringify(user));
    } else {
        localStorage.removeItem('user');
    }
}

async function apiCall(url, options = {}) {
    const token = getToken();
    const headers = { ...options.headers };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    if (options.body && !(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(`${API_BASE}${url}`, {
        ...options,
        headers,
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || `HTTP ${response.status}`);
    }

    return data;
}

// ─── Authentication ──────────────────────────────────────────────────────────

async function handleLogin(username, password) {
    showLoading(true);
    try {
        const data = await apiCall('/api/login', {
            method: 'POST',
            body: JSON.stringify({ username, password }),
        });
        setToken(data.access_token);
        setUser(data.user);
        await loadDashboard();
    } catch (err) {
        alert('Login failed: ' + err.message);
    } finally {
        showLoading(false);
    }
}

async function handleRegister(username, password) {
    showLoading(true);
    try {
        await apiCall('/api/register', {
            method: 'POST',
            body: JSON.stringify({ username, password }),
        });
        // Auto-login after registration
        await handleLogin(username, password);
    } catch (err) {
        alert('Registration failed: ' + err.message);
    } finally {
        showLoading(false);
    }
}

function handleLogout() {
    setToken(null);
    setUser(null);
    showScreen('screen-login');
}

// ─── Dashboard ───────────────────────────────────────────────────────────────

async function loadDashboard() {
    const user = getUser();
    if (!user) {
        showScreen('screen-login');
        return;
    }

    document.getElementById('user-greeting').textContent = user.username;
    showLoading(true);

    try {
        const games = await apiCall('/api/games');
        renderHistory(games);
        showScreen('screen-dashboard');
    } catch (err) {
        alert('Failed to load games: ' + err.message);
    } finally {
        showLoading(false);
    }
}

function renderHistory(games) {
    const container = document.getElementById('game-history');

    if (!games || games.length === 0) {
        container.innerHTML = '<p>No games played yet.</p>';
        return;
    }

    let html = '<table><thead><tr><th>#</th><th>Result</th><th>Opponent</th><th>Date</th></tr></thead><tbody>';
    games.forEach(game => {
        const resultClass = game.result ? `result-${game.result}` : '';
        const resultText = game.result ? game.result.charAt(0).toUpperCase() + game.result.slice(1) : 'In progress';
        html += `<tr>
            <td>${game.id}</td>
            <td class="${resultClass}">${resultText}</td>
            <td>${game.opponent}</td>
            <td>${new Date(game.created_at).toLocaleDateString()}</td>
        </tr>`;
    });
    html += '</tbody></table>';
    container.innerHTML = html;
}

// ─── Game ────────────────────────────────────────────────────────────────────

async function startNewGame() {
    showLoading(true);
    try {
        const game = await apiCall('/api/games', { method: 'POST' });
        currentGameId = game.id;
        renderBoard(game);
        showScreen('screen-game');
    } catch (err) {
        alert('Failed to create game: ' + err.message);
    } finally {
        showLoading(false);
    }
}

async function loadGame(gameId) {
    showLoading(true);
    try {
        const game = await apiCall(`/api/games/${gameId}`);
        currentGameId = game.id;
        renderBoard(game);
        showScreen('screen-game');
    } catch (err) {
        alert('Failed to load game: ' + err.message);
    } finally {
        showLoading(false);
    }
}

function renderBoard(game) {
    const cells = document.querySelectorAll('.cell');
    cells.forEach((cell, index) => {
        const mark = game.board[index];
        cell.textContent = mark;
        cell.className = 'cell';
        if (mark === 'X') cell.classList.add('x');
        if (mark === 'O') cell.classList.add('o');
    });

    const statusEl = document.getElementById('game-status');
    if (game.status === 'finished') {
        if (game.winner === 'X') {
            statusEl.textContent = 'You win! 🎉';
        } else if (game.winner === 'O') {
            statusEl.textContent = 'Computer wins!';
        } else if (game.winner === 'draw') {
            statusEl.textContent = "It's a draw!";
        } else {
            statusEl.textContent = 'Game finished';
        }
    } else {
        statusEl.textContent = game.current_turn === 'X' ? 'Your turn (X)' : "Computer's turn (O)...";
    }
}

async function handleCellClick(index) {
    if (!currentGameId) return;

    // Check if cell is already occupied
    const cell = document.querySelector(`.cell[data-index="${index}"]`);
    if (cell.textContent) return;

    // Check if game is still in progress by getting current state
    showLoading(true);
    try {
        const game = await apiCall(`/api/games/${currentGameId}/move`, {
            method: 'POST',
            body: JSON.stringify({ position: index }),
        });
        renderBoard(game);
    } catch (err) {
        alert('Move failed: ' + err.message);
    } finally {
        showLoading(false);
    }
}

function backToDashboard() {
    currentGameId = null;
    loadDashboard();
}

// ─── Event Listeners ────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    // Login form
    document.getElementById('form-login').addEventListener('submit', (e) => {
        e.preventDefault();
        const username = document.getElementById('login-username').value;
        const password = document.getElementById('login-password').value;
        handleLogin(username, password);
    });

    // Register form
    document.getElementById('form-register').addEventListener('submit', (e) => {
        e.preventDefault();
        const username = document.getElementById('register-username').value;
        const password = document.getElementById('register-password').value;
        const confirm = document.getElementById('register-confirm').value;
        if (password !== confirm) {
            alert('Passwords do not match');
            return;
        }
        handleRegister(username, password);
    });

    // Navigation links
    document.getElementById('link-to-register').addEventListener('click', () => {
        showScreen('screen-register');
    });

    document.getElementById('link-to-login').addEventListener('click', () => {
        showScreen('screen-login');
    });

    // Dashboard buttons
    document.getElementById('btn-new-game').addEventListener('click', startNewGame);
    document.getElementById('btn-logout').addEventListener('click', handleLogout);
    document.getElementById('btn-back').addEventListener('click', backToDashboard);

    // Board cells
    document.querySelectorAll('.cell').forEach(cell => {
        cell.addEventListener('click', () => {
            const index = parseInt(cell.dataset.index);
            handleCellClick(index);
        });
    });

    // Check if already logged in
    if (getToken()) {
        loadDashboard();
    } else {
        showScreen('screen-login');
    }
});
