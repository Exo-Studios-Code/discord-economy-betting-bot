import discord
import chess
import io
from PIL import Image, ImageDraw

SQUARE_SIZE = 64

def generate_board_image(board: chess.Board, pov_color=chess.WHITE, last_move=None):
    board_size = 8 * SQUARE_SIZE
    img = Image.new("RGB", (board_size, board_size), "white")
    draw = ImageDraw.Draw(img)

    light = (240, 217, 181)
    dark = (181, 136, 99)

    pieces = {
        "P": "♙", "p": "♟",
        "R": "♖", "r": "♜",
        "N": "♘", "n": "♞",
        "B": "♗", "b": "♝",
        "Q": "♕", "q": "♛",
        "K": "♔", "k": "♚"
    }

    for rank in range(8):
        for file in range(8):
            square = chess.square(file, 7 - rank)

            if pov_color == chess.BLACK:
                square = chess.square(7 - file, rank)

            x = file * SQUARE_SIZE
            y = rank * SQUARE_SIZE

            color = light if (file + rank) % 2 == 0 else dark
            draw.rectangle([x, y, x + SQUARE_SIZE, y + SQUARE_SIZE], fill=color)

            piece = board.piece_at(square)
            if piece:
                draw.text((x + 18, y + 12), pieces[piece.symbol()], fill="black")

    if last_move:
        for sq in [last_move.from_square, last_move.to_square]:
            f = chess.square_file(sq)
            r = 7 - chess.square_rank(sq)

            if pov_color == chess.BLACK:
                f = 7 - f
                r = 7 - r

            x = f * SQUARE_SIZE
            y = r * SQUARE_SIZE
            draw.rectangle([x, y, x + SQUARE_SIZE, y + SQUARE_SIZE], outline="red", width=3)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return discord.File(buffer, filename="board.png")


class ChallengeView(discord.ui.View):
    def __init__(self, challenger: discord.Member, opponent: discord.Member, wager: float):
        super().__init__(timeout=300.0)
        self.challenger = challenger
        self.opponent = opponent
        self.wager = wager
        self.accepted = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message("Toto není tvoje výzva!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Přijmout", style=discord.ButtonStyle.green)
    async def accept_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.accepted = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Odmítnout", style=discord.ButtonStyle.red)
    async def decline_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.accepted = False
        self.stop()
        await interaction.response.defer()