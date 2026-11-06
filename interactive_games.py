# soubor: interactive_games.py
import discord
import sqlite3
import random
import datetime

# soubor: interactive_games.py
import discord
import sqlite3
import random
import datetime

# v souboru interactive_games.py

# --- FINÁLNÍ VERZE TŘÍDY PRO BLACKJACK ---
class BlackjackGame(discord.ui.View):
    def __init__(self, bot, sazka: float, hrac: discord.Member):
        super().__init__(timeout=180.0)
        self.bot = bot
        self.hrac = hrac
        self.owner_id = hrac.id
        self.sazka = sazka
        self.deck = self.create_deck()
        self.player_hand, self.dealer_hand = [], []
        self.player_score, self.dealer_score = 0, 0
        self.game_over = False

    async def start_game(self, ctx: discord.ApplicationContext):
        # Krok 1: Jen ověříme, zda má hráč dostatek kreditů
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            c.execute("SELECT balance FROM users WHERE user_id = ?", (self.owner_id,))
            result = c.fetchone()
            if not result or result[0] < self.sazka:
                await ctx.respond(f"Nemáš dostatek kreditů na sázku **{self.sazka}**!", ephemeral=True)
                return

        # Rozdání karet
        self.deal_card(self.player_hand)
        self.deal_card(self.dealer_hand)
        self.deal_card(self.player_hand)
        self.deal_card(self.dealer_hand)
        
        embed = self.create_embed()
        await ctx.respond(embed=embed, view=self)
        
        # Okamžitá kontrola na blackjack
        if self.calculate_score(self.player_hand) == 21:
            # Hra končí okamžitě, předáme 'interaction' z kontextu
            await self.end_game(ctx.interaction, win=True, reason="BLACKJACK!")

    # --- Herní Metody (zůstávají stejné) ---
    def create_deck(self):
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        suits = ['♥️', '♦️', '♣️', '♠️']
        deck = [{'rank': rank, 'suit': suit} for rank in ranks for suit in suits]
        random.shuffle(deck)
        return deck

    def get_card_value(self, card):
        if card['rank'] in ['J', 'Q', 'K']: return 10
        if card['rank'] == 'A': return 11
        return int(card['rank'])

    def calculate_score(self, hand):
        score = sum(self.get_card_value(card) for card in hand)
        aces = sum(1 for card in hand if card['rank'] == 'A')
        while score > 21 and aces > 0:
            score -= 10
            aces -= 1
        return score

    def deal_card(self, hand):
        card = self.deck.pop()
        hand.append(card)

    def format_hand(self, hand):
        return " ".join([f"**[{card['suit']}{card['rank']}]**" for card in hand])


    def create_embed(self, game_over=False, result_text=None, win_status=None):
        if game_over:
            if win_status is True: color = discord.Color.gold()
            elif win_status is False: color = discord.Color.red()
            else: color = discord.Color.light_grey()
        else:
            color = discord.Color.dark_green()

        embed = discord.Embed(title="🃏 Blackjack 🃏", color=color)
        embed.set_author(name=f"Hra pro: {self.hrac.display_name}", icon_url=self.hrac.display_avatar.url)
        
        self.player_score = self.calculate_score(self.player_hand)
        embed.add_field(name=f"Tvoje karty ({self.player_score})", value=self.format_hand(self.player_hand), inline=False)
        
        dealer_hand_text = self.format_hand(self.dealer_hand) if game_over else f"{self.format_hand([self.dealer_hand[0]])} [?]"
        dealer_score_text = f"({self.calculate_score(self.dealer_hand)})" if game_over else "(?)"
        embed.add_field(name=f"Karty krupiéra {dealer_score_text}", value=dealer_hand_text, inline=False)

        if game_over:
            embed.description = result_text
        
        return embed

    # --- Tlačítka ---
    @discord.ui.button(label="Hit (Další)", style=discord.ButtonStyle.green, custom_id="bj_hit")
    async def hit_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        self.deal_card(self.player_hand)
        
        if self.calculate_score(self.player_hand) > 21:
            await self.end_game(interaction, win=False, reason="Přesáhl jsi 21! Prohráváš.")
        else:
            embed = self.create_embed()
            await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Stand (Stojím)", style=discord.ButtonStyle.red, custom_id="bj_stand")
    async def stand_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.dealer_turn(interaction)

    # --- Ukončení Hry ---
    async def dealer_turn(self, interaction):
        self.dealer_score = self.calculate_score(self.dealer_hand)
        while self.dealer_score < 17:
            self.deal_card(self.dealer_hand)
            self.dealer_score = self.calculate_score(self.dealer_hand)

        player_score = self.calculate_score(self.player_hand)
        if self.dealer_score > 21: await self.end_game(interaction, win=True, reason="Krupiér přesáhl 21! Vyhráváš!")
        elif self.dealer_score > player_score: await self.end_game(interaction, win=False, reason="Krupiér má více bodů. Prohráváš.")
        elif self.dealer_score < player_score: await self.end_game(interaction, win=True, reason="Máš více bodů než krupiér! Vyhráváš!")
        else: await self.end_game(interaction, win=None, reason="Remíza (Push)! Sázka se vrací.")

    # v souboru interactive_games.py, uvnitř třídy BlackjackGame

    async def end_game(self, interaction: discord.Interaction, win, reason):
        if self.game_over: return
        self.game_over = True
        self.disable_all_items()
        
        net_change, nasobek_pro_xp = 0, 0
        if win is True:
            net_change = self.sazka
            nasobek_pro_xp = 2
        elif win is False:
            net_change = -self.sazka
            nasobek_pro_xp = 1
        
        new_level = None
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            if net_change != 0:
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (net_change, self.owner_id))

            if win is not None:
                if win: c.execute("UPDATE users SET games_played = games_played + 1, games_won = games_won + 1 WHERE user_id = ?", (self.owner_id,))
                else: c.execute("UPDATE users SET games_played = games_played + 1 WHERE user_id = ?", (self.owner_id,))
            
            profile_cog = self.bot.get_cog('ProfileCog')
            if profile_cog:
                xp_to_add = max(1.0, self.sazka * 0.1) * (nasobek_pro_xp if win is not False else 1)
                new_level = await profile_cog._add_xp(c, self.owner_id, xp_to_add)
            
            conn.commit()
        
        payout = self.sazka + net_change
        result_text = f"**{reason}**\nVýhra: **{payout:.2f} Kreditů**"
        
        # ZMĚNA ZDE: Přidáme info o level upu přímo do výsledku
        if new_level:
            result_text += f"\n\n🎉 **LEVEL UP!** Dosáhl jsi **Levelu {new_level}**!"

        final_embed = self.create_embed(game_over=True, result_text=result_text, win_status=win)
        
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=final_embed, view=self)
        else:
            await interaction.edit_original_response(embed=final_embed, view=self)

