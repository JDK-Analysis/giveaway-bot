import os
import json
import io
from datetime import datetime

import discord
from discord.ext import commands
from dotenv import load_dotenv

# ---------- Load config from .env ----------

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))  # optional, not used directly

ENTRIES_FILE = "entries.json"


# ---------- Helpers to load/save entries ----------

def load_entries():
    if not os.path.exists(ENTRIES_FILE):
        with open(ENTRIES_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)

    with open(ENTRIES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_entries(entries):
    with open(ENTRIES_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)


# ---------- Bot setup ----------

intents = discord.Intents.default()
intents.message_content = True  # needed for prefix commands

bot = commands.Bot(command_prefix="!", intents=intents)


# ---------- Modal + View ----------

class UIDModal(discord.ui.Modal, title="Enter Giveaway"):
    uid = discord.ui.TextInput(
        label="Your Exchange UID",
        placeholder="Paste your UID here",
        max_length=100,
    )

    async def on_submit(self, interaction: discord.Interaction):
        uid_value = self.uid.value.strip()
        entries = load_entries()

        # Prevent same UID twice
        if any(e["uid"] == uid_value for e in entries):
            await interaction.response.send_message(
                "❌ This UID has already been used to enter the giveaway.",
                ephemeral=True,
            )
            return

        # Prevent same Discord user twice
        if any(e["discord_user_id"] == str(interaction.user.id) for e in entries):
            await interaction.response.send_message(
                "❌ You have already entered the giveaway.",
                ephemeral=True,
            )
            return

        entry = {
            "discord_user_id": str(interaction.user.id),
            "discord_tag": str(interaction.user),
            "uid": uid_value,
            "timestamp": datetime.utcnow().isoformat(),
        }

        entries.append(entry)
        save_entries(entries)

        await interaction.response.send_message(
            "✅ You have successfully entered the giveaway!",
            ephemeral=True,
        )


class EnterView(discord.ui.View):
    def __init__(self):
        # timeout=None so the view can be persistent
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Enter giveaway",
        style=discord.ButtonStyle.green,
        custom_id="giveaway_enter_button",
    )
    async def enter_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_modal(UIDModal())


# ---------- Events ----------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("Bot is ready.")

    # Register persistent view (so buttons on old messages still work)
    bot.add_view(EnterView())


# ---------- Commands ----------

@bot.command(name="start_giveaway")
@commands.has_permissions(administrator=True)
async def start_giveaway(ctx: commands.Context):
    """Post the giveaway message with the button."""
    embed = discord.Embed(
        title="💸 $300 Giveaway – 3 Winners!",
        description=(
            "We're giving away **$300** to **3 lucky winners** ($100 each).\n\n"
            "**How to enter:**\n"
            "1. Create an account with **BingX**.\n"
            "2. Trade at least **$1** before the draw.\n"
            "3. Click the button below and submit your **BingX UID**.\n\n"
            "You may only enter **once per UID and Discord account**."
        ),
        colour=discord.Colour.green(),
    )

    view = EnterView()
    await ctx.send(embed=embed, view=view)


@bot.command(name="export_entries")
@commands.has_permissions(administrator=True)
async def export_entries(ctx: commands.Context):
    """Admin exports all entries as a CSV file."""
    entries = load_entries()

    if not entries:
        await ctx.reply("⚠ No entries found.")
        return

    header = "discordUserId,discordTag,uid,timestamp\n"
    rows = []

    for e in entries:
        safe_uid = e["uid"].replace('"', '""')  # escape quotes for CSV

        row = ",".join(
            [
                f'"{e["discord_user_id"]}"',
                f'"{e["discord_tag"]}"',
                f'"{safe_uid}"',
                f'"{e["timestamp"]}"',
            ]
        )
        rows.append(row)

    csv_content = header + "\n".join(rows)
    csv_bytes = csv_content.encode("utf-8")

    file_obj = io.BytesIO(csv_bytes)
    file = discord.File(file_obj, filename="entries.csv")

    await ctx.reply(
        f"📁 Exported **{len(entries)}** entries.",
        file=file,
    )


# ---------- Run the bot ----------

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set in .env")

bot.run(TOKEN)
