# ⚠️ DŮLEŽITÉ: Tento bot vyžaduje py-cord, ne standardní discord.py!
# Před spuštěním bota nainstalujte py-cord:
#   1. Odinstalujte discord.py: pip uninstall discord.py -y
#   2. Nainstalujte py-cord: pip install py-cord
# Případně v jednom kroku: pip uninstall discord.py -y && pip install py-cord

import discord
from discord.commands import SlashCommandGroup
from discord.ext import commands, tasks
import sqlite3
import datetime
import asyncio
import random
import re
from interactive_games import BlackjackGame, ScratchTicketView
import chess
from chess_logic import ChallengeView, generate_board_image
import json
import os

# --- Konfigurace ---
# ⚠️ DŮLEŽITÉ: ZMĚŇTE SI TOKEN PO OTESTOVÁNÍ! VÁŠ TOKEN JE VEŘEJNĚ VIDITELNÝ.
BOT_TOKEN = os.getenv("DISCORD_TOKEN")
STARTING_CURRENCY = 5000
DAILY_REWARD = 800
GUILD_IDS = [1440328538636025990] # ID vašeho serveru
CASINO_VOICE_CHANNEL_ID = 1411274286366461972 # Vložte sem ID vašeho hlasového kanálu
PRESTIGE_MAX_LEVEL = 50
PRESTIGE_REWARD = 100000 
VAULT_INTEREST_RATE_PERCENT = 0.5 # Denní úrok 0.1% z částky v trezoru
# Kolik Credits hráč dostane za prestiž
# v hlavním souboru, v sekci Konfigurace
SMALL_BLIND = 50
BIG_BLIND = 100
# NOVINKA: Konfigurace pro posílání Credits
TRANSACTION_FEE_PERCENT = 3 # Poplatek 3% za každou transakci

# NOVINKA: ID vlastníka bota pro speciální oprávnění
OWNER_ID = 1224452995442540647 # Vložte sem vaše zkopírované ID

# NOVINKA: Konfigurace pro propojení s Twitchem
TWITCH_POINTS_TO_CREDITS_RATE = 10  # Kolik Credits dostane uživatel za 1 Twitch bod
PLAYER_VALUE_PER_GOAL = 2500   # O kolik stoupne hodnota hráče za gól
PLAYER_VALUE_PER_ASSIST = 1100 # O kolik stoupne hodnota hráče za asistenci

GOOGLE_AI_API_KEY = os.getenv("GOOGLE_AI_API_KEY")

GUILD_CREATION_COST = 4250 # Cena za založení týmu

# Konfigurace pro transfer systém
CAPTAIN_ROLE_NAME = "General manager"  # Název role kapitána
TRANSFERS_CHANNEL_NAME = "transfer"  # Kanál pro oznámení přestupů
TRANSFERS_LOG_CHANNEL_NAME = "transfers-log"  # Kanál pro interní logy
TRANSFERS_DATA_PATH = "data"  # Složka pro ukládání dat
TRANSFERS_FILE = os.path.join(TRANSFERS_DATA_PATH, "transfers.json")  # Soubor s historií

# Konfigurace pro minihry
ROULETTE_WHEEL = {
    0: 'green', 1: 'red', 2: 'black', 3: 'red', 4: 'black', 5: 'red', 6: 'black', 7: 'red', 8: 'black',
    9: 'red', 10: 'black', 11: 'black', 12: 'red', 13: 'black', 14: 'red', 15: 'black', 16: 'red',
    17: 'black', 18: 'red', 19: 'red', 20: 'black', 21: 'red', 22: 'black', 23: 'red', 24: 'black',
    25: 'red', 26: 'black', 27: 'red', 28: 'black', 29: 'black', 30: 'red', 31: 'black', 32: 'red',
    33: 'black', 34: 'red', 35: 'black', 36: 'red'
}

SCRATCH_TICKET_PRICE = 250  # Cena za jeden los
SCRATCH_TICKET_PRIZES = {
    '💰': 50000, # Jackpot
    '💎': 10000,
    '🍀': 5000,
    '⭐': 2500,
    '🍉': 1000,
    '🍒': 500   # Cena útěchy
}
# --- Automatická aktualizace databáze ---
# v souboru 3.py

# v souboru 4.py

def _update_database_structure(c):
    """
    Tato funkce POUZE přidává nové sloupce do již existujících tabulek,
    aby se zachovala data při každém updatu.
    """
    # --- Úprava tabulky 'users' ---
    c.execute("PRAGMA table_info(users)")
    user_columns = [row[1] for row in c.fetchall()]
    
    all_user_columns = {
        "last_daily": "TEXT", "twitch_username": "TEXT", "twitch_points": "INTEGER DEFAULT 0",
        "twitch_message_count": "INTEGER DEFAULT 0", "level": "INTEGER DEFAULT 1", "xp": "REAL DEFAULT 0",
        "xp_booster_end_time": "TEXT", "games_played": "INTEGER DEFAULT 0", "games_won": "INTEGER DEFAULT 0",
        "badges": "TEXT DEFAULT '[]'", "prestige": "INTEGER DEFAULT 0", "owned_backgrounds": "TEXT DEFAULT '[\"default\"]'",
        "active_background": "TEXT DEFAULT 'default'", "assets": "TEXT DEFAULT '{}'", "passive_income_total": "REAL DEFAULT 0",
        "vault_balance": "REAL DEFAULT 0", "last_interest_date": "TEXT", "loan_amount": "REAL DEFAULT 0", "loan_due_date": "TEXT"
    }

    for col, col_type in all_user_columns.items():
        if col not in user_columns:
            print(f"DB: Přidávám sloupec '{col}' do tabulky 'users'...")
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {col_type}")

    if 'twitch_username' in user_columns and 'idx_twitch_username' not in [i[1] for i in c.execute("PRAGMA index_list(users);")]:
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_twitch_username ON users (twitch_username) WHERE twitch_username IS NOT NULL")

    # --- Úprava tabulky 'poker_games' ---
    c.execute("PRAGMA table_info(poker_games)")
    poker_columns = [row[1] for row in c.fetchall()]
    if 'betting_round' not in poker_columns:
        c.execute("ALTER TABLE poker_games ADD COLUMN betting_round TEXT DEFAULT 'preflop'")
    if 'current_bet' not in poker_columns:
        c.execute("ALTER TABLE poker_games ADD COLUMN current_bet REAL DEFAULT 0")


def setup_database():
    """
    Tato funkce se stará o vytvoření VŠECH tabulek, pokud neexistují,
    a zavolá pomocníka pro aktualizaci sloupců v existujících tabulkách.
    """
    with sqlite3.connect('sazkovka.db') as conn:
        c = conn.cursor()
        
        # --- ZÁKLADNÍ TABULKY ---
        c.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS matches (match_id INTEGER PRIMARY KEY AUTOINCREMENT, team1 TEXT NOT NULL, team2 TEXT NOT NULL, status TEXT NOT NULL, winning_team TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS bot_settings (setting_key TEXT PRIMARY KEY, setting_value TEXT NOT NULL)')

        # --- TABULKY PRO HERNÍ SYSTÉMY ---
        c.execute("DROP TABLE IF EXISTS bets")
        c.execute('''
            CREATE TABLE IF NOT EXISTS bets (
                bet_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, match_id INTEGER NOT NULL,
                bet_type TEXT NOT NULL, bet_value TEXT NOT NULL, odds REAL NOT NULL, amount REAL NOT NULL,
                status TEXT DEFAULT 'pending', FOREIGN KEY (user_id) REFERENCES users (user_id),
                FOREIGN KEY (match_id) REFERENCES matches (match_id))
        ''')
        c.execute('CREATE TABLE IF NOT EXISTS betting_options (option_id INTEGER PRIMARY KEY AUTOINCREMENT, match_id INTEGER NOT NULL, bet_type TEXT NOT NULL, bet_value TEXT NOT NULL, odds REAL NOT NULL, UNIQUE(match_id, bet_type, bet_value), FOREIGN KEY (match_id) REFERENCES matches (match_id))')
        c.execute('CREATE TABLE IF NOT EXISTS chess_games (game_id INTEGER PRIMARY KEY AUTOINCREMENT, message_id INTEGER, channel_id INTEGER, player_white_id INTEGER, player_black_id INTEGER, current_turn_id INTEGER, board_fen TEXT, wager REAL DEFAULT 0, status TEXT, betting_round TEXT DEFAULT "preflop")')
        c.execute('CREATE TABLE IF NOT EXISTS lottery_tickets (ticket_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, purchase_date TEXT NOT NULL, FOREIGN KEY (user_id) REFERENCES users (user_id))')
        c.execute('CREATE TABLE IF NOT EXISTS guilds (guild_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, leader_id INTEGER NOT NULL, bank_balance REAL DEFAULT 0, creation_date TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS guild_members (user_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL, join_date TEXT NOT NULL, FOREIGN KEY (guild_id) REFERENCES guilds (guild_id))')
        c.execute('CREATE TABLE IF NOT EXISTS stocks (stock_id TEXT PRIMARY KEY, name TEXT NOT NULL, current_price REAL NOT NULL, history TEXT DEFAULT "[]")')
        c.execute('CREATE TABLE IF NOT EXISTS stock_portfolios (portfolio_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, stock_id TEXT NOT NULL, quantity INTEGER NOT NULL, FOREIGN KEY (user_id) REFERENCES users (user_id), FOREIGN KEY (stock_id) REFERENCES stocks (stock_id))')
        c.execute('CREATE TABLE IF NOT EXISTS players (player_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE, current_value REAL NOT NULL, history TEXT DEFAULT "[]")')
        c.execute('CREATE TABLE IF NOT EXISTS player_portfolios (portfolio_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, player_id INTEGER NOT NULL, quantity INTEGER NOT NULL, UNIQUE(user_id, player_id), FOREIGN KEY (user_id) REFERENCES users (user_id), FOREIGN KEY (player_id) REFERENCES players (player_id))')
        
        # --- POKER TABULKY ---
        c.execute('''CREATE TABLE IF NOT EXISTS poker_games (
            game_id INTEGER PRIMARY KEY AUTOINCREMENT, 
            channel_id INTEGER NOT NULL, 
            message_id INTEGER, 
            status TEXT, 
            pot REAL DEFAULT 0, 
            community_cards TEXT DEFAULT "[]", 
            current_turn_user_id INTEGER,
            betting_round TEXT DEFAULT 'preflop',
            current_bet REAL DEFAULT 0
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS poker_players (
            player_id INTEGER PRIMARY KEY AUTOINCREMENT, 
            game_id INTEGER NOT NULL, 
            user_id INTEGER NOT NULL, 
            hand TEXT DEFAULT "[]", 
            stack REAL NOT NULL, 
            current_bet REAL DEFAULT 0, 
            is_folded INTEGER DEFAULT 0, 
            is_all_in INTEGER DEFAULT 0, 
            UNIQUE(game_id, user_id), 
            FOREIGN KEY (game_id) REFERENCES poker_games (game_id), 
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )''')
        
        # --- ZÁKLADNÍ NASTAVENÍ A AKTUALIZACE ---
        c.execute("INSERT OR IGNORE INTO bot_settings (setting_key, setting_value) VALUES ('progressive_jackpot', '10000')")
        _update_database_structure(c)
        
        conn.commit()
        print("✅ Databáze úspěšně inicializována s VŠEMI tabulkami včetně poker_players!")
# --- Vytvoření instance bota ---
setup_database()
bot = discord.Bot(intents=discord.Intents.all())

# --- Skupina (Cog) pro běžné uživatele ---
class UserCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    minihry = SlashCommandGroup("minigames", "Play for Credits.", guild_ids=GUILD_IDS)
    @commands.slash_command(name="register", description="They will open an account for you and give you initial capital.", guild_ids=GUILD_IDS)
    async def register(self, ctx):
        conn = sqlite3.connect('sazkovka.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (ctx.author.id,))
        if c.fetchone():
            await ctx.respond("You already have an account!", ephemeral=True)
        else:
            c.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (ctx.author.id, STARTING_CURRENCY))
            conn.commit()
            await ctx.respond(f"Welcome to the game! I created an account for you and credited you {STARTING_CURRENCY} Credit.", ephemeral=True)
        conn.close()

    # Vložte tento nový příkaz dovnitř vaší třídy UserCommands

    @commands.slash_command(name="send", description="Send credits to another player (3% fee).")
    async def send_credits(self, ctx: discord.ApplicationContext, prijemce: discord.Member, castka: float):
        # --- Vstupní validace ---
        if prijemce.bot:
            await ctx.respond("You can't send credits to bots!", ephemeral=True)
            return
        if prijemce.id == ctx.author.id:
            await ctx.respond("You can't send credits to yourself!", ephemeral=True)
            return
        if castka <= 0:
            await ctx.respond("The amount must be a positive number.", ephemeral=True)
            return

        # --- Bezpečná databázová transakce ---
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()

            # Zkontrolujeme odesílatele
            c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
            sender_balance = c.fetchone()
            if not sender_balance or sender_balance[0] < castka:
                await ctx.respond(f"You don't have enough Credits na odeslání **{castka:.2f}**.", ephemeral=True)
                return

            # Zkontrolujeme příjemce
            c.execute("SELECT balance FROM users WHERE user_id = ?", (prijemce.id,))
            if not c.fetchone():
                await ctx.respond(f"Uživatel {prijemce.display_name} není zaregistrován v systému.", ephemeral=True)
                return
                
            # Výpočet poplatku a finální částky
            fee = castka * (TRANSACTION_FEE_PERCENT / 100.0)
            amount_to_receive = castka - fee

            # Provedeme obě operace najednou
            # Odečteme celou částku odesílateli
            c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (castka, ctx.author.id))
            # Přičteme částku po poplatku příjemci
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount_to_receive, prijemce.id))
            
            conn.commit()

        # Odeslání potvrzení
        embed = discord.Embed(
            title="✅ Transaction Successful",
            description=f"You have successfully sent credits.",
            color=discord.Color.green()
        )
        embed.add_field(name="Sender", value=ctx.author.mention, inline=True)
        embed.add_field(name="Recipient", value=prijemce.mention, inline=True)
        embed.add_field(name="Amount sent", value=f"{castka:.2f} Credits", inline=False)
        embed.add_field(name=f"Fee ({TRANSACTION_FEE_PERCENT}%)", value=f"-{fee:.2f} Credits", inline=True)
        embed.add_field(name="Amount to be credited", value=f"{amount_to_receive:.2f} Credits", inline=True)
        
        await ctx.respond(embed=embed)
    @commands.slash_command(name="conto", description="Displays your account status.", guild_ids=GUILD_IDS)
    async def balance(self, ctx):
        conn = sqlite3.connect('sazkovka.db')
        c = conn.cursor()
        c.execute("SELECT balance, twitch_points, twitch_username FROM users WHERE user_id = ?", (ctx.author.id,))
        result = c.fetchone()
        if result:
            balance, points, twitch_name = result
            response_text = f"Na tvém kontě je aktuálně: **{balance:.2f} Credits**."
            if twitch_name:
                response_text += f"\nJsi propojen s Twitchem jako: `{twitch_name}`"
                response_text += f"\nNasbírané body z Twitche: **{points or 0}** (převeď pomocí `/prevest_body`)"
            await ctx.respond(response_text, ephemeral=True)
        else:
            await ctx.respond("Nemáš ještě založený účet. Použij příkaz `/registrovat`.", ephemeral=True)
        conn.close()

    
    @commands.slash_command(name="daily", description=f"Claim your daily reward {DAILY_REWARD} Credit.", guild_ids=GUILD_IDS)
    async def daily(self, ctx: discord.ApplicationContext):
        conn = sqlite3.connect('sazkovka.db')
        c = conn.cursor()
        c.execute("SELECT balance, last_daily FROM users WHERE user_id = ?", (ctx.author.id,))
        user_data = c.fetchone()
        if not user_data:
            await ctx.respond("First you need to register using the `/register` command.", ephemeral=True)
            conn.close()
            return
        balance, last_daily_str = user_data
        now = datetime.datetime.now()
        cooldown = datetime.timedelta(hours=24)
        if last_daily_str:
            last_daily = datetime.datetime.fromisoformat(last_daily_str)
            if now - last_daily < cooldown:
                remaining = cooldown - (now - last_daily)
                hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                await ctx.respond(f"You have already claimed your daily reward. Try again later. **{hours}h a {minutes}m**.", ephemeral=True)
                conn.close()
                return
        c.execute("UPDATE users SET balance = balance + ?, last_daily = ? WHERE user_id = ?", (DAILY_REWARD, now.isoformat(), ctx.author.id))
        conn.commit()
        new_balance = balance + DAILY_REWARD
        conn.close()
        await ctx.respond(f"🎉 You have collected your daily reward. **{DAILY_REWARD} Credits**! Your new account is **{new_balance:.2f} Credits**.", ephemeral=True)

    # --- NOVÉ PŘÍKAZY PRO PROPOJENÍ S TWITCHEM ---

    @commands.slash_command(name="propojit_twitch", description="Propojí tvůj Discord účet s tvým Twitch jménem.", guild_ids=GUILD_IDS)
    async def link_twitch(self, ctx: discord.ApplicationContext, twitch_jmeno: str):
        twitch_username_lower = twitch_jmeno.lower()
        conn = sqlite3.connect('sazkovka.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (ctx.author.id,))
        if not c.fetchone():
            await ctx.respond("First you need to register using the `/register` command.", ephemeral=True)
            conn.close()
            return
        c.execute("SELECT user_id FROM users WHERE twitch_username = ?", (twitch_username_lower,))
        existing_link = c.fetchone()
        if existing_link and existing_link[0] != ctx.author.id:
            await ctx.respond(f"Twitch účet `{twitch_jmeno}` je již propojen s jiným Discord účtem!", ephemeral=True)
            conn.close()
            return
        c.execute("UPDATE users SET twitch_username = ? WHERE user_id = ?", (twitch_username_lower, ctx.author.id))
        conn.commit()
        conn.close()
        await ctx.respond(f"Tvůj účet byl úspěšně propojen s Twitchem: `{twitch_username_lower}`.", ephemeral=True)

    @commands.slash_command(name="prevest_body", description="Převede body nasbírané na Twitchi na Kredity.", guild_ids=GUILD_IDS)
    async def convert_points(self, ctx: discord.ApplicationContext):
        conn = sqlite3.connect('sazkovka.db')
        c = conn.cursor()
        c.execute("SELECT twitch_points FROM users WHERE user_id = ?", (ctx.author.id,))
        result = c.fetchone()
        if not result or result[0] is None:
            await ctx.respond("Nemáš žádné body k převedení nebo tvůj účet není propojen (`/propojit_twitch`).", ephemeral=True)
            conn.close()
            return
        points_to_convert = result[0]
        if points_to_convert <= 0:
            await ctx.respond("Máš 0 bodů z Twitche, není co převádět.", ephemeral=True)
            conn.close()
            return
        credits_to_add = points_to_convert * TWITCH_POINTS_TO_CREDITS_RATE
        c.execute("UPDATE users SET balance = balance + ?, twitch_points = 0 WHERE user_id = ?", (credits_to_add, ctx.author.id))
        conn.commit()
        c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
        new_balance = c.fetchone()[0]
        conn.close()
        await ctx.respond(f"Úspěšně jsi převedl **{points_to_convert}** bodů z Twitche na **{credits_to_add} Credits**!\nTvůj nový stav konta je **{new_balance:.2f} Credits**.", ephemeral=True)

    # --- ZBYTEK PŮVODNÍCH PŘÍKAZŮ ---
# v souboru 2.py, uvnitř třídy UserCommands

    async def _update_stats_and_xp(self, c, ctx: discord.ApplicationContext, sazka, vyhral, vyherni_nasobek=2.0):
        """Finální verze funkce pro zápis statistik a XP."""
        if vyhral:
            c.execute("UPDATE users SET games_played = games_played + 1, games_won = games_won + 1 WHERE user_id = ?", (ctx.author.id,))
        else:
            c.execute("UPDATE users SET games_played = games_played + 1 WHERE user_id = ?", (ctx.author.id,))
        
        profile_cog = self.bot.get_cog('ProfileCog')
        if not profile_cog: return

        xp_to_add = max(1.0, sazka * 0.1)
        if vyhral:
            xp_to_add *= vyherni_nasobek
        
        new_level = await profile_cog._add_xp(c, ctx.author.id, xp_to_add)
        if new_level:
            # ZMĚNA ZDE: Používáme followup.send pro spolehlivé odeslání
            try:
                await ctx.followup.send(f"🎉 **LEVEL UP!** Gratulujeme, {ctx.author.mention}! Právě jsi dosáhl/a **Levelu {new_level}**!")
            except Exception as e:
                print(f"Nepodařilo se odeslat followup zprávu o levelu: {e}")
    @commands.slash_command(name="matches", description="It lists all matches open for betting.", guild_ids=GUILD_IDS)
    async def list_matches(self, ctx):
        conn = sqlite3.connect('sazkovka.db')
        c = conn.cursor()
        c.execute("SELECT match_id, team1, team2 FROM matches WHERE status = 'open'")
        open_matches = c.fetchall()
        conn.close()
        if not open_matches:
            await ctx.respond("Momentálně nejsou vypsány žádné zápasy pro sázení.", ephemeral=True)
            return
        embed = discord.Embed(title="Aktuálně vypsané zápasy", color=discord.Color.blue())
        for match in open_matches:
            embed.add_field(name=f"ID zápasu: {match[0]}", value=f"**{match[1]}** vs **{match[2]}**", inline=False)
        await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(name="kurzy", description="Zobrazí aktuální dynamické kurzy pro daný zápas.", guild_ids=GUILD_IDS)
    async def odds(self, ctx, id_zapasu: int):
        conn = sqlite3.connect('sazkovka.db')
        c = conn.cursor()
        c.execute("SELECT team1, team2 FROM matches WHERE match_id = ? AND status = 'open'", (id_zapasu,))
        match = c.fetchone()
        if not match:
            await ctx.respond("Zápas s tímto ID neexistuje nebo je již uzavřen.", ephemeral=True)
            conn.close()
            return
        team1, team2 = match[0], match[1]
        c.execute("SELECT SUM(amount) FROM bets WHERE match_id = ?", (id_zapasu,))
        total_pot = c.fetchone()[0] or 0.0
        c.execute("SELECT SUM(amount) FROM bets WHERE match_id = ? AND team_bet_on = ?", (id_zapasu, team1))
        bet_on_team1 = c.fetchone()[0] or 0.0
        c.execute("SELECT SUM(amount) FROM bets WHERE match_id = ? AND team_bet_on = ?", (id_zapasu, team2))
        bet_on_team2 = c.fetchone()[0] or 0.0
        conn.close()
        odds_team1 = (total_pot / bet_on_team1) if bet_on_team1 > 0 else 0.0
        odds_team2 = (total_pot / bet_on_team2) if bet_on_team2 > 0 else 0.0
        embed = discord.Embed(title=f"Kurzy pro zápas: {team1} vs {team2} (ID: {id_zapasu})", color=discord.Color.gold())
        embed.add_field(name=f"Kurz na {team1}", value=f"{odds_team1:.2f}" if odds_team1 > 0 else "Zatím nevsazeno", inline=True)
        embed.add_field(name=f"Kurz na {team2}", value=f"{odds_team2:.2f}" if odds_team2 > 0 else "Zatím nevsazeno", inline=True)
        embed.set_footer(text=f"Celkem vsazeno na zápas: {total_pot:.2f} Credits")
        await ctx.respond(embed=embed, ephemeral=True)

    @minihry.command(name="coinflip", description="Bet on heads or tails.")
    async def coin_flip(self, ctx: discord.ApplicationContext, sazka: float, strana: discord.Option(str, "What are you betting on?", choices=["hlava", "orel"])):
        if sazka <= 0:
            await ctx.respond("The bet must be a positive number.", ephemeral=True)
            return

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
            result = c.fetchone()
            if not result or result[0] < sazka:
                await ctx.respond(f"You don't have enough Credits na tuto sázku.", ephemeral=True)
                return

            vysledek = random.choice(["hlava", "orel"])
            vyhral = (strana == vysledek)
            zmena_konta = sazka if vyhral else -sazka
            
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (zmena_konta, ctx.author.id))
            await self._update_stats_and_xp(c, ctx, sazka, vyhral, 2.0)
            conn.commit()

            c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
            final_balance = c.fetchone()[0]

        embed = discord.Embed(title="🪙 Hod mincí", color=discord.Color.green() if vyhral else discord.Color.red())
        embed.description = f"Padla **{vysledek}**! {'You win!' if vyhral else 'You are losing.'}"
        embed.add_field(name="Net profit/loss", value=f"{zmena_konta:+.2f} Credits", inline=True)
        embed.add_field(name="New account", value=f"{final_balance:.2f} Credits", inline=True)
        await ctx.respond(embed=embed)

    @commands.slash_command(name="vsadit", description="Vsaď si na vítěze zápasu.", guild_ids=GUILD_IDS)
    async def bet(self, ctx, id_zapasu: int, vitezny_tym: str, castka: float):
        if castka <= 0:
            await ctx.respond("The amount must be a positive number.", ephemeral=True)
            return
        conn = sqlite3.connect('sazkovka.db')
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
        user_balance = c.fetchone()
        if not user_balance:
            await ctx.respond("You do not have an account. Use `/register`.", ephemeral=True)
            conn.close()
            return
        if user_balance[0] < castka:
            await ctx.respond(f"You don't have enough Credits. Your account: {user_balance[0]:.2f} Credits.", ephemeral=True)
            conn.close()
            return
        c.execute("SELECT team1, team2 FROM matches WHERE match_id = ? AND status = 'open'", (id_zapasu,))
        match = c.fetchone()
        if not match:
            await ctx.respond("Tento zápas neexistuje nebo je již uzavřen pro sázení.", ephemeral=True)
            conn.close()
            return
        team1, team2 = match[0], match[1]
        if vitezny_tym.lower() not in (team1.lower(), team2.lower()):
            await ctx.respond(f"Neplatný tým. V tomto zápase hrají: {team1} a {team2}.", ephemeral=True)
            conn.close()
            return
        c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (castka, ctx.author.id))
        c.execute("INSERT INTO bets (user_id, match_id, team_bet_on, amount) VALUES (?, ?, ?, ?)", (ctx.author.id, id_zapasu, vitezny_tym.capitalize(), castka))
        conn.commit()
        conn.close()
        await ctx.respond(f"Úspěšně vsazeno **{castka:.2f} Credits** na vítězství týmu **{vitezny_tym.capitalize()}** v zápase s ID {id_zapasu}.", ephemeral=True)

    # v souboru 2.py, uvnitř třídy UserCommands

    @commands.slash_command(name="zebricek", description="Displays rankings of the best players in various categories.")
    async def leaderboard(self, ctx: discord.ApplicationContext, 
                          kategorie: discord.Option(str, "Vyber kategorii žebříčku", 
                                                    choices=["Kredity", "Level", "Odehrané hry", "Výhry", "Prestiž"])):
        await ctx.defer()

        query = ""
        title = ""
        value_format = ""

        if kategorie == "Kredity":
            query = "SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10"
            title = "🏆 Žebříček nejbohatších hráčů"
            value_format = "**{value:,.2f}** Credits"
        elif kategorie == "Level":
            query = "SELECT user_id, level, xp FROM users ORDER BY level DESC, xp DESC LIMIT 10"
            title = "🚀 Žebříček nejvyšších levelů"
            value_format = "**Level {value}** ({extra} XP)"
        elif kategorie == "Odehrané hry":
            query = "SELECT user_id, games_played FROM users ORDER BY games_played DESC LIMIT 10"
            title = "🎲 Žebříček největších gamblerů"
            value_format = "**{value}** her"
        elif kategorie == "Výhry":
            query = "SELECT user_id, games_won FROM users ORDER BY games_won DESC LIMIT 10"
            title = "🥇 Žebříček nejúspěšnějších hráčů"
            value_format = "**{value}** výher"
        elif kategorie == "Prestiž":
            query = "SELECT user_id, prestige FROM users WHERE prestige > 0 ORDER BY prestige DESC LIMIT 10"
            title = "⭐ Žebříček elitních hráčů"
            value_format = "**Prestiž {value}**"

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute(query)
            top_users = c.fetchall()

        if not top_users:
            await ctx.respond(f"V kategorii **{kategorie}** zatím nejsou žádní hráči k zobrazení.")
            return

        embed = discord.Embed(title=title, color=discord.Color.gold())
        
        for i, user_data in enumerate(top_users):
            user_id = user_data[0]
            try:
                user = await self.bot.fetch_user(user_id)
                user_name = user.display_name
            except discord.NotFound:
                user_name = f"Neznámý uživatel ({user_id})"

            # Formátování hodnoty podle kategorie
            if kategorie == "Level":
                value_str = value_format.format(value=user_data[1], extra=int(user_data[2]))
            else:
                # Pro formátování Credits použijeme speciální f-string
                if kategorie == "Kredity":
                    value_str = f"**{user_data[1]:,.2f}** Credits".replace(",", " ")
                else:
                    value_str = value_format.format(value=user_data[1])

            embed.add_field(name=f"#{i+1} {user_name}", value=value_str, inline=False)
            
        await ctx.respond(embed=embed)

    @commands.slash_command(name="moje_sazky", description="Zobrazí historii tvých sázek.", guild_ids=GUILD_IDS)
    async def my_bets(self, ctx):
        conn = sqlite3.connect('sazkovka.db')
        c = conn.cursor()
        c.execute("""
            SELECT m.team1, m.team2, b.team_bet_on, b.amount, m.status, m.winning_team
            FROM bets b JOIN matches m ON b.match_id = m.match_id
            WHERE b.user_id = ? ORDER BY m.match_id DESC
        """, (ctx.author.id,))
        user_bets = c.fetchall()
        conn.close()
        if not user_bets:
            await ctx.respond("Zatím jsi neuzavřel žádné sázky.", ephemeral=True)
            return
        embed = discord.Embed(title=f"Historie sázek pro {ctx.author.name}", color=discord.Color.purple())
        active_bets_str = ""
        past_bets_str = ""
        for bet in user_bets:
            team1, team2, team_bet_on, amount, status, winning_team = bet
            match_str = f"**{team1} vs {team2}**\n> Vsazeno: **{amount:.2f}** na **{team_bet_on}**\n"
            if status == 'open':
                active_bets_str += match_str
            else:
                if winning_team and team_bet_on.lower() == winning_team.lower():
                    match_str += f"> ✅ **Výhra!** (Vyhrál tým: {winning_team})\n"
                else:
                    match_str += f"> ❌ **Prohra!** (Vyhrál tým: {winning_team})\n"
                past_bets_str += match_str
        if active_bets_str:
            embed.add_field(name="--- Aktivní sázky ---", value=active_bets_str, inline=False)
        if past_bets_str:
            embed.add_field(name="--- Ukončené sázky ---", value=past_bets_str, inline=False)
        await ctx.respond(embed=embed, ephemeral=True)
