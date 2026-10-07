import os
from dotenv import load_dotenv
import discord
from discord.ext import commands
import db
import pairing
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

CHALLENGER_ROLE = "Challenger"
OPTED_IN_ROLE = "opted-in"
OPTED_OUT_ROLE = "opted-out"
YES_EMOJI = "✅"
NO_EMOJI = "❌"
TEAMS_CHANNEL_NAME = "teams"  # channel where the teams get posted

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
    # Posting, saving and clearing roles can take longer than the 3 seconds
    # Discord allows for a reply, so we "defer" and answer later with followup.send().
    await interaction.response.defer(ephemeral=True)

    # Pick a random unused project. This does NOT mark it as used yet.
    project = db.draw_project()
    if project is None:
        await interaction.followup.send("All projects have been used!")
        return

    channel = bot.get_channel(ANNOUNCE_CHANNEL_ID)
    if channel is None:
        await interaction.followup.send("I can't find the announcements channel. Check ANNOUNCE_CHANNEL_ID in .env.")
        return

    embed = discord.Embed(
        title=f"Next round: {project['name']}",
        description=project["description"],
    )
    embed.add_field(name="Skills", value=project["skills"])
    embed.set_footer(text="React \u2705 to join, \u274c to sit this one out")

    # Post the announcement. If this fails, nothing in the database has changed yet,
    # so no project is wasted and you can simply run the command again.
    try:
        message = await channel.send(embed=embed)
    except discord.Forbidden:
        await interaction.followup.send("I'm not allowed to post in the announcements channel. Check my permissions there.")
        return

    # The announcement is out, so now (and only now) update the database:
    #  1. close any older round that was still open, so reactions on the old
    #     announcement stop giving out roles
    #  2. save this round (we need its message id to recognise reactions later)
    #  3. mark the project as used so it can't be drawn again
    db.close_all_open_rounds()
    db.create_round(project["id"], message.id)
    db.mark_project_used(project["id"])

    # Clear leftover opted-in/opted-out roles from the previous round, so nobody
    # starts this round already opted in. We do this BEFORE adding the starter
    # reactions, so nobody can click a reaction and then have their role wiped.
    roles_note = ""
    try:
        cleared = await clear_opt_roles(interaction.guild)
        if cleared is None:
            roles_note = " The opted-in/opted-out roles are missing, so I couldn't clear them."
        else:
            roles_note = f" Cleared old roles from {cleared} members."
    except discord.Forbidden:
        roles_note = " I couldn't clear the old opted-in/opted-out roles. Check that my role is above them."

    # Add the starter reactions people can click
    try:
        await message.add_reaction(YES_EMOJI)
        await message.add_reaction(NO_EMOJI)
    except discord.Forbidden:
        roles_note += " I couldn't add the reactions. Check I have Add Reactions in the announcements channel."

    await interaction.followup.send("Announced!" + roles_note)


def get_opt_roles(guild):
    """Return (opted_in_role, opted_out_role), or (None, None) if either is missing."""
    opted_in = discord.utils.get(guild.roles, name=OPTED_IN_ROLE)
    opted_out = discord.utils.get(guild.roles, name=OPTED_OUT_ROLE)
    if opted_in is None or opted_out is None:
        print(f"Missing role: make sure '{OPTED_IN_ROLE}' and '{OPTED_OUT_ROLE}' exist in the server")
        return None, None
    return opted_in, opted_out


async def clear_opt_roles(guild):
    """Remove opted-in / opted-out from every member who has them.

    Returns how many members were changed, or None if the roles don't exist.
    May raise discord.Forbidden if the bot isn't allowed to change the roles.
    """
    opted_in, opted_out = get_opt_roles(guild)
    if opted_in is None:
        return None

    cleared = 0
    for member in guild.members:
        # Build a list of whichever of the two roles this member has
        roles_to_remove = [role for role in (opted_in, opted_out) if role in member.roles]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)
            cleared += 1
    return cleared


