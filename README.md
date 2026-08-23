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
JOKE_MODEL=cognitivecomputations/dolphin-mistral-24b-venice-edition
ROAST_MODEL=cognitivecomputations/dolphin-mistral-24b-venice-edition
```

Per-feature model ids are shown in `/admin` and can be changed without restart.
Empty `HOROSCOPE_MODEL` means the bot uses `SUMMARY_MODEL`.
Empty `JOKE_MODEL` falls back to the uncensored default model.

## Schedule And Context

Schedules can be changed from `/admin` without restarting the bot. For the
`*_EVERY_DAYS` values, `0` disables automatic posts, `1` means every day, and
larger values mean once per that many days at the configured time. Decimal
values are supported, so `0.5` means every 12 hours.

```env
HOROSCOPE_TIME=09:30
HOROSCOPE_EVERY_DAYS=1
DAILY_SUMMARY_TIME=23:30
SUMMARY_EVERY_DAYS=1
JOKE_A_TIME=12:00
JOKE_A_EVERY_DAYS=1
JOKE_B_TIME=18:00
JOKE_B_EVERY_DAYS=1
CONSPIRACY_TIME=20:00
CONSPIRACY_EVERY_DAYS=3
ALABUGA_EVERY_HOURS=4
```

Context windows are independent from posting frequency:

```env
SUMMARY_CONTEXT_HOURS=24
HOROSCOPE_CONTEXT_DAYS=7
CONSPIRACY_CONTEXT_DAYS=3
ROAST_CONTEXT_DAYS=3
```

`ROAST_CONTEXT_DAYS` applies both to the selected participant's messages and
to the surrounding group-chat context.

## Prompts

Prompts are configurable files, not hardcoded runtime settings. During setup,
`setup_cli.py` asks for prompt file paths and creates defaults if the files do
not exist:

```env
SYSTEM_PROMPT_PATH=prompts/system.txt
SUMMARY_PROMPT_PATH=prompts/summary.txt
CONSPIRACY_PROMPT_PATH=prompts/conspiracy.txt
HOROSCOPE_PROMPT_PATH=prompts/horoscope.txt
JOKE_PROMPT_PATH=prompts/joke.txt
JOKE_A_PROMPT_PATH=prompts/joke.txt
JOKE_B_PROMPT_PATH=prompts/joke_b.txt
ROAST_PROMPT_PATH=prompts/roast.txt
```

The Telegram admin panel can also write direct prompt overrides into the bot database.
Prompt priority is: admin prompt override, then prompt file path from effective settings, then built-in default.
Jokes have two independent main prompt overrides: `JOKE_A_PROMPT_TEXT` and
`JOKE_B_PROMPT_TEXT`. The older `JOKE_PROMPT_TEXT` is still accepted as a
fallback for type A.

System prompts are configured independently per service in `/admin`:
`ANSWER_SYSTEM_PROMPT_TEXT`, `SUMMARY_SYSTEM_PROMPT_TEXT`,
`CONSPIRACY_SYSTEM_PROMPT_TEXT`, `HOROSCOPE_SYSTEM_PROMPT_TEXT`,
`JOKE_SYSTEM_PROMPT_TEXT`, and `ROAST_SYSTEM_PROMPT_TEXT`. They are stored in
SQLite and applied immediately without changing `.env` or restarting the bot.

`/bully` does not call the LLM. It uses `BULLY_MESSAGE_TEXT` from `/admin`
or `.env`; the template supports `{target}` and `{username}`. The default
target is `BULLY_TARGET_USERNAME`, falling back to the older `TARGET_USERNAME`.
Quick commands:

```text
/bully_text
/bully_text {target}, your custom text
/bully_target morchao
```

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
CONSPIRACY_TEMPERATURE=0.85
CONSPIRACY_TOP_P=0.95
CONSPIRACY_PRESENCE_PENALTY=0
CONSPIRACY_FREQUENCY_PENALTY=0.05
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
```

Attach a Railway Volume at `/app/data`. Without it the bot can start, but the
SQLite database, admin-panel overrides, message history, and uploaded local
images are lost when Railway replaces the deployment. Railway provides the
mount location as `RAILWAY_VOLUME_MOUNT_PATH`; the bot automatically stores the
database at `<mount>/bot.sqlite3` and images at `<mount>/images`. Explicit
`DATABASE_PATH` and `LOCAL_IMAGE_DIR` values still take priority when set.

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

The bot registers its commands with Telegram on startup, so they appear in the
native `/` command picker. Public and administrator commands are defined in one
role-aware registry. Users see only public commands; IDs from `ADMIN_USER_IDS`
receive the full menu in their private chat and in the bound group.

- `/start` - quick health response.
- `/bind_chat` - prints the current chat id for `.env`.
- `/runtime_config` - shows effective models and system-prompt hashes from runtime.
- `/summary_now` - generates a summary immediately.
- `/horoscope_now` - generates a horoscope immediately.
- `/joke_now`, `/joke_now a`, `/joke_now b` - generates a joke immediately.
- `/conspiracy_now` - generates a conspiracy post immediately.
- `/bully @username` - sends the static bully template.
- `/bully_text` - shows or changes the static bully text.
- `/bully_target` - shows or changes the default bully target.
- `/alabuga_random` - forwards a random Alabuga Polytech post when Telegram allows it.

## Telegram Forwarding

For Alabuga posts the bot tries three steps:

1. Bot API `forward_message` from the public channel post.
2. Optional userbot forward through Telethon, if configured.
3. Text fallback with the post link.

Bot API forwarding can fail when the bot account has no access to the source
channel or Telegram blocks forwarding. To enable the userbot fallback, create a
Telegram app at `my.telegram.org`, run:

```bash
python make_telegram_user_session.py
```

Then set these values in Railway variables or `/admin`:

```env
TELEGRAM_USER_API_ID=
TELEGRAM_USER_API_HASH=
TELEGRAM_USER_SESSION=
```

The personal account used for `TELEGRAM_USER_SESSION` must be able to read the
source channel and must be present in the destination group.
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