# --- NOVÁ SEKCE PRO MINIHRY ---
    minihry = SlashCommandGroup("minihry", "Zahraj si o Kredity.", guild_ids=GUILD_IDS)
# v souboru sazkovka_bot.py, uvnitř třídy UserCommands

    async def _update_stats_and_xp(self, c, ctx, sazka, vyhral, vyherni_nasobek=2.0):
        """Nová centrální funkce pro zápis statistik a XP po dohrání hry."""
        if vyhral:
            c.execute("UPDATE users SET games_played = games_played + 1, games_won = games_won + 1 WHERE user_id = ?", (ctx.author.id,))
        else:
            c.execute("UPDATE users SET games_played = games_played + 1 WHERE user_id = ?", (ctx.author.id,))
        
        profile_cog = self.bot.get_cog('ProfileCog')
        if not profile_cog: return

        xp_to_add = max(1.0, sazka * 0.1)
        if vyhral:
            xp_to_add *= vyherni_nasobek
        
        # Změna: Předáváme existující 'c' (cursor) do funkce _add_xp
        new_level = await profile_cog._add_xp(c, ctx.author.id, xp_to_add)
        
        if new_level:
            await ctx.channel.send(f"🎉 **LEVEL UP!** Gratulujeme, {ctx.author.mention}! Právě jsi dosáhl/a **Levelu {new_level}**!")


    async def _handle_xp_gain(self, ctx, sazka, vyhral, vyherni_nasobek=2):
        """Centrální funkce pro zpracování zisku XP a level upů."""
        profile_cog = self.bot.get_cog('ProfileCog')
        if not profile_cog: return

        # Základní XP je 10% ze sázky (minimálně 1 XP)
        xp_to_add = max(1.0, sazka * 0.1)
        if vyhral:
            # Bonus za výhru je násobek základního zisku
            xp_to_add *= vyherni_nasobek 
        
        new_level = await profile_cog._add_xp(ctx.author.id, xp_to_add)
        if new_level:
            await ctx.channel.send(f"🎉 **LEVEL UP!** Gratulujeme, {ctx.author.mention}! Právě jsi dosáhl/a **Levelu {new_level}**!")
    
    @minihry.command(name="kostka", description="Displays rankings of the best players in various categories.")
    async def dice_roll(self, ctx: discord.ApplicationContext, sazka: float, volba: discord.Option(str, "Vsaď na...", choices=["nízká (2-6)", "vysoká (8-12)", "sedmička"])):
        if sazka <= 0:
            await ctx.respond("The bet must be a positive number.", ephemeral=True)
            return

        # Konfigurace pro jackpot
        JACKPOT_CONTRIBUTION_PERCENT = 1.0 # 1% z každé sázky jde do jackpotu
        JACKPOT_WIN_CHANCE = 50000 # Šance 1 ku 50,000 na výhru jackpotu
        
        jackpot_won_amount = 0

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
            result = c.fetchone()
            if not result or result[0] < sazka:
                await ctx.respond(f"You don't have enough Credits na tuto sázku.", ephemeral=True)
                return

            # Přičtení do jackpotu
            jackpot_contribution = sazka * (JACKPOT_CONTRIBUTION_PERCENT / 100.0)
            c.execute("UPDATE bot_settings SET setting_value = setting_value + ? WHERE setting_key = 'progressive_jackpot'", (jackpot_contribution,))
            
            # Herní logika
            d1, d2 = random.randint(1, 6), random.randint(1, 6)
            soucet = d1 + d2
            vyhral, nasobek = False, 0

            if soucet < 7 and volba == "nízká (2-6)": vyhral, nasobek = True, 2
            elif soucet > 7 and volba == "vysoká (8-12)": vyhral, nasobek = True, 2
            elif soucet == 7 and volba == "sedmička": vyhral, nasobek = True, 5
            
            zmena_konta = (sazka * nasobek) - sazka if vyhral else -sazka

            # Šance na výhru jackpotu
            if random.randint(1, JACKPOT_WIN_CHANCE) == 1:
                c.execute("SELECT setting_value FROM bot_settings WHERE setting_key = 'progressive_jackpot'")
                jackpot_won_amount = float(c.fetchone()[0])
                zmena_konta += jackpot_won_amount
                c.execute("UPDATE bot_settings SET setting_value = '10000' WHERE setting_key = 'progressive_jackpot'")

            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (zmena_konta, ctx.author.id))
            await self._update_stats_and_xp(c, ctx, sazka, vyhral, nasobek)
            conn.commit()

            c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
            final_balance = c.fetchone()[0]

        embed = discord.Embed(title="🎲 Hod kostkou 🎲", description=f"Hodils **{d1}** + **{d2}** = **{soucet}**", color=discord.Color.green() if vyhral else discord.Color.red())
        
        if jackpot_won_amount > 0:
            embed.add_field(name="🎉🎉🎉 JACKPOT! 🎉🎉🎉", value=f"Gratulujeme! Právě jsi trefil/a globální jackpot v hodnotě **{jackpot_won_amount:,.2f} Credits**!".replace(","," "), inline=False)
            embed.color = 0xFFD700 # Zlatá
        elif vyhral:
            embed.add_field(name="Výsledek", value=f"Gratuluji, trefil jsi **{volba}**!", inline=False)
        else:
            embed.add_field(name="Výsledek", value="Bohužel, tentokrát to nevyšlo.", inline=False)
        
        embed.add_field(name="Net profit/loss", value=f"{zmena_konta:+.2f} Credits", inline=True)
        embed.add_field(name="New account", value=f"{final_balance:.2f} Credits", inline=True)
        await ctx.respond(embed=embed)
# v souboru 2.py, ve třídě UserCommands nebo MinihryCog

    @minihry.command(name="blackjack", description="Play classic Blackjack against the dealer.")
    async def blackjack(self, ctx: discord.ApplicationContext, sazka: float):
        if sazka <= 0:
            await ctx.respond("The bet must be a positive number.", ephemeral=True)
            return

        # ZDE JE OPRAVA - argumenty jsou nyní ve správném pořadí: (bot, sázka, hráč)
        game = BlackjackGame(self.bot, sazka, ctx.author)
        
        # Hra sama se postará o první odpověď a kontrolu sázky
        await game.start_game(ctx)

    # v souboru 2.py, nahraďte původní funkci slots

    @minihry.command(name="automat", description="Roztoč válce a zkus vyhrát progresivní jackpot!")
    async def slots(self, ctx: discord.ApplicationContext, sazka: float):
        if sazka <= 0:
            await ctx.respond("The bet must be a positive number.", ephemeral=True)
            return

        # Konfigurace pro jackpot
        JACKPOT_CONTRIBUTION_PERCENT = 1.0 # 1% z každé sázky jde do jackpotu
        JACKPOT_WIN_CHANCE = 50000 # Šance 1 ku 50,000 na výhru jackpotu

        jackpot_won_amount = 0
        
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
            result = c.fetchone()
            if not result or result[0] < sazka:
                await ctx.respond(f"You don't have enough Credits na tuto sázku.", ephemeral=True)
                return

            # Přičtení do jackpotu a odečtení sázky
            jackpot_contribution = sazka * (JACKPOT_CONTRIBUTION_PERCENT / 100.0)
            c.execute("UPDATE bot_settings SET setting_value = setting_value + ? WHERE setting_key = 'progressive_jackpot'", (jackpot_contribution,))
            
            reels = ['🍒', '🍋', '🍊', '🍉', '⭐', '💎', '💰']
            weights = [25, 20, 15, 10, 8, 5, 2]
            payouts = {('💰','💰','💰'): 250, ('💎','💎','💎'): 100, ('⭐','⭐','⭐'): 50, ('🍉','🍉','🍉'): 25, ('🍊','🍊','🍊'): 15, ('🍋','🍋','🍋'): 10, ('🍒','🍒','🍒'): 5, ('💰','💰'): 10, ('💎','💎'): 5, ('⭐','⭐'): 3}
            
            r1, r2, r3 = random.choices(reels, weights=weights, k=3)
            nasobek, vyhral = 0, False
            
            if (r1, r2, r3) in payouts: nasobek = payouts[(r1, r2, r3)]
            elif (r1, r2) in payouts: nasobek = payouts[(r1, r2)]
            
            if nasobek > 0: vyhral = True
            
            zmena_konta = (sazka * nasobek) - sazka if vyhral else -sazka

            # Šance na výhru jackpotu
            if random.randint(1, JACKPOT_WIN_CHANCE) == 1:
                c.execute("SELECT setting_value FROM bot_settings WHERE setting_key = 'progressive_jackpot'")
                jackpot_won_amount = float(c.fetchone()[0])
                zmena_konta += jackpot_won_amount
                # Reset jackpotu na základní hodnotu
                c.execute("UPDATE bot_settings SET setting_value = '10000' WHERE setting_key = 'progressive_jackpot'")

            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (zmena_konta, ctx.author.id))
            await self._update_stats_and_xp(c, ctx, sazka, vyhral, nasobek)
            conn.commit()

            c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
            final_balance = c.fetchone()[0]

        embed = discord.Embed(title="🎰 Výherní automat 🎰", description=f"**| {r1} | {r2} | {r3} |**", color=discord.Color.gold() if vyhral else discord.Color.dark_grey())
        
        if jackpot_won_amount > 0:
            embed.add_field(name="🎉🎉🎉 JACKPOT! 🎉🎉🎉", value=f"Gratulujeme! Právě jsi trefil/a globální jackpot v hodnotě **{jackpot_won_amount:,.2f} Credits**!".replace(","," "), inline=False)
            embed.color = 0xFFD700 # Zlatá barva
        elif vyhral:
            embed.add_field(name="VÝHRA!", value=f"Trefil jsi kombinaci a vyhráváš **{nasobek}x** svoji sázku!", inline=False)
        else:
            embed.add_field(name="No win", value="Zkus to znovu!", inline=False)

        embed.add_field(name="Net profit/loss", value=f"{zmena_konta:+.2f} Credits", inline=True)
        embed.add_field(name="New account", value=f"{final_balance:.2f} Credits", inline=True)
        await ctx.respond(embed=embed)
    
    @minihry.command(name="koupit_los", description=f"Kup si stírací los za {SCRATCH_TICKET_PRICE} Credits.")
    async def buy_scratch_ticket(self, ctx: discord.ApplicationContext):
        conn, c = await self._check_and_deduct_bet(ctx, SCRATCH_TICKET_PRICE)
        if not conn: return
        conn.close() # Uzavřeme spojení, cena je odečtena

        # Vytvoříme a spustíme hru
        view = ScratchTicketView(self.bot, ctx, SCRATCH_TICKET_PRICE, SCRATCH_TICKET_PRIZES)
        embed = await view.create_initial_embed()
        
        # Odpovídáme na interakci se zprávou, která obsahuje tlačítka
        await ctx.respond(embed=embed, view=view)
 
    @minihry.command(name="ruleta", description="Vsaď si na číslo, barvu nebo sudou/lichou a hraj o jackpot!")
    async def roulette(self, ctx: discord.ApplicationContext, sazka: float, sazka_na: str):
        if sazka <= 0:
            await ctx.respond("The bet must be a positive number.", ephemeral=True)
            return

        # Konfigurace pro jackpot
        JACKPOT_CONTRIBUTION_PERCENT = 1.0 # 1% z každé sázky jde do jackpotu
        JACKPOT_WIN_CHANCE = 75000 # Šance 1 ku 75,000 na výhru jackpotu (o něco těžší než u ostatních)
        
        jackpot_won_amount = 0

        # Validace typu sázky
        sazka_na_lower = sazka_na.lower()
        bet_type, bet_value = None, None
        try:
            num = int(sazka_na_lower)
            if 0 <= num <= 36: bet_type, bet_value = 'cislo', num
        except ValueError:
            if sazka_na_lower in ['cervena', 'červená', 'red']: bet_type, bet_value = 'barva', 'red'
            elif sazka_na_lower in ['cerna', 'černá', 'black']: bet_type, bet_value = 'barva', 'black'
            elif sazka_na_lower in ['suda', 'sudá', 'even']: bet_type, bet_value = 'parita', 'suda'
            elif sazka_na_lower in ['licha', 'lichá', 'odd']: bet_type, bet_value = 'parita', 'licha'

        if not bet_type:
            await ctx.respond("Neplatný typ sázky. Vsaď na `červená`, `černá`, `sudá`, `lichá` nebo na číslo od 0 do 36.", ephemeral=True)
            return

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
            result = c.fetchone()
            if not result or result[0] < sazka:
                await ctx.respond(f"You don't have enough Credits na tuto sázku.", ephemeral=True)
                return

            # Přičtení do jackpotu
            jackpot_contribution = sazka * (JACKPOT_CONTRIBUTION_PERCENT / 100.0)
            c.execute("UPDATE bot_settings SET setting_value = setting_value + ? WHERE setting_key = 'progressive_jackpot'", (jackpot_contribution,))
            
            # Herní logika
            vysledek = random.randint(0, 36)
            vysledek_barva = ROULETTE_WHEEL[vysledek]
            vysledek_parita = 'suda' if vysledek != 0 and vysledek % 2 == 0 else 'licha'
            vyhral, nasobek = False, 0

            if bet_type == 'cislo' and bet_value == vysledek: vyhral, nasobek = True, 36
            elif bet_type == 'barva' and bet_value == vysledek_barva: vyhral, nasobek = True, 2
            elif bet_type == 'parita' and bet_value == vysledek_parita: vyhral, nasobek = True, 2
            
            zmena_konta = (sazka * nasobek) - sazka if vyhral else -sazka

            # Šance na výhru jackpotu
            if random.randint(1, JACKPOT_WIN_CHANCE) == 1:
                c.execute("SELECT setting_value FROM bot_settings WHERE setting_key = 'progressive_jackpot'")
                jackpot_won_amount = float(c.fetchone()[0])
                zmena_konta += jackpot_won_amount
                c.execute("UPDATE bot_settings SET setting_value = '10000' WHERE setting_key = 'progressive_jackpot'")

            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (zmena_konta, ctx.author.id))
            await self._update_stats_and_xp(c, ctx, sazka, vyhral, nasobek)
            conn.commit()

            c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
            final_balance = c.fetchone()[0]

        color_map = {'red': discord.Color.red(), 'black': discord.Color.dark_grey(), 'green': discord.Color.green()}
        embed = discord.Embed(title="🎡 Ruleta 🎡", description=f"Kulička se zastavila na čísle **{vysledek} {vysledek_barva.capitalize()}**!", color=color_map[vysledek_barva])

        if jackpot_won_amount > 0:
            embed.add_field(name="🎉🎉🎉 JACKPOT! 🎉🎉🎉", value=f"Gratulujeme! Právě jsi trefil/a globální jackpot v hodnotě **{jackpot_won_amount:,.2f} Credits**!".replace(","," "), inline=False)
            embed.color = 0xFFD700 # Zlatá
        elif vyhral:
            embed.add_field(name="VÝHRA!", value=f"You hit the bet on **{sazka_na}**!", inline=False)
        else:
            embed.add_field(name="No win", value=f"Bohužel, sázka na **{sazka_na}** nevyšla.", inline=False)
        
        embed.add_field(name="Net profit/loss", value=f"{zmena_konta:+.2f} Credits", inline=True)
        embed.add_field(name="New account", value=f"{final_balance:.2f} Credits", inline=True)
        await ctx.respond(embed=embed)


# v souboru sazkovka_bot.py

from PIL import Image, ImageDraw, ImageFont
import io
import aiohttp
import json

class ProfileCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.SHOP_ITEMS = {
            "xp_booster": {"name": "XP Booster (1 hodina)", "price": 1000, "type": "item", "description": "Na 1 hodinu získáš 2x více zkušeností (XP)."},
            "pozadi_hokej": {"name": "Pozadí: Hokej", "price": 15000, "type": "background", "filename": "hokej", "description": "Odemkne hokejové pozadí pro tvůj profil."},
            "pozadi_vesmir": {"name": "Pozadí: Vesmír", "price": 25000, "type": "background", "filename": "vesmir", "description": "Odemkne vesmírné pozadí pro tvůj profil."}
        }
        self.BADGES = {
            "level_10": "Level 10", "level_25": "Level 25", "level_50": "Level 50 (Prestiž ready)",
            "veteran": "Veterán (100+ her)", "milionar": "Milionář",
            "twitch": "Twitch Propojen", "prestige_1": "Prestiž I"
        }

    def get_xp_for_level(self, level):
        return int(150 * (level ** 1.5))

    async def _check_and_award_badges(self, c, user_id):
        c.execute("SELECT level, games_played, balance, twitch_username, badges, prestige FROM users WHERE user_id = ?", (user_id,))
        data = c.fetchone()
        if not data: return
        
        level, games, balance, twitch, badges_str, prestige = data
        badges = json.loads(badges_str)
        new_badges = []
        
        if level >= 10 and "level_10" not in badges: new_badges.append("level_10")
        if level >= 25 and "level_25" not in badges: new_badges.append("level_25")
        if level >= PRESTIGE_MAX_LEVEL and "level_50" not in badges: new_badges.append("level_50")
        if games >= 100 and "veteran" not in badges: new_badges.append("veteran")
        if balance >= 1000000 and "milionar" not in badges: new_badges.append("milionar")
        if twitch and "twitch" not in badges: new_badges.append("twitch")
        if prestige >= 1 and "prestige_1" not in badges: new_badges.append("prestige_1")
        
        if new_badges:
            badges.extend(new_badges)
            c.execute("UPDATE users SET badges = ? WHERE user_id = ?", (json.dumps(badges), user_id))
            try:
                user = await self.bot.fetch_user(user_id)
                new_badge_names = [self.BADGES[b] for b in new_badges if b in self.BADGES]
                if new_badge_names:
                    await user.send(f"🏆 Gratulujeme! Získal jsi nové medaile: **{', '.join(new_badge_names)}**")
            except Exception as e:
                print(f"Nepodařilo se odeslat DM o medaili: {e}")

    # v souboru sazkovka_bot.py, uvnitř třídy ProfileCog

    async def _add_xp(self, c, user_id, amount):
        """Centrální funkce POUZE pro přidávání XP a kontrolu level upů."""
        new_level = None
        
        c.execute("SELECT level, xp, xp_booster_end_time FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        if not result: return None

        level, xp, booster_end_str = result
        if level >= PRESTIGE_MAX_LEVEL:
            return None

        if booster_end_str and datetime.datetime.now() < datetime.datetime.fromisoformat(booster_end_str):
            amount *= 2
        
        xp += amount
        xp_for_next_level = self.get_xp_for_level(level)
        
        while xp >= xp_for_next_level and level < PRESTIGE_MAX_LEVEL:
            xp -= xp_for_next_level
            level += 1
            new_level = level
            xp_for_next_level = self.get_xp_for_level(level)

        c.execute("UPDATE users SET level = ?, xp = ? WHERE user_id = ?", (level, xp, user_id))
        if new_level:
            await self._check_and_award_badges(c, user_id)
        
        return new_level

    async def generate_profile_image(self, user: discord.Member):
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT user_id FROM users ORDER BY balance DESC")
            sorted_users = [row[0] for row in c.fetchall()]
            try:
                rank = sorted_users.index(user.id) + 1
            except ValueError: rank = 'N/A'
            c.execute("SELECT level, xp, balance, games_played, games_won, badges, prestige, active_background FROM users WHERE user_id = ?", (user.id,))
            data = c.fetchone()
        if not data: return None
        
        level, xp, balance, games, wins, badges_str, prestige, active_bg = data
        xp_needed = self.get_xp_for_level(level)
        xp_percent = (xp / xp_needed) * 100 if xp_needed > 0 else 100
        badges = json.loads(badges_str)
        win_rate = (wins / games) * 100 if games > 0 else 0

        try:
            bg = Image.open(f"backgrounds/{active_bg}.png").convert("RGBA")
        except FileNotFoundError:
            bg = Image.open("backgrounds/default.png").convert("RGBA")

        font_big = ImageFont.truetype("font.ttf", 50)
        font_medium = ImageFont.truetype("font.ttf", 35)
        font_small = ImageFont.truetype("font.ttf", 28)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(str(user.display_avatar.url)) as resp:
                avatar_data = await resp.read()
        avatar = Image.open(io.BytesIO(avatar_data)).convert("RGBA").resize((160, 160))
        mask = Image.new("L", avatar.size, 0)
        draw_mask = ImageDraw.Draw(mask)
        draw_mask.ellipse((0, 0) + avatar.size, fill=255)
        
        draw = ImageDraw.Draw(bg)
        bg.paste(avatar, (60, 60), mask)
        
        prestige_stars = '⭐' * prestige
        draw.text((250, 65), f"{user.display_name} {prestige_stars}", font=font_big, fill="#FFFFFF")
        draw.text((255, 125), f"Level {level}", font=font_medium, fill="#dddddd")
        draw.text((700, 30), f"🏆 Pořadí: #{rank}", font=font_medium, fill="#FFD700")

        bar_x, bar_y, bar_w, bar_h = 250, 180, 660, 35
        draw.rectangle((bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), fill="#444444")
        if xp_percent > 0:
            draw.rectangle((bar_x, bar_y, bar_x + (bar_w * xp_percent / 100), bar_y + bar_h), fill="#00A9FF")
        xp_text = f"{int(xp)} / {xp_needed} XP" if level < PRESTIGE_MAX_LEVEL else "MAX LEVEL"
        draw.text((bar_x + 15, bar_y - 1), xp_text, font=font_small, fill="#FFFFFF")
        
        draw.text((65, 250), f"Kredity: {balance:,.2f}".replace(",", " "), font=font_medium, fill="#FFFFFF")
        draw.text((65, 300), f"Odehrané hry: {games}", font=font_small, fill="#cccccc")
        draw.text((300, 300), f"Výhry: {wins}", font=font_small, fill="#cccccc")
        draw.text((480, 300), f"Úspěšnost: {win_rate:.1f}%", font=font_small, fill="#cccccc")

        badge_x, badge_y = 65, 350
        for badge_name in badges:
            try:
                badge_img = Image.open(f"badges/{badge_name}.png").convert("RGBA").resize((64, 64))
                bg.paste(badge_img, (badge_x, badge_y), badge_img)
                badge_x += 74
            except FileNotFoundError:
                print(f"Chyba: Obrázek pro medaili 'badges/{badge_name}.png' nebyl nalezen.")

        buffer = io.BytesIO()
        bg.save(buffer, format="PNG")
        buffer.seek(0)
        return discord.File(buffer, filename="profile.png")

    @commands.slash_command(name="profil", description="Displays your or someone else's game profile.")
    async def profile(self, ctx: discord.ApplicationContext, uzivatel: discord.Option(discord.Member, "Zobraz profil tohoto uživatele (nepovinné)", required=False) = None):
        target_user = uzivatel or ctx.author
        await ctx.defer()
        image_file = await self.generate_profile_image(target_user)
        if not image_file:
            await ctx.respond(f"Uživatel `{target_user.display_name}` ještě není zaregistrován.", ephemeral=True)
            return
        await ctx.respond(file=image_file)

    @commands.slash_command(name="obchod", description="Zobrazí nabídku e-shopu.")
    async def shop(self, ctx: discord.ApplicationContext):
        embed = discord.Embed(title="🛒 E-shop", description="Vítej v obchodě! Zde si můžeš za své Kredity koupit vylepšení.", color=discord.Color.teal())
        for item_id, item_data in self.SHOP_ITEMS.items():
            embed.add_field(name=f"{item_data['name']} - Cena: {item_data['price']} Credits", value=item_data['description'], inline=False)
        await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(name="obchod_koupit", description="Koupí předmět z e-shopu.")
    async def buy_item(self, ctx: discord.ApplicationContext, polozka: str):
        item_id = polozka.lower().replace(" ", "_") # 'Pozadí: Hokej' -> 'pozadi:_hokej'
        if item_id not in self.SHOP_ITEMS:
            await ctx.respond("Tato položka neexistuje. Podívej se do `/obchod`.", ephemeral=True)
            return
        
        item_data = self.SHOP_ITEMS[item_id]
        
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT balance, owned_backgrounds FROM users WHERE user_id = ?", (ctx.author.id,))
            result = c.fetchone()
            if not result:
                await ctx.respond("You must register first.", ephemeral=True)
                return
            
            balance, owned_bgs_str = result
            if balance < item_data['price']:
                await ctx.respond(f"You don't have enough Credits. Potřebuješ {item_data['price']}, ale máš jen {balance:.2f}.", ephemeral=True)
                return

            new_balance = balance - item_data['price']

            if item_data['type'] == 'item':
                c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_balance, ctx.author.id))
                # Zde logika pro specifické itemy, např. XP booster
                # ...
            elif item_data['type'] == 'background':
                owned_bgs = json.loads(owned_bgs_str)
                if item_data['filename'] in owned_bgs:
                    await ctx.respond("Toto pozadí již vlastníš!", ephemeral=True)
                    return
                owned_bgs.append(item_data['filename'])
                c.execute("UPDATE users SET balance = ?, owned_backgrounds = ? WHERE user_id = ?", (new_balance, json.dumps(owned_bgs), ctx.author.id))

            conn.commit()
            await ctx.respond(f"Úspěšně jsi zakoupil/a **{item_data['name']}**! Použij `/profil nastavit_pozadi` pro jeho aktivaci.", ephemeral=True)

    @commands.slash_command(name="prestige", description=f"Vyměň svůj Level {PRESTIGE_MAX_LEVEL} za prestiž a obrovskou odměnu!")
    async def prestige(self, ctx: discord.ApplicationContext):
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT level, prestige FROM users WHERE user_id = ?", (ctx.author.id,))
            result = c.fetchone()
            if not result:
                await ctx.respond("You must register first.", ephemeral=True)
                return
            
            level, prestige = result
            if level < PRESTIGE_MAX_LEVEL:
                await ctx.respond(f"Ještě nemůžeš použít prestiž! Musíš nejprve dosáhnout **Levelu {PRESTIGE_MAX_LEVEL}**.", ephemeral=True)
                return

            new_prestige = prestige + 1
            c.execute("UPDATE users SET level=1, xp=0, prestige=?, balance = balance + ? WHERE user_id=?", (new_prestige, PRESTIGE_REWARD, ctx.author.id))
            await self._check_and_award_badges(c, ctx.author.id)
            conn.commit()

        await ctx.respond(f"**GRATULUJEME K PRESTIŽI!** {ctx.author.mention} obětoval svůj level a dosáhl **Prestiže {new_prestige}**! Za odměnu získal **{PRESTIGE_REWARD:,.0f} Credits** a jeho cesta začíná nanovo!".replace(",", " "))

    @commands.slash_command(name="profil_nastavit_pozadi", description="Nastaví zakoupené pozadí na tvém profilu.")
    async def set_background(self, ctx: discord.ApplicationContext, nazev: str):
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT owned_backgrounds FROM users WHERE user_id = ?", (ctx.author.id,))
            result = c.fetchone()
            if not result:
                await ctx.respond("You must register first.", ephemeral=True)
                return
            
            owned_bgs = json.loads(result[0])
            nazev_lower = nazev.lower()

            if nazev_lower not in owned_bgs:
                await ctx.respond(f"Nevlastníš pozadí s názvem `{nazev}`. Můžeš si ho koupit v `/obchod`.", ephemeral=True)
                return
            
            c.execute("UPDATE users SET active_background = ? WHERE user_id = ?", (nazev_lower, ctx.author.id))
            conn.commit()
            await ctx.respond(f"Tvoje profilové pozadí bylo nastaveno na `{nazev_lower}`.", ephemeral=True)

# v souboru sazkovka_bot.py
# v souboru sazkovka_bot.py

# Ujistěte se, že máte nahoře tento import
from roulette_logic import RouletteView

# --- NOVÁ TŘÍDA (COG) PRO MULTIPLAYER RULETU ---
class RouletteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_roulette_game = None

    BETTING_DURATION = 30 # Délka sázkové fáze v sekundách

    ruleta_multiplayer = SlashCommandGroup("ruleta_multiplayer", "Hraj ruletu s ostatními hráči!", guild_ids=GUILD_IDS)

    @ruleta_multiplayer.command(name="start", description="Spustí nové kolo multiplayer rulety.")
    async def start_mp_roulette(self, ctx: discord.ApplicationContext):
        if self.active_roulette_game:
            await ctx.respond("The roulette wheel is already running! Wait for it to finish.", ephemeral=True)
            return

        await ctx.defer()
        voice_assistant = self.bot.get_cog('VoiceAssistantCog')
        if voice_assistant:
            await voice_assistant.speak("I'm starting a new round of roulette! I'm accepting bets.")

        end_time = datetime.datetime.now() + datetime.timedelta(seconds=self.BETTING_DURATION)
        self.active_roulette_game = {"bets": [], "message": None, "betting_end_time": end_time}
        
        embed = discord.Embed(title="🎡 Multiplayer Ruleta 🎡", description=f"**Sázky jsou otevřeny!** Kolo se točí za **{self.BETTING_DURATION} sekund**.\n\nKlikni na tlačítko a vsaď si!", color=discord.Color.dark_purple())
        embed.set_footer(text="Sázky se uzavřou")
        embed.timestamp = end_time
        
        view = RouletteView(self.bot)
        message = await ctx.respond(embed=embed, view=view)
        self.active_roulette_game["message"] = message

        await asyncio.sleep(self.BETTING_DURATION)
        await self._spin_the_wheel()
    
    async def handle_bet_submission(self, interaction: discord.Interaction, sazka_na_str, sazka_str):
        if not self.active_roulette_game or datetime.datetime.now() > self.active_roulette_game["betting_end_time"]:
            await interaction.response.send_message("Sázky na tuto hru jsou již bohužel uzavřeny.", ephemeral=True)
            return
        
        try:
            sazka = float(sazka_str)
            if sazka <= 0: raise ValueError("The bet must be positive.")
        except ValueError:
            await interaction.response.send_message("Invalid bet amount. Please enter a positive number.", ephemeral=True)
            return
        
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT balance FROM users WHERE user_id = ?", (interaction.user.id,))
            result = c.fetchone()
            if not result:
                await interaction.response.send_message("You must register first.", ephemeral=True)
                return
            balance = result[0]
            if balance < sazka:
                await interaction.response.send_message(f"You don't have enough Credits. Your account: **{balance:.2f} Credits**.", ephemeral=True)
                return
            
            c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (balance - sazka, interaction.user.id))
            conn.commit()
            
        self.active_roulette_game["bets"].append({'user_id': interaction.user.id, 'user_mention': interaction.user.mention, 'sazka_na': sazka_na_str, 'sazka': sazka})
        await interaction.response.send_message(f"I accepted your bet. **{sazka:.2f} Credits** na **{sazka_na_str}**.", ephemeral=True)

    async def _spin_the_wheel(self):
        if not self.active_roulette_game: return
        
        message = self.active_roulette_game["message"]
        view = RouletteView(self.bot)
        for item in view.children: item.disabled = True
        
        embed = message.embeds[0]
        embed.description = "**Sázky uzavřeny!** Kolo se točí..."
        embed.color = discord.Color.orange()
        embed.set_footer(text=None)
        embed.timestamp = None
        voice_assistant = self.bot.get_cog('VoiceAssistantCog')
        if voice_assistant:
            await voice_assistant.speak("Sázky uzavřeny, kolo se točí!")
        await message.edit(embed=embed, view=view)
        await asyncio.sleep(3)

        vysledek_cislo = random.randint(0, 36)
        vysledek_barva = ROULETTE_WHEEL[vysledek_cislo]
        vysledek_parita = 'suda' if vysledek_cislo != 0 and vysledek_cislo % 2 == 0 else 'licha'
        
        color_map = {'red': discord.Color.red(), 'black': discord.Color.dark_grey(), 'green': discord.Color.green()}
        final_embed = discord.Embed(title="🎡 Konec Sázek 🎡", description=f"Kulička se zastavila na čísle **{vysledek_cislo}**!", color=color_map[vysledek_barva])
        
        winners_payouts = {}
        
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            profile_cog = self.bot.get_cog('ProfileCog')
            
            for bet in self.active_roulette_game["bets"]:
                vyhral, nasobek = False, 0
                sazka_na_lower = bet['sazka_na'].lower()

                try:
                    num_bet = int(sazka_na_lower)
                    if num_bet == vysledek_cislo: vyhral, nasobek = True, 36
                except ValueError:
                    if sazka_na_lower in ['cervena', 'červená', 'red'] and vysledek_barva == 'red': vyhral, nasobek = True, 2
                    elif sazka_na_lower in ['cerna', 'černá', 'black'] and vysledek_barva == 'black': vyhral, nasobek = True, 2
                    elif sazka_na_lower in ['suda', 'sudá', 'even'] and vysledek_parita == 'suda': vyhral, nasobek = True, 2
                    elif sazka_na_lower in ['licha', 'lichá', 'odd'] and vysledek_parita == 'licha': vyhral, nasobek = True, 2

                # Aktualizace statistik a XP
                if vyhral:
                    c.execute("UPDATE users SET games_played = games_played + 1, games_won = games_won + 1 WHERE user_id = ?", (bet['user_id'],))
                else:
                    c.execute("UPDATE users SET games_played = games_played + 1 WHERE user_id = ?", (bet['user_id'],))
                
                if profile_cog:
                    xp_to_add = max(1.0, bet['sazka'] * 0.1) * nasobek if vyhral else max(1.0, bet['sazka'] * 0.1)
                    await profile_cog._add_xp(c, bet['user_id'], xp_to_add)

                # Vyplacení výhry
                if vyhral:
                    payout = bet['sazka'] * nasobek
                    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (payout, bet['user_id']))
                    winners_payouts[bet['user_mention']] = winners_payouts.get(bet['user_mention'], 0) + payout
            
            conn.commit()

        if not winners_payouts:
            final_embed.add_field(name="Výherci", value="Bohužel, tentokrát nikdo nic nevyhrál.", inline=False)
        else:
            winners_text = ""
            for user_mention, total_payout in winners_payouts.items():
                winners_text += f"{user_mention} vyhrál/a celkem **{total_payout:.2f} Credits**!\n"
            final_embed.add_field(name="Congratulations to the winners!", value=winners_text, inline=False)
        
        await message.edit(embed=final_embed, view=None)
        self.active_roulette_game = None # Reset hry
# NOVINKA: Funkce, která kontroluje, zda je uživatel admin NEBO vlastník bota
async def is_admin_or_owner(ctx: discord.ApplicationContext):
    if ctx.user.id == OWNER_ID:
        return True # Pokud je to vlastník, vždy povolit
    
    # Pokud to není vlastník, zkontrolujeme, jestli je to admin serveru
    return ctx.user.guild_permissions.administrator
# --- Skupina (Cog) pro administrátory ---
class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

