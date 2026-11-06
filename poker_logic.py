# soubor: poker_logic.py
import discord
import sqlite3

class BuyInModal(discord.ui.Modal):
    def __init__(self, bot, game_id: int, *args, **kwargs) -> None:
        super().__init__(title="Vstup do hry", *args, **kwargs)
        self.bot = bot
        self.game_id = game_id
        self.add_item(discord.ui.InputText(label="Kolik kreditů si bereš ke stolu?", placeholder="Minimálně 1000", required=True))

    async def callback(self, interaction: discord.Interaction):
        poker_cog = self.bot.get_cog('PokerCog')
        if not poker_cog:
            await interaction.response.send_message("Chyba: Komponenta pokeru není aktivní.", ephemeral=True)
            return

        try:
            # TOTO JE KLÍČOVÁ OPRAVA: Převedeme vstup na číslo (float)
            buy_in_amount = float(self.children[0].value)
            
            # Až poté voláme funkci, které už posíláme číslo, ne text
            await poker_cog.handle_player_join(interaction, self.game_id, buy_in_amount)
        except ValueError:
            # Pokud hráč zadá něco jiného než číslo (např. "tisíc")
            await interaction.response.send_message("Zadej prosím platné číslo (např. 1000).", ephemeral=True)

class BetRaiseModal(discord.ui.Modal):
    def __init__(self, bot, game_id: int, min_bet: float, player_stack: float, *args, **kwargs) -> None:
        super().__init__(title="Sázka / Navýšení", *args, **kwargs)
        self.bot = bot
        self.game_id = game_id
        self.add_item(discord.ui.InputText(label=f"Zadej celkovou částku sázky", placeholder=f"Min. navýšení je na {min_bet}. Máš: {player_stack}", required=True))

    async def callback(self, interaction: discord.Interaction):
        poker_cog = self.bot.get_cog('PokerCog')
        if poker_cog:
            await poker_cog.handle_bet_raise_action(interaction, self.game_id, self.children[0].value)

class PokerLobbyView(discord.ui.View):
    def __init__(self, bot, host_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.host_id = host_id

    # v souboru poker_logic.py

    @discord.ui.button(label="Připojit se", style=discord.ButtonStyle.success, custom_id="poker_join")
    async def join_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        # OPRAVA ZDE: Hledáme správný text "ID Stolu: "
        try:
            game_id = int(interaction.message.embeds[0].footer.text.split("ID Stolu: ")[1])
        except (IndexError, ValueError):
            await interaction.response.send_message("Chyba: Nepodařilo se přečíst ID stolu z původní zprávy.", ephemeral=True)
            return
            
        modal = BuyInModal(self.bot, game_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Start Hry", style=discord.ButtonStyle.primary, custom_id="poker_start")
    async def start_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.host_id:
            await interaction.response.send_message("Hru může spustit pouze zakladatel stolu.", ephemeral=True)
            return

        poker_cog = self.bot.get_cog('PokerCog')
        if poker_cog:
            # OPRAVA ZDE: Hledáme správný text "ID Stolu: "
            try:
                game_id = int(interaction.message.embeds[0].footer.text.split("ID Stolu: ")[1])
            except (IndexError, ValueError):
                await interaction.response.send_message("Chyba: Nepodařilo se přečíst ID stolu.", ephemeral=True)
                return
                
            await poker_cog.start_game_loop(interaction, game_id)
        else:
            await interaction.response.send_message("Chyba: Komponenta pokeru není aktivní.", ephemeral=True)

class PokerGameView(discord.ui.View):
    def __init__(self, bot, game_state: dict):
        super().__init__(timeout=300.0) # Hráč má 5 minut na tah
        self.bot = bot
        self.game_id = game_state['game_id']
        self.current_player_id = game_state['current_turn_user_id']
        self._setup_buttons(game_state)

    def _setup_buttons(self, game_state):
        player_state = next((p for p in game_state['players'] if p['user_id'] == self.current_player_id), None)
        if not player_state: return

        can_check = game_state['current_bet'] == player_state['current_bet']
        self.check_call_button.label = "Check" if can_check else f"Call ({game_state['current_bet'] - player_state['current_bet']})"
        self.check_call_button.style = discord.ButtonStyle.secondary if can_check else discord.ButtonStyle.primary
        self.bet_raise_button.label = "Raise" if game_state['current_bet'] > 0 else "Bet"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.current_player_id:
            await interaction.response.send_message("Nejsi na tahu!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Check/Call", style=discord.ButtonStyle.secondary, custom_id="poker_check_call")
    async def check_call_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        poker_cog = self.bot.get_cog('PokerCog')
        if poker_cog: await poker_cog.handle_check_call_action(interaction, self.game_id)

    @discord.ui.button(label="Bet/Raise", style=discord.ButtonStyle.success, custom_id="poker_bet_raise")
    async def bet_raise_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        poker_cog = self.bot.get_cog('PokerCog')
        if poker_cog: await poker_cog.open_bet_modal(interaction, self.game_id)

    @discord.ui.button(label="Fold", style=discord.ButtonStyle.red, custom_id="poker_fold")
    async def fold_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        poker_cog = self.bot.get_cog('PokerCog')
        if poker_cog: await poker_cog.handle_fold_action(interaction, self.game_id)