# Telegram Moderation Bot

A Python Telegram bot for collecting text and photo submissions, reviewing them
through a moderation queue, and publishing approved content to a channel.

## Features

- Text and photo submission queues.
- Moderation through inline buttons.
- Administrator and main-administrator roles.
- User reputation and temporary bans.
- JSON state persistence and backups.
- Background autosave, cleanup, moderation reminders, and daily statistics.
- State recovery after a restart.

## Technology stack

- Python 3.11+
- `python-telegram-bot`
- `python-dotenv`

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # Windows: copy .env.example .env
```

Fill in `.env` with your configuration, then start the bot:

```bash
python -m tg_bot.app
```

## Configuration

Sensitive configuration is read from environment variables. The repository excludes
Telegram tokens, real administrator IDs, and runtime JSON containing user data.

| Variable | Purpose |
|---|---|
| `BOT_TOKEN` | Telegram bot token |
| `CHANNEL_ID` | Destination channel |
| `MAIN_ADMIN_ID` | Main administrator's Telegram ID |
| `ADMIN_SECRET_WORD` | Secret phrase for the admin flow |
| `ADMIN_ACCESS_CODE` | Administrator access code |
| `DATA_FILE` | Main state JSON file |
| `BACKUP_FILE` | State backup JSON file |

> An old token from the original local project was removed before this version
> was published. If it was ever used, revoke and replace it through BotFather.