# --- Zde můžete v budoucnu přidat logiku pro další interaktivní hry ---
# v souboru interactive_games.py

# --- Logika pro Stírací Los ---
class ScratchTicketView(discord.ui.View):
    def __init__(self, bot, ctx, price, prizes):
        super().__init__(timeout=180.0)
        self.bot = bot
        self.ctx = ctx
        self.owner_id = ctx.author.id
        self.price = price
        self.prizes = prizes
        
        self.scratches_left = 3
        self.revealed = [[False] * 3 for _ in range(3)]
        self.grid = self.generate_grid()
        self.game_over = False

    def generate_grid(self):
        """Vygeneruje skrytou mřížku se symboly podle jejich vzácnosti."""
        emojis = list(self.prizes.keys())
        # Vzácnější emoji (s vyšší výhrou) se objeví méně často
        weights = [1, 2, 4, 8, 15, 25] 
        
        # Zaručíme alespoň jednu výherní trojici, aby to bylo zábavnější
        winning_emoji = random.choices(emojis, weights=weights, k=1)[0]
        grid_items = [winning_emoji] * 3
        
        # Doplníme zbytek mřížky
        while len(grid_items) < 9:
            grid_items.append(random.choices(emojis, weights=weights, k=1)[0])
            
        random.shuffle(grid_items)
        return [grid_items[i*3:(i+1)*3] for i in range(3)]

    def get_grid_display(self):
        """Vytvoří textovou reprezentaci mřížky pro embed."""
        display = ""
        for r in range(3):
            for c in range(3):
                if self.revealed[r][c]:
                    display += f" {self.grid[r][c]} "
                else:
                    display += f" ||:grey_question:|| "
            display += "\n"
        return display

    async def create_initial_embed(self):
        embed = discord.Embed(
            title="🎫 Stírací Los 🎫",
            description=self.get_grid_display(),
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Zbývá pokusů: {self.scratches_left}")
        return embed

    def check_for_win(self):
        """Zkontroluje, zda odhalená políčka tvoří výherní kombinaci."""
        revealed_emojis = []
        for r in range(3):
            for c in range(3):
                if self.revealed[r][c]:
                    revealed_emojis.append(self.grid[r][c])
        
        from collections import Counter
        counts = Counter(revealed_emojis)
        
        for emoji, count in counts.items():
            if count == 3:
                return self.prizes[emoji], emoji # Vrátí výhru a výherní emoji
        return 0, None

# Tuto funkci použijte pro end_game v BlackjackGame i ScratchTicketView
# v souboru interactive_games.py

    async def end_game(self, interaction: discord.Interaction, win, reason_or_emoji):
        payout = 0
        nasobek_pro_xp = 0
        sazka = self.bet if hasattr(self, 'bet') else self.price # Získáme sázku/cenu
        vyhral = win

        if isinstance(win, bool) and win: # Pro Blackjack
            payout = sazka * 2
            nasobek_pro_xp = 2
        elif isinstance(win, int) and win > 0: # Pro Stírací losy
             payout = win
             nasobek_pro_xp = win / sazka
        elif win is None: # Pro remízu v Blackjacku
            payout = sazka
            nasobek_pro_xp = 1
        
        with sqlite3.connect('sazkovka.db') as conn:
            c = conn.cursor()
            if payout > 0:
                c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (payout, self.owner_id))

            if vyhral is not None:
                if vyhral: c.execute("UPDATE users SET games_played = games_played + 1, games_won = games_won + 1 WHERE user_id = ?", (self.owner_id,))
                else: c.execute("UPDATE users SET games_played = games_played + 1 WHERE user_id = ?", (self.owner_id,))

            profile_cog = self.bot.get_cog('ProfileCog')
            if profile_cog:
                xp_to_add = max(1.0, sazka * 0.1)
                if vyhral is not False: xp_to_add *= nasobek_pro_xp
                
                new_level = await profile_cog._add_xp(c, self.owner_id, xp_to_add)
                if new_level:
                    await interaction.followup.send(f"🎉 **LEVEL UP!** Gratulujeme, {interaction.user.mention}! Právě jsi dosáhl/a **Levelu {new_level}**!", ephemeral=False)
            
            conn.commit()
        
        # Aktualizace původní zprávy
        if "Blackjack" in self.title:
             await self.update_view(interaction, game_over=True, result_text=f"**{reason_or_emoji}**\nVýhra: **{payout:.2f} Kreditů**")
        else: # Stírací los
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.gold() if vyhral else discord.Color.red()
            embed.add_field(name="VÝHRA!" if vyhral else "Žádná výhra", value=f"Našel jsi 3x {reason_or_emoji} a vyhráváš **{payout:,.0f} Kreditů**!".replace(",", " ") if vyhral else "Bohužel, tentokrát to nevyšlo.", inline=False)
            await interaction.message.edit(embed=embed, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Toto není tvůj los!", ephemeral=True)
            return False
        return True

    # Generování tlačítek pro mřížku 3x3
    # Každé tlačítko má unikátní custom_id a volá stejnou funkci
    @discord.ui.button(label="​", style=discord.ButtonStyle.secondary, custom_id="scratch_0_0", row=0)
    async def button_0_0(self, button: discord.ui.Button, interaction: discord.Interaction): await self.on_button_click(button, interaction)
    @discord.ui.button(label="​", style=discord.ButtonStyle.secondary, custom_id="scratch_0_1", row=0)
    async def button_0_1(self, button: discord.ui.Button, interaction: discord.Interaction): await self.on_button_click(button, interaction)
    @discord.ui.button(label="​", style=discord.ButtonStyle.secondary, custom_id="scratch_0_2", row=0)
    async def button_0_2(self, button: discord.ui.Button, interaction: discord.Interaction): await self.on_button_click(button, interaction)
    @discord.ui.button(label="​", style=discord.ButtonStyle.secondary, custom_id="scratch_1_0", row=1)
    async def button_1_0(self, button: discord.ui.Button, interaction: discord.Interaction): await self.on_button_click(button, interaction)
    @discord.ui.button(label="​", style=discord.ButtonStyle.secondary, custom_id="scratch_1_1", row=1)
    async def button_1_1(self, button: discord.ui.Button, interaction: discord.Interaction): await self.on_button_click(button, interaction)
    @discord.ui.button(label="​", style=discord.ButtonStyle.secondary, custom_id="scratch_1_2", row=1)
    async def button_1_2(self, button: discord.ui.Button, interaction: discord.Interaction): await self.on_button_click(button, interaction)
    @discord.ui.button(label="​", style=discord.ButtonStyle.secondary, custom_id="scratch_2_0", row=2)
    async def button_2_0(self, button: discord.ui.Button, interaction: discord.Interaction): await self.on_button_click(button, interaction)
    @discord.ui.button(label="​", style=discord.ButtonStyle.secondary, custom_id="scratch_2_1", row=2)
    async def button_2_1(self, button: discord.ui.Button, interaction: discord.Interaction): await self.on_button_click(button, interaction)
    @discord.ui.button(label="​", style=discord.ButtonStyle.secondary, custom_id="scratch_2_2", row=2)
    async def button_2_2(self, button: discord.ui.Button, interaction: discord.Interaction): await self.on_button_click(button, interaction)

    async def on_button_click(self, button: discord.ui.Button, interaction: discord.Interaction):
        if self.game_over:
            await interaction.response.defer()
            return

        # Zjistíme pozici z custom_id
        _, r, c = button.custom_id.split('_')
        row, col = int(r), int(c)

        if self.revealed[row][col]:
            await interaction.response.send_message("Toto políčko jsi už seškrábal!", ephemeral=True)
            return

        await interaction.response.defer()

        self.scratches_left -= 1
        self.revealed[row][col] = True
        button.disabled = True # Zneaktivníme tlačítko
        button.style = discord.ButtonStyle.primary

        # Zkontrolujeme výhru, pokud už nezbývají pokusy
        if self.scratches_left == 0:
            win_amount, win_emoji = self.check_for_win()
            await self.end_game(interaction, win_amount, win_emoji)
        else:
            # Jinak jen aktualizujeme embed
            embed = await self.create_initial_embed()
            await interaction.message.edit(embed=embed, view=self)