/**
 * Tic-Tac-Toe SPA — client-side logic.
 * Communicates with the FastAPI backend via REST API.
 */

// ─── Constants ──────────────────────────────────────────────────────────────
const API_BASE = window.location.origin;
const TOKEN_KEY = 'ttt_access_token';

// ─── State ──────────────────────────────────────────────────────────────────
let currentGameId = null;

// ─── Token helpers ──────────────────────────────────────────────────────────
function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

function isAuthenticated() {
  return !!getToken();
}

// ─── API call wrapper ───────────────────────────────────────────────────────
async function apiCall(url, options = {}) {
  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers,
  });

  // Handle 204 No Content
  if (response.status === 204) {
    return null;
  }

  let data;
  try {
    data = await response.json();
  } catch (e) {
    data = { detail: 'Unexpected server response' };
  }

  if (!response.ok) {
    const message = data.detail || `Request failed with status ${response.status}`;
    throw new Error(message);
  }

  return data;
}

// ─── Screen management ──────────────────────────────────────────────────────
function showScreen(screenId) {
  document.querySelectorAll('.screen').forEach((el) => {
    el.classList.remove('active');
  });
  const screen = document.getElementById(screenId);
  if (screen) {
    screen.classList.add('active');
  }
}

function showError(elementId, message) {
  const el = document.getElementById(elementId);
  if (el) {
    el.textContent = message;
  }
}

function clearError(elementId) {
  const el = document.getElementById(elementId);
  if (el) {
    el.textContent = '';
  }
}

// ─── Win line patterns ──────────────────────────────────────────────────────
const WIN_LINES = [
  [0, 1, 2],
  [3, 4, 5],
  [6, 7, 8], // rows
  [0, 3, 6],
  [1, 4, 7],
  [2, 5, 8], // columns
  [0, 4, 8],
  [2, 4, 6], // diagonals
];

function getWinLine(board) {
  for (const line of WIN_LINES) {
    const [a, b, c] = line;
    if (board[a] && board[a] === board[b] && board[a] === board[c]) {
      return line;
    }
  }
  return null;
}