@bot.event
async def on_raw_reaction_add(payload):
    # Ignore bots (including this bot's own starter reactions) and DMs
    if payload.guild_id is None or payload.member is None or payload.member.bot:
        return

    # Only the two opt-in emoji count
    emoji = str(payload.emoji)
    if emoji not in (YES_EMOJI, NO_EMOJI):
        return

    # Only reactions on a saved, still-open announcement count
    if db.get_open_round_by_message(payload.message_id) is None:
        return

    member = payload.member
    guild = bot.get_guild(payload.guild_id)

    # Only Challengers can opt in or out
    if discord.utils.get(member.roles, name=CHALLENGER_ROLE) is None:
        print(f"Ignored {member}: they don't have the {CHALLENGER_ROLE} role")
        return

    opted_in, opted_out = get_opt_roles(guild)
    if opted_in is None:
        return

    # Give the role for the emoji they clicked, and take away the other one (swap)
    if emoji == YES_EMOJI:
        add_role, remove_role = opted_in, opted_out
    else:
        add_role, remove_role = opted_out, opted_in

    try:
        await member.add_roles(add_role)
        if remove_role in member.roles:
            await member.remove_roles(remove_role)
        print(f"{member} -> {add_role.name}")
    except discord.Forbidden:
        print("Can't change roles: move the bot's role above opted-in and opted-out, and give it Manage Roles")

    # Take back their other reaction so only one choice shows on the post
    other_emoji = NO_EMOJI if emoji == YES_EMOJI else YES_EMOJI
    channel = guild.get_channel(payload.channel_id)
    if channel is not None:
        try:
            await channel.get_partial_message(payload.message_id).remove_reaction(other_emoji, member)
        except discord.NotFound:
            pass  # they hadn't clicked the other emoji, nothing to remove
        except discord.Forbidden:
            print("Can't remove the other reaction: give the bot Manage Messages in the announcements channel")


@bot.event
async def on_raw_reaction_remove(payload):
    if payload.guild_id is None:
        return

    emoji = str(payload.emoji)
    if emoji not in (YES_EMOJI, NO_EMOJI):
        return

    if db.get_open_round_by_message(payload.message_id) is None:
        return

    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id)  # remove events don't include the member
    if member is None or member.bot:
        return

    opted_in, opted_out = get_opt_roles(guild)
    if opted_in is None:
        return

    # Taking back a reaction removes the matching role
    role = opted_in if emoji == YES_EMOJI else opted_out
    try:
        if role in member.roles:
            await member.remove_roles(role)
            print(f"{member} removed {role.name}")
    except discord.Forbidden:
        print("Can't change roles: move the bot's role above opted-in and opted-out, and give it Manage Roles")


@bot.tree.command(name="close-optin", description="Close sign-ups, then pair everyone who opted in", guild=TEST_GUILD)
@app_commands.default_permissions(administrator=True)
async def close_optin(interaction: discord.Interaction):
    # Changing lots of roles can take longer than the 3 seconds Discord gives us
    # to reply. "Deferring" tells Discord "I'm working on it", and we send the
    # real answer afterwards with interaction.followup.send().
    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild

    # Find the announcement that is currently open for sign-ups
    current_round = db.get_latest_open_round()
    if current_round is None:
        await interaction.followup.send("There's no open round to close. Run /announce-round first.")
        return

    # Look up everything we need BEFORE changing anything, so a missing
    # role or channel can't leave us with a half-finished round.
    challenger_role = discord.utils.get(guild.roles, name=CHALLENGER_ROLE)
    opted_in_role, opted_out_role = get_opt_roles(guild)
    teams_channel = discord.utils.get(guild.text_channels, name=TEAMS_CHANNEL_NAME)
    if challenger_role is None or opted_in_role is None:
        await interaction.followup.send("A required role is missing. Check the bot's terminal for details.")
        return
    if teams_channel is None:
        await interaction.followup.send(f"I can't find a #{TEAMS_CHANNEL_NAME} channel.")
        return

    # Sort every Challenger into two groups:
    #   opted_in_members    = reacted with the checkmark
    #   no_response_members = haven't reacted at all (these become opted-out)
    opted_in_members = []
    no_response_members = []
    for member in guild.members:
        if member.bot or challenger_role not in member.roles:
            continue  # skip bots and anyone who isn't part of the challenge
        if opted_in_role in member.roles:
            opted_in_members.append(member)
        elif opted_out_role not in member.roles:
            no_response_members.append(member)

    # Need at least 2 people to make a team. If not, change nothing and leave
    # sign-ups open so more people can still opt in.
    if len(opted_in_members) < 2:
        await interaction.followup.send(
            f"Only {len(opted_in_members)} opted in so far and I need at least 2. Sign-ups are still open."
        )
        return

    try:
        # Step 5: everyone who didn't respond becomes opted-out
        for member in no_response_members:
            await member.add_roles(opted_out_role)

        # Close the round, so reactions added after this point are ignored
        db.close_round(current_round["id"])

        # Step 6: shuffle the opted-in people into teams (see pairing.py)
        teams = pairing.make_pairs(opted_in_members)

        # Save who is on which team (stored as Discord user ids)
        db.save_teams(current_round["id"], [[m.id for m in team] for team in teams])

        # Step 7: post the teams. member.mention pings the person.
        project = db.get_project(current_round["project_id"])
        lines = [f"**Teams for {project['name']}**"]
        for team_number, team in enumerate(teams, start=1):
            names = " & ".join(m.mention for m in team)
            lines.append(f"**Team {team_number}:** {names}")
        await teams_channel.send("\n".join(lines))

    except discord.Forbidden:
        await interaction.followup.send(
            "I don't have permission to do that. Check that my role is above opted-in/opted-out "
            f"and that I can send messages in #{TEAMS_CHANNEL_NAME}."
        )
        return

    await interaction.followup.send(
        f"Done! {len(opted_in_members)} people paired into {len(teams)} teams, "
        f"{len(no_response_members)} marked as opted-out."
    )