# v souboru 2.py, uvnitř třídy AdminCommands

    # v souboru 2.py, uvnitř třídy AdminCommands
    admin = SlashCommandGroup("admin", "Příkazy pro správu sázkové kanceláře", guild_ids=GUILD_IDS)
    uzivatel = admin.create_subgroup("uzivatel", "Spravuje účty a kredity uživatelů.")
    zapas = admin.create_subgroup("zapas", "Spravuje sázkové zápasy.")
    sazka_admin = admin.create_subgroup("sazka", "Spravuje kurzy a sázkové příležitosti.")
    giveaway = admin.create_subgroup("giveaway", "Spravuje giveawaye o kredity")
    twitch = admin.create_subgroup("twitch", "Spravuje body a propojení s Twitchem.")
    hrac = admin.create_subgroup("hrac", "Spravuje hráče na fantasy trhu.")
    ai_admin = admin.create_subgroup("ai", "Nástroje umělé inteligence pro administrátory.")
    loterie_admin = admin.create_subgroup("loterie", "Spravuje týdenní loterii.")

    @hrac.command(name="pridat", description="[Admin] Přidá nového hokejistu na fantasy trh.")
    @commands.check(is_admin_or_owner)
    async def add_player_to_market(self, ctx: discord.ApplicationContext, jmeno: str, pocatecni_hodnota: float):
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            try:
                history = json.dumps([pocatecni_hodnota])
                c.execute("INSERT INTO players (name, current_value, history) VALUES (?, ?, ?)", (jmeno, pocatecni_hodnota, history))
                conn.commit()
                await ctx.respond(f"Hráč **{jmeno}** byl úspěšně přidán na trh s hodnotou **{pocatecni_hodnota:.2f} Credits**.", ephemeral=True)
            except sqlite3.IntegrityError:
                await ctx.respond("Hráč s tímto jménem již na trhu existuje.", ephemeral=True)


    @hrac.command(name="update", description="[Admin] Aktualizuje hodnotu hráče na základě jeho výkonu v zápase.")
    @commands.check(is_admin_or_owner)
    async def update_player_value(self, ctx: discord.ApplicationContext, jmeno: str, goly: int = 0, asistence: int = 0):
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT player_id, current_value, history FROM players WHERE name = ?", (jmeno,))
            player_data = c.fetchone()
            if not player_data:
                await ctx.respond("Hráč s tímto jménem nebyl na trhu nalezen.", ephemeral=True)
                return

            player_id, old_value, history_str = player_data
            value_change = (goly * PLAYER_VALUE_PER_GOAL) + (asistence * PLAYER_VALUE_PER_ASSIST)
            
            # Pokud hráč nebodoval, může jeho hodnota mírně klesnout (simulace formy)
            if value_change == 0:
                value_change = - (old_value * random.uniform(0.01, 0.03)) # Pokles o 1-3%
            
            new_value = max(100.0, old_value + value_change) # Hodnota neklesne pod 100
            
            history = json.loads(history_str)
            history.append(new_value)
            if len(history) > 10: history.pop(0) # Udržujeme historii posledních 10 změn

            c.execute("UPDATE players SET current_value = ?, history = ? WHERE player_id = ?", (new_value, json.dumps(history), player_id))
            conn.commit()
            
            emoji = "📈" if new_value > old_value else "📉"
            await ctx.respond(f"{emoji} Hodnota hráče **{jmeno}** byla aktualizována na **{new_value:,.2f} Credits** (změna: {new_value - old_value:+.2f}).".replace(",", " "))

    

    # --- PODSKUPINA PRO SPRÁVU UŽIVATELŮ ---
    

    @uzivatel.command(name="info", description="[Admin] Zobrazí informace o konkrétním uživateli.")
    @commands.check(is_admin_or_owner) # ZDE JE ZMĚNA
    async def user_info(self, ctx: discord.ApplicationContext, uzivatel: discord.Member):
        conn = sqlite3.connect('sazkovka.db')
        c = conn.cursor()
        c.execute("SELECT balance, twitch_username, twitch_points FROM users WHERE user_id = ?", (uzivatel.id,))
        result = c.fetchone()
        conn.close()

        if not result:
            await ctx.respond(f"Uživatel {uzivatel.mention} nemá založený účet.", ephemeral=True)
            return

        balance, twitch_name, twitch_points = result
        embed = discord.Embed(title=f"Info o uživateli: {uzivatel.display_name}", color=discord.Color.orange())
        embed.set_thumbnail(url=uzivatel.display_avatar.url)
        embed.add_field(name="Kredity", value=f"**{balance:.2f}**", inline=True)
        embed.add_field(name="Twitch body", value=f"**{twitch_points or 0}**", inline=True)
        embed.add_field(name="Propojený Twitch", value=f"`{twitch_name}`" if twitch_name else "Není propojen", inline=False)
        
        await ctx.respond(embed=embed, ephemeral=True)

    @uzivatel.command(name="pridat_kredity", description="[Admin] Přidá kredity na účet uživatele.")
    @commands.check(is_admin_or_owner) # ZDE JE ZMĚNA
    async def add_credits(self, ctx: discord.ApplicationContext, uzivatel: discord.Member, pocet: float):
        if pocet <= 0:
            await ctx.respond("Počet musí být kladné číslo.", ephemeral=True)
            return
        conn = sqlite3.connect('sazkovka.db')
        c = conn.cursor()
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (pocet, uzivatel.id))
        conn.commit()
        if conn.total_changes == 0:
            await ctx.respond(f"Uživatel {uzivatel.mention} nemá účet.", ephemeral=True)
        else:
            await ctx.respond(f"Uživateli {uzivatel.mention} bylo úspěšně připsáno **{pocet:.2f} Credits**.", ephemeral=True)
        conn.close()

    @uzivatel.command(name="odebrat_kredity", description="[Admin] Odebere kredity z účtu uživatele.")
    @commands.check(is_admin_or_owner) # ZDE JE ZMĚNA
    async def remove_credits(self, ctx: discord.ApplicationContext, uzivatel: discord.Member, pocet: float):
        if pocet <= 0:
            await ctx.respond("Počet musí být kladné číslo.", ephemeral=True)
            return
        conn = sqlite3.connect('sazkovka.db')
        c = conn.cursor()
        c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (pocet, uzivatel.id))
        conn.commit()
        if conn.total_changes == 0:
            await ctx.respond(f"Uživatel {uzivatel.mention} nemá účet.", ephemeral=True)
        else:
            await ctx.respond(f"Uživateli {uzivatel.mention} bylo úspěšně odebráno **{pocet:.2f} Credits**.", ephemeral=True)
        conn.close()

    @uzivatel.command(name="nastavit_kredity", description="[Admin] Nastaví přesný počet Credits na účtu uživatele.")
    @commands.check(is_admin_or_owner) # ZDE JE ZMĚNA
    async def set_credits(self, ctx: discord.ApplicationContext, uzivatel: discord.Member, pocet: float):
        if pocet < 0:
            await ctx.respond("Počet nemůže být záporné číslo.", ephemeral=True)
            return
        conn = sqlite3.connect('sazkovka.db')
        c = conn.cursor()
        c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (pocet, uzivatel.id))
        conn.commit()
        if conn.total_changes == 0:
            await ctx.respond(f"Uživatel {uzivatel.mention} nemá účet.", ephemeral=True)
        else:
            await ctx.respond(f"Konto uživatele {uzivatel.mention} bylo nastaveno na **{pocet:.2f} Credits**.", ephemeral=True)
        conn.close()



    # v souboru 2.py, uvnitř třídy AdminCommands
    
    # v souboru 2.py, uvnitř třídy AdminCommands

    # --- PODSKUPINA PRO SPRÁVU SÁZKOVÝCH PŘÍLEŽITOSTÍ ---
    
    

    @sazka_admin.command(name="pridat_moznost", description="[Admin] Přidá novou sázkovou možnost k existujícímu zápasu.")
    @commands.check(is_admin_or_owner)
    async def add_bet_option(self, ctx: discord.ApplicationContext, 
                             id_zapasu: int, 
                             typ_sazky: discord.Option(str, choices=["vitez", "skore", "over_under"]),
                             hodnota_sazky: str,
                             kurz: float):
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            try:
                c.execute("INSERT INTO betting_options (match_id, bet_type, bet_value, odds) VALUES (?, ?, ?, ?)",
                          (id_zapasu, typ_sazky, hodnota_sazky, kurz))
                conn.commit()
                await ctx.respond(f"Sázková možnost `{typ_sazky}` na `{hodnota_sazky}` s kurzem `{kurz}` byla úspěšně přidána k zápasu {id_zapasu}.", ephemeral=True)
            except sqlite3.IntegrityError:
                await ctx.respond("Tato sázková možnost již u tohoto zápasu existuje.", ephemeral=True)
            except Exception as e:
                await ctx.respond(f"Nastala chyba: {e}", ephemeral=True)

    @zapas.command(name="pridat_zapas", description="[Admin] Vytvoří nový zápas pro sázení.")
    @commands.check(is_admin_or_owner)
    async def pridat_zapas(self, ctx: discord.ApplicationContext, tym1: str, tym2: str):
        """Vytvoří nový zápas a automaticky přidá základní sázkové možnosti."""
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            
            # Vytvoříme nový zápas
            c.execute("INSERT INTO matches (team1, team2, status) VALUES (?, ?, 'open')", (tym1, tym2))
            match_id = c.lastrowid
            
            # Přidáme základní sázkové možnosti
            default_odds = [
                ("vitez", tym1, 2.0),
                ("vitez", tym2, 2.0),
                ("vitez", "remiza", 3.5),
            ]
            
            for bet_type, bet_value, odds in default_odds:
                c.execute("INSERT INTO betting_options (match_id, bet_type, bet_value, odds) VALUES (?, ?, ?, ?)",
                         (match_id, bet_type, bet_value, odds))
            
            conn.commit()
        
        # Vytvoříme embed pro oznámení
        embed = discord.Embed(
            title="🆕 Nový Zápas k Sázení!", 
            description=f"**{tym1}** vs **{tym2}**",
            color=discord.Color.green()
        )
        embed.add_field(name="ID Zápasu", value=f"`{match_id}`", inline=True)
        embed.add_field(name="Status", value="Otevřeno pro sázení", inline=True)
        embed.add_field(
            name="Základní kurzy", 
            value=f"**{tym1}**: 2.0x\n**{tym2}**: 2.0x\n**Remíza**: 3.5x",
            inline=False
        )
        embed.set_footer(text=f"Pro sázení použij: /sazka vsadit {match_id}")
        
        await ctx.respond(embed=embed)
        
        # Odešleme oznámení do kanálu
        await ctx.channel.send(f"@everyone New match is available! Bet on **{tym1} vs {tym2}**!", embed=embed)

    @zapas.command(name="vyhodnotit", description="[Admin] Vyhodnotí zápas na základě finálního skóre.")
    @commands.check(is_admin_or_owner)
    async def settle_match(self, ctx: discord.ApplicationContext, id_zapasu: int, skore: str):
        # Validace skóre (např. "3:1")
        match = re.match(r"(\d+):(\d+)", skore)
        if not match:
            await ctx.respond("Neplatný formát skóre. Použij formát `DOMÁCÍ:HOSTÉ`, např. `3:1`.", ephemeral=True)
            return
        
        score_home, score_away = int(match.group(1)), int(match.group(2))
        total_goals = score_home + score_away
        
        await ctx.defer()
        
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT team1, team2 FROM matches WHERE match_id = ? AND status = 'open'", (id_zapasu,))
            match_info = c.fetchone()
            if not match_info:
                await ctx.respond("A match with this ID does not exist or has already been evaluated.", ephemeral=True)
                return
            
            team_home, team_away = match_info
            winner = team_home if score_home > score_away else team_away if score_away > score_home else "remiza"

            # Najdeme všechny nevyhodnocené sázky na tento zápas
            c.execute("SELECT bet_id, user_id, bet_type, bet_value, odds, amount FROM bets WHERE match_id = ? AND status = 'pending'", (id_zapasu,))
            pending_bets = c.fetchall()
            
            winners_payouts = {}

            for bet_id, user_id, bet_type, bet_value, odds, amount in pending_bets:
                won = False
                if bet_type == 'vitez' and bet_value.lower() == winner.lower(): won = True
                elif bet_type == 'skore' and bet_value == skore: won = True
                elif bet_type == 'over_under':
                    try:
                        limit = float(bet_value.split('_')[1])
                        if bet_value.startswith('over') and total_goals > limit: won = True
                        elif bet_value.startswith('under') and total_goals < limit: won = True
                    except: pass # Neplatná hodnota sázky

                if won:
                    payout = amount * odds
                    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (payout, user_id))
                    c.execute("UPDATE bets SET status = 'won' WHERE bet_id = ?", (bet_id,))
                    winners_payouts[user_id] = winners_payouts.get(user_id, 0) + payout
                else:
                    c.execute("UPDATE bets SET status = 'lost' WHERE bet_id = ?", (bet_id,))
            
            c.execute("UPDATE matches SET status = 'finished' WHERE match_id = ?", (id_zapasu,))
            conn.commit()

        # Oznámení výsledků
        embed = discord.Embed(title=f"Výsledky Zápasu: {team_home} vs {team_away}", description=f"**Konečné skóre: {skore}**", color=0x58D68D)
        if not winners_payouts:
            embed.add_field(name="Výplaty", value="Žádné vítězné sázky.", inline=False)
        else:
            payout_text = ""
            for user_id, total_payout in winners_payouts.items():
                payout_text += f"<@{user_id}> vyhrál/a celkem **{total_payout:.2f} Credits**!\n"
            embed.add_field(name="Congratulations to the winners!", value=payout_text, inline=False)
            
        await ctx.respond(embed=embed)


    # --- NOVÁ PODSKUPINA PRO AI NÁSTROJE ---
    

    @ai_admin.command(name="shrnuti", description="[Admin] Vytvoří shrnutí posledních zpráv v kanálu.")
    @commands.check(is_admin_or_owner)
    async def summarize_channel(self, ctx: discord.ApplicationContext, 
                                kanal: discord.TextChannel, 
                                pocet_zprav: int = 50):
        
        if pocet_zprav > 100 or pocet_zprav < 5:
            await ctx.respond("Počet zpráv musí být mezi 5 a 100.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        try:
            messages = await kanal.history(limit=pocet_zprav).flatten()
        except discord.Forbidden:
            await ctx.respond(f"Chyba: Nemám oprávnění číst zprávy v kanálu {kanal.mention}.", ephemeral=True)
            return
        
        if not messages:
            await ctx.respond(f"V kanálu {kanal.mention} nebyly nalezeny žádné zprávy.", ephemeral=True)
            return

        # Sestavíme konverzaci pro AI
        conversation_text = ""
        for msg in reversed(messages): # Seřadíme od nejstarší po nejnovější
            conversation_text += f"{msg.author.display_name}: {msg.clean_content}\n"
            
        # Získáme AI model z AICog
        ai_cog = self.bot.get_cog('AICog')
        if not ai_cog or not ai_cog.ai_model:
            await ctx.respond("Chyba: Komponenta pro AI není dostupná.", ephemeral=True)
            return
            
        prompt = f"""Jsi asistent pro administrátora Discord serveru. Tvým úkolem je analyzovat následující konverzaci z kanálu '{kanal.name}' a vytvořit stručné, jasné a neutrální shrnutí v bodech. 
        Zaměř se na hlavní témata diskuze, případné problémy, otázky uživatelů nebo důležité oznámení. Ignoruj běžné pozdravy a nepodstatné zprávy.

        Konverzace k analýze:
        ---
        {conversation_text}
        ---
        Stručné shrnutí v bodech:"""

        try:
            response = await ai_cog.ai_model.generate_content_async(prompt)
            summary_text = response.text
        except Exception as e:
            await ctx.respond(f"Při generování shrnutí nastala chyba: {e}", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📋 AI Shrnutí kanálu #{kanal.name}",
            description=f"Zde je shrnutí posledních **{len(messages)}** zpráv:",
            color=0xF1C40F # Žlutá barva
        )
        embed.add_field(name="Hlavní body diskuze", value=summary_text, inline=False)
        embed.set_footer(text="Vygenerováno pomocí AI.")
        
        await ctx.respond(embed=embed, ephemeral=True)
    @zapas.command(name="zrusit", description="[Admin] Zruší vypsaný zápas a vrátí všechny sázky.")
    @commands.check(is_admin_or_owner) # ZDE JE ZMĚNA
    async def zrusit_zapas(self, ctx, id_zapasu: int):
        conn = sqlite3.connect('sazkovka.db')
        c = conn.cursor()
        c.execute("SELECT * FROM matches WHERE match_id = ? AND status = 'open'", (id_zapasu,))
        if not c.fetchone():
            await ctx.respond(f"Zápas s ID {id_zapasu} neexistuje nebo není otevřený pro sázení.", ephemeral=True)
            conn.close()
            return
        
        # Najdeme všechny sázky a vrátíme peníze
        c.execute("SELECT user_id, amount FROM bets WHERE match_id = ?", (id_zapasu,))
        bets_to_refund = c.fetchall()
        
        if bets_to_refund:
            for user_id, amount in bets_to_refund:
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
            
            # Smažeme sázky
            c.execute("DELETE FROM bets WHERE match_id = ?", (id_zapasu,))

        # Smažeme zápas
        c.execute("DELETE FROM matches WHERE match_id = ?", (id_zapasu,))
        conn.commit()
        conn.close()

        await ctx.respond(f"Zápas s ID {id_zapasu} byl zrušen a všechny sázky ({len(bets_to_refund)}) byly vráceny.", ephemeral=True)
        await ctx.channel.send(f"Admin zrušil zápas s ID {id_zapasu}. Všechny sázky byly vráceny na vaše účty.")

# v souboru 2.py, uvnitř třídy AdminCommands

    # --- PODSKUPINA PRO SPRÁVU LOTERIE ---
    

    @loterie_admin.command(name="losovat", description="[Admin] Vylosuje vítěze loterie a resetuje ji.")
    @commands.check(is_admin_or_owner)
    async def draw_lottery(self, ctx: discord.ApplicationContext):
        await ctx.defer()
        
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT ticket_id, user_id FROM lottery_tickets")
            all_tickets = c.fetchall()

            if not all_tickets:
                await ctx.respond("V loterii nejsou žádné losy. Nelze losovat.", ephemeral=True)
                return

            jackpot = len(all_tickets) * LotteryCog.LOTTERY_TICKET_PRICE
            
            # Losování
            winning_ticket = random.choice(all_tickets)
            winner_id = winning_ticket[1]

            # Připsání výhry
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (jackpot, winner_id))
            
            # Smazání všech losů pro další kolo
            c.execute("DELETE FROM lottery_tickets")
            conn.commit()

        winner_user = await self.bot.fetch_user(winner_id)
        
        embed = discord.Embed(
            title="🎉 LOSOVÁNÍ LOTERIE 🎉",
            description=f"Proběhlo velké losování o neuvěřitelný jackpot **{jackpot:,.0f} Credits**!".replace(",", " "),
            color=discord.Color.gold()
        )
        embed.add_field(name="Vítězem se stává...", value=f"**{winner_user.mention}!**", inline=False)
        embed.set_footer(text="Gratulujeme vítězi! Loterie byla resetována a můžete znovu kupovat losy.")
        
        await ctx.respond(embed=embed)
    # --- PODSKUPINA PRO SPRÁVU GIVEAWAYŮ ---
    

    def parse_duration(self, duration_string: str) -> datetime.timedelta:
        match = re.match(r"(\d+)([dhm])", duration_string.lower())
        if not match:
            raise ValueError("Neplatný formát doby trvání. Použij např. '10m', '2h', '1d'.")
        value, unit = int(match.group(1)), match.group(2)
        if unit == 'd': return datetime.timedelta(days=value)
        elif unit == 'h': return datetime.timedelta(hours=value)
        elif unit == 'm': return datetime.timedelta(minutes=value)
            
    @giveaway.command(name="start", description="[Admin] Spustí giveaway o kredity.")
    @commands.check(is_admin_or_owner) # ZDE JE ZMĚNA
    async def start_giveaway(self, ctx: discord.ApplicationContext, doba_trvani: str, pocet_vyhercu: int, vyhra_na_vyherce: int, popis: str):
        try:
            duration = self.parse_duration(doba_trvani)
        except ValueError as e:
            await ctx.respond(str(e), ephemeral=True)
            return
        if pocet_vyhercu <= 0 or vyhra_na_vyherce <= 0:
            await ctx.respond("Počet výherců a výhra musí být kladná čísla.", ephemeral=True)
            return
        end_time = datetime.datetime.now() + duration
        embed = discord.Embed(title="🎉 GIVEAWAY Credits 🎉", description=f"{popis}\n\nReaguj s 🎉 pro účast!", color=discord.Color.gold())
        embed.add_field(name="Výhra", value=f"**{vyhra_na_vyherce} Credits**", inline=True)
        embed.add_field(name="Počet výherců", value=str(pocet_vyhercu), inline=True)
        embed.set_footer(text=f"Giveaway končí")
        embed.timestamp = end_time
        giveaway_msg = await ctx.channel.send(embed=embed) 
        await giveaway_msg.add_reaction("🎉")
        await ctx.respond("Giveaway spuštěn!", ephemeral=True)

        await asyncio.sleep(duration.total_seconds())

        try:
            updated_msg = await ctx.channel.fetch_message(giveaway_msg.id)
            reaction = discord.utils.get(updated_msg.reactions, emoji="🎉")
            users = await reaction.users().flatten()
            entrants = [user for user in users if not user.bot]

            if not entrants:
                raise ValueError("Nikdo se nezapojil.")

            winner_count = min(pocet_vyhercu, len(entrants))
            winners = random.sample(entrants, k=winner_count)
            winner_mentions = ", ".join(w.mention for w in winners)
            result_text = f"Giveaway skončil!\n\nVýherci: {winner_mentions}"
            
            conn = sqlite3.connect('sazkovka.db')
            c = conn.cursor()
            for winner in winners:
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (vyhra_na_vyherce, winner.id))
            conn.commit()
            conn.close()

            ended_embed = updated_msg.embeds[0]
            ended_embed.description = result_text
            ended_embed.color = discord.Color.green()
            await updated_msg.edit(embed=ended_embed)
            await ctx.channel.send(f"Gratulujeme {winner_mentions}! Vyhráli jste v giveawayi a bylo vám připsáno **{vyhra_na_vyherce} Credits**.", reference=updated_msg, mention_author=False)

        except Exception as e:
            # Obecná chyba, např. zpráva byla smazána nebo se nikdo nepřipojil
            ended_embed = giveaway_msg.embeds[0]
            ended_embed.description = f"Giveaway skončil!\n\nDošlo k chybě nebo se nikdo nezapojil."
            ended_embed.color = discord.Color.greyple()
            await giveaway_msg.edit(embed=ended_embed)
            print(f"Chyba při vyhodnocování giveawaye: {e}")

    @giveaway.command(name="reroll", description="[Admin] Znovu losuje výherce z ukončeného giveawaye.")
    @commands.check(is_admin_or_owner) # ZDE JE ZMĚNA
    async def reroll_giveaway(self, ctx: discord.ApplicationContext, id_zpravy: str):
        try:
            message_id = int(id_zpravy)
            giveaway_msg = await ctx.channel.fetch_message(message_id)
        except (ValueError, discord.NotFound):
            await ctx.respond("Neplatné ID zprávy nebo zpráva nebyla nalezena v tomto kanálu.", ephemeral=True)
            return

        if not giveaway_msg.embeds or "Giveaway skončil!" not in giveaway_msg.embeds[0].description:
            await ctx.respond("Tato zpráva nepatří ukončenému giveawayi.", ephemeral=True)
            return

        reaction = discord.utils.get(giveaway_msg.reactions, emoji="🎉")
        if not reaction:
            await ctx.respond("Na zprávě nejsou žádné reakce.", ephemeral=True)
            return

        users = await reaction.users().flatten()
        entrants = [user for user in users if not user.bot]
        
        # Získáme původní výherce z textu, abychom je nelosovali znovu
        old_winners_text = giveaway_msg.embeds[0].description
        old_winner_ids = [int(uid) for uid in re.findall(r'<@(\d+)>', old_winners_text)]
        
        # Odfiltrujeme staré výherce
        potential_new_winners = [u for u in entrants if u.id not in old_winner_ids]

        if not potential_new_winners:
            await ctx.respond("Nezbyli žádní další účastníci pro nové losování.", ephemeral=True)
            return

        # Vylosujeme jednoho nového výherce
        new_winner = random.choice(potential_new_winners)
        
        # Získáme výhru z původního embedu
        try:
            vyhra_text = giveaway_msg.embeds[0].fields[0].value
            vyhra_na_vyherce = int(re.search(r'\d+', vyhra_text).group())
        except (IndexError, AttributeError):
            await ctx.respond("Nepodařilo se zjistit výši výhry z původní zprávy. Nelze připsat kredity.", ephemeral=True)
            return

        conn = sqlite3.connect('sazkovka.db')
        c = conn.cursor()
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (vyhra_na_vyherce, new_winner.id))
        conn.commit()
        conn.close()

        await ctx.channel.send(f"Reroll giveawaye! Novým výhercem je {new_winner.mention}, který získává **{vyhra_na_vyherce} Credits**. Gratulujeme!", reference=giveaway_msg)
        await ctx.respond("Nový výherce byl úspěšně vylosován a odměna připsána.", ephemeral=True)
        # --- NOVÁ PODSKUPINA PRO SPRÁVU TWITCHE ---
    

    @twitch.command(name="pridat_body", description="[Admin] Ručně přidá Twitch body uživateli.")
    @commands.check(is_admin_or_owner) # ZDE JE ZMĚNA
    async def add_twitch_points(self, ctx: discord.ApplicationContext, uzivatel: discord.Member, pocet: int):
        conn = sqlite3.connect('sazkovka.db')
        c = conn.cursor()
        c.execute("UPDATE users SET twitch_points = twitch_points + ? WHERE user_id = ?", (pocet, uzivatel.id))
        conn.commit()
        if conn.total_changes == 0:
            await ctx.respond(f"Uživatel {uzivatel.mention} nemá propojený účet.", ephemeral=True)
        else:
            await ctx.respond(f"Uživateli {uzivatel.mention} bylo úspěšně připsáno **{pocet}** Twitch bodů.", ephemeral=True)
        conn.close()

# --- NOVÁ TŘÍDA (COG) PRO ŠNEČÍ DOSTIHY ---
class RaceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_race = None # Zde budeme uchovávat stav aktivního závodu

    # --- KONFIGURACE DOSTIHŮ ---
    BETTING_DURATION = 60  # Délka sázkové fáze v sekundách
    NUM_SNAILS = 5         # Počet závodících šneků
    RACE_TRACK_LENGTH = 20 # Délka závodní dráhy
    PAYOUT_MULTIPLIER = 5  # Násobek sázky pro výherce

    dostihy = SlashCommandGroup("dostihy", "Bet on exciting snail races!", guild_ids=GUILD_IDS)

    @dostihy.command(name="start", description="Odstartuje nový šnečí dostih a otevře sázky.")
    async def start_race(self, ctx: discord.ApplicationContext):
        if self.active_race:
            await ctx.respond("Šnečí dostih již probíhá! Počkej, až skončí.", ephemeral=True)
            return

        await ctx.defer()

        # Inicializace nového závodu
        end_time = datetime.datetime.now() + datetime.timedelta(seconds=self.BETTING_DURATION)
        self.active_race = {
            "channel_id": ctx.channel_id,
            "betting_end_time": end_time,
            "bets": [],
            "message": None
        }

        embed = discord.Embed(
            title="🐌 ŠNEČÍ DOSTIHY 🐌",
            description=f"**Sázky se otevírají!** Závod začíná za **{self.BETTING_DURATION} sekund**.",
            color=discord.Color.blue()
        )
        racers_text = ""
        for i in range(1, self.NUM_SNAILS + 1):
            racers_text += f"**Dráha {i}:** 🐌\n"
        embed.add_field(name="Závodníci", value=racers_text, inline=False)
        embed.set_footer(text=f"Vsaď si pomocí /dostihy vsadit <sázka> <číslo_šneka>")
        embed.timestamp = end_time
        
        race_message = await ctx.respond(embed=embed)
        self.active_race["message"] = race_message

        # Počkáme na konec sázkové fáze
        await asyncio.sleep(self.BETTING_DURATION)
        
        # Zkontrolujeme, zda závod stále běží (nebyl zrušen)
        if not self.active_race or self.active_race["message"].id != race_message.id:
            return # Závod byl mezitím zrušen

        # Spustíme animaci závodu
        await self._run_race_animation(ctx)

    @dostihy.command(name="vsadit", description="Vsaď si na svého favorita ve šnečím dostihu.")
    async def place_bet(self, ctx: discord.ApplicationContext, sazka: float, cislo_sneka: int):
        if not self.active_race:
            await ctx.respond("Momentálně neprobíhají žádné sázky na dostihy.", ephemeral=True)
            return
        
        if datetime.datetime.now() > self.active_race["betting_end_time"]:
            await ctx.respond("Sázky na tento dostih již byly uzavřeny!", ephemeral=True)
            return
            
        if not (1 <= cislo_sneka <= self.NUM_SNAILS):
            await ctx.respond(f"Můžeš sázet pouze na šneky s číslem 1 až {self.NUM_SNAILS}.", ephemeral=True)
            return

        if sazka <= 0:
            await ctx.respond("The bet must be a positive number.", ephemeral=True)
            return
        
        conn = sqlite3.connect('sazkovka.db')
        c = conn.cursor()
        c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
        result = c.fetchone()
        
        if not result:
            await ctx.respond("Nejprve se musíš zaregistrovat příkazem `/registrovat`.", ephemeral=True)
            conn.close()
            return
        
        balance = result[0]
        if balance < sazka:
            await ctx.respond(f"You don't have enough Credits. Your account: **{balance:.2f} Credits**.", ephemeral=True)
            conn.close()
            return

        # Odečteme sázku a uložíme ji
        c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (sazka, ctx.author.id))
        conn.commit()
        conn.close()

        self.active_race["bets"].append({"user_id": ctx.author.id, "amount": sazka, "snail_number": cislo_sneka})
        await ctx.respond(f"I accepted your bet. **{sazka:.2f} Credits** na šneka číslo **{cislo_sneka}**! Hodně štěstí!", ephemeral=True)

    async def _run_race_animation(self, ctx):
        race_message = self.active_race["message"]
        snail_positions = [0] * self.NUM_SNAILS
        
        start_embed = race_message.embeds[0]
        start_embed.description = "**ZÁVOD PRÁVĚ ODSTARTOVAL!**"
        start_embed.color = discord.Color.orange()
        await race_message.edit(embed=start_embed)
        await asyncio.sleep(2)

        winner = None
        while winner is None:
            track_text = ""
            for i in range(self.NUM_SNAILS):
                move = random.randint(1, 3)
                snail_positions[i] += move
                
                track = '─' * snail_positions[i]
                track += '🐌'
                track += '─' * (self.RACE_TRACK_LENGTH - snail_positions[i])
                track_text += f"**{i+1}:** |{track}| 🏁\n"

                if snail_positions[i] >= self.RACE_TRACK_LENGTH:
                    winner = i + 1
            
            race_embed = discord.Embed(title="🐌 DOSTIHY PROBÍHAJÍ 🐌", description=track_text, color=discord.Color.orange())
            await race_message.edit(embed=race_embed)
            
            if winner is not None:
                break
            
            await asyncio.sleep(2.5)

        # Vyhlášení vítěze a výplaty
        await self._payout_winners(ctx, winner)

    async def _payout_winners(self, ctx, winner_number):
        race_message = self.active_race["message"]
        final_embed = race_message.embeds[0]
        final_embed.title = "🏁 VÝSLEDKY DOSTIHŮ 🏁"
        final_embed.description = f"**VÍTĚZEM JE ŠNEK ČÍSLO {winner_number}!**"
        final_embed.color = discord.Color.gold()
        
        winning_bets = [bet for bet in self.active_race["bets"] if bet["snail_number"] == winner_number]
        
        if not winning_bets:
            final_embed.add_field(name="Výherci", value="Bohužel, nikdo si na vítěze nevsadil.", inline=False)
        else:
            conn = sqlite3.connect('sazkovka.db')
            c = conn.cursor()
            winners_text = ""
            for bet in winning_bets:
                payout = bet["amount"] * self.PAYOUT_MULTIPLIER
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (payout, bet["user_id"]))
                winners_text += f"<@{bet['user_id']}> vyhrál/a **{payout:.2f} Credits**!\n"
            conn.commit()
            conn.close()
            final_embed.add_field(name="Congratulations to the winners!", value=winners_text, inline=False)

        await race_message.edit(embed=final_embed)
        
        # Reset závodu
        self.active_race = None

@bot.event
async def on_ready():
    # Tento blok se pokusí synchronizovat příkazy způsobem,
    # který by neměl vyvolat chybu 50240.
    try:
        # První pokus o běžnou synchronizaci
        print("Probíhá běžná synchronizace příkazů...")
        await bot.sync_commands()
        print("Běžná synchronizace úspěšná.")
    except discord.HTTPException as e:
        # Pokud selže s chybou 50240, zkusíme záložní metodu
        if e.code == 50240:
            print("Běžná synchronizace selhala s chybou 50240. Zkouším záložní metodu (bez mazání)...")
            # Tato metoda se nesnaží smazat existující příkazy
            await bot.sync_commands(delete_existing=False)
            print("Záložní synchronizace dokončena. Některé staré příkazy mohou na Discordu zůstat.")
        else:
            # Pokud je to jiná chyba, tak ji vypíšeme
            print(f"Při synchronizaci nastala neočekávaná chyba: {e}")
    print('------')
    print(f'Bot je připraven a přihlášen jako {bot.user}')
    print('------')
# v souboru sazkovka_bot.py

