import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
import db
from discord import app_commands


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if TOKEN is None:
    raise SystemExit("DISCORD_TOKEN is missing from .env")

GUILD_ID = os.getenv("GUILD_ID")
if GUILD_ID is None:
    raise SystemExit("GUILD_ID is missing from .env")

TEST_GUILD = discord.Object(id=int(GUILD_ID))



ANNOUNCE_CHANNEL_ID = os.getenv("ANNOUNCE_CHANNEL_ID")
if ANNOUNCE_CHANNEL_ID is None:
    raise SystemExit("ANNOUNCE_CHANNEL_ID is missing from .env")
ANNOUNCE_CHANNEL_ID = int(ANNOUNCE_CHANNEL_ID)

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
    db.init_db()
    db.load_projects()
    await bot.tree.sync(guild=TEST_GUILD)


@bot.tree.command(name="announce-round", description="Draw a project and announce the next round", guild=TEST_GUILD)
@app_commands.default_permissions(administrator=True)
async def announce_round(interaction: discord.Interaction):
    project = db.draw_project()
    if project is None:
        await interaction.response.send_message("All projects have been used!", ephemeral=True)
        return

    channel = bot.get_channel(ANNOUNCE_CHANNEL_ID)
    embed = discord.Embed(
        title=f"Next round: {project['name']}",
        description=project["description"],
    )
    embed.add_field(name="Skills", value=project["skills"])
    embed.set_footer(text="React ✅ to join, ❌ to sit this one out")

    message = await channel.send(embed=embed)
    await message.add_reaction("✅")
    await message.add_reaction("❌")
    db.create_round(project["id"], message.id)
    await interaction.response.send_message("Announced!", ephemeral=True)


bot.run(TOKEN)