// ─── Login ──────────────────────────────────────────────────────────────────
async function handleLogin(event) {
  event.preventDefault();
  clearError('login-error');

  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value;

  if (!username || !password) {
    showError('login-error', 'Заполните все поля');
    return;
  }

  try {
    const data = await apiCall('/api/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });

    setToken(data.access_token);
    await loadDashboard();
  } catch (err) {
    showError('login-error', err.message);
  }
}

// ─── Register ───────────────────────────────────────────────────────────────
async function handleRegister(event) {
  event.preventDefault();
  clearError('register-error');

  const username = document.getElementById('register-username').value.trim();
  const password = document.getElementById('register-password').value;
  const confirm = document.getElementById('register-confirm').value;

  if (!username || !password || !confirm) {
    showError('register-error', 'Заполните все поля');
    return;
  }

  if (password !== confirm) {
    showError('register-error', 'Пароли не совпадают');
    return;
  }

  if (password.length < 4) {
    showError('register-error', 'Пароль должен быть не менее 4 символов');
    return;
  }

  try {
    await apiCall('/api/register', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });

    // Auto-login after registration
    const loginData = await apiCall('/api/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });

    setToken(loginData.access_token);
    await loadDashboard();
  } catch (err) {
    showError('register-error', err.message);
  }
}

// ─── Dashboard ──────────────────────────────────────────────────────────────
async function loadDashboard() {
  showScreen('screen-dashboard');

  // Show username
  try {
    const me = await apiCall('/api/me');
    document.getElementById('username-display').textContent = me.username;
  } catch (err) {
    // If token is invalid, redirect to login
    logout();
    return;
  }

  // Load game history
  await loadGameHistory();
}

async function loadGameHistory() {
  const loadingEl = document.getElementById('history-loading');
  const emptyEl = document.getElementById('history-empty');
  const errorEl = document.getElementById('history-error');
  const tableWrapper = document.getElementById('history-table-wrapper');
  const tbody = document.getElementById('history-body');

  // Show loading
  loadingEl.style.display = 'block';
  emptyEl.style.display = 'none';
  errorEl.textContent = '';
  tableWrapper.style.display = 'none';

  try {
    const games = await apiCall('/api/games');

    loadingEl.style.display = 'none';

    if (!games || games.length === 0) {
      emptyEl.style.display = 'block';
      return;
    }

    tableWrapper.style.display = 'block';
    tbody.innerHTML = '';

    games.forEach((game) => {
      const tr = document.createElement('tr');

      // Date
      const tdDate = document.createElement('td');
      tdDate.textContent = formatDate(game.created_at);
      tr.appendChild(tdDate);

      // Opponent
      const tdOpponent = document.createElement('td');
      tdOpponent.textContent = game.opponent || 'Компьютер';
      tr.appendChild(tdOpponent);

      // Result
      const tdResult = document.createElement('td');
      tdResult.textContent = formatResult(game.result, game.status);
      tdResult.className = getResultClass(game.result);
      tr.appendChild(tdResult);

      tbody.appendChild(tr);
    });
  } catch (err) {
    loadingEl.style.display = 'none';
    showError('history-error', 'Не удалось загрузить историю игр: ' + err.message);
  }
}

function formatDate(dateStr) {
  if (!dateStr) return '—';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch (e) {
    return dateStr;
  }
}

function formatResult(result, status) {
  if (status !== 'finished') return 'В процессе';
  switch (result) {
    case 'win':
      return 'Победа';
    case 'lose':
      return 'Поражение';
    case 'draw':
      return 'Ничья';
    default:
      return '—';
  }
}

function getResultClass(result) {
  switch (result) {
    case 'win':
      return 'result-win';
    case 'lose':
      return 'result-lose';
    case 'draw':
      return 'result-draw';
    default:
      return 'result-unknown';
  }
}

// ─── New Game ───────────────────────────────────────────────────────────────
async function createNewGame() {
  try {
    const game = await apiCall('/api/games', {
      method: 'POST',
    });

    currentGameId = game.id;
    await loadGame(game.id);
  } catch (err) {
    showError('history-error', 'Не удалось создать игру: ' + err.message);
  }
}

// ─── Game Screen ────────────────────────────────────────────────────────────
async function loadGame(gameId) {
  showScreen('screen-game');
  const loadingEl = document.getElementById('game-loading');
  const errorEl = document.getElementById('game-error');
  const boardEl = document.getElementById('board');
  const statusEl = document.getElementById('game-status');
  const resultEl = document.getElementById('game-result');

  loadingEl.style.display = 'block';
  errorEl.textContent = '';
  boardEl.style.display = 'none';
  resultEl.textContent = '';
  resultEl.className = 'game-result';

  try {
    const game = await apiCall(`/api/games/${gameId}`);
    loadingEl.style.display = 'none';
    boardEl.style.display = 'grid';
    renderBoard(game);
  } catch (err) {
    loadingEl.style.display = 'none';
    showError('game-error', 'Не удалось загрузить игру: ' + err.message);
  }
}

function renderBoard(game) {
  const board = game.board;
  const cells = document.querySelectorAll('.cell');
  const statusEl = document.getElementById('game-status');
  const resultEl = document.getElementById('game-result');

  // Reset board state
  resultEl.textContent = '';
  resultEl.className = 'game-result';

  // Update cells
  cells.forEach((cell, index) => {
    const value = board[index];
    cell.textContent = value || '';
    cell.className = 'cell';
    if (value === 'X') {
      cell.classList.add('x');
    } else if (value === 'O') {
      cell.classList.add('o');
    }
  });

  // Check for a winner
  const winLine = getWinLine(board);
  const isFinished = game.status === 'finished';

  if (winLine) {
    // Highlight winning cells
    winLine.forEach((index) => {
      cells[index].classList.add('win-cell');
    });
  }

  // Show result if game is finished
  if (isFinished) {
    if (game.winner === 'X') {
      resultEl.textContent = '🎉 Вы победили!';
      resultEl.className = 'game-result result-win';
      statusEl.textContent = 'Игра завершена';
    } else if (game.winner === 'O') {
      resultEl.textContent = '😞 Вы проиграли!';
      resultEl.className = 'game-result result-lose';
      statusEl.textContent = 'Игра завершена';
    } else if (game.winner === 'draw') {
      resultEl.textContent = '🤝 Ничья!';
      resultEl.className = 'game-result result-draw';
      statusEl.textContent = 'Игра завершена';
    } else {
      statusEl.textContent = 'Игра завершена';
    }

    // Disable all cells
    cells.forEach((cell) => cell.classList.add('disabled'));
    currentGameId = null;
  } else {
    // Game is in progress
    const turnLabel = game.current_turn === 'X' ? 'Ваш ход (X)' : 'Ход компьютера (O)';
    statusEl.textContent = turnLabel;

    if (game.current_turn === 'O') {
      // Computer's turn — disable cells and wait
      cells.forEach((cell) => cell.classList.add('disabled'));
    } else {
      // Player's turn — enable only empty cells
      cells.forEach((cell, index) => {
        if (!board[index]) {
          cell.classList.remove('disabled');
        } else {
          cell.classList.add('disabled');
        }
      });
    }
  }
}

// ─── Make a move ────────────────────────────────────────────────────────────
async function handleCellClick(event) {
  const cell = event.currentTarget;
  const index = parseInt(cell.dataset.index, 10);

  // Guard: don't allow moves on occupied or disabled cells
  if (cell.textContent || cell.classList.contains('disabled')) {
    return;
  }

  if (!currentGameId) {
    return;
  }

  // Optimistically mark the cell
  cell.textContent = 'X';
  cell.classList.add('x', 'disabled');

  const statusEl = document.getElementById('game-status');
  statusEl.textContent = 'Ход компьютера (O)...';

  try {
    const game = await apiCall(`/api/games/${currentGameId}/move`, {
      method: 'POST',
      body: JSON.stringify({ position: index }),
    });

    renderBoard(game);
  } catch (err) {
    // Revert the optimistic update on error
    cell.textContent = '';
    cell.classList.remove('x', 'disabled');
    showError('game-error', err.message);
  }
}

// ─── Logout ─────────────────────────────────────────────────────────────────
function logout() {
  clearToken();
  currentGameId = null;
  showScreen('screen-login');
  document.getElementById('form-login').reset();
  clearError('login-error');
  clearError('register-error');
  clearError('game-error');
}

// ─── Navigation ─────────────────────────────────────────────────────────────
function goToRegister() {
  clearError('login-error');
  document.getElementById('form-login').reset();
  showScreen('screen-register');
}

function goToLogin() {
  clearError('register-error');
  document.getElementById('form-register').reset();
  showScreen('screen-login');
}

function goBackToDashboard() {
  clearError('game-error');
  currentGameId = null;
  loadDashboard();
}

// ─── Initialization ─────────────────────────────────────────────────────────
function init() {
  // ── Login form ──
  document.getElementById('form-login').addEventListener('submit', handleLogin);
  document.getElementById('link-to-register').addEventListener('click', (e) => {
    e.preventDefault();
    goToRegister();
  });

  // ── Register form ──
  document.getElementById('form-register').addEventListener('submit', handleRegister);
  document.getElementById('link-to-login').addEventListener('click', (e) => {
    e.preventDefault();
    goToLogin();
  });

  // ── Dashboard ──
  document.getElementById('btn-new-game').addEventListener('click', createNewGame);
  document.getElementById('btn-logout').addEventListener('click', logout);

  // ── Game screen ──
  document.getElementById('btn-back').addEventListener('click', goBackToDashboard);
  document.querySelectorAll('.cell').forEach((cell) => {
    cell.addEventListener('click', handleCellClick);
  });

  // ── Initial screen ──
  if (isAuthenticated()) {
    loadDashboard();
  } else {
    showScreen('screen-login');
  }
}

// Start the app once DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