# --- NOVÁ TŘÍDA (COG) PRO ŠACHY ---
class ChessCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    sachy = SlashCommandGroup("sachy", "Vyzvi hráče na partii šachů o kredity.", guild_ids=GUILD_IDS)

    async def _end_game(self, ctx, game_data, winner_id, loser_id, reason):
        """Ukončí hru, vyplatí sázku a aktualizuje databázi."""
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            if game_data['wager'] > 0:
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (game_data['wager'] * 2, winner_id))
            c.execute("UPDATE chess_games SET status = 'finished' WHERE game_id = ?", (game_data['game_id'],))
            conn.commit()
        
        await ctx.channel.send(f"Partie skončila! {reason}\n<@{winner_id}> porazil/a <@{loser_id}> a vyhrává **{game_data['wager'] * 2} Credits**!")
        
        # Získání a připsání XP
        profile_cog = self.bot.get_cog('ProfileCog')
        if profile_cog:
            await profile_cog._update_stats_and_xp(sqlite3.connect('sazkovka.db').cursor(), ctx, game_data['wager'], True, 2.0)


    @sachy.command(name="vyzvat", description="Vyzvi jiného hráče na partii šachů.")
    async def challenge(self, ctx: discord.ApplicationContext, protihrac: discord.Member, sazka: float = 0):
        if protihrac.bot or protihrac.id == ctx.author.id:
            await ctx.respond("Nemůžeš vyzvat bota nebo sám sebe!", ephemeral=True)
            return
        if sazka < 0:
            await ctx.respond("Sázka nemůže být záporná.", ephemeral=True)
            return

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            # Kontrola, zda hráči již nejsou ve hře
            c.execute("SELECT game_id FROM chess_games WHERE (player_white_id = ? OR player_black_id = ?) AND status = 'active'", (ctx.author.id, ctx.author.id))
            if c.fetchone():
                await ctx.respond("Již jsi v aktivní hře!", ephemeral=True)
                return
            c.execute("SELECT game_id FROM chess_games WHERE (player_white_id = ? OR player_black_id = ?) AND status = 'active'", (protihrac.id, protihrac.id))
            if c.fetchone():
                await ctx.respond("Vyzvaný hráč je již v aktivní hře!", ephemeral=True)
                return
            
            # Kontrola Credits
            if sazka > 0:
                c.execute("SELECT balance FROM users WHERE user_id IN (?, ?)", (ctx.author.id, protihrac.id))
                balances = c.fetchall()
                if len(balances) != 2 or any(b[0] < sazka for b in balances):
                    await ctx.respond(f"Jeden z vás nemá dostatek Credits na sázku **{sazka}**.", ephemeral=True)
                    return
        
        view = ChallengeView(ctx.author, protihrac, sazka)
        await ctx.respond(f"{protihrac.mention}, hráč {ctx.author.mention} tě vyzývá na partii šachů o **{sazka} Credits**! Přijímáš?", view=view)
        
        await view.wait()
        original_message = await ctx.interaction.original_response()

        if view.accepted is None:
            await original_message.edit(content="Výzva vypršela.", view=None)
        elif view.accepted is False:
            await original_message.edit(content="Výzva byla odmítnuta.", view=None)
        else: # Hra přijata
            # Odečteme sázky
            with sqlite3.connect('sazkovka.db') as conn:
                c = conn.cursor()
                if sazka > 0:
                    c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (sazka, ctx.author.id))
                    c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (sazka, protihrac.id))

                # Náhodné rozdělení barev
                players = [ctx.author.id, protihrac.id]
                random.shuffle(players)
                white_id, black_id = players[0], players[1]

                board = chess.Board()
                c.execute("INSERT INTO chess_games (message_id, channel_id, player_white_id, player_black_id, current_turn_id, board_fen, wager, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'active')",
                          (original_message.id, ctx.channel_id, white_id, black_id, white_id, board.fen(), sazka))
                conn.commit()

            board_image = generate_board_image(board)
            await original_message.edit(content=f"Partie byla přijata! Bílý na tahu: <@{white_id}>", view=None, file=board_image)


    @sachy.command(name="tah", description="Proveď tah v probíhající partii.")
    async def move(self, ctx: discord.ApplicationContext, tah: str):
        await ctx.defer()
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM chess_games WHERE (player_white_id = ? OR player_black_id = ?) AND status = 'active'", (ctx.author.id, ctx.author.id))
            game_data_raw = c.fetchone()
            
            if not game_data_raw:
                await ctx.respond("Nejsi v žádné aktivní hře.", ephemeral=True)
                return

            game_data = dict(zip([d[0] for d in c.description], game_data_raw))
            
            if game_data['current_turn_id'] != ctx.author.id:
                await ctx.respond("Nejsi na tahu!", ephemeral=True)
                return
            
            board = chess.Board(game_data['board_fen'])
            try:
                move = board.push_san(tah)
            except chess.IllegalMoveError:
                await ctx.respond("Neplatný tah! Zadej tah ve Standardní algebraické notaci (např. e4, Nf3, O-O).", ephemeral=True)
                return

            next_turn_id = game_data['player_black_id'] if ctx.author.id == game_data['player_white_id'] else game_data['player_white_id']
            c.execute("UPDATE chess_games SET board_fen = ?, current_turn_id = ? WHERE game_id = ?", (board.fen(), next_turn_id, game_data['game_id']))
            conn.commit()
            
            board_image = generate_board_image(board, pov_color=chess.WHITE if next_turn_id == game_data['player_white_id'] else chess.BLACK, last_move=move)
            
            # Kontrola konce hry
            if board.is_checkmate():
                await self._end_game(ctx, game_data, ctx.author.id, next_turn_id, "Šach mat!")
                await ctx.respond(f"Šach mat! <@{ctx.author.id}> vyhrává!", file=board_image)
            elif board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
                c.execute("UPDATE chess_games SET status = 'finished' WHERE game_id = ?", (game_data['game_id'],))
                conn.commit()
                await ctx.respond(f"Remíza! Sázky se vrací.", file=board_image)
                # Vrácení sázek
                if game_data['wager'] > 0:
                     c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (game_data['wager'], game_data['player_white_id']))
                     c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (game_data['wager'], game_data['player_black_id']))
                     conn.commit()
            else:
                 await ctx.respond(f"Na tahu je <@{next_turn_id}>.", file=board_image)
    
    @sachy.command(name="vzdat_se", description="Vzdá probíhající partii šachů.")
    async def forfeit(self, ctx: discord.ApplicationContext):
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM chess_games WHERE (player_white_id = ? OR player_black_id = ?) AND status = 'active'", (ctx.author.id, ctx.author.id))
            game_data_raw = c.fetchone()
            
            if not game_data_raw:
                await ctx.respond("Nejsi v žádné aktivní hře.", ephemeral=True)
                return

            game_data = dict(zip([d[0] for d in c.description], game_data_raw))
            winner_id = game_data['player_black_id'] if ctx.author.id == game_data['player_white_id'] else game_data['player_white_id']
            
            await self._end_game(ctx, game_data, winner_id, ctx.author.id, f"<@{ctx.author.id}> se vzdal/a.")
            await ctx.respond("Partii jsi vzdal.", ephemeral=True)

# v souboru 2.py

# --- NOVÁ TŘÍDA (COG) PRO TÝDENNÍ LOTERII ---
class LotteryCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    LOTTERY_TICKET_PRICE = 100  # Cena za jeden los
    MAX_TICKETS_PER_USER = 50   # Maximální počet losů na jednoho hráče

    loterie = SlashCommandGroup("loterie", "Zkus své štěstí v týdenní loterii!", guild_ids=GUILD_IDS)

    @loterie.command(name="info", description="Zobrazí informace o aktuální loterii.")
    async def lottery_info(self, ctx: discord.ApplicationContext):
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM lottery_tickets")
            total_tickets = c.fetchone()[0]
        
        jackpot = total_tickets * self.LOTTERY_TICKET_PRICE
        
        embed = discord.Embed(title="🎟️ Týdenní Loterie 🎟️", color=discord.Color.purple())
        embed.add_field(name="Aktuální Jackpot", value=f"**{jackpot:,.0f} Credits**".replace(",", " "), inline=False)
        embed.add_field(name="Celkem prodaných losů", value=str(total_tickets), inline=True)
        embed.add_field(name="Cena za los", value=f"{self.LOTTERY_TICKET_PRICE} Credits", inline=True)
        embed.set_footer(text="Losování probíhá každou neděli, nebo po použití admin příkazu.")
        
        await ctx.respond(embed=embed)

    @loterie.command(name="koupit", description="Kup si losy do týdenní loterie.")
    async def buy_tickets(self, ctx: discord.ApplicationContext, pocet: int = 1):
        if pocet <= 0:
            await ctx.respond("Počet losů musí být kladné číslo.", ephemeral=True)
            return
        
        total_cost = pocet * self.LOTTERY_TICKET_PRICE

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            
            # Kontrola, kolik losů už hráč má
            c.execute("SELECT COUNT(*) FROM lottery_tickets WHERE user_id = ?", (ctx.author.id,))
            user_tickets = c.fetchone()[0]
            if user_tickets + pocet > self.MAX_TICKETS_PER_USER:
                await ctx.respond(f"Můžeš vlastnit maximálně **{self.MAX_TICKETS_PER_USER}** losů. Již jich máš {user_tickets}.", ephemeral=True)
                return

            # Kontrola a odečtení Credits
            c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
            result = c.fetchone()
            if not result or result[0] < total_cost:
                await ctx.respond(f"You don't have enough Credits na nákup {pocet} losů. Potřebuješ **{total_cost} Credits**.", ephemeral=True)
                return
            
            c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_cost, ctx.author.id))
            
            # Vložení losů do databáze
            now = datetime.datetime.now().isoformat()
            for _ in range(pocet):
                c.execute("INSERT INTO lottery_tickets (user_id, purchase_date) VALUES (?, ?)", (ctx.author.id, now))
            
            conn.commit()

        await ctx.respond(f"Úspěšně jsi zakoupil/a **{pocet}** losů do loterie za **{total_cost} Credits**! Hodně štěstí!", ephemeral=True)

    # v souboru 2.py

# --- NOVÁ TŘÍDA (COG) PRO TÝMOVÝ SYSTÉM ---



# v souboru 2.py

# --- TŘÍDA (COG) PRO TÝMOVÝ SYSTÉM ---

# Zde musí být definice třídy InviteView z předchozí zprávy
class InviteView(discord.ui.View):
    def __init__(self, bot, guild_name, guild_id, inviter, invited):
        super().__init__(timeout=3600.0) # Pozvánka platí 1 hodinu
        self.bot = bot
        self.guild_name = guild_name
        self.guild_id = guild_id
        self.inviter = inviter
        self.invited = invited

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.invited.id:
            await interaction.response.send_message("Toto není pozvánka pro tebe!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Přijmout", style=discord.ButtonStyle.green)
    async def accept_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT guild_id FROM guild_members WHERE user_id = ?", (self.invited.id,))
            if c.fetchone():
                await interaction.response.send_message("Už jsi v jiném týmu!", ephemeral=True)
                self.disable_all_items()
                await interaction.message.edit(content=f"Uživatel {self.invited.mention} je již v jiném týmu.", view=self)
                return

            now = datetime.datetime.now().isoformat()
            c.execute("INSERT INTO guild_members (user_id, guild_id, join_date) VALUES (?, ?, ?)", (self.invited.id, self.guild_id, now))
            conn.commit()
        
        self.disable_all_items()
        await interaction.message.edit(content=f"✅ {self.invited.mention} přijal/a pozvánku do týmu **{self.guild_name}**!", view=self)
        await interaction.response.send_message(f"Vítej v týmu **{self.guild_name}**!", ephemeral=True)

    @discord.ui.button(label="Odmítnout", style=discord.ButtonStyle.red)
    async def decline_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.disable_all_items()
        await interaction.message.edit(content=f"❌ {self.invited.mention} odmítl/a pozvánku do týmu **{self.guild_name}**.", view=self)
        await interaction.response.send_message("Pozvánka byla odmítnuta.", ephemeral=True)

class GuildCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("✅ Cog 'GuildCog' (Týmy) byl úspěšně načten.")

    tym = SlashCommandGroup("tym", "Manage your own gaming team or join one.", guild_ids=GUILD_IDS)

    # --- DOPLNĚNÉ ZÁKLADNÍ PŘÍKAZY ---

    @tym.command(name="vytvorit", description=f"Založí nový tým za {GUILD_CREATION_COST} Credits.")
    async def create_guild(self, ctx: discord.ApplicationContext, nazev: str):
        if not (3 <= len(nazev) <= 20):
            await ctx.respond("Název týmu musí mít 3-20 znaků.", ephemeral=True)
            return

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            
            c.execute("SELECT guild_id FROM guild_members WHERE user_id = ?", (ctx.author.id,))
            if c.fetchone():
                await ctx.respond("Už jsi členem jiného týmu! Nejprve musíš odejít.", ephemeral=True)
                return

            c.execute("SELECT guild_id FROM guilds WHERE LOWER(name) = ?", (nazev.lower(),))
            if c.fetchone():
                await ctx.respond("Tým s tímto názvem již existuje.", ephemeral=True)
                return

            c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
            result = c.fetchone()
            if not result or result[0] < GUILD_CREATION_COST:
                await ctx.respond(f"Na založení týmu You don't have enough Credits. Potřebuješ **{GUILD_CREATION_COST}**.", ephemeral=True)
                return

            c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (GUILD_CREATION_COST, ctx.author.id))
            
            now = datetime.datetime.now().isoformat()
            c.execute("INSERT INTO guilds (name, leader_id, creation_date) VALUES (?, ?, ?)", (nazev, ctx.author.id, now))
            new_guild_id = c.lastrowid
            
            c.execute("INSERT INTO guild_members (user_id, guild_id, join_date) VALUES (?, ?, ?)", (ctx.author.id, new_guild_id, now))
            conn.commit()

        await ctx.respond(f"🎉 Congratulations! You have created a new team called **{name}**! You are its captain. You can now invite other members with `/invite team`.")

    @tym.command(name="pozvat", description="Pozve hráče do tvého týmu.")
    async def invite_to_guild(self, ctx: discord.ApplicationContext, hrac: discord.Member):
        if hrac.bot or hrac.id == ctx.author.id:
            await ctx.respond("Nemůžeš pozvat bota nebo sám sebe.", ephemeral=True)
            return

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT guild_id, name FROM guilds WHERE leader_id = ?", (ctx.author.id,))
            guild_data = c.fetchone()
            if not guild_data:
                await ctx.respond("Nejsi kapitánem žádného týmu, nemůžeš zvát hráče.", ephemeral=True)
                return
            
            guild_id, guild_name = guild_data
            
            c.execute("SELECT guild_id FROM guild_members WHERE user_id = ?", (hrac.id,))
            if c.fetchone():
                await ctx.respond(f"Hráč {hrac.display_name} je již v jiném týmu.", ephemeral=True)
                return

        view = InviteView(self.bot, guild_name, guild_id, ctx.author, hrac)
        await ctx.respond(f"{hrac.mention}, dostal jsi pozvánku do týmu **{guild_name}** od kapitána {ctx.author.mention}!", view=view)


    @tym.command(name="info", description="Zobrazí informace o tvém nebo jiném týmu.")
    async def guild_info(self, ctx: discord.ApplicationContext, nazev: discord.Option(str, "Název týmu (nech prázdné pro tvůj tým)", required=False) = None):
        await ctx.defer()
        
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            
            guild_id_to_find = None
            if nazev:
                c.execute("SELECT guild_id FROM guilds WHERE LOWER(name) = ?", (nazev.lower(),))
                result = c.fetchone()
                if not result:
                    await ctx.respond("Tým s tímto názvem neexistuje.", ephemeral=True)
                    return
                guild_id_to_find = result[0]
            else:
                c.execute("SELECT guild_id FROM guild_members WHERE user_id = ?", (ctx.author.id,))
                result = c.fetchone()
                if not result:
                    await ctx.respond("Nejsi v žádném týmu. Zadej název týmu, který chceš zobrazit.", ephemeral=True)
                    return
                guild_id_to_find = result[0]
            
            c.execute("SELECT name, leader_id, bank_balance FROM guilds WHERE guild_id = ?", (guild_id_to_find,))
            guild_data = c.fetchone()
            guild_name, leader_id, bank_balance = guild_data
            
            c.execute("SELECT user_id FROM guild_members WHERE guild_id = ?", (guild_id_to_find,))
            member_ids = [row[0] for row in c.fetchall()]

        leader = await self.bot.fetch_user(leader_id)
        members_mentions = [f"<@{mid}>" for mid in member_ids]

        embed = discord.Embed(title=f"🛡️ Profil Týmu: {guild_name}", color=discord.Color.blue())
        embed.set_thumbnail(url=leader.display_avatar.url)
        embed.add_field(name="Kapitán", value=leader.mention, inline=True)
        embed.add_field(name="Počet členů", value=f"{len(member_ids)}", inline=True)
        embed.add_field(name="Stav týmové banky", value=f"**{bank_balance:,.2f}** Credits".replace(",", " "), inline=False)
        embed.add_field(name="Členové", value=", ".join(members_mentions) if members_mentions else "Žádní", inline=False)
        
        await ctx.respond(embed=embed)


    @tym.command(name="opustit", description="Opustí tvůj současný tým.")
    async def leave_guild(self, ctx: discord.ApplicationContext):
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT g.guild_id, g.leader_id, (SELECT COUNT(*) FROM guild_members WHERE guild_id = g.guild_id) as member_count FROM guilds g JOIN guild_members gm ON g.guild_id = gm.guild_id WHERE gm.user_id = ?", (ctx.author.id,))
            guild_info = c.fetchone()

            if not guild_info:
                await ctx.respond("Nejsi členem žádného týmu.", ephemeral=True)
                return

            guild_id, leader_id, member_count = guild_info
            
            if leader_id == ctx.author.id and member_count > 1:
                await ctx.respond("Jsi kapitán! Nemůžeš opustit tým, dokud jsi poslední člen. Nejprve musíš tým rozpustit (`/admin tym rozpustit`).", ephemeral=True)
                return
            
            # Pokud je kapitán poslední člen, může odejít a tým se rozpustí
            if leader_id == ctx.author.id and member_count == 1:
                c.execute("DELETE FROM guild_members WHERE user_id = ?", (ctx.author.id,))
                c.execute("DELETE FROM guilds WHERE guild_id = ?", (guild_id,))
                await ctx.respond("Opustil jsi svůj tým. Protože jsi byl poslední člen, tým byl rozpuštěn.", ephemeral=True)
            else: # Běžný člen odchází
                c.execute("DELETE FROM guild_members WHERE user_id = ?", (ctx.author.id,))
                await ctx.respond("Úspěšně jsi opustil/a svůj tým.", ephemeral=True)
            
            conn.commit()


    @tym.command(name="vklad", description="Vloží kredity ze svého účtu do týmové banky.")
    async def deposit_to_guild(self, ctx: discord.ApplicationContext, castka: float):
        if castka <= 0:
            await ctx.respond("The amount must be a positive number.", ephemeral=True)
            return

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
            user_balance = c.fetchone()
            if not user_balance or user_balance[0] < castka:
                await ctx.respond("You don't have enough Credits na tento vklad.", ephemeral=True)
                return

            c.execute("SELECT guild_id FROM guild_members WHERE user_id = ?", (ctx.author.id,))
            guild_result = c.fetchone()
            if not guild_result:
                await ctx.respond("Nejsi členem žádného týmu.", ephemeral=True)
                return
            
            guild_id = guild_result[0]

            # Transakce
            c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (castka, ctx.author.id))
            c.execute("UPDATE guilds SET bank_balance = bank_balance + ? WHERE guild_id = ?", (castka, guild_id))
            conn.commit()

        await ctx.respond(f"Úspěšně jsi vložil **{castka:.2f} Credits** do týmové banky.", ephemeral=True)


    @tym.command(name="vybrat", description="[Pouze pro kapitána] Vybere kredity z týmové banky na svůj účet.")
    async def withdraw_from_guild(self, ctx: discord.ApplicationContext, castka: float):
        if castka <= 0:
            await ctx.respond("The amount must be a positive number.", ephemeral=True)
            return

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT guild_id, bank_balance FROM guilds WHERE leader_id = ?", (ctx.author.id,))
            guild_data = c.fetchone()

            if not guild_data:
                await ctx.respond("Nejsi kapitánem žádného týmu.", ephemeral=True)
                return
            
            guild_id, bank_balance = guild_data
            if bank_balance < castka:
                await ctx.respond(f"V týmové bance není dostatek Credits. K dispozici je **{bank_balance:.2f}**.", ephemeral=True)
                return

            # Transakce
            c.execute("UPDATE guilds SET bank_balance = bank_balance - ? WHERE guild_id = ?", (castka, guild_id))
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (castka, ctx.author.id))
            conn.commit()
            
        await ctx.respond(f"Jako kapitán jsi úspěšně vybral **{castka:.2f} Credits** z týmové banky.", ephemeral=True)
    
    # v souboru 2.py

# --- NOVÁ TŘÍDA (COG) PRO VIRTUÁLNÍ BURZU ---
# v souboru 2.py

# --- TŘÍDA (COG) PRO VIRTUÁLNÍ BURZU ---
class StockMarketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Zde si můžete snadno přidat další firmy
        self.stocks = {
            "ACME": {"name": "ACME Corporation", "initial_price": 1000},
            "CYBER": {"name": "Cyberdyne Systems", "initial_price": 1500},
            "STARK": {"name": "Stark Industries", "initial_price": 2500},
            "WAYNE": {"name": "Wayne Enterprises", "initial_price": 2200}
        }
        self.initialize_stocks()
        self.update_stock_prices.start()

    def cog_unload(self):
        self.update_stock_prices.cancel()

    def initialize_stocks(self):
        """Při startu zkontroluje a případně vloží akcie do databáze."""
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            for stock_id, data in self.stocks.items():
                c.execute("SELECT * FROM stocks WHERE stock_id = ?", (stock_id,))
                if not c.fetchone():
                    history = json.dumps([data['initial_price']])
                    c.execute("INSERT INTO stocks (stock_id, name, current_price, history) VALUES (?, ?, ?, ?)",
                              (stock_id, data['name'], data['initial_price'], history))
            conn.commit()

    @tasks.loop(hours=1)
    async def update_stock_prices(self):
        """Úloha na pozadí, která každou hodinu aktualizuje ceny akcií."""
        print(f"[{datetime.datetime.now()}] Aktualizuji ceny akcií na burze...")
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            for stock_id in self.stocks.keys():
                c.execute("SELECT current_price, history FROM stocks WHERE stock_id = ?", (stock_id,))
                price, history_str = c.fetchone()
                history = json.loads(history_str)
                
                change_percent = random.uniform(-0.15, 0.15)
                new_price = max(50.0, price * (1 + change_percent))
                
                history.append(new_price)
                if len(history) > 24: history.pop(0)

                c.execute("UPDATE stocks SET current_price = ?, history = ? WHERE stock_id = ?",
                          (new_price, json.dumps(history), stock_id))
            conn.commit()
        print("Ceny akcií úspěšně aktualizovány.")

    @update_stock_prices.before_loop
    async def before_update_prices(self):
        await self.bot.wait_until_ready()

    # --- PŘÍKAZY PRO BURZU ---
    burza = SlashCommandGroup("burza", "Obchoduj s virtuálními akciemi a zbohatni!", guild_ids=GUILD_IDS)

    @burza.command(name="ceny", description="Zobrazí aktuální ceny všech akcií na trhu.")
    async def stock_prices(self, ctx: discord.ApplicationContext):
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT stock_id, name, current_price, history FROM stocks")
            all_stocks = c.fetchall()

        embed = discord.Embed(title="📈 Aktuální Kurzy na Burze", color=0x3498DB)
        for stock_id, name, price, history_str in all_stocks:
            history = json.loads(history_str)
            if len(history) > 1:
                change = price - history[-2]
                change_percent = (change / history[-2]) * 100
                trend_emoji = "🔼" if change >= 0 else "🔽"
                value_text = f"**{price:,.2f}** Credits {trend_emoji} ({change:+.2f} / {change_percent:+.2f}%)"
            else:
                value_text = f"**{price:,.2f}** Credits"
            
            embed.add_field(name=f"{name} ({stock_id})", value=value_text.replace(",", " "), inline=False)
        
        await ctx.respond(embed=embed)

    @burza.command(name="portfolio", description="Zobrazí tvé osobní portfolio akcií.")
    async def portfolio(self, ctx: discord.ApplicationContext):
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("""
                SELECT p.stock_id, s.name, p.quantity, s.current_price
                FROM stock_portfolios p
                JOIN stocks s ON p.stock_id = s.stock_id
                WHERE p.user_id = ?
            """, (ctx.author.id,))
            portfolio_items = c.fetchall()

        embed = discord.Embed(title=f"💼 Portfolio hráče {ctx.author.display_name}", color=0x2ECC71)
        if not portfolio_items:
            embed.description = "Zatím nevlastníš žádné akcie."
        else:
            total_value = 0
            for stock_id, name, quantity, price in portfolio_items:
                value = quantity * price
                total_value += value
                embed.add_field(name=f"{name} ({stock_id})", value=f"Počet: **{quantity}**\nAktuální hodnota: **{value:,.2f}** Credits".replace(",", " "), inline=False)
            embed.set_footer(text=f"Celková hodnota portfolia: {total_value:,.2f} Credits".replace(",", " "))
            
        await ctx.respond(embed=embed, ephemeral=True)

    @burza.command(name="koupit", description="Kup akcie vybrané firmy.")
    async def buy_stock(self, ctx: discord.ApplicationContext, firma: str, pocet: int):
        stock_id = firma.upper()
        if stock_id not in self.stocks:
            await ctx.respond("Firma s tímto označením neexistuje.", ephemeral=True)
            return
        if pocet <= 0:
            await ctx.respond("Počet akcií musí být kladné číslo.", ephemeral=True)
            return

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT current_price FROM stocks WHERE stock_id = ?", (stock_id,))
            price = c.fetchone()[0]
            total_cost = price * pocet

            c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
            balance = c.fetchone()[0]
            if balance < total_cost:
                await ctx.respond(f"You don't have enough Credits. Potřebuješ **{total_cost:,.2f}**.".replace(",", " "), ephemeral=True)
                return

            c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_cost, ctx.author.id))
            
            c.execute("SELECT quantity FROM stock_portfolios WHERE user_id = ? AND stock_id = ?", (ctx.author.id, stock_id))
            current_quantity = c.fetchone()
            if current_quantity:
                c.execute("UPDATE stock_portfolios SET quantity = quantity + ? WHERE user_id = ? AND stock_id = ?", (pocet, ctx.author.id, stock_id))
            else:
                c.execute("INSERT INTO stock_portfolios (user_id, stock_id, quantity) VALUES (?, ?, ?)", (ctx.author.id, stock_id, pocet))
            
            conn.commit()
        
        await ctx.respond(f"Úspěšně jsi zakoupil/a **{pocet}** akcií firmy **{self.stocks[stock_id]['name']}** za celkem **{total_cost:,.2f} Credits**.".replace(",", " "), ephemeral=True)

    @burza.command(name="prodat", description="Prodej akcie, které vlastníš.")
    async def sell_stock(self, ctx: discord.ApplicationContext, firma: str, pocet: int):
        stock_id = firma.upper()
        if stock_id not in self.stocks:
            await ctx.respond("Firma s tímto označením neexistuje.", ephemeral=True)
            return
        if pocet <= 0:
            await ctx.respond("Počet akcií musí být kladné číslo.", ephemeral=True)
            return

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT quantity FROM stock_portfolios WHERE user_id = ? AND stock_id = ?", (ctx.author.id, stock_id))
            current_quantity = c.fetchone()
            if not current_quantity or current_quantity[0] < pocet:
                await ctx.respond(f"Nevlastníš dostatek akcií firmy **{self.stocks[stock_id]['name']}**.", ephemeral=True)
                return

            c.execute("SELECT current_price FROM stocks WHERE stock_id = ?", (stock_id,))
            price = c.fetchone()[0]
            total_gain = price * pocet

            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (total_gain, ctx.author.id))
            
            new_quantity = current_quantity[0] - pocet
            if new_quantity == 0:
                c.execute("DELETE FROM stock_portfolios WHERE user_id = ? AND stock_id = ?", (ctx.author.id, stock_id))
            else:
                c.execute("UPDATE stock_portfolios SET quantity = ? WHERE user_id = ? AND stock_id = ?", (new_quantity, ctx.author.id, stock_id))
            
            conn.commit()

        await ctx.respond(f"Úspěšně jsi prodal/a **{pocet}** akcií firmy **{self.stocks[stock_id]['name']}** za celkem **{total_gain:,.2f} Credits**.".replace(",", " "), ephemeral=True)
    # --- Příkaz pro losování přidáme do AdminCommands ---
    # v souboru 2.py

