import os
# soubor: twitch_activity_bot.py
import twitchio
from twitchio.ext import commands
import sqlite3
import time

# --- Konfigurace Twitch Bota ---
TWITCH_OAUTH_TOKEN = os.getenv("TWITCH_OAUTH_TOKEN", "")
TWITCH_BOT_NICKNAME = "lsce_bot"
TARGET_TWITCH_CHANNEL = "Ex0Gen12"
MESSAGES_PER_POINT = 5 # Za kolik zpráv dostane uživatel 1 bod
CHAT_FEEDBACK_ENABLED = True # True = bot bude psát do chatu, False = bot bude potichu

class TwitchBot(commands.Bot):
    def __init__(self):
        # Připojení k Twitchi
        super().__init__(token=TWITCH_OAUTH_TOKEN.replace('oauth:', ''), prefix='!', initial_channels=[TARGET_TWITCH_CHANNEL])
        self.cooldowns = {} # Slovník pro sledování cooldownů na zprávy

    async def event_ready(self):
        print('------')
        print(f'Twitch Bot přihlášen jako | {self.nick}')
        print(f'Sleduje kanál | {TARGET_TWITCH_CHANNEL}')
        print(f'Bod za | {MESSAGES_PER_POINT} zpráv')
        print(f'Zpětná vazba v chatu | {"Zapnuta" if CHAT_FEEDBACK_ENABLED else "Vypnuta"}')
        print('------')

    async def event_message(self, message):
        # Ignorujeme zprávy od samotného bota
        if message.echo:
            return

        author = message.author.name.lower()

        # Použijeme robustní `with` pro správu databázového připojení
        try:
            with sqlite3.connect('sazkovka.db') as conn:
                c = conn.cursor()

                # Zvýšíme počet zpráv a hned získáme nový počet
                c.execute("UPDATE users SET twitch_message_count = twitch_message_count + 1 WHERE twitch_username = ?", (author,))
                conn.commit()

                # Zkontrolujeme, zda se vůbec něco aktualizovalo (tj. zda je uživatel propojen)
                if conn.total_changes == 0:
                    return # Uživatel není v naší databázi, nic neděláme

                c.execute("SELECT twitch_message_count FROM users WHERE twitch_username = ?", (author,))
                current_count = c.fetchone()[0]
                
                print(f"[{time.strftime('%H:%M:%S')}] {author}: {current_count}/{MESSAGES_PER_POINT} zpráv")

                # Pokud uživatel dosáhl cíle
                if current_count >= MESSAGES_PER_POINT:
                    # Resetujeme počítadlo a přidáme bod
                    c.execute("UPDATE users SET twitch_points = twitch_points + 1, twitch_message_count = 0 WHERE twitch_username = ?", (author,))
                    conn.commit()
                    
                    print(f"--- Bod připsán pro {author}! ---")
                    
                    # Odeslání zprávy do chatu (pokud je povoleno)
                    if CHAT_FEEDBACK_ENABLED:
                        await message.channel.send(f"@{message.author.name} získal/a 1 bod za aktivitu! 🔥")

        except sqlite3.Error as e:
            print(f"Nastala chyba při práci s databází: {e}")
        except Exception as e:
            print(f"Nastala neočekávaná chyba: {e}")

if __name__ == "__main__":
    bot = TwitchBot()
    bot.run()