@bot.tree.command(name="reset-round", description="Clear the opted-in/opted-out roles to get ready for the next round", guild=TEST_GUILD)
@app_commands.default_permissions(administrator=True)
async def reset_round(interaction: discord.Interaction):
    # Defer again: removing roles from many members can take a few seconds
    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    opted_in_role, opted_out_role = get_opt_roles(guild)
    if opted_in_role is None:
        await interaction.followup.send("A required role is missing. Check the bot's terminal for details.")
        return

    try:
        cleared = await clear_opt_roles(guild)
    except discord.Forbidden:
        await interaction.followup.send("I don't have permission to remove those roles. Check my role is above them.")
        return

    # Close any round that's still open so its announcement stops counting
    db.close_all_open_rounds()

    await interaction.followup.send(f"Reset! Cleared roles from {cleared} members. Ready for the next round.")


@bot.tree.command(name="projects", description="Show every project and whether it's been used", guild=TEST_GUILD)
@app_commands.default_permissions(administrator=True)
async def projects(interaction: discord.Interaction):
    all_projects = db.list_projects()
    available = [p for p in all_projects if p["used"] == 0]

    # One line per project. Used ones get a "(used)" tag.
    lines = []
    for p in all_projects:
        tag = " *(used)*" if p["used"] == 1 else ""
        lines.append(f"**{p['name']}**{tag} - {p['skills']}")

    # Embed descriptions are limited to 4096 characters, so cut if we ever go over
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n..."

    embed = discord.Embed(
        title=f"Projects: {len(available)} available / {len(all_projects)} total",
        description=text or "No projects yet. Add one with /add-project.",
    )
    # ephemeral = only you can see the reply
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="add-project", description="Add a new project to the list", guild=TEST_GUILD)
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
    name="Project name",
    description="One-line description of what people build",
    skills="Skills used, for example: JS, SQL",
)
async def add_project(interaction: discord.Interaction, name: str, description: str, skills: str = ""):
    # db.add_project returns False if a project with that name already exists
    added = db.add_project(name.strip(), description.strip(), skills.strip())
    if added:
        await interaction.response.send_message(f"Added **{name.strip()}**.", ephemeral=True)
    else:
        await interaction.response.send_message(f"There's already a project called **{name.strip()}**.", ephemeral=True)


@bot.tree.command(name="remove-project", description="Remove a project that hasn't been used yet", guild=TEST_GUILD)
@app_commands.default_permissions(administrator=True)
@app_commands.describe(name="The project to remove")
async def remove_project(interaction: discord.Interaction, name: str):
    result = db.remove_project(name.strip())
    if result == "removed":
        await interaction.response.send_message(f"Removed **{name.strip()}**.", ephemeral=True)
    elif result == "used":
        await interaction.response.send_message(
            f"**{name.strip()}** has already been used in a round, so it stays in the history.", ephemeral=True
        )
    else:
        await interaction.response.send_message(f"I couldn't find a project called **{name.strip()}**.", ephemeral=True)


# Autocomplete: as you type in the "name" box of /remove-project, Discord asks
# this function for suggestions. We suggest unused projects that match what you've typed.
@remove_project.autocomplete("name")
async def remove_project_autocomplete(interaction: discord.Interaction, current: str):
    unused_names = [p["name"] for p in db.list_projects() if p["used"] == 0]
    matches = [n for n in unused_names if current.lower() in n.lower()]
    # Discord allows at most 25 suggestions
    return [app_commands.Choice(name=n, value=n) for n in matches[:25]]


bot.run(TOKEN)