# Ujistěte se, že máte nahoře tyto importy
import google.generativeai as genai

# --- NOVÁ TŘÍDA (COG) PRO UMĚLOU INTELIGENCI ---
class AICog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Konfigurace AI modelu
        genai.configure(api_key=GOOGLE_AI_API_KEY)
        self.ai_model = genai.GenerativeModel('gemini-1.5-flash-latest')
        print(f"--- DIAGNOSTIKA: AI Model nastaven na: {self.ai_model.model_name} ---")

    async def get_match_analysis(self, team1: str, team2: str) -> str:
        """
        Pošle dotaz na Gemini API a vrátí textovou analýzu zápasu.
        """
        prompt = f"""Jsi vtipný a sebevědomý český sportovní analytik pro hokej. Tvůj styl je mírně prostořeký a zábavný. 
        Napiš krátkou, fiktivní předzápasovou analýzu (cca 3-4 věty) a svůj tip na výsledek pro zápas mezi týmy '{team1}' a '{team2}'. 
        Buď kreativní a nepoužívej fráze jako 'jsem jazykový model'. Vytvoř dojem, že jsi skutečný expert."""
        
        try:
            response = await self.ai_model.generate_content_async(prompt)
            return response.text
        except Exception as e:
            print(f"Chyba při komunikaci s Google AI: {e}")
            return "Promiňte, moje křišťálová koule je zrovna zamlžená. Zkuste to později."

    @commands.slash_command(name="analyza_zapasu", description="Získej exkluzivní AI analýzu pro vybraný zápas!")
    async def analyze_match(self, ctx: discord.ApplicationContext, id_zapasu: int):
        await ctx.defer()
        
        team1, team2 = None, None
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT team1, team2 FROM matches WHERE match_id = ? AND status = 'open'", (id_zapasu,))
            match_data = c.fetchone()
        
        if not match_data:
            await ctx.respond("Zápas s tímto ID neexistuje nebo je již uzavřen.", ephemeral=True)
            return
            
        team1, team2 = match_data

        # Získání analýzy od AI
        analysis_text = await self.get_match_analysis(team1, team2)

        embed = discord.Embed(
            title=f"🤖 AI Analýza: {team1} vs. {team2}",
            description=analysis_text,
            color=0x4A90E2 # Modrá barva
        )
        embed.set_footer(text="Tato analýza je fiktivní a byla vygenerována AI.")
        
        await ctx.respond(embed=embed) 

# v souboru 2.py

# --- NOVÁ TŘÍDA (COG) PRO FANTASY TRH ---
# v souboru 2.py

# --- TŘÍDA (COG) PRO FANTASY TRH ---
class PlayerMarketCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    trh = SlashCommandGroup("trh", "Obchoduj s akciemi reálných hokejistů!", guild_ids=GUILD_IDS)

    @trh.command(name="ceny", description="Zobrazí aktuální hodnoty všech hokejistů na trhu.")
    async def player_prices(self, ctx: discord.ApplicationContext):
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT name, current_value, history FROM players ORDER BY current_value DESC")
            all_players = c.fetchall()

        embed = discord.Embed(title="🏒 Fantasy Trh - Kurzy Hráčů 🏒", color=0x1ABC9C)
        if not all_players:
            embed.description = "Na trhu zatím nejsou žádní hráči."
        
        for name, value, history_str in all_players:
            history = json.loads(history_str)
            if len(history) > 1:
                change = value - history[-2]
                trend_emoji = "🔼" if change >= 0 else "🔽"
                value_text = f"**{value:,.2f}** Credits {trend_emoji} ({change:+.2f})"
            else:
                value_text = f"**{value:,.2f}** Credits"
            embed.add_field(name=name, value=value_text.replace(",", " "), inline=False)
            
        await ctx.respond(embed=embed)

    @trh.command(name="portfolio", description="Zobrazí tvé portfolio akcií hokejistů.")
    async def player_portfolio(self, ctx: discord.ApplicationContext, uzivatel: discord.Option(discord.Member, "Zobraz portfolio tohoto hráče (nepovinné)", required=False) = None):
        target_user = uzivatel or ctx.author
        
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("""
                SELECT p.name, pf.quantity, s.current_value
                FROM player_portfolios pf
                JOIN players s ON pf.player_id = s.player_id
                WHERE pf.user_id = ?
            """, (target_user.id,))
            portfolio_items = c.fetchall()

        embed = discord.Embed(title=f"📈 Portfolio hráče {target_user.display_name}", color=0x2ECC71)
        if not portfolio_items:
            embed.description = "Tento hráč zatím nevlastní žádné akcie."
        else:
            total_value = 0
            for name, quantity, value in portfolio_items:
                stock_total_value = quantity * value
                total_value += stock_total_value
                embed.add_field(
                    name=f"{name}",
                    value=f"Počet: **{quantity}**\nAktuální hodnota: **{stock_total_value:,.2f}** Credits".replace(",", " "),
                    inline=False
                )
            embed.set_footer(text=f"Celková hodnota portfolia: {total_value:,.2f} Credits".replace(",", " "))
            
        await ctx.respond(embed=embed, ephemeral=True)

    @trh.command(name="koupit", description="Kup akcie vybraného hokejisty.")
    async def buy_player_stock(self, ctx: discord.ApplicationContext, jmeno_hrace: str, pocet: int):
        if pocet <= 0:
            await ctx.respond("Počet akcií musí být kladné číslo.", ephemeral=True)
            return

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT player_id, current_value FROM players WHERE name = ?", (jmeno_hrace,))
            player_data = c.fetchone()
            if not player_data:
                await ctx.respond("Hráč s tímto jménem není na trhu.", ephemeral=True)
                return
            
            player_id, price = player_data
            total_cost = price * pocet

            c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
            balance = c.fetchone()[0]
            if balance < total_cost:
                await ctx.respond(f"You don't have enough Credits. Potřebuješ **{total_cost:,.2f}**.".replace(",", " "), ephemeral=True)
                return

            # Transakce
            c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (total_cost, ctx.author.id))
            c.execute("""
                INSERT INTO player_portfolios (user_id, player_id, quantity) VALUES (?, ?, ?)
                ON CONFLICT(user_id, player_id) DO UPDATE SET quantity = quantity + excluded.quantity
            """, (ctx.author.id, player_id, pocet))
            conn.commit()
        
        await ctx.respond(f"✅ Úspěšně jsi zakoupil/a **{pocet}** akcií hráče **{jmeno_hrace}** za celkem **{total_cost:,.2f} Credits**.".replace(",", " "), ephemeral=True)

    @trh.command(name="prodat", description="Prodej akcie hokejisty, které vlastníš.")
    async def sell_player_stock(self, ctx: discord.ApplicationContext, jmeno_hrace: str, pocet: int):
        if pocet <= 0:
            await ctx.respond("Počet akcií musí být kladné číslo.", ephemeral=True)
            return

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT p.player_id, pf.quantity, p.current_value FROM player_portfolios pf JOIN players p ON pf.player_id = p.player_id WHERE pf.user_id = ? AND p.name = ?", (ctx.author.id, jmeno_hrace))
            portfolio_data = c.fetchone()
            
            if not portfolio_data or portfolio_data[1] < pocet:
                await ctx.respond(f"Nevlastníš dostatek akcií hráče **{jmeno_hrace}**.", ephemeral=True)
                return
            
            player_id, current_quantity, price = portfolio_data
            total_gain = price * pocet

            # Transakce
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (total_gain, ctx.author.id))
            
            new_quantity = current_quantity - pocet
            if new_quantity == 0:
                c.execute("DELETE FROM player_portfolios WHERE user_id = ? AND player_id = ?", (ctx.author.id, player_id))
            else:
                c.execute("UPDATE player_portfolios SET quantity = ? WHERE user_id = ? AND player_id = ?", (new_quantity, ctx.author.id, player_id))
            
            conn.commit()

        await ctx.respond(f"✅ Úspěšně jsi prodal/a **{pocet}** akcií hráče **{jmeno_hrace}** za celkem **{total_gain:,.2f} Credits**.".replace(",", " "), ephemeral=True)


    # v souboru 2.py

# --- NOVÁ TŘÍDA (COG) PRO ROZŠÍŘENÉ SÁZENÍ ---
class BettingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    sazka = SlashCommandGroup("sazka", "Podej si rozšířenou sázku na zápas.", guild_ids=GUILD_IDS)

    @sazka.command(name="nabidka", description="Zobrazí všechny dostupné sázky pro daný zápas.")
    async def show_odds(self, ctx: discord.ApplicationContext, id_zapasu: int):
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT team1, team2 FROM matches WHERE match_id = ? AND status = 'open'", (id_zapasu,))
            match_info = c.fetchone()
            if not match_info:
                await ctx.respond("Zápas s tímto ID neexistuje nebo není otevřený pro sázení.", ephemeral=True)
                return
            
            c.execute("SELECT bet_type, bet_value, odds FROM betting_options WHERE match_id = ?", (id_zapasu,))
            options = c.fetchall()

        if not options:
            await ctx.respond("Pro tento zápas zatím nebyly vypsány žádné sázkové příležitosti.", ephemeral=True)
            return

        embed = discord.Embed(title=f"Sázková Nabídka: {match_info[0]} vs {match_info[1]}", color=0xE67E22)
        
        # Seskupení sázek podle typu
        grouped_options = {}
        for bet_type, bet_value, odds in options:
            if bet_type not in grouped_options:
                grouped_options[bet_type] = ""
            grouped_options[bet_type] += f"`{bet_value}` - Kurz: **{odds}**\n"

        type_names = {"vitez": "Vítěz Zápasu", "skore": "Přesné Skóre", "over_under": "Over/Under"}
        for bet_type, value_str in grouped_options.items():
            embed.add_field(name=type_names.get(bet_type, bet_type), value=value_str, inline=False)

        await ctx.respond(embed=embed)

    @sazka.command(name="podat", description="Podej si sázku na vybranou příležitost.")
    async def place_bet(self, ctx: discord.ApplicationContext, id_zapasu: int, typ_sazky: discord.Option(str, choices=["vitez", "skore", "over_under"]), hodnota_sazky: str, castka: float):
        if castka <= 0:
            await ctx.respond("The amount must be a positive number.", ephemeral=True)
            return

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT odds FROM betting_options WHERE match_id = ? AND bet_type = ? AND LOWER(bet_value) = ?", (id_zapasu, typ_sazky, hodnota_sazky.lower()))
            option = c.fetchone()
            if not option:
                await ctx.respond("Tato sázková příležitost neexistuje. Zkontroluj si nabídku pomocí `/sazka nabidka`.", ephemeral=True)
                return
            
            odds = option[0]
            
            c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
            balance = c.fetchone()
            if not balance or balance[0] < castka:
                await ctx.respond("You don't have enough Credits na tuto sázku.", ephemeral=True)
                return

            # Transakce
            c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (castka, ctx.author.id))
            c.execute("INSERT INTO bets (user_id, match_id, bet_type, bet_value, odds, amount) VALUES (?, ?, ?, ?, ?, ?)",
                      (ctx.author.id, id_zapasu, typ_sazky, hodnota_sazky, odds, castka))
            conn.commit()

        await ctx.respond(f"✅ Přijato! Vsazeno **{castka:.2f} Credits** na **{hodnota_sazky}** (typ: {typ_sazky}) s kurzem **{odds}**.", ephemeral=True)

# Ujistěte se, že máte tento kód ve vašem souboru 3.py
# PŘED řádkem bot.add_cog(PersonalityCog(bot))

