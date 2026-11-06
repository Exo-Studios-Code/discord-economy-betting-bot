# soubor: roulette_logic.py
import discord
import sqlite3

class BetModal(discord.ui.Modal):
    def __init__(self, bot, *args, **kwargs) -> None:
        super().__init__(title="Vsaď si na Ruletu", *args, **kwargs)
        self.bot = bot
        self.add_item(discord.ui.InputText(label="Na co sázíš? (číslo, barva, ...)", required=True))
        self.add_item(discord.ui.InputText(label="Kolik kreditů sázíš?", required=True))

    async def callback(self, interaction: discord.Interaction):
        roulette_cog = self.bot.get_cog('RouletteCog')
        if roulette_cog:
            await roulette_cog.handle_bet_submission(interaction, self.children[0].value, self.children[1].value)
        else:
            await interaction.response.send_message("Chyba: Komponenta rulety není aktivní.", ephemeral=True)

class RouletteView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Vsadit si!", style=discord.ButtonStyle.success, custom_id="place_roulette_bet")
    async def place_bet_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        roulette_cog = self.bot.get_cog('RouletteCog')
        if not roulette_cog or not roulette_cog.active_roulette_game:
            button.disabled = True
            await interaction.message.edit(view=self)
            await interaction.response.send_message("Sázky na tuto hru jsou již uzavřeny.", ephemeral=True)
            return
            
        modal = BetModal(self.bot)
        await interaction.response.send_modal(modal)