# Telegram Chat Bot

Python bot for a Telegram group chat: horoscopes, daily summaries, random images,
playful roasts, jokes, absurd conspiracy posts, and configurable Alabuga news.

## Security first

The Telegram token pasted into a chat/log should be treated as leaked. Rotate it in
BotFather before running this in production, then put the fresh token into `.env`.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python setup_cli.py
python run.py
```

The setup script asks for:

- Telegram bot token;
- OpenRouter API key;
- target chat id or admin ids;
- public Telegram channels/URLs for image sources;
- Alabuga channel/jobs URL;
- schedule times and timezone.

If you do not know the group chat id yet, start the bot, add it to the group, and
send `/bind_chat`. Put the returned id into `.env` as `BOT_CHAT_ID`, then restart.

## Configuration

`.env` is the bootstrap/fallback layer; values changed from `/admin` are stored in
SQLite and applied at runtime. Use `.env.example` as the reference for first setup.

Model ids are deliberately configurable:

```env
OPENROUTER_DEFAULT_MODEL=cognitivecomputations/dolphin-mistral-24b-venice-edition
OPENROUTER_QUALITY_MODEL=deepseek/deepseek-chat
OPENROUTER_CHEAP_MODEL=openai/gpt-4.1-nano
ANSWER_MODEL=cognitivecomputations/dolphin-mistral-24b-venice-edition
SUMMARY_MODEL=deepseek/deepseek-chat
CONSPIRACY_MODEL=deepseek/deepseek-chat
HOROSCOPE_MODEL=
JOKE_MODEL=openai/gpt-4.1-nano
ROAST_MODEL=cognitivecomputations/dolphin-mistral-24b-venice-edition
```

Per-feature model ids are shown in `/admin` and can be changed without restart.
Empty `HOROSCOPE_MODEL` means the bot uses `SUMMARY_MODEL`.

## Prompts

Prompts are configurable files, not hardcoded runtime settings. During setup,
`setup_cli.py` asks for prompt file paths and creates defaults if the files do
not exist:

```env
SYSTEM_PROMPT_PATH=prompts/system.txt
ANSWER_SYSTEM_PROMPT_PATH=prompts/answer_system.txt
ANSWER_PROMPT_PATH=prompts/answer.txt
SUMMARY_PROMPT_PATH=prompts/summary.txt
CONSPIRACY_PROMPT_PATH=prompts/conspiracy.txt
HOROSCOPE_PROMPT_PATH=prompts/horoscope.txt
JOKE_PROMPT_PATH=prompts/joke.txt
ROAST_PROMPT_PATH=prompts/roast.txt
```

The Telegram admin panel can also write direct prompt overrides into the bot database.
Prompt priority is: admin prompt override, then prompt file path from effective settings, then built-in default.

Temperatures are also configurable:

```env
ANSWER_TEMPERATURE=0.7
ANSWER_TOP_P=0.9
ANSWER_TOP_K=
ANSWER_PRESENCE_PENALTY=
ANSWER_FREQUENCY_PENALTY=
ANSWER_REPETITION_PENALTY=
ANSWER_MIN_P=
ANSWER_TOP_A=
ANSWER_MAX_TOKENS=1800
SUMMARY_TEMPERATURE=0.5
SUMMARY_TOP_P=
SUMMARY_PRESENCE_PENALTY=
SUMMARY_FREQUENCY_PENALTY=
CONSPIRACY_TEMPERATURE=1.05
CONSPIRACY_TOP_P=0.92
CONSPIRACY_PRESENCE_PENALTY=0.25
CONSPIRACY_FREQUENCY_PENALTY=0.15
HOROSCOPE_TEMPERATURE=1.0
JOKE_TEMPERATURE=1.0
ROAST_TEMPERATURE=1.0
```

Admin prompt overrides are applied at runtime. Prompt file path changes from
`/admin` are also reloaded immediately.

You can also manage prompt files through an interactive CLI:

```powershell
python manage_prompts.py
```

The manager can show, rewrite, or reset individual prompt files.

## Railway

The repository contains `railway.json` and a `Dockerfile`, so Railway does not
depend on Railpack's Python start-command detection. Keep the service root
directory empty (repository root), or set the config file path to
`/railway.json`. The container starts with `python -u main.py` and does not need
a public domain or a `PORT` variable because Telegram is consumed by polling.

At minimum, add these service variables in Railway:

```env
TELEGRAM_BOT_TOKEN=<fresh BotFather token>
OPENROUTER_API_KEY=<OpenRouter key>
ADMIN_USER_IDS=<comma-separated Telegram user ids>
DATABASE_PATH=/app/data/bot.sqlite3
LOCAL_IMAGE_DIR=/app/data/images
```

Attach a Railway Volume at `/app/data`. Without it the bot can start, but the
SQLite database, admin-panel overrides, message history, and uploaded local
images are lost when Railway replaces the deployment.

If Railway still reports `No start command detected`, check the deployment's
commit SHA and source branch. A deployment containing `railway.json` uses the
Dockerfile builder and therefore never reaches Railpack start-command detection.

## Image Sources

Local images go into:

```text
data/images
```

Public Telegram image sources are comma-separated:

```env
IMAGE_SOURCE_CHANNELS=@channel1,https://t.me/s/channel2
```

Bot API cannot read arbitrary private channel history by `channel_id`. Public
channels are fetched through `t.me/s/...`. For private channels, add a future
Telethon/user-session integration or forward posts to a channel where the bot can
receive them.

## Commands

- `/start` - quick health response.
- `/bind_chat` - prints the current chat id for `.env`.
- `/summary_now` - generates a summary immediately.
- `/horoscope_now` - generates a horoscope immediately.
- `/word_stats_now` - prints daily tracked-word stats immediately.

## Safety Boundaries

The bot is intentionally configured not to provide instructions for self-harm,
home surgery, illegal harm, doxing, threats, or targeted harassment. Dangerous
medical questions get a sharp but safe refusal and a recommendation to seek
professional help. Roast mode is playful only.

## Daily Word Stats

Configure a comma-separated scope of tracked words:

```env
TRACKED_WORDS=
WORD_STATS_TIME=23:35
```

Every day the bot counts exact word occurrences for the last 24 hours by chat
participant and posts totals. The manual admin command is `/word_stats_now`.
