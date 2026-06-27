# BIDE Bot

Telegram-бот для федерации нард BIDE. Рейтинг ELO, учёт игр, управление членством.

## Быстрый старт

### 1. Настройка

```bash
cp .env.example .env   # или создай .env вручную
```

В `.env` прописать:
```
BOT_TOKEN=...
SPREADSHEET_ID=...
```

Положить JSON-ключ сервисного аккаунта Google в `credentials/service_account.json`.

### 2. Локальный запуск

```bash
uv sync
uv run -m bot.main
```

### 3. Docker

```bash
docker compose up --build
```

Или в фоне:

```bash
docker compose up --build -d
```

### Первоначальная настройка

- Листы Google Sheets создаются автоматически при первом запуске
- Первых начальников (`admins`) добавить вручную через Sheets: `tg_id`, `username`
- Первых участников (`members`) — тоже вручную, с рейтингом 1500
