import json
import datetime
import os
import httpx
from fastapi import FastAPI, Form, HTTPException, Cookie, Request
from fastapi.responses import HTMLResponse, Response, RedirectResponse
import redis

app = FastAPI(title="OpenCode Cluster Portal")

# Конфигурация шлюза и инференса (настраивается через переменные окружения)
LITELLM_URL = os.getenv("LITELLM_URL", "http://litellm:4000")
MASTER_KEY = os.getenv("MASTER_KEY", "sk-master-key-ros2")
LOCAL_IP = os.getenv("LOCAL_IP", "192.168.1.44")
STRATA_URL = os.getenv("STRATA_URL", f"http://{LOCAL_IP}:8080")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen3.8-flash-next-iq3_s")

# Пароль администратора (можно изменить через переменную окружения ADMIN_PASSWORD)
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Подключение к Redis (для хранения вопросов)
try:
    redis_client = redis.Redis(host="redis", port=6379, decode_responses=True)
    redis_client.ping()
except Exception:
    redis_client = None
    _local_questions = []

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLM Cluster Access Portal</title>
    <style>
        :root {
            --bg-color: #f8fafc;
            --card-bg: #ffffff;
            --text-color: #0f172a;
            --text-muted: #64748b;
            --border-color: #e2e8f0;
            --input-bg: #ffffff;
            --status-bg: #0f172a;
            --status-text: #ffffff;
            --hint-bg: #f1f5f9;
            --hint-border: #3b82f6;
            --row-border: #f1f5f9;
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --success: #10b981;
            --success-hover: #059669;
            --support-btn: #4f46e5;
            --support-hover: #4338ca;
            --danger: #ef4444;
            --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
        }

        [data-theme="dark"] {
            --bg-color: #09090b;
            --card-bg: #18181b;
            --text-color: #f4f4f5;
            --text-muted: #a1a1aa;
            --border-color: #27272a;
            --input-bg: #27272a;
            --status-bg: #18181b;
            --status-text: #f4f4f5;
            --hint-bg: #1e1e24;
            --hint-border: #3b82f6;
            --row-border: #27272a;
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --success: #10b981;
            --success-hover: #059669;
            --support-btn: #6366f1;
            --support-hover: #4f46e5;
            --danger: #f87171;
            --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        }

        * { box-sizing: border-box; transition: background-color 0.2s ease, border-color 0.2s ease, color 0.2s ease; }

        body {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            margin: 0;
            padding: 2rem 1rem;
            background: var(--bg-color);
            color: var(--text-color);
            min-height: 100vh;
        }

        .header-bar {
            width: 100%;
            max-width: 900px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
        }

        .logo-title {
            font-size: 1.25rem;
            font-weight: 700;
            letter-spacing: -0.025em;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .header-actions {
            display: flex;
            gap: 0.75rem;
            align-items: center;
        }

        .theme-toggle, .admin-link {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            color: var(--text-color);
            padding: 0.5rem 1rem;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            font-size: 0.875rem;
            box-shadow: var(--shadow);
            text-decoration: none;
            display: inline-flex;
            align-items: center;
        }
        .theme-toggle:hover, .admin-link:hover { opacity: 0.85; }

        /* Дашборд статуса */
        .status-card {
            width: 100%;
            max-width: 900px;
            margin-bottom: 2rem;
            background: var(--status-bg);
            color: var(--status-text);
            display: flex;
            justify-content: space-around;
            align-items: center;
            padding: 1.25rem 1.5rem;
            border-radius: 12px;
            box-shadow: var(--shadow);
            border: 1px solid var(--border-color);
            flex-wrap: wrap;
            gap: 1rem;
        }

        .status-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 0.25rem;
        }

        .status-label {
            font-size: 0.75rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 600;
        }

        .status-value {
            font-size: 1.1rem;
            font-weight: 700;
        }

        .badge-green { color: #4ade80; }
        .badge-yellow { color: #facc15; }
        .badge-red { color: #f87171; }

        /* Грид карточек */
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            width: 100%;
            max-width: 900px;
        }

        .card {
            background: var(--card-bg);
            padding: 1.75rem;
            border-radius: 12px;
            box-shadow: var(--shadow);
            border: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .card h2 {
            font-size: 1.15rem;
            margin-top: 0;
            margin-bottom: 0.5rem;
            font-weight: 700;
        }

        .card p {
            color: var(--text-muted);
            font-size: 0.875rem;
            margin-top: 0;
            margin-bottom: 1.25rem;
            line-height: 1.4;
        }

        input, textarea, button {
            width: 100%;
            box-sizing: border-box;
            padding: 0.75rem;
            margin-top: 0.25rem;
            border-radius: 8px;
            font-family: inherit;
            font-size: 0.9rem;
        }

        input, textarea {
            border: 1px solid var(--border-color);
            background: var(--input-bg);
            color: var(--text-color);
            margin-bottom: 1rem;
            outline: none;
        }
        input:focus, textarea:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
        }

        textarea { resize: vertical; height: 90px; }

        .btn-primary { background: var(--primary); color: white; border: none; font-weight: 600; cursor: pointer; }
        .btn-primary:hover { background: var(--primary-hover); }

        .btn-secondary { background: var(--success); color: white; border: none; font-weight: 600; cursor: pointer; }
        .btn-secondary:hover { background: var(--success-hover); }

        .btn-support { background: var(--support-btn); color: white; border: none; font-weight: 600; cursor: pointer; }
        .btn-support:hover { background: var(--support-hover); }

        .btn-danger { background: var(--danger); color: white; border: none; font-weight: 600; cursor: pointer; }
        .btn-danger:hover { opacity: 0.9; }

        .stat-row {
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid var(--row-border);
            font-size: 0.9rem;
        }
        .stat-row strong { color: var(--text-color); }

        .back-link {
            display: inline-block;
            margin-top: 1.25rem;
            color: var(--primary);
            text-decoration: none;
            font-weight: 600;
            font-size: 0.9rem;
        }
        .back-link:hover { text-decoration: underline; }

        .hint-box {
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 1rem;
            padding: 0.85rem;
            background: var(--hint-bg);
            border-radius: 8px;
            border-left: 3px solid var(--hint-border);
            line-height: 1.4;
            border: 1px solid var(--border-color);
        }
        .hint-box code {
            background: var(--input-bg);
            padding: 2px 4px;
            border-radius: 4px;
            font-family: ui-monospace, monospace;
            font-size: 0.75rem;
            border: 1px solid var(--border-color);
        }
    </style>
</head>
<body>

    <!-- Шапка -->
    <div class="header-bar">
        <div class="logo-title">⚡ OpenCode Cluster Portal</div>
        <div class="header-actions">
            <a href="/admin/questions" class="admin-link">📋 Вопросы пользователей</a>
            <button class="theme-toggle" onclick="toggleTheme()" id="theme-btn">🌙 Темная</button>
        </div>
    </div>

    <!-- Мониторинг движка -->
    <div class="status-card">
        <div class="status-item">
            <span class="status-label">Движок</span>
            <span class="status-value" id="engine-health">⏳ Опрос...</span>
        </div>
        <div class="status-item">
            <span class="status-label">Модель</span>
            <span class="status-value" id="engine-model">-</span>
        </div>
        <div class="status-item">
            <span class="status-label">Состояние</span>
            <span class="status-value" id="engine-state">-</span>
        </div>
        <div class="status-item">
            <span class="status-label">В очереди</span>
            <span class="status-value" id="engine-queue" style="color: #60a5fa;">0</span>
        </div>
    </div>

    <!-- Карточки -->
    <div class="container">
        <!-- Блок 1: Генерация ключа -->
        <div class="card">
            <div>
                <h2>Доступ к OpenCode</h2>
                <p>Регистрация персонального ключа и выгрузка конфигурации для клиента.</p>
                <form action="/generate" method="post">
                    <input type="text" name="username" placeholder="Ваш никнейм (например, andrei)" required>
                    <button type="submit" class="btn-primary">Получить opencode.json</button>
                </form>
            </div>
            <div class="hint-box">
                <strong>Путь установки конфига:</strong><br>
                💻 <strong>Win:</strong> <code>%APPDATA%\\OpenCode\\config</code><br>
                🍏 <strong>Mac:</strong> <code>~/.config/opencode/</code>
            </div>
        </div>

        <!-- Блок 2: Статистика и статус очереди -->
        <div class="card">
            <div>
                <h2>Статистика и лимиты</h2>
                <p>Проверка расхода токенов, бюджета и персонального статуса очереди.</p>
                <form action="/stats" method="post" onsubmit="saveKey(this)">
                    <input type="password" id="api_key_input" name="api_key" placeholder="API-ключ (sk-...)" required>
                    <button type="submit" class="btn-secondary">Проверить баланс</button>
                </form>
            </div>
            <div class="hint-box" style="margin-top: 1rem; border-left-color: var(--success);">
                🔒 Ключ сохраняется в браузере для вашего удобства.
            </div>
        </div>

        <!-- Блок 3: Поддержка и вопросы -->
        <div class="card">
            <div>
                <h2>Поддержка сервиса</h2>
                <p>Столкнулись с проблемой или есть вопрос? Напишите нам.</p>
                <form action="/support/ask" method="post">
                    <input type="text" name="username" placeholder="Ваше имя / никнейм" required>
                    <textarea name="message" placeholder="Опишите ваш вопрос..." required></textarea>
                    <button type="submit" class="btn-support">Задать вопрос</button>
                </form>
            </div>
        </div>
    </div>

    <script>
        function setTheme(theme) {
            document.documentElement.setAttribute('data-theme', theme);
            localStorage.setItem('portal_theme', theme);
            let btn = document.getElementById('theme-btn');
            btn.innerHTML = theme === 'dark' ? '☀️ Светлая' : '🌙 Темная';
        }

        function toggleTheme() {
            let current = document.documentElement.getAttribute('data-theme');
            setTheme(current === 'dark' ? 'light' : 'dark');
        }

        window.addEventListener('DOMContentLoaded', () => {
            let savedTheme = localStorage.getItem('portal_theme') || 'light';
            setTheme(savedTheme);

            let savedKey = localStorage.getItem('opencode_last_key');
            if (savedKey) {
                let input = document.getElementById('api_key_input');
                if (input) input.value = savedKey;
            }
        });

        function saveKey(form) {
            let key = form.querySelector('input[name="api_key"]').value;
            localStorage.setItem('opencode_last_key', key);
        }

        async function fetchStatus() {
            try {
                let response = await fetch('/api/status');
                let data = await response.json();

                let healthEl = document.getElementById('engine-health');
                let stateEl = document.getElementById('engine-state');
                let queueEl = document.getElementById('engine-queue');

                queueEl.innerHTML = data.queue_length > 0 ? `<span class="badge-yellow">${data.queue_length}</span>` : `<span>0</span>`;

                if (data.is_online) {
                    healthEl.innerHTML = '<span class="badge-green">🟢 Online</span>';
                    document.getElementById('engine-model').innerText = data.model;

                    if (data.state === 'idle') {
                        stateEl.innerHTML = '<span class="badge-green">Ожидает</span>';
                    } else if (data.state === 'processing') {
                        stateEl.innerHTML = '<span class="badge-yellow">⚡ Занят</span>';
                    } else {
                        stateEl.innerHTML = `<span class="badge-yellow">${data.state}</span>`;
                    }
                } else {
                    healthEl.innerHTML = '<span class="badge-red">🔴 Offline</span>';
                    document.getElementById('engine-model').innerText = '-';
                    stateEl.innerHTML = '<span class="badge-red">Недоступен</span>';
                }
            } catch (error) {
                document.getElementById('engine-health').innerHTML = '<span class="badge-red">🔴 Сбой</span>';
            }
        }
        setInterval(fetchStatus, 3000);
        fetchStatus();
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def get_form():
    return HTML_TEMPLATE


@app.post("/support/ask", response_class=HTMLResponse)
async def submit_question(username: str = Form(...), message: str = Form(...)):
    question_data = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "username": username,
        "message": message
    }

    if redis_client:
        redis_client.rpush("portal:questions", json.dumps(question_data))
    else:
        _local_questions.append(question_data)

    return f"""
    <html>
    <head><style>{HTML_TEMPLATE.split('<style>')[1].split('</style>')[0]}</style></head>
    <body>
        <div class="card" style="margin: 10vh auto; text-align: center; width: 400px; max-width: 90%;">
            <h2 style="color: var(--success);">✅ Вопрос отправлен!</h2>
            <p style="color: var(--text-muted); margin: 1rem 0;">Спасибо! Ваше обращение записано, администратор ответит вам в ближайшее время.</p>
            <a href="/" class="back-link">← На главную</a>
        </div>
    </body>
    </html>
    """


@app.get("/admin/questions", response_class=HTMLResponse)
async def view_questions(admin_auth: str = Cookie(default=None)):
    if admin_auth != ADMIN_PASSWORD:
        return f"""
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="utf-8">
            <title>Вход для администратора</title>
            <style>{HTML_TEMPLATE.split('<style>')[1].split('</style>')[0]}</style>
        </head>
        <body>
            <div class="card" style="margin: 15vh auto; width: 380px; max-width: 90%;">
                <h2>🔒 Доступ ограничен</h2>
                <p>Введите пароль администратора для просмотра вопросов.</p>
                <form action="/admin/login" method="post">
                    <input type="password" name="password" placeholder="Пароль администратора" required autofocus>
                    <button type="submit" class="btn-primary">Войти</button>
                </form>
                <a href="/" class="back-link">← На главную портала</a>
            </div>
        </body>
        </html>
        """

    questions = []
    if redis_client:
        raw_list = redis_client.lrange("portal:questions", 0, -1)
        questions = [json.loads(q) for q in raw_list]
    else:
        questions = _local_questions

    rows_html = ""
    if not questions:
        rows_html = '<tr><td colspan="3" style="text-align: center; color: var(--text-muted); padding: 2rem;">Пока нет ни одного вопроса.</td></tr>'
    else:
        for q in reversed(questions):
            rows_html += f"""
            <tr style="border-bottom: 1px solid var(--border-color);">
                <td style="padding: 1rem; white-space: nowrap; color: var(--text-muted); font-size: 0.85rem;">{q.get('timestamp')}</td>
                <td style="padding: 1rem; font-weight: 600; white-space: nowrap;">{q.get('username')}</td>
                <td style="padding: 1rem; word-break: break-word;">{q.get('message')}</td>
            </tr>
            """

    return f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="utf-8">
        <title>Вопросы пользователей</title>
        <style>{HTML_TEMPLATE.split('<style>')[1].split('</style>')[0]}</style>
    </head>
    <body>
        <div style="width: 100%; max-width: 900px;">
            <div class="header-bar" style="margin-bottom: 2rem;">
                <div class="logo-title">📋 Вопросы пользователей</div>
                <div class="header-actions">
                    <a href="/" class="admin-link">← На главную</a>
                    <a href="/admin/logout" class="admin-link" style="color: var(--danger); border-color: var(--danger);">Выйти</a>
                </div>
            </div>

            <div class="card" style="width: 100%; padding: 0; overflow: hidden;">
                <table style="width: 100%; border-collapse: collapse; text-align: left;">
                    <thead>
                        <tr style="background: var(--hint-bg); border-bottom: 1px solid var(--border-color);">
                            <th style="padding: 1rem; font-size: 0.85rem; text-transform: uppercase;">Дата / Время</th>
                            <th style="padding: 1rem; font-size: 0.85rem; text-transform: uppercase;">Пользователь</th>
                            <th style="padding: 1rem; font-size: 0.85rem; text-transform: uppercase;">Сообщение</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """


@app.post("/admin/login")
async def admin_login(password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        response = RedirectResponse(url="/admin/questions", status_code=303)
        response.set_cookie(key="admin_auth", value=ADMIN_PASSWORD, httponly=True, max_age=2592000)
        return response
    else:
        return HTMLResponse(content="""
        <html>
        <head><style>""" + HTML_TEMPLATE.split('<style>')[1].split('</style>')[0] + """</style></head>
        <body>
            <div class="card" style="margin: 15vh auto; text-align: center; width: 380px; max-width: 90%;">
                <h2 style="color: var(--danger);">❌ Неверный пароль</h2>
                <p style="color: var(--text-muted); margin: 1rem 0;">Указанный пароль администратора неверен.</p>
                <a href="/admin/questions" class="back-link">← Попробовать снова</a>
            </div>
        </body>
        </html>
        """, status_code=401)


@app.get("/admin/logout")
async def admin_logout():
    response = RedirectResponse(url="/admin/questions", status_code=303)
    response.delete_cookie(key="admin_auth")
    return response


@app.get("/api/status")
async def get_engine_status():
    status_data = {"is_online": False, "model": MODEL_NAME, "state": "unknown", "queue_length": 0}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{STRATA_URL}/health", timeout=1.5)
            if response.status_code == 200:
                status_data["is_online"] = True
                raw_status = response.json().get("status", "idle").lower()
                status_data["state"] = "idle" if raw_status in ["ok", "idle"] else "processing" if raw_status in [
                    "processing", "busy", "generating"] else raw_status
        except Exception:
            pass

        try:
            metrics_resp = await client.get(f"{LITELLM_URL}/metrics", timeout=1.5)
            if metrics_resp.status_code == 200:
                for line in metrics_resp.text.split('\n'):
                    if not line.startswith("#") and ("queue_length" in line or "requests_in_queue" in line):
                        parts = line.split()
                        if len(parts) >= 2:
                            status_data["queue_length"] += int(float(parts[-1]))
        except Exception:
            pass
    return status_data


@app.post("/generate")
async def generate_key(username: str = Form(...)):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{LITELLM_URL}/key/generate",
                headers={"Authorization": f"Bearer {MASTER_KEY}"},
                json={"key_alias": username, "models": [MODEL_NAME], "max_parallel_requests": 1},
                timeout=10.0
            )
            response.raise_for_status()
            key_data = response.json()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка связи с LiteLLM: {str(e)}")

    config = {
        "api_key": key_data["key"],
        "base_url": f"http://{LOCAL_IP}:4000/v1",
        "model": MODEL_NAME,
        "timeout": 600000,
        "stream": True
    }
    return Response(
        content=json.dumps(config, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="opencode_{username}.json"'}
    )


@app.post("/stats", response_class=HTMLResponse)
async def check_stats(api_key: str = Form(...)):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"{LITELLM_URL}/key/info",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=5.0
            )

            if response.status_code in (401, 403):
                return "<div style='text-align:center; margin-top:50px; font-family:sans-serif;'><h2>❌ Ошибка авторизации</h2><p>Неверный API-ключ.</p><a href='/'>Назад</a></div>"

            response.raise_for_status()
            data = response.json()
            info = data.get("info", {})
            spend = float(info.get("spend", 0.0))
            budget = info.get("max_budget")
            key_alias = info.get("key_alias") or "Пользователь"
            models = ", ".join(info.get("models", [])) or "Все доступные"

            engine_state = "idle"
            queue_len = 0
            try:
                health_resp = await client.get(f"{STRATA_URL}/health", timeout=1.0)
                if health_resp.status_code == 200:
                    raw_st = health_resp.json().get("status", "idle").lower()
                    if raw_st in ["processing", "busy", "generating"]:
                        engine_state = "processing"

                metrics_resp = await client.get(f"{LITELLM_URL}/metrics", timeout=1.0)
                if metrics_resp.status_code == 200:
                    for line in metrics_resp.text.split('\n'):
                        if not line.startswith("#") and ("queue_length" in line or "requests_in_queue" in line):
                            parts = line.split()
                            if len(parts) >= 2:
                                queue_len += int(float(parts[-1]))
            except Exception:
                pass

            if engine_state == "processing":
                if queue_len > 0:
                    queue_status_html = '<span style="color: #facc15; font-weight: bold;">⏳ Модель занята. Ваш запрос в очереди.</span>'
                else:
                    queue_status_html = '<span style="color: #4ade80; font-weight: bold;">⚡ Модель обрабатывает запрос.</span>'
            else:
                queue_status_html = '<span style="color: #10b981; font-weight: bold;">🟢 Движок свободен. Запросы выполняются мгновенно.</span>'

            progress_html = ""
            if budget and float(budget) > 0:
                budget_val = float(budget)
                percent = min(100, (spend / budget_val) * 100)
                fill_class = "danger" if percent >= 90 else "warning" if percent >= 75 else ""
                progress_html = f"""
                <div class="progress-wrapper">
                    <div class="progress-text">
                        <span>Использовано: {percent:.1f}%</span>
                        <span>${spend:.2f} / ${budget_val:.2f}</span>
                    </div>
                    <div class="progress-bg">
                        <div class="progress-fill {fill_class}" style="width: {percent}%;"></div>
                    </div>
                </div>
                """
            else:
                progress_html = f"""
                <div class="progress-wrapper" style="color: var(--success); font-size: 0.9rem; font-weight: bold;">
                    Безлимитный бюджет (Потрачено: ${spend:.2f})
                </div>
                """

            result_html = f"""
            <html>
            <head>
                <meta charset="utf-8">
                <style>{HTML_TEMPLATE.split('<style>')[1].split('</style>')[0]}</style>
            </head>
            <body>
                <div class="card" style="margin: 5vh auto; width: 420px; max-width: 90%;">
                    <h2>Статистика и статус</h2>
                    <div class="stat-row"><strong>Пользователь:</strong> <span>{key_alias}</span></div>
                    <div class="stat-row"><strong>Модели:</strong> <span>{models}</span></div>

                    <div style="margin-top: 1.2rem; padding: 0.75rem; background: var(--hint-bg); border-radius: 8px; border: 1px solid var(--border-color);">
                        <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 4px; text-transform: uppercase;">ВАШ СТАТУС:</div>
                        {queue_status_html}
                    </div>

                    <h3 style="margin-top: 1.5rem; margin-bottom: 0.5rem; font-size: 1rem;">Бюджет</h3>
                    {progress_html}

                    <a href="/" class="back-link">← На главную</a>
                </div>
            </body>
            </html>
            """
            return result_html

        except Exception as e:
            return f"<div style='text-align:center; margin-top:50px; font-family:sans-serif;'><h2>⚠️ Ошибка</h2><p>{str(e)}</p><a href='/'>Назад</a></div>"