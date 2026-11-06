# Discord Economy & Betting Bot

A feature-packed Discord bot built around a virtual-credit economy. Members bet on matches, play casino games, trade on a stock market, collect profile badges and compete on leaderboards. No real money is involved.

## Features

- **Economy:** registration, daily reward, bank, transfers between players (3% fee)
- **Match betting:** dynamic odds that change with the bets placed, bet history
- **Casino games:** blackjack, roulette, Texas Hold'em poker, scratch tickets, wheel of fortune, progressive jackpot, lottery
- **Chess:** challenge other members, with rendered board images
- **Racing mini-game and player market**
- **Stock market** simulation
- **Guilds** for teams of players
- **Profiles:** level, prestige, shop, custom profile backgrounds and badges
- **Leaderboards** in multiple categories
- **AI match analysis** powered by Google Gemini
- **Twitch integration:** a chat bot awards activity points that players convert to credits
- **Voice announcements** with text-to-speech
- Owner tools for moderation (ban, kick, timeout, server list)

## Tech Stack

- Python 3.10+
- py-cord (slash commands, cogs)
- SQLite
- Pillow, CairoSVG and python-chess (images and chess)
- treys (poker hand evaluation)
- Google Generative AI (Gemini)
- TwitchIO
- gTTS, PyNaCl and FFmpeg (voice)

## Getting Started

### Prerequisites

- Python 3.10+
- FFmpeg installed and in your PATH
- Cairo graphics library (required by CairoSVG)
- Discord bot token, plus optional Google AI API key and Twitch OAuth token

### Installation

```bash
git clone https://github.com/Exo-Studios-Code/discord-economy-betting-bot.git
cd discord-economy-betting-bot
pip install -r requirements.txt
```

### Configuration

Set your credentials as environment variables.

Linux/macOS:

```bash
export DISCORD_TOKEN=your_bot_token
export GOOGLE_AI_API_KEY=your_gemini_key      # optional, for AI analysis
export TWITCH_OAUTH_TOKEN=oauth:your_token    # optional, for the Twitch bot
```

Windows PowerShell:

```powershell
$env:DISCORD_TOKEN="your_bot_token"
$env:GOOGLE_AI_API_KEY="your_gemini_key"
```

Then open `bot.py` and set `GUILD_IDS` to your server ID(s). In `twitch_activity_bot.py` set `TWITCH_BOT_NICKNAME` and `TARGET_TWITCH_CHANNEL`.

### Run

```bash
python bot.py
```

Optional Twitch activity bot (separate terminal):

```bash
python twitch_activity_bot.py
```

The `sazkovka.db` database is created automatically.

## Main Commands

| Command | Description |
|---------|-------------|
| `/register`, `/conto`, `/daily`, `/send` | Account, balance, daily reward, transfers |
| `/matches`, `/kurzy`, `/vsadit`, `/moje_sazky` | Match betting |
| `/analyza_zapasu` | AI match analysis |
| `/profil`, `/obchod`, `/prestige`, `/zebricek` | Profile, shop, prestige, leaderboards |
| `/kolo_stesti`, `/jackpot` | Wheel of fortune and jackpot |
| `/propojit_twitch`, `/prevest_body` | Link Twitch and convert points |
