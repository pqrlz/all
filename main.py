import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import math
from discord.ui import Button, View
import datetime
import os
from keep_alive import keep_alive

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.reactions = True
bot = commands.Bot(command_prefix="!", intents=intents)

config = {
    "channel_id": None,
    "reaction_emoji": None,
    "trigger_phrase": None,
    "correct_mention_id": None,
    "warning_channel_id": None,
    "role_to_remove": None,
    "notify_channel_id": None,
}

sticky_messages = {}
sticky_tracker = {}

@bot.event
async def on_ready():
    print(f"✅ logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ synced {len(synced)} commands")
    except Exception as e:
        print(f"❌ error syncing commands: {e}")

@bot.tree.command(name="rsetup", description="setup the reaction bot")
@app_commands.describe(
    channel="channel where vouches will be monitored",
    reaction="emoji for correct vouches",
    trigger="trigger phrase (e.g., 'vouch @user for')",
    mention="correct mention id",
    warning_channel="channel for warnings",
    role="role to remove on correct vouch",
    notify_channel="channel to notify when the role is added"
)
async def rsetup(interaction: discord.Interaction, channel: discord.TextChannel, reaction: str, trigger: str, mention: str, warning_channel: discord.TextChannel, role: discord.Role, notify_channel: discord.TextChannel):
    config.update({
        "channel_id": channel.id,
        "reaction_emoji": reaction,
        "trigger_phrase": trigger.lower(),
        "correct_mention_id": mention,
        "warning_channel_id": warning_channel.id,
        "role_to_remove": role.id,
        "notify_channel_id": notify_channel.id
    })
    await interaction.response.send_message("✅ reaction bot setup complete!", ephemeral=True)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await bot.process_commands(message)

    if config["channel_id"] and message.channel.id == config["channel_id"]:
        if config["trigger_phrase"] not in message.content.lower():
            await send_warning(message.author, "wrong vouching format")
            return
        if f"<@{config['correct_mention_id']}>" not in message.content:
            await send_warning(message.author, "wrong vouching format")
            return
        if not message.attachments:
            await send_warning(message.author, "no image attached")
            return

        await message.add_reaction(config["reaction_emoji"])
        role = message.guild.get_role(config["role_to_remove"])
        if role and role not in message.author.roles:
            await message.author.add_roles(role)

            notify_channel = bot.get_channel(config["notify_channel_id"])
            if notify_channel:
                await notify_channel.send(f"✅ role **{role.name}** added to {message.author.mention}.")

            asyncio.create_task(countdown_timer(message.author, role))

    if message.channel.id in sticky_messages:
        try:
            if message.channel.id in sticky_tracker:
                old_msg = await message.channel.fetch_message(sticky_tracker[message.channel.id])
                await old_msg.delete()
        except discord.NotFound:
            pass
        sent_message = await message.channel.send(sticky_messages[message.channel.id])
        sticky_tracker[message.channel.id] = sent_message.id

async def countdown_timer(user, role):
    notify_channel = bot.get_channel(config["notify_channel_id"])
    if not notify_channel:
        return

    start_time = datetime.datetime.now()

    while True:
        await asyncio.sleep(60)
        elapsed_time = datetime.datetime.now() - start_time
        remaining_time = datetime.timedelta(seconds=86400) - elapsed_time

        if remaining_time.total_seconds() <= 0:
            if role in user.roles:
                await notify_channel.send(
                    f"⚠️ 24 hours passed and {user.mention} still has the role **{role.name}**."
                )
                await send_role_removal_button(user, role)
            break

        if role not in user.roles:
            break

async def send_role_removal_button(user, role):
    button = Button(label="remove role", style=discord.ButtonStyle.danger)

    async def button_callback(interaction: discord.Interaction):
        if interaction.user == user:
            await user.remove_roles(role)
            await interaction.response.send_message(f"✅ removed **{role.name}** from {user.mention}", ephemeral=True)
            await send_warning(user, "24 hours no vouch", penalty="warranty voided")
        else:
            await interaction.response.send_message("❌ you are not allowed to press this.", ephemeral=True)

    button.callback = button_callback
    view = View(timeout=None)
    view.add_item(button)
    warning_channel = bot.get_channel(config["warning_channel_id"])
    if warning_channel:
        await warning_channel.send(
            f"⚠️ click the button below to remove **{role.name}** from {user.mention} and issue a warning.", view=view
        )

async def send_warning(user, reason, penalty="warning"):
    warning_channel = bot.get_channel(config["warning_channel_id"])
    if warning_channel:
        await warning_channel.send(
            f"<a:emoji_24:1347809978039402536> <a:loading:1355816574409248769> **oh no, looks like you didn't follow the rules** ***!***\n\n"
            f"<:r_arrowright01:1346236422729765085> **offender** : {user.mention}\n"
            f"<:r_arrowright01:1346236422729765085> **penalty** : {penalty}\n"
            f"<:r_arrowright01:1346236422729765085> **reason** : {reason}"
        )

@bot.tree.command(name="calcu", description="perform basic arithmetic calculations")
@app_commands.describe(expression="mathematical expression to calculate (e.g., 5+3*2)")
async def calcu(interaction: discord.Interaction, expression: str):
    expression = expression.replace('x', '*').replace('÷', '/')
    try:
        result = eval(expression, {"__builtins__": None}, {})
        await interaction.response.send_message(f"<:r_arrowright01:1346236422729765085> the answer is: `{result}`")
    except Exception:
        await interaction.response.send_message("❌ invalid mathematical expression!", ephemeral=True)

@bot.tree.command(name="tax", description="calculate the gamepass amount by reversing a 30% deduction.")
async def tax(interaction: discord.Interaction, robux: float):
    result = math.ceil(robux / 0.7)
    if result < robux:
        result += 1
    await interaction.response.send_message(f"<:r_arrowright01:1346236422729765085> gamepass amount would be: `{result}`")

@bot.tree.command(name="note", description="set a sticky message in a channel")
async def note(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    sticky_messages[channel.id] = message
    sent_message = await channel.send(message)
    sticky_tracker[channel.id] = sent_message.id
    await interaction.response.send_message(f"sticky message set for {channel.mention}", ephemeral=True)

@bot.tree.command(name="unnote", description="remove the sticky message from a channel")
async def unnote(interaction: discord.Interaction, channel: discord.TextChannel):
    if channel.id in sticky_messages:
        del sticky_messages[channel.id]
        if channel.id in sticky_tracker:
            try:
                msg = await channel.fetch_message(sticky_tracker[channel.id])
                await msg.delete()
            except discord.NotFound:
                pass
            del sticky_tracker[channel.id]
        await interaction.response.send_message(f"sticky message removed from {channel.mention}", ephemeral=True)
    else:
        await interaction.response.send_message(f"no sticky message set for {channel.mention}", ephemeral=True)

keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))