# --- TŘÍDA (COG) PRO OSOBNOST BOTA ---
class PersonalityCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        print("✅ Cog 'PersonalityCog' byl úspěšně načten.")
        # Konfigurace AI modelu
        try:
            # Předpokládá se, že GOOGLE_AI_API_KEY je definován globálně
            genai.configure(api_key=GOOGLE_AI_API_KEY)
            self.ai_model = genai.GenerativeModel('gemini-1.5-flash-latest')
            print("Osobnost bota úspěšně inicializována s modelem Gemini.")
        except Exception as e:
            self.ai_model = None
            print(f"CHYBA při inicializaci Google AI pro osobnost: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignorujeme zprávy od botů a zprávy bez zmínky
        if message.author.bot or self.bot.user not in message.mentions:
            return
            
        if not self.ai_model:
            return

        # Ukážeme, že bot "přemýšlí"
        async with message.channel.typing():
            prompt = f"""Jsi prostořeký, ale v jádru dobrácký bookmaker z Brna, který všem tyká a občas použije nějaké slovo z hantecu. 
            Jsi sebevědomý a vždy máš po ruce nějakou vtipnou nebo mírně jízlivou radu ohledně sázení. 
            Nereaguj na zmínku o tom, že jsi AI. Chovej se jako skutečná postava.
            
            Uživatel '{message.author.display_name}' ti právě napsal/a tuto zprávu: '{message.clean_content.replace(f'@{self.bot.user.name}', '').strip()}'
            
            Odpověz mu/jí ve svém stylu."""
            
            try:
                response = await self.ai_model.generate_content_async(prompt)
                await message.reply(response.text)
            except Exception as e:
                print(f"Chyba při generování odpovědi osobnosti: {e}")
                await message.reply("Co se do mě trefuješ? Mám zrovna plný ruce práce s kurzama.")

# v souboru 2.py

# --- NOVÁ TŘÍDA (COG) PRO JACKPOT ---
class JackpotCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_jackpot_status.start()

    def cog_unload(self):
        self.update_jackpot_status.cancel()

    @tasks.loop(minutes=5)
    async def update_jackpot_status(self):
        """Úloha, která každých 5 minut aktualizuje status bota s výší jackpotu."""
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT setting_value FROM bot_settings WHERE setting_key = 'progressive_jackpot'")
            jackpot = float(c.fetchone()[0])
        
        activity = discord.Game(name=f"Jackpot: {jackpot:,.0f} Credits!".replace(",", " "))
        await self.bot.change_presence(activity=activity)

    @update_jackpot_status.before_loop
    async def before_update_status(self):
        await self.bot.wait_until_ready()

    @commands.slash_command(name="jackpot", description="Zobrazí aktuální výši progresivního jackpotu.")
    async def jackpot(self, ctx: discord.ApplicationContext):
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT setting_value FROM bot_settings WHERE setting_key = 'progressive_jackpot'")
            jackpot = float(c.fetchone()[0])

        embed = discord.Embed(title="💰 Progresivní Jackpot 💰", description="Tento jackpot roste s každou sázkou na automatech a může padnout komukoliv a kdykoliv!", color=0xFFD700)
        embed.add_field(name="Aktuální hodnota", value=f"## **{jackpot:,.2f} Credits**".replace(",", " "))
        embed.set_footer(text="Hraj /minihry automat a zkus své štěstí!")
        await ctx.respond(embed=embed)


# v souboru 2.py

# Ujistěte se, že máte nahoře tyto importy
from poker_logic import PokerLobbyView, PokerGameView, BetRaiseModal
from treys import Card, Evaluator, Deck

# --- NOVÁ TŘÍDA (COG) PRO POKER ---
class PokerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.card_evaluator = Evaluator()
        self.active_games = {} 

    poker = SlashCommandGroup("poker", "Hraj Texas Hold'em Poker s ostatními hráči.", guild_ids=GUILD_IDS)

    async def update_lobby_embed(self, game_id: int, message: discord.Message):
        """Vylepšená verze, která zobrazuje jména hráčů."""
        if not message.embeds:
            return # Zpráva nemá embed, nelze upravit

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT user_id, stack FROM poker_players WHERE game_id = ?", (game_id,))
            players = c.fetchall()
        
        embed = message.embeds[0]
        embed.clear_fields()
        
        player_list = ""
        if not players:
            player_list = "Zatím nikdo."
        else:
            for user_id, stack in players:
                # Vylepšení: Získáme jméno uživatele
                try:
                    user = await self.bot.fetch_user(user_id)
                    user_name = user.display_name
                except discord.NotFound:
                    user_name = f"Neznámý hráč ({user_id})"
                
                player_list += f"**{user_name}** - Stack: **{stack:,.0f}**\n".replace(",", " ")
        
        embed.add_field(name=f"Hráči u stolu ({len(players)}/8)", value=player_list, inline=False)
        
        try:
            await message.edit(embed=embed)
        except discord.NotFound:
            print("Chyba: Zprávu lobby se nepodařilo najít, byla pravděpodobně smazána.")

    @poker.command(name="vytvorit_stul", description="Vytvoří nový pokerový stůl a otevře lobby.")
    async def create_table(self, ctx: discord.ApplicationContext):
        # Nejprve zkontrolujeme, zda hráč již není ve hře
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT game_id FROM poker_players WHERE user_id = ?", (ctx.author.id,))
            if c.fetchone():
                await ctx.respond("Již sedíš u jiného pokerového stolu!", ephemeral=True)
                return

        # Vytvoříme dočasný embed a view, abychom mohli poslat zprávu a získat její ID
        temp_embed = discord.Embed(title="♠️ Pokerové Lobby ♥️", description="Vytvářím stůl...", color=0xC70039)
        await ctx.respond(embed=temp_embed)
        message = await ctx.interaction.original_response()
        
        # Nyní, když máme ID zprávy, provedeme všechny databázové operace najednou
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("INSERT INTO poker_games (channel_id, message_id, status) VALUES (?, ?, 'waiting')", 
                      (ctx.channel_id, message.id))
            game_id = c.lastrowid
            conn.commit()

        # Nakonec upravíme původní zprávu s finálním obsahem a tlačítky
        final_embed = discord.Embed(
            title="♠️ Pokerové Lobby ♥️", 
            description=f"**{ctx.author.mention}** založil/a nový stůl! Klikni na **Připojit se** a zadej svůj buy-in.", 
            color=0xC70039
        )
        final_embed.set_footer(text=f"ID Stolu: {game_id}")
        
        view = PokerLobbyView(self.bot, ctx.author.id)
        await message.edit(embed=final_embed, view=view)

    async def handle_player_join(self, interaction: discord.Interaction, game_id: int, buy_in_amount: float):
        min_buy_in = 1000
        if buy_in_amount < min_buy_in:
            await interaction.response.send_message(f"Minimální buy-in je **{min_buy_in} Credits**.", ephemeral=True)
            return

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            
            # Vylepšení: Zkontrolujeme, zda uživatel vůbec existuje a má dostatek Credits
            c.execute("SELECT balance FROM users WHERE user_id = ?", (interaction.user.id,))
            result = c.fetchone()
            if not result:
                await interaction.response.send_message("Nejprve se musíš zaregistrovat pomocí `/registrovat`, abys mohl hrát.", ephemeral=True)
                return
            
            balance = result[0]
            if balance < buy_in_amount:
                await interaction.response.send_message("You don't have enough Credits na tento buy-in.", ephemeral=True)
                return
            
            # Kontrola, zda již hráč nesedí u stolu
            c.execute("SELECT * FROM poker_players WHERE game_id = ? AND user_id = ?", (game_id, interaction.user.id))
            if c.fetchone():
                await interaction.response.send_message("Už sedíš u tohoto stolu.", ephemeral=True)
                return
            
            # Kontrola, zda není stůl plný
            c.execute("SELECT COUNT(*) FROM poker_players WHERE game_id = ?", (game_id,))
            player_count = c.fetchone()[0]
            if player_count >= 8:
                await interaction.response.send_message("Stůl je již plný.", ephemeral=True)
                return

            # Vše je v pořádku, provedeme transakci
            c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (buy_in_amount, interaction.user.id))
            c.execute("INSERT INTO poker_players (game_id, user_id, stack) VALUES (?, ?, ?)", (game_id, interaction.user.id, buy_in_amount))
            conn.commit()

        await interaction.response.send_message(f"Úspěšně ses připojil/a ke stolu s **{buy_in_amount:,.0f} kredity**.".replace(",", " "), ephemeral=True)
        await self.update_lobby_embed(game_id, interaction.message)
        
    async def start_game_loop(self, interaction: discord.Interaction, game_id: int):
        await interaction.response.defer()
        
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT user_id, stack FROM poker_players WHERE game_id = ? ORDER BY player_id", (game_id,))
            players_data = c.fetchall()
            
            if len(players_data) < 2:
                await interaction.followup.send("Na zahájení hry jsou potřeba alespoň 2 hráči.", ephemeral=True)
                return
            
            c.execute("UPDATE poker_games SET status = 'active', betting_round = 'preflop' WHERE game_id = ?", (game_id,))

            player_objects = {}
            for user_id, stack in players_data:
                player_objects[user_id] = await self.bot.fetch_user(user_id)

            self.active_games[game_id] = {
                'deck': Deck(), 
                'last_raiser_id': None,
                'player_objects': player_objects
            }
            
            await self._deal_cards(c, game_id)

            # Zde byla původní chyba, nyní předáváme i 'c'
            await self._start_betting_round(c, interaction.message, game_id)
            
            conn.commit()


    async def _deal_cards(self, c, game_id): # Přijímá kurzor 'c', neotevírá novou db
        deck = self.active_games[game_id]['deck']
        
        c.execute("SELECT user_id FROM poker_players WHERE game_id = ? AND is_folded = 0", (game_id,))
        player_ids = [row[0] for row in c.fetchall()]

        for user_id in player_ids:
            hand_ints = deck.draw(2) # Vždy vrátí seznam 2 karet
            
            hand_str = json.dumps([Card.int_to_str(card) for card in hand_ints])
            c.execute("UPDATE poker_players SET hand = ? WHERE game_id = ? AND user_id = ?", (hand_str, game_id, user_id))
            
            try:
                user = await self.bot.fetch_user(user_id)
                pretty_hand = Card.ints_to_pretty_str(hand_ints)
                await user.send(f"Tvoje karty ve hře #{game_id}: {pretty_hand}")
            except Exception as e:
                print(f"Nepodařilo se odeslat DM hráči {user_id}: {e}")

    async def _start_betting_round(self, c, message: discord.Message, game_id: int):
        # Tato funkce již neotevírá vlastní spojení, ale přijímá ho jako 'c'
        
        # Resetujeme sázky z minulého kola
        c.execute("UPDATE poker_players SET current_bet = 0 WHERE game_id = ?", (game_id,))
        c.execute("UPDATE poker_games SET current_bet = 0 WHERE game_id = ?", (game_id,))
        
        # Najdeme prvního hráče na tahu, který ještě nesložil karty
        c.execute("SELECT user_id FROM poker_players WHERE game_id = ? AND is_folded = 0 ORDER BY player_id", (game_id,))
        players = [row[0] for row in c.fetchall()]
        
        if not players: # Všichni složili, hra končí
            # Tuto logiku bychom doplnili, ale prozatím to stačí
            return

        first_player_id = players[0]
        c.execute("UPDATE poker_games SET current_turn_user_id = ? WHERE game_id = ?", (first_player_id, game_id))
        
        # Nastavíme posledního sázejícího na prvního hráče, aby se kolo mohlo správně uzavřít
        self.active_games[game_id]['last_raiser_id'] = first_player_id
        
        # Commit se provede ve funkci, která tuto volá (_advance_game_stage)
        await self._update_game_view(message, game_id)

    async def _get_game_state(self, c, game_id):
        c.execute("SELECT * FROM poker_games WHERE game_id = ?", (game_id,))
        game_row = c.fetchone()
        if not game_row: return None
        game_keys = [desc[0] for desc in c.description]
        game_state = dict(zip(game_keys, game_row))
        
        c.execute("SELECT * FROM poker_players WHERE game_id = ? ORDER BY player_id", (game_id,))
        player_rows = c.fetchall()
        player_keys = [desc[0] for desc in c.description]
        game_state['players'] = [dict(zip(player_keys, row)) for row in player_rows]
        return game_state

    async def _update_game_view(self, message: discord.Message, game_id: int):
        # Tato funkce již neotevírá vlastní spojení, ale přijímá ho
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            state = await self._get_game_state(c, game_id)
        
        if not state: return

        embed = discord.Embed(title="♠️ Texas Hold'em Poker ♥️", color=0xC70039)
        community_cards = json.loads(state['community_cards'])
        community_cards_str = " ".join([Card.int_to_pretty_str(Card.new(c)) for c in community_cards])
        embed.add_field(name=f"Pot: {state['pot']:.2f} Credits", value=f"Společné karty: {community_cards_str if community_cards_str else 'Zatím žádné'}", inline=False)
        
        player_objects = self.active_games.get(game_id, {}).get('player_objects', {})
        players_text = ""
        for p in state['players']:
            player_obj = player_objects.get(p['user_id'])
            player_name = player_obj.display_name if player_obj else f"Hráč {p['user_id']}"
            
            status = " (Folded)" if p['is_folded'] else " (All-in)" if p['is_all_in'] else ""
            line = f"{player_name}: **{p['stack']:.2f}**{status} | Sázka: {p['current_bet']:.2f}"
            players_text += f"**> {line}**\n" if p['user_id'] == state['current_turn_user_id'] else f"{line}\n"
            
        embed.add_field(name=f"Hráči u stolu ({state['betting_round'].upper()})", value=players_text, inline=False)
        embed.set_footer(text=f"ID Stolu: {game_id}")
        
        view = PokerGameView(self.bot, state)
        try:
            await message.edit(embed=embed, view=view)
        except discord.NotFound:
            print(f"Chyba: Zprávu s hrou #{game_id} se nepodařilo najít pro aktualizaci.")

    async def _next_turn(self, c, message: discord.Message, game_id: int):
        # Tato funkce již neotevírá vlastní spojení, ale přijímá ho jako 'c'
        state = await self._get_game_state(c, game_id)
        if not state: return
        
        active_players = [p for p in state['players'] if not p['is_folded'] and not p['is_all_in']]
        if len(active_players) <= 1:
            return await self._showdown(message, game_id)

        current_player_index = next((i for i, p in enumerate(state['players']) if p['user_id'] == state['current_turn_user_id']), -1)
        
        # Najdeme dalšího hráče v pořadí
        for i in range(1, len(state['players']) + 2):
            next_index = (current_player_index + i) % len(state['players'])
            next_player = state['players'][next_index]

            if not next_player['is_folded'] and not next_player['is_all_in']:
                # Zkontrolujeme, zda sázkové kolo skončilo
                last_raiser_id = self.active_games[game_id].get('last_raiser_id')
                # Všichni aktivní hráči dorovnali aktuální nejvyšší sázku
                all_called = all(p['current_bet'] == state['current_bet'] for p in active_players)
                
                if next_player['user_id'] == last_raiser_id or (state['current_bet'] > 0 and all_called):
                    return await self._advance_game_stage(c, message, game_id)
                
                # Pokud kolo nekončí, předáme tah dalšímu hráči
                c.execute("UPDATE poker_games SET current_turn_user_id = ? WHERE game_id = ?", (next_player['user_id'], game_id))
                await self._update_game_view(c, message, game_id)
                return
        
    async def _advance_game_stage(self, message: discord.Message, game_id: int):
        deck = self.active_games[game_id]['deck']
        voice_assistant = self.bot.get_cog('VoiceAssistantCog')
        
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            state = await self._get_game_state(c, game_id)
            
            next_round_name = ""
            community_cards_str_list = json.loads(state['community_cards'])
            community_cards_int_list = [Card.new(c_str) for c_str in community_cards_str_list]

            if state['betting_round'] == 'preflop':
                next_round_name = "flop"
                deck.draw(1) # Spálíme kartu
                community_cards_int_list.extend(deck.draw(3)) # Flop
                if voice_assistant: await voice_assistant.speak("Přichází flop!")
            
            elif state['betting_round'] == 'flop':
                next_round_name = "turn"
                deck.draw(1) # Spálíme kartu
                community_cards_int_list.append(deck.draw(1)) # Turn
                if voice_assistant: await voice_assistant.speak("Na řadě je turn!")

            elif state['betting_round'] == 'turn':
                next_round_name = "river"
                deck.draw(1) # Spálíme kartu
                community_cards_int_list.append(deck.draw(1)) # River
                if voice_assistant: await voice_assistant.speak("Poslední karta, river!")

            elif state['betting_round'] == 'river':
                return await self._showdown(message, game_id)
            
            # OPRAVA ZDE: Ukládáme správný formát karet
            final_community_cards_str = json.dumps([Card.int_to_str(c) for c in community_cards_int_list])
            c.execute("UPDATE poker_games SET community_cards = ?, betting_round = ? WHERE game_id = ?", 
                      (final_community_cards_str, next_round_name, game_id))
            conn.commit()
            
        await self._start_betting_round(c, message, game_id)


    async def _showdown(self, message: discord.Message, game_id: int):
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            state = await self._get_game_state(c, game_id)
            
            board = [Card.new(c_str) for c_str in json.loads(state['community_cards'])]
            
            best_score, winners = 9999, []
            
            for player in state['players']:
                if not player['is_folded']:
                    hand = [Card.new(c_str) for c_str in json.loads(player['hand'])]
                    score = self.card_evaluator.evaluate(board, hand)
                    if score < best_score:
                        best_score, winners = score, [player]
                    elif score == best_score:
                        winners.append(player)
            
            hand_rank = self.card_evaluator.class_to_string(self.card_evaluator.get_rank_class(best_score))
            payout = state['pot'] / len(winners)
            winner_ids = [w['user_id'] for w in winners]
            winner_mentions = ", ".join([f"<@{uid}>" for uid in winner_ids])
            
            # TOTO PŘIDEJTE
            voice_assistant = self.bot.get_cog('VoiceAssistantCog')
            if voice_assistant:
                winner_names = [str(await self.bot.fetch_user(uid)) for uid in winner_ids]
                await voice_assistant.speak(f"Konec hry! Vítězí {', '.join(winner_names)} s kombinací {hand_rank}!")

            result_text = f"Showdown! Vítězí **{winner_mentions}** s kombinací **{hand_rank}** a bere si pot **{state['pot']:.2f}** Credits (každý {payout:.2f})!"
            
            for winner in winners:
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (payout, winner['user_id']))
            
            c.execute("UPDATE poker_games SET status = 'finished' WHERE game_id = ?", (game_id,))
            conn.commit()

        final_embed = message.embeds[0]
        final_embed.description = result_text
        await message.edit(embed=final_embed, view=None)
        del self.active_games[game_id]

    async def handle_fold_action(self, interaction: discord.Interaction, game_id: int):
        await interaction.response.defer()
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("UPDATE poker_players SET is_folded = 1 WHERE game_id = ? AND user_id = ?", (game_id, interaction.user.id))
            conn.commit()
            
            # Volání musí být uvnitř 'with' bloku
            await self._next_turn(c, interaction.message, game_id)

    async def handle_check_call_action(self, interaction: discord.Interaction, game_id: int):
        await interaction.response.defer()
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            state = await self._get_game_state(c, game_id)
            player = next((p for p in state['players'] if p['user_id'] == interaction.user.id), None)

            if not player: return

            amount_to_call = state['current_bet'] - player['current_bet']
            
            # Kontrola all-in situace
            is_all_in = False
            if amount_to_call >= player['stack']:
                amount_to_call = player['stack']
                is_all_in = True

            if amount_to_call > 0:
                c.execute("UPDATE poker_players SET stack = stack - ?, current_bet = current_bet + ?, is_all_in = ? WHERE game_id = ? AND user_id = ?",
                          (amount_to_call, amount_to_call, 1 if is_all_in else 0, game_id, interaction.user.id))
                c.execute("UPDATE poker_games SET pot = pot + ? WHERE game_id = ?", (amount_to_call, game_id))
            
            conn.commit()

            # Volání musí být uvnitř 'with' bloku
            await self._next_turn(c, interaction.message, game_id)

    async def open_bet_modal(self, c, interaction: discord.Interaction, game_id: int):
        # Tato funkce již neotevírá vlastní spojení, přijímá ho jako 'c'
        state = await self._get_game_state(c, game_id)
        player_state = next((p for p in state['players'] if p['user_id'] == interaction.user.id), None)
        if not player_state: return

        # OPRAVA ZDE: Správný výpočet minimální sázky/navýšení
        if state['current_bet'] > 0:
            min_bet = state['current_bet'] * 2
        else:
            min_bet = BIG_BLIND # Použijeme konstantu z konfigurace
        
        modal = BetRaiseModal(self.bot, game_id, min_bet, player_state['stack'])
        await interaction.response.send_modal(modal)

    async def handle_bet_raise_action(self, interaction: discord.Interaction, game_id: int, amount_str: str):
        try:
            amount = float(amount_str)
        except ValueError:
            await interaction.response.send_message("Neplatná částka. Zadej prosím platné číslo.", ephemeral=True)
            return

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            state = await self._get_game_state(c, game_id)
            player = next((p for p in state['players'] if p['user_id'] == interaction.user.id), None)

            if not player: # Pojistka
                await interaction.response.send_message("Chyba: Hráč nenalezen ve hře.", ephemeral=True)
                return

            # --- Kompletní validace sázky ---
            if amount > player['stack'] + player['current_bet']:
                await interaction.response.send_message("You don't have enough žetonů (stack) na tuto sázku.", ephemeral=True)
                return
            
            min_raise = state['current_bet'] + (state['current_bet'] - (self.active_games[game_id].get('last_raise_amount', 0)))
            if state['current_bet'] == 0: min_raise = BIG_BLIND # Minimální sázka je big blind

            if amount < min_raise and amount < player['stack'] + player['current_bet']:
                await interaction.response.send_message(f"Minimální sázka/navýšení (raise) je na **{min_raise}**.", ephemeral=True)
                return
            
            # --- Transakce ---
            is_all_in = False
            amount_from_stack = amount - player['current_bet']
            if amount_from_stack >= player['stack']:
                amount_from_stack = player['stack']
                amount = player['stack'] + player['current_bet']
                is_all_in = True

            # Pozor: Kredity se odečítají z herního stacku, ne z hlavního balance
            c.execute("UPDATE poker_players SET stack = stack - ?, current_bet = ?, is_all_in = ? WHERE game_id = ? AND user_id = ?",
                      (amount_from_stack, amount, 1 if is_all_in else 0, game_id, interaction.user.id))
            
            c.execute("UPDATE poker_games SET pot = pot + ?, current_bet = ? WHERE game_id = ?", 
                      (amount_from_stack, amount, game_id))
            
            conn.commit()
            
        self.active_games[game_id]['last_raiser_id'] = interaction.user.id
        self.active_games[game_id]['last_raise_amount'] = state['current_bet']
        
        # Potvrdíme interakci s modalem a posuneme hru
        await interaction.response.defer()
        await self._next_turn(c, interaction.message, game_id)

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            state = await self._get_game_state(c, game_id)
            player = next(p for p in state['players'] if p['user_id'] == interaction.user.id)
            
            # Validace sázky
            if amount > player['stack'] + player['current_bet']:
                await interaction.followup.send("You don't have enough Credits na tuto sázku.", ephemeral=True)
                return
            if amount < state['current_bet'] * 2 and state['current_bet'] > 0:
                await interaction.followup.send(f"Minimální navýšení (raise) je na **{state['current_bet'] * 2}**.", ephemeral=True)
                return

            amount_from_stack = amount - player['current_bet']
            c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount_from_stack, interaction.user.id))
            c.execute("UPDATE poker_players SET stack = stack - ?, current_bet = ? WHERE game_id = ? AND user_id = ?",
                      (amount_from_stack, amount, game_id, interaction.user.id))
            c.execute("UPDATE poker_games SET pot = pot + ?, current_bet = ? WHERE game_id = ?", (amount_from_stack, amount, game_id))
            conn.commit()
            
        self.active_games[game_id]['last_raiser_id'] = interaction.user.id
        await self._next_turn(interaction.message, game_id)

# v souboru 2.py

from gtts import gTTS
import os

# --- NOVÁ TŘÍDA (COG) PRO HLASOVÉHO ASISTENTA ---
class VoiceAssistantCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def speak(self, text: str):
        """Vygeneruje řeč z textu a přehraje ji v nastaveném hlasovém kanálu."""
        if not CASINO_VOICE_CHANNEL_ID:
            print("Chyba: Není nastaveno ID hlasového kanálu pro krupiéra.")
            return

        try:
            guild = self.bot.guilds[0] # Předpokládáme, že bot je jen na jednom serveru
            channel = self.bot.get_channel(CASINO_VOICE_CHANNEL_ID)
            if not isinstance(channel, discord.VoiceChannel):
                print(f"Chyba: Kanál {CASINO_VOICE_CHANNEL_ID} není hlasový kanál.")
                return

            # Vygenerování řeči do souboru
            tts = gTTS(text=text, lang='cs', slow=False)
            tts.save("announcement.mp3")
            
            # Připojení a přehrání
            voice_client = discord.utils.get(self.bot.voice_clients, guild=guild)
            if voice_client and voice_client.is_connected():
                if not voice_client.is_playing():
                    voice_client.play(discord.FFmpegPCMAudio("announcement.mp3"), after=lambda e: print(f'Přehrávání dokončeno, chyba: {e}'))
            else:
                vc = await channel.connect()
                vc.play(discord.FFmpegPCMAudio("announcement.mp3"), after=lambda e: print(f'Přehrávání dokončeno, chyba: {e}'))
            
            # Bot zůstane v kanálu připojený pro případné další oznámení

        except Exception as e:
            print(f"Nastala chyba v hlasovém asistentovi: {e}")


# v souboru 2.py

