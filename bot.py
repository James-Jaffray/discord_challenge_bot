import os
from dotenv import load_dotenv
import discord
from discord.ext import commands

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN is None:
    raise SystemExit("DISCORD_TOKEN is missing from .env")

GUILD_ID = os.getenv("GUILD_ID")
if GUILD_ID is None:
    raise SystemExit("GUILD_ID is missing from .env")

TEST_GUILD = discord.Object(id=int(GUILD_ID))

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")



# print("Token loaded") # troubleshooting
@bot.tree.command(name="ping", description="Check that the bot is alive", guild=TEST_GUILD)
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!")


@bot.event
async def setup_hook():
    await bot.tree.sync(guild=TEST_GUILD)

bot.run(TOKEN)