# --- NOVÁ TŘÍDA (COG) PRO BANKU A TREZOR ---
class BankCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_interest.start()
        self.loan_collection.start()

    def cog_unload(self):
        self.daily_interest.cancel()
        self.loan_collection.cancel()

    trezor = SlashCommandGroup("trezor", "Spravuj své finance v bezpečném bankovním trezoru.", guild_ids=GUILD_IDS)

    @tasks.loop(hours=24)
    async def daily_interest(self):
        """Jednou denně připíše úroky všem hráčům, co mají peníze v trezoru."""
        print(f"[{datetime.datetime.now()}] Spouštím denní připisování úroků z trezoru...")
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            interest_amount = VAULT_INTEREST_RATE_PERCENT / 100.0
            # Přičteme úrok a aktualizujeme datum
            c.execute("UPDATE users SET vault_balance = vault_balance * (1 + ?), last_interest_date = ? WHERE vault_balance > 0",
                      (interest_amount, datetime.datetime.now().isoformat()))
            conn.commit()
        print("Úroky z trezoru úspěšně připsány.")

    @daily_interest.before_loop
    async def before_daily_interest(self):
        await self.bot.wait_until_ready()

    @tasks.loop(hours=12) # Spustí se každých 12 hodin
    async def loan_collection(self):
        print(f"[{datetime.datetime.now()}] Spouštím kontrolu a vymáhání půjček po splatnosti...")
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            # Najdeme všechny dlužníky
            c.execute("SELECT user_id, loan_amount, loan_due_date, balance FROM users WHERE loan_amount > 0")
            debtors = c.fetchall()

            for user_id, loan_amount, due_date_str, balance in debtors:
                due_date = datetime.datetime.fromisoformat(due_date_str)
                # Pokud je půjčka po splatnosti A hráč má dost peněz
                if datetime.datetime.now() > due_date and balance >= loan_amount:
                    print(f"Vymáhám půjčku {loan_amount} od uživatele {user_id}...")
                    # Provedeme transakci
                    new_balance = balance - loan_amount
                    c.execute("UPDATE users SET balance = ?, loan_amount = 0, loan_due_date = NULL WHERE user_id = ?",
                              (new_balance, user_id))
                    
                    # Pokusíme se odeslat upozornění do DM
                    try:
                        user = await self.bot.fetch_user(user_id)
                        await user.send(f"Automatická splátka: Tvoje půjčka ve výši **{loan_amount:,.2f}** Credits byla automaticky splacena z tvého účtu.".replace(",", " "))
                    except Exception as e:
                        print(f"Nepodařilo se odeslat DM o splátce hráči {user_id}: {e}")
            
            conn.commit()
        print("Kontrola půjček dokončena.")

    @loan_collection.before_loop
    async def before_loan_collection(self):
        await self.bot.wait_until_ready()

    @trezor.command(name="info", description="Zobrazí stav tvého hlavního konta a trezoru.")
    async def vault_info(self, ctx: discord.ApplicationContext):
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT balance, vault_balance FROM users WHERE user_id = ?", (ctx.author.id,))
            data = c.fetchone()
        
        if not data:
            await ctx.respond("Nemáš založený účet.", ephemeral=True)
            return

        balance, vault_balance = data
        embed = discord.Embed(title=f"🏦 Bankovní Přehled: {ctx.author.display_name}", color=0xbdc3c7)
        embed.add_field(name="Kredity v peněžence", value=f"**{balance:,.2f}** (lze prosázet)".replace(",", " "), inline=False)
        embed.add_field(name="Kredity v trezoru", value=f"**{vault_balance:,.2f}** (bezpečné)".replace(",", " "), inline=False)
        embed.set_footer(text=f"Denní úrok z trezoru: {VAULT_INTEREST_RATE_PERCENT}%")
        await ctx.respond(embed=embed, ephemeral=True)

    @trezor.command(name="ulozit", description="Uloží kredity z peněženky do bezpečného trezoru.")
    async def deposit(self, ctx: discord.ApplicationContext, castka: float):
        if castka <= 0:
            await ctx.respond("The amount must be a positive number.", ephemeral=True)
            return
        
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
            balance = c.fetchone()
            if not balance or balance[0] < castka:
                await ctx.respond("V peněžence You don't have enough Credits na tento vklad.", ephemeral=True)
                return
            
            # Transakce
            c.execute("UPDATE users SET balance = balance - ?, vault_balance = vault_balance + ? WHERE user_id = ?", (castka, castka, ctx.author.id))
            conn.commit()
        
        await ctx.respond(f"Úspěšně jsi uložil/a **{castka:,.2f} Credits** do trezoru.".replace(",", " "), ephemeral=True)

    @trezor.command(name="vybrat", description="Vybere kredity z trezoru zpět do tvé peněženky.")
    async def withdraw(self, ctx: discord.ApplicationContext, castka: float):
        if castka <= 0:
            await ctx.respond("The amount must be a positive number.", ephemeral=True)
            return

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT vault_balance FROM users WHERE user_id = ?", (ctx.author.id,))
            vault_balance = c.fetchone()
            if not vault_balance or vault_balance[0] < castka:
                await ctx.respond("V trezoru You don't have enough Credits k výběru.", ephemeral=True)
                return
            
            # Transakce
            c.execute("UPDATE users SET vault_balance = vault_balance - ?, balance = balance + ? WHERE user_id = ?", (castka, castka, ctx.author.id))
            conn.commit()
            
        await ctx.respond(f"Úspěšně jsi vybral/a **{castka:,.2f} Credits** z trezoru.".replace(",", " "), ephemeral=True)
    # v souboru 3.py, uvnitř třídy BankCog

    # --- PŘÍKAZY PRO PŮJČKY ---
    pujcka = SlashCommandGroup("pujcka", "Půjč si kredity, když jsi na dně.", guild_ids=GUILD_IDS)

    @pujcka.command(name="info", description="Zobrazí informace o tvé aktuální půjčce.")
    async def loan_info(self, ctx: discord.ApplicationContext):
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT loan_amount, loan_due_date FROM users WHERE user_id = ?", (ctx.author.id,))
            data = c.fetchone()

        if not data or data[0] == 0:
            await ctx.respond("Momentálně nemáš žádnou aktivní půjčku.", ephemeral=True)
            return

        loan_amount, due_date_str = data
        due_date = datetime.datetime.fromisoformat(due_date_str)
        time_left = due_date - datetime.datetime.now()
        
        embed = discord.Embed(title="ℹ️ Informace o Půjčce", color=0xE74C3C)
        embed.add_field(name="Dlužná částka", value=f"**{loan_amount:,.2f}** Credits".replace(",", " "), inline=False)
        if time_left.total_seconds() > 0:
            days, remainder = divmod(time_left.seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, _ = divmod(remainder, 60)
            embed.add_field(name="Zbývá času na splacení", value=f"{time_left.days} dní, {hours}h {minutes}m", inline=False)
        else:
            embed.add_field(name="Status", value="Půjčka je po splatnosti!", inline=False)

        await ctx.respond(embed=embed, ephemeral=True)

    @pujcka.command(name="vzit_si", description="Vezmi si rychlou půjčku s vysokým úrokem.")
    async def take_loan(self, ctx: discord.ApplicationContext, castka: float):
        LOAN_INTEREST_RATE = 25 # 25% úrok
        LOAN_DURATION_DAYS = 3 # Doba splatnosti 3 dny
        MAX_LOAN_AMOUNT = 10000 # Maximální výše půjčky

        if not (100 <= castka <= MAX_LOAN_AMOUNT):
            await ctx.respond(f"Můžeš si půjčit částku mezi 100 a {MAX_LOAN_AMOUNT} kredity.", ephemeral=True)
            return
        
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT balance, loan_amount FROM users WHERE user_id = ?", (ctx.author.id,))
            data = c.fetchone()
            if not data:
                await ctx.respond("You must register first.", ephemeral=True)
                return
            
            balance, current_loan = data
            if current_loan > 0:
                await ctx.respond("Už máš aktivní půjčku! Nejprve ji musíš splatit.", ephemeral=True)
                return
            if balance > castka * 0.5:
                await ctx.respond("Na půjčku máš nárok, jen pokud jsi téměř na nule (máš méně než 50 % žádané částky).", ephemeral=True)
                return

            amount_to_repay = castka * (1 + (LOAN_INTEREST_RATE / 100.0))
            due_date = (datetime.datetime.now() + datetime.timedelta(days=LOAN_DURATION_DAYS)).isoformat()
            
            # Transakce
            c.execute("UPDATE users SET balance = balance + ?, loan_amount = ?, loan_due_date = ? WHERE user_id = ?",
                      (castka, amount_to_repay, due_date, ctx.author.id))
            conn.commit()

        await ctx.respond(f"✅ Půjčka schválena! Na účet ti bylo připsáno **{castka:,.2f}** Credits.\nDo **{LOAN_DURATION_DAYS} dnů** musíš mít na účtě dostatek prostředků na splacení **{amount_to_repay:,.2f}** Credits.".replace(",", " "), ephemeral=True)
    # --- NOVÝ PŘÍKAZ PRO MANUÁLNÍ SPLACENÍ ---
    @pujcka.command(name="splatit", description="Splatí tvou aktuální půjčku z Credits v peněžence.")
    async def repay_loan(self, ctx: discord.ApplicationContext):
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT balance, loan_amount FROM users WHERE user_id = ?", (ctx.author.id,))
            data = c.fetchone()

            if not data:
                await ctx.respond("Nemáš založený účet.", ephemeral=True)
                return

            balance, loan_amount = data
            if loan_amount == 0:
                await ctx.respond("Nemáš žádnou půjčku ke splacení.", ephemeral=True)
                return
            
            if balance < loan_amount:
                await ctx.respond(f"You don't have enough Credits na splacení půjčky. Potřebuješ **{loan_amount:,.2f}**, ale máš jen **{balance:,.2f}**.".replace(",", " "), ephemeral=True)
                return

            # Transakce splacení
            new_balance = balance - loan_amount
            c.execute("UPDATE users SET balance = ?, loan_amount = 0, loan_due_date = NULL WHERE user_id = ?", (new_balance, ctx.author.id))
            conn.commit()

        await ctx.respond(f"✅ Půjčka úspěšně splacena! Z účtu ti bylo strženo **{loan_amount:,.2f} Credits**.".replace(",", " "), ephemeral=True)


# v souboru 2.py

# --- NOVÁ TŘÍDA (COG) PRO KOLO ŠTĚSTÍ ---
class WheelOfFortuneCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Segmenty kola: násobek -> (úhel, šance)
        self.segments = {
            1:   (0,   10.0),   # 10.0 %
            2:   (45,   6.0),   # 6.0 %
            5:   (90,   3.0),   # 3.0 %
            0:   (135, 79.5),   # 79.5 % (Bankrot)
            10:  (180,  1.0),   # 1.0 %
            20:  (225,  0.4),   # 0.4 %
            100: (270,  0.1)    # 0.1 % (Jackpot)
        }
        # Vyrovnání šipky
        self.pointer_offset = 90


    def _generate_wheel_image(self, result_segment):
        """Vygeneruje finální obrázek kola s otočenou šipkou."""
        angle = self.segments[result_segment][0]
        
        background = Image.open("kolo.png").convert("RGBA")
        pointer = Image.open("sipka.png").convert("RGBA")

        # Otočíme šipku a vložíme ji na kolo
        rotated_pointer = pointer.rotate(angle + self.pointer_offset, resample=Image.Resampling.BICUBIC, expand=True)
        bg_center = (background.width // 2, background.height // 2)
        pointer_center = (rotated_pointer.width // 2, rotated_pointer.height // 2)
        
        # Vložíme otočenou šipku na střed pozadí
        background.paste(rotated_pointer, (bg_center[0] - pointer_center[0], bg_center[1] - pointer_center[1]), rotated_pointer)

        buffer = io.BytesIO()
        background.save(buffer, format="PNG")
        buffer.seek(0)
        return discord.File(buffer, filename="wheel_result.png")

    @commands.slash_command(name="kolo_stesti", description="Roztoč Kolo štěstí a vyhraj násobek své sázky!")
    async def spin_wheel(self, ctx: discord.ApplicationContext, sazka: float):
        if sazka <= 0:
            await ctx.respond("The bet must be a positive number.", ephemeral=True)
            return

        await ctx.defer()

        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
            result = c.fetchone()
            if not result or result[0] < sazka:
                await ctx.respond(f"You don't have enough Credits na tuto sázku.", ephemeral=True)
                return

            # Herní logika
            segment_keys = list(self.segments.keys())
            segment_weights = [s[1] for s in self.segments.values()]
            result_segment = random.choices(segment_keys, weights=segment_weights, k=1)[0]
            
            nasobek = result_segment
            vyhral = nasobek > 0
            
            zmena_konta = (sazka * nasobek) - sazka
            
            c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (zmena_konta, ctx.author.id))
            await self.bot.get_cog('UserCommands')._update_stats_and_xp(c, ctx, sazka, vyhral, nasobek)
            conn.commit()

            c.execute("SELECT balance FROM users WHERE user_id = ?", (ctx.author.id,))
            final_balance = c.fetchone()[0]

        # Generování obrázku
        result_image = self._generate_wheel_image(result_segment)

        # Vytvoření a odeslání výsledku
        embed = discord.Embed(title="🎡 Kolo Štěstí 🎡", color=discord.Color.gold() if vyhral else discord.Color.red())
        if result_segment == 0:
            embed.description = f"**BANKROT!** Kolo se zastavilo na 0 a prohráváš svou sázku."
        else:
            embed.description = f"Kolo se zastavilo a trefil jsi **{result_segment}x** násobek!"
        
        embed.add_field(name="Net profit/loss", value=f"{zmena_konta:+.2f} Credits", inline=True)
        embed.add_field(name="New account", value=f"{final_balance:.2f} Credits", inline=True)
        embed.set_image(url="attachment://wheel_result.png")
        
        await ctx.respond(embed=embed, file=result_image)



# ----------------------------------------------------
# TRANSFER SYSTEM - COG FOR PLAYER TRANSFERS BETWEEN TEAMS
# ----------------------------------------------------
class TransferCog(commands.Cog):
    """Cog for managing player transfers between teams."""
    
    def __init__(self, bot):
        self.bot = bot
        self._ensure_data_file()
    
    def _ensure_data_file(self):
        """Ensures that the folder and file for transfer data exist."""
        os.makedirs(TRANSFERS_DATA_PATH, exist_ok=True)
        if not os.path.exists(TRANSFERS_FILE):
            with open(TRANSFERS_FILE, 'w', encoding='utf-8') as f:
                json.dump([], f)
    
    def _load_transfers(self):
        """Loads transfer data from file."""
        try:
            with open(TRANSFERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    def _save_transfers(self, transfers):
        """Saves transfer data to file."""
        with open(TRANSFERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(transfers, f, indent=2, ensure_ascii=False)
    
    @commands.slash_command(
        name="transfer",
        description="Transfer a player between teams (captains only)",
        guild_ids=GUILD_IDS
    )
    async def transfer(
        self,
        ctx: discord.ApplicationContext,
        player: discord.Option(discord.Member, description="Player to transfer", required=True),
        from_team: discord.Option(discord.Role, description="Role - team the player is leaving", required=True),
        to_team: discord.Option(discord.Role, description="Role - team the player is joining", required=True)
    ):
        """Command to transfer a player between teams."""
        
        # Check if the user has the captain role
        initiator = ctx.author
        has_captain = discord.utils.get(initiator.roles, name=CAPTAIN_ROLE_NAME)
        
        if not has_captain:
            await ctx.respond(
                f"❌ Only users with the **{CAPTAIN_ROLE_NAME}** role can use this command.",
                ephemeral=True
            )
            return
        
        # Check bot permissions
        bot_member = ctx.guild.me
        if not bot_member.guild_permissions.manage_roles:
            await ctx.respond(
                "❌ Bot doesn't have `Manage Roles` permission. Please grant this permission.",
                ephemeral=True
            )
            return
        
        # Check if player is on the server
        if not player:
            await ctx.respond("❌ User is not on the server or cannot be loaded.", ephemeral=True)
            return
        
        # Remove old role (if they have it)
        had_from = from_team in player.roles
        if had_from:
            try:
                await player.remove_roles(from_team, reason=f"Transfer by {ctx.author.name}")
            except discord.Forbidden:
                await ctx.respond(
                    f"❌ Failed to remove role {from_team.name}. Check role hierarchy.",
                    ephemeral=True
                )
                return
            except Exception as e:
                await ctx.respond(
                    f"❌ Error removing role: {str(e)}",
                    ephemeral=True
                )
                return
        
        # Add new role
        try:
            await player.add_roles(to_team, reason=f"Transfer by {ctx.author.name}")
        except discord.Forbidden:
            await ctx.respond(
                f"❌ Failed to add role {to_team.name}. Check role hierarchy.",
                ephemeral=True
            )
            return
        except Exception as e:
            await ctx.respond(
                f"❌ Error adding role: {str(e)}",
                ephemeral=True
            )
            return
        
        # Create announcement
        announcement = (
            "🔁 **Transfer Update**\n"
            f"🧍‍♂️ Player: {player.mention}\n"
            f"📤 From team: {from_team.name}\n"
            f"📥 To team: {to_team.name}\n"
            f"✍️ Transfer approved by captain: {ctx.author.mention}"
        )
        
        # Send to #transfers channel
        transfer_channel = discord.utils.get(
            ctx.guild.text_channels,
            name=TRANSFERS_CHANNEL_NAME
        )
        if transfer_channel:
            try:
                await transfer_channel.send(announcement)
            except Exception as e:
                print(f"Error sending to {TRANSFERS_CHANNEL_NAME}: {e}")
        
        # Send to log channel
        log_channel = discord.utils.get(
            ctx.guild.text_channels,
            name=TRANSFERS_LOG_CHANNEL_NAME
        )
        if log_channel:
            try:
                log_message = (
                    f"📝 [LOG] {ctx.author.name}#{ctx.author.discriminator} "
                    f"transferred {player.name}#{player.discriminator} "
                    f"from {from_team.name} -> {to_team.name} (ID: {player.id})"
                )
                await log_channel.send(log_message)
            except Exception as e:
                print(f"Error sending to {TRANSFERS_LOG_CHANNEL_NAME}: {e}")
        
        # Save record to JSON
        try:
            transfers = self._load_transfers()
            entry = {
                "timestamp": datetime.datetime.now().isoformat(),
                "playerId": str(player.id),
                "oldTeam": from_team.name,
                "newTeam": to_team.name,
                "by": {
                    "id": str(ctx.author.id),
                    "tag": f"{ctx.author.name}#{ctx.author.discriminator}"
                }
            }
            transfers.append(entry)
            self._save_transfers(transfers)
        except Exception as e:
            print(f"Error writing to transfers.json: {e}")
        
        # Respond to user
        await ctx.respond(
            f"✅ Transfer completed: {player.mention} → **{to_team.name}**",
            ephemeral=False
        )
    
    # Command group for transfer-related commands
    transfers = SlashCommandGroup("transfers", "Commands for transfer history", guild_ids=GUILD_IDS)
    
    @transfers.command(
        name="history",
        description="Display transfer history for a player"
    )
    async def history(
        self,
        ctx: discord.ApplicationContext,
        player: discord.Option(discord.Member, description="Player", required=True)
    ):
        """Displays transfer history for a given player."""
        
        transfers = self._load_transfers()
        
        if not transfers:
            await ctx.respond("No records available.", ephemeral=True)
            return
        
        # Filter transfers for the given player
        player_transfers = [t for t in transfers if t.get("playerId") == str(player.id)]
        
        if not player_transfers:
            await ctx.respond(
                f"🚫 Player {player.mention} has no transfer history.",
                ephemeral=True
            )
            return
        
        # Display last 10 records
        last_transfers = player_transfers[-10:]
        last_transfers.reverse()
        
        lines = []
        for t in last_transfers:
            try:
                timestamp = datetime.datetime.fromisoformat(t["timestamp"])
                date_str = timestamp.strftime("%d.%m.%Y %H:%M")
            except:
                date_str = "unknown date"
            
            old_team = t.get("oldTeam", "?")
            new_team = t.get("newTeam", "?")
            by_tag = t.get("by", {}).get("tag", "unknown")
            
            lines.append(f"• {date_str} — {old_team} → {new_team} (by {by_tag})")
        
        response = f"📜 **Transfer history for {player.mention}:**\n" + "\n".join(lines)
        
        await ctx.respond(response, ephemeral=False)

# ============================================
# OWNER COMMANDS - Vzdálené ovládání serverů
# ============================================
class OwnerCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    def is_owner(self, user_id):
        """Kontrola, zda je uživatel owner bota"""
        return user_id == OWNER_ID
    
    def get_guild(self, guild_identifier):
        """Najde server podle ID nebo názvu"""
        try:
            # Zkus jako ID
            guild_id = int(guild_identifier)
            return self.bot.get_guild(guild_id)
        except ValueError:
            # Zkus jako název
            return discord.utils.get(self.bot.guilds, name=guild_identifier)
    
    # --- LIST SERVERS (pro zjištění ID) ---
    @discord.slash_command(
        name="owner_servers",
        description="[OWNER] Zobrazí všechny servery s ID",
        guild_ids=GUILD_IDS
    )
    async def owner_servers(self, ctx: discord.ApplicationContext):
        if not self.is_owner(ctx.author.id):
            await ctx.respond("❌ Tento příkaz je pouze pro vlastníka bota.", ephemeral=True)
            return
        
        info = []
        for i, guild in enumerate(self.bot.guilds, 1):
            info.append(
                f"**{i}. {guild.name}**\n"
                f"   📋 ID: `{guild.id}`\n"
                f"   👥 Členů: {guild.member_count}\n"
                f"   👑 Owner: {guild.owner}"
            )
        
        # Rozdělení na více zpráv, pokud je příliš dlouhé
        chunks = []
        current_chunk = f"🌐 **Bot je na {len(self.bot.guilds)} serverech:**\n\n"
        
        for item in info:
            if len(current_chunk) + len(item) > 1900:
                chunks.append(current_chunk)
                current_chunk = ""
            current_chunk += item + "\n"
        
        if current_chunk:
            chunks.append(current_chunk)
        
        for chunk in chunks:
            await ctx.respond(chunk, ephemeral=True)
    
    # --- BAN USER (vzdáleně) ---
    @discord.slash_command(
        name="owner_ban",
        description="[OWNER] Zabanuje uživatele na vybraném serveru",
        guild_ids=GUILD_IDS
    )
    async def owner_ban(
        self,
        ctx: discord.ApplicationContext,
        server_id: discord.Option(str, description="ID serveru (nebo 'all' pro všechny)", required=True),
        user_id: discord.Option(str, description="ID uživatele", required=True),
        reason: discord.Option(str, description="Důvod", required=False, default="Owner ban")
    ):
        if not self.is_owner(ctx.author.id):
            await ctx.respond("❌ Tento příkaz je pouze pro vlastníka bota.", ephemeral=True)
            return
        
        await ctx.defer(ephemeral=True)
        
        try:
            uid = int(user_id.strip('<@!>'))
            user = await self.bot.fetch_user(uid)
            
            banned_servers = []
            
            if server_id.lower() == "all":
                # Ban na všech serverech
                for guild in self.bot.guilds:
                    try:
                        await guild.ban(user, reason=f"[OWNER] {reason}")
                        banned_servers.append(guild.name)
                    except:
                        continue
            else:
                # Ban na konkrétním serveru
                guild = self.get_guild(server_id)
                if not guild:
                    await ctx.respond("❌ Server nenalezen.", ephemeral=True)
                    return
                
                try:
                    await guild.ban(user, reason=f"[OWNER] {reason}")
                    banned_servers.append(guild.name)
                except discord.Forbidden:
                    await ctx.respond("❌ Nemám oprávnění banovat na tomto serveru.", ephemeral=True)
                    return
            
            await ctx.respond(
                f"✅ **Uživatel zabanován**\n"
                f"👤 User: {user.name} (ID: {uid})\n"
                f"📝 Důvod: {reason}\n"
                f"🌐 Servery ({len(banned_servers)}): {', '.join(banned_servers)}",
                ephemeral=True
            )
                
        except ValueError:
            await ctx.respond("❌ Neplatné ID.", ephemeral=True)
        except Exception as e:
            await ctx.respond(f"❌ Chyba: {str(e)}", ephemeral=True)
    
    # --- UNBAN USER (vzdáleně) ---
    @discord.slash_command(
        name="owner_unban",
        description="[OWNER] Odbanuje uživatele na vybraném serveru",
        guild_ids=GUILD_IDS
    )
    async def owner_unban(
        self,
        ctx: discord.ApplicationContext,
        server_id: discord.Option(str, description="ID serveru (nebo 'all')", required=True),
        user_id: discord.Option(str, description="ID uživatele", required=True)
    ):
        if not self.is_owner(ctx.author.id):
            await ctx.respond("❌ Tento příkaz je pouze pro vlastníka bota.", ephemeral=True)
            return
        
        await ctx.defer(ephemeral=True)
        
        try:
            uid = int(user_id.strip('<@!>'))
            user = await self.bot.fetch_user(uid)
            
            unbanned_servers = []
            
            if server_id.lower() == "all":
                for guild in self.bot.guilds:
                    try:
                        await guild.unban(user)
                        unbanned_servers.append(guild.name)
                    except:
                        continue
            else:
                guild = self.get_guild(server_id)
                if not guild:
                    await ctx.respond("❌ Server nenalezen.", ephemeral=True)
                    return
                
                await guild.unban(user)
                unbanned_servers.append(guild.name)
            
            await ctx.respond(
                f"✅ **Uživatel odbanován**\n"
                f"👤 User: {user.name}\n"
                f"🌐 Servery: {', '.join(unbanned_servers)}",
                ephemeral=True
            )
                
        except Exception as e:
            await ctx.respond(f"❌ Chyba: {str(e)}", ephemeral=True)
    
    # --- KICK USER (vzdáleně) ---
    @discord.slash_command(
        name="owner_kick",
        description="[OWNER] Vyhodí uživatele ze serveru",
        guild_ids=GUILD_IDS
    )
    async def owner_kick(
        self,
        ctx: discord.ApplicationContext,
        server_id: discord.Option(str, description="ID serveru", required=True),
        user_id: discord.Option(str, description="ID uživatele", required=True),
        reason: discord.Option(str, description="Důvod", required=False, default="Owner kick")
    ):
        if not self.is_owner(ctx.author.id):
            await ctx.respond("❌ Tento příkaz je pouze pro vlastníka bota.", ephemeral=True)
            return
        
        try:
            guild = self.get_guild(server_id)
            if not guild:
                await ctx.respond("❌ Server nenalezen.", ephemeral=True)
                return
            
            uid = int(user_id.strip('<@!>'))
            member = guild.get_member(uid)
            
            if not member:
                await ctx.respond("❌ Uživatel není na tomto serveru.", ephemeral=True)
                return
            
            await member.kick(reason=f"[OWNER] {reason}")
            await ctx.respond(
                f"✅ **Uživatel vyhozen**\n"
                f"🌐 Server: {guild.name}\n"
                f"👤 User: {member.name}\n"
                f"📝 Důvod: {reason}",
                ephemeral=True
            )
        except Exception as e:
            await ctx.respond(f"❌ Chyba: {str(e)}", ephemeral=True)
    
    # --- BAN ALL (na konkrétním serveru) ---
    @discord.slash_command(
        name="owner_ban_all",
        description="[OWNER] Zabanuje všechny na serveru",
        guild_ids=GUILD_IDS
    )
    async def owner_ban_all(
        self,
        ctx: discord.ApplicationContext,
        server_id: discord.Option(str, description="ID serveru", required=True),
        confirm: discord.Option(str, description="Napiš 'CONFIRM'", required=True)
    ):
        if not self.is_owner(ctx.author.id):
            await ctx.respond("❌ Tento příkaz je pouze pro vlastníka bota.", ephemeral=True)
            return
        
        if confirm != "CONFIRM":
            await ctx.respond("❌ Musíš napsat přesně: CONFIRM", ephemeral=True)
            return
        
        guild = self.get_guild(server_id)
        if not guild:
            await ctx.respond("❌ Server nenalezen.", ephemeral=True)
            return
        
        await ctx.defer(ephemeral=True)
        
        banned_count = 0
        failed_count = 0
        
        for member in guild.members:
            if member.id == OWNER_ID or member.id == self.bot.user.id or member.bot:
                continue
            
            try:
                await guild.ban(member, reason="[OWNER] Mass ban")
                banned_count += 1
                await asyncio.sleep(1)
            except:
                failed_count += 1
        
        await ctx.respond(
            f"✅ **Hromadný ban dokončen na {guild.name}**\n"
            f"✅ Zabanováno: {banned_count}\n"
            f"❌ Selhalo: {failed_count}",
            ephemeral=True
        )
    
    # --- CLEAR MESSAGES (vzdáleně) ---
    @discord.slash_command(
        name="owner_clear",
        description="[OWNER] Smaže zprávy v kanálu",
        guild_ids=GUILD_IDS
    )
    async def owner_clear(
        self,
        ctx: discord.ApplicationContext,
        server_id: discord.Option(str, description="ID serveru", required=True),
        channel_id: discord.Option(str, description="ID kanálu", required=True),
        amount: discord.Option(int, description="Počet zpráv (max 100)", required=True)
    ):
        if not self.is_owner(ctx.author.id):
            await ctx.respond("❌ Tento příkaz je pouze pro vlastníka bota.", ephemeral=True)
            return
        
        try:
            guild = self.get_guild(server_id)
            if not guild:
                await ctx.respond("❌ Server nenalezen.", ephemeral=True)
                return
            
            channel = guild.get_channel(int(channel_id))
            if not channel:
                await ctx.respond("❌ Kanál nenalezen.", ephemeral=True)
                return
            
            if amount > 100:
                amount = 100
            
            deleted = await channel.purge(limit=amount)
            await ctx.respond(
                f"✅ Smazáno {len(deleted)} zpráv\n🌐 Server: {guild.name}\n📺 Kanál: {channel.name}",
                ephemeral=True
            )
        except Exception as e:
            await ctx.respond(f"❌ Chyba: {str(e)}", ephemeral=True)
    
    # --- BANLIST (vzdáleně) ---
    @discord.slash_command(
        name="owner_banlist",
        description="[OWNER] Seznam banů na serveru",
        guild_ids=GUILD_IDS
    )
    async def owner_banlist(
        self,
        ctx: discord.ApplicationContext,
        server_id: discord.Option(str, description="ID serveru", required=True)
    ):
        if not self.is_owner(ctx.author.id):
            await ctx.respond("❌ Tento příkaz je pouze pro vlastníka bota.", ephemeral=True)
            return
        
        await ctx.defer(ephemeral=True)
        
        try:
            guild = self.get_guild(server_id)
            if not guild:
                await ctx.respond("❌ Server nenalezen.", ephemeral=True)
                return
            
            bans = [entry async for entry in guild.bans()]
            
            if not bans:
                await ctx.respond(f"✅ Žádní zabanovaní na serveru **{guild.name}**", ephemeral=True)
                return
            
            ban_list = "\n".join([
                f"• {ban.user.name} (ID: {ban.user.id}) - {ban.reason or 'Bez důvodu'}" 
                for ban in bans[:20]
            ])
            
            await ctx.respond(
                f"🚫 **Bany na {guild.name} ({len(bans)} celkem):**\n{ban_list}",
                ephemeral=True
            )
        except Exception as e:
            await ctx.respond(f"❌ Chyba: {str(e)}", ephemeral=True)
    
    # --- LEAVE SERVER ---
    @discord.slash_command(
        name="owner_leave",
        description="[OWNER] Opustí server",
        guild_ids=GUILD_IDS
    )
    async def owner_leave(
        self,
        ctx: discord.ApplicationContext,
        server_id: discord.Option(str, description="ID serveru", required=True),
        confirm: discord.Option(str, description="Napiš 'LEAVE'", required=True)
    ):
        if not self.is_owner(ctx.author.id):
            await ctx.respond("❌ Tento příkaz je pouze pro vlastníka bota.", ephemeral=True)
            return
        
        if confirm != "LEAVE":
            await ctx.respond("❌ Musíš napsat: LEAVE", ephemeral=True)
            return
        
        guild = self.get_guild(server_id)
        if not guild:
            await ctx.respond("❌ Server nenalezen.", ephemeral=True)
            return
        
        guild_name = guild.name
        await guild.leave()
        await ctx.respond(f"✅ Bot opustil server: **{guild_name}**", ephemeral=True)
    
    # --- SHUTDOWN BOT ---
    @discord.slash_command(
        name="owner_shutdown",
        description="[OWNER] Vypne bota",
        guild_ids=GUILD_IDS
    )
    async def owner_shutdown(self, ctx: discord.ApplicationContext):
        if not self.is_owner(ctx.author.id):
            await ctx.respond("❌ Tento příkaz je pouze pro vlastníka bota.", ephemeral=True)
            return
        
        await ctx.respond("🔴 Bot se vypíná...", ephemeral=True)
        await self.bot.close()
 
 
     # --- TIMEOUT USER (vzdáleně) ---
    @discord.slash_command(
        name="owner_timeout",
        description="[OWNER] Timeout (mute) uživatele na serveru",
        guild_ids=GUILD_IDS
    )
    async def owner_timeout(
        self,
        ctx: discord.ApplicationContext,
        server_id: discord.Option(str, description="ID serveru (nebo 'all')", required=True),
        user_id: discord.Option(str, description="ID uživatele", required=True),
        duration: discord.Option(int, description="Délka timeoutu v minutách", required=True),
        reason: discord.Option(str, description="Důvod", required=False, default="Owner timeout")
    ):
        if not self.is_owner(ctx.author.id):
            await ctx.respond("❌ Tento příkaz je pouze pro vlastníka bota.", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)

        try:
            uid = int(user_id.strip('<@!>'))
            until = discord.utils.utcnow() + timedelta(minutes=duration)

            affected_servers = []

            if server_id.lower() == "all":
                for guild in self.bot.guilds:
                    member = guild.get_member(uid)
                    if not member:
                        continue

                    try:
                        await member.timeout(until, reason=f"[OWNER] {reason}")
                        affected_servers.append(guild.name)
                    except:
                        continue
            else:
                guild = self.get_guild(server_id)
                if not guild:
                    await ctx.respond("❌ Server nenalezen.", ephemeral=True)
                    return

                member = guild.get_member(uid)
                if not member:
                    await ctx.respond("❌ Uživatel není na tomto serveru.", ephemeral=True)
                    return

                await member.timeout(until, reason=f"[OWNER] {reason}")
                affected_servers.append(guild.name)

            if not affected_servers:
                await ctx.respond("⚠️ Uživatel nebyl nalezen na žádném serveru.", ephemeral=True)
                return

            await ctx.respond(
                f"🔇 **Timeout udělen**\n"
                f"👤 User ID: {uid}\n"
                f"⏱️ Délka: {duration} minut\n"
                f"📝 Důvod: {reason}\n"
                f"🌐 Servery ({len(affected_servers)}): {', '.join(affected_servers)}",
                ephemeral=True
            )

        except ValueError:
            await ctx.respond("❌ Neplatné ID.", ephemeral=True)
        except discord.Forbidden:
            await ctx.respond("❌ Nemám oprávnění dát timeout.", ephemeral=True)
        except Exception as e:
            await ctx.respond(f"❌ Chyba: {str(e)}", ephemeral=True)
# ----------------------------------------------------
# FINÁLNÍ REGISTRACE VŠECH FUNKCÍ (COGŮ)
# ----------------------------------------------------
print("--- Registruji všechny Cogy... ---")
bot.add_cog(UserCommands(bot))
bot.add_cog(AdminCommands(bot))
bot.add_cog(ProfileCog(bot))
bot.add_cog(RaceCog(bot)) 
bot.add_cog(ChessCog(bot))
bot.add_cog(RouletteCog(bot))
bot.add_cog(LotteryCog(bot))
bot.add_cog(PlayerMarketCog(bot))
bot.add_cog(BettingCog(bot))
bot.add_cog(AICog(bot))
bot.add_cog(GuildCog(bot))
bot.add_cog(PersonalityCog(bot)) # Přidána chybějící osobnost
bot.add_cog(StockMarketCog(bot)) # Přidána pro jistotu
bot.add_cog(JackpotCog(bot))
bot.add_cog(PokerCog(bot))
bot.add_cog(VoiceAssistantCog(bot))
bot.add_cog(BankCog(bot))
bot.add_cog(WheelOfFortuneCog(bot))
bot.add_cog(OwnerCommands(bot))
bot.add_cog(TransferCog(bot))  # Transfer systém
print("--- Registrace dokončena. ---")

# Spuštění bota
bot.run(BOT_TOKEN)