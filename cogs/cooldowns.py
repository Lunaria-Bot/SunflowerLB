import os
import re
import asyncio
import datetime
import discord
from discord import app_commands
from discord.ext import commands

# --- IDs (mets-les dans .env si tu veux les rendre dynamiques) ---
GUILD_ID = int(os.getenv("GUILD_ID", "1196690004852883507"))
MAZOKU_BOT_ID = int(os.getenv("MAZOKU_BOT_ID", "1242388858897956906"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "1420095365494866001"))
ROLE_ID_E = int(os.getenv("ROLE_ID_E", "1420099864548868167"))
ROLE_ID_SUNFLOWER = int(os.getenv("ROLE_ID_SUNFLOWER", "1298320344037462177"))
CONTACT_ID = int(os.getenv("CONTACT_ID", "801879772421423115"))

# --- Daily reminder time (UTC) ---
# Optionnel: DAILY_REMINDER_HHMM="12:00" ou DAILY_REMINDER_UNIX="1758844801"
DAILY_REMINDER_HHMM = os.getenv("DAILY_REMINDER_HHMM", "12:00")
DAILY_REMINDER_UNIX = os.getenv("DAILY_REMINDER_UNIX", "")

# --- Emojis & Regex ---
ELAINA_YAY = "<:ElainaYay:1336678776771186753>"
EMOJI_REGEX = re.compile(r"<a?:\w+:(\d+)>")

# --- Cooldowns ---
COOLDOWN_SECONDS = {
    "summon": 1800,
    "open-boxes": 60,
    "open-pack": 60,
    "vote": 43200  # 12h
}

# --- Utility ---
async def safe_send(channel: discord.TextChannel, *args, **kwargs):
    try:
        return await channel.send(*args, **kwargs)
    except Exception:
        pass


class Cooldowns(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._daily_task = None

    # ----------------
    # Slash commands
    # ----------------
    @app_commands.command(name="cooldowns", description="Check your active cooldowns")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def cooldowns_cmd(self, interaction: discord.Interaction):
        if not getattr(self.bot, "redis", None):
            await interaction.response.send_message("❌ Redis not connected!", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        embed = discord.Embed(
            title="🌻 MoonQuill reminds you:",
            description="Here are your remaining cooldowns before you can play again!",
            color=discord.Color.from_rgb(255, 204, 0)
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)

        found = False
        for cmd in COOLDOWN_SECONDS.keys():
            key = f"cooldown:{user_id}:{cmd}"
            ttl = await self.bot.redis.ttl(key)
            if ttl > 0:
                mins, secs = divmod(ttl, 60)
                embed.add_field(name=f"/{cmd}", value=f"⏱️ {mins}m {secs}s left", inline=False)
                found = True

        if not found:
            embed.description = "✅ No active cooldowns, enjoy the sunshine ☀️"
            embed.color = discord.Color.green()

        embed.set_footer(text="Like a sunflower, always turn towards the light 🌞")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="force-clear", description="Reset a player's cooldowns (ADMIN only)")
    @app_commands.describe(member="The member whose cooldowns you want to reset", command="Optional: the command name to reset")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def force_clear(self, interaction: discord.Interaction, member: discord.Member, command: str = None):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You must be an administrator.", ephemeral=True)
            return
        if not getattr(self.bot, "redis", None):
            await interaction.response.send_message("❌ Redis not connected.", ephemeral=True)
            return

        user_id = str(member.id)
        deleted = 0
        if command:
            if command not in COOLDOWN_SECONDS:
                await interaction.response.send_message(f"⚠️ Unknown command: `{command}`", ephemeral=True)
                return
            key = f"cooldown:{user_id}:{command}"
            deleted = await self.bot.redis.delete(key)
        else:
            for cmd in COOLDOWN_SECONDS.keys():
                key = f"cooldown:{user_id}:{cmd}"
                deleted += await self.bot.redis.delete(key)

        await interaction.response.send_message(
            f"✅ Cooldowns reset for {member.mention} ({deleted} removed).",
            ephemeral=True
        )

    @app_commands.command(name="toggle-reminder", description="Enable or disable reminders for a specific command")
    @app_commands.describe(command="The command to toggle reminders for")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def toggle_reminder(self, interaction: discord.Interaction, command: str):
        if not getattr(self.bot, "redis", None):
            await interaction.response.send_message("❌ Redis not connected!", ephemeral=True)
            return
        if command not in COOLDOWN_SECONDS:
            await interaction.response.send_message(f"⚠️ Unknown command: `{command}`", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        key = f"reminder:{user_id}:{command}"
        current = await self.bot.redis.get(key)
        if current == "off":
            await self.bot.redis.set(key, "on")
            status = "✅ Reminders enabled"
        else:
            await self.bot.redis.set(key, "off")
            status = "❌ Reminders disabled"

        embed = discord.Embed(
            title="🔔 Reminder preference updated",
            description=f"For **/{command}**: {status}",
            color=discord.Color.from_rgb(255, 204, 0)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="togglereminder-daily", description="Toggle your daily Mazoku reminder")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def toggle_reminder_daily(self, interaction: discord.Interaction):
        if not getattr(self.bot, "redis", None):
            await interaction.response.send_message("❌ Redis not connected!", ephemeral=True)
            return

        user_id = str(interaction.user.id)
        key = f"dailyreminder:{user_id}"
        current = await self.bot.redis.get(key)

        if current == "on":
            await self.bot.redis.set(key, "off")
            status = "❌ Daily reminder disabled"
        else:
            await self.bot.redis.set(key, "on")
            status = "✅ Daily reminder enabled"

        embed = discord.Embed(
            title="🔔 Daily Reminder Preference Updated",
            description=status,
            color=discord.Color.from_rgb(255, 204, 0)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Optional: role assignment like your original "flower" command
    @app_commands.command(name="flower", description="Get the special flower role if you are part of Sunflower")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def flower(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        sunflower_role = guild.get_role(ROLE_ID_SUNFLOWER)
        special_role = guild.get_role(ROLE_ID_E)

        if sunflower_role in member.roles:
            if special_role not in member.roles:
                await member.add_roles(special_role)
                await interaction.response.send_message(
                    f"🌻 {member.mention}, you have received the role **{special_role.name}**!",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"✅ You already have the role **{special_role.name}**.",
                    ephemeral=True
                )
        else:
            await interaction.response.send_message(
                f"❌ You are not part of Sunflower but you can always join us, "
                f"contact <@{CONTACT_ID}> to join us !",
                ephemeral=True
            )

    # ----------------
    # Listener: on_message
    # ----------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not getattr(self.bot, "redis", None):
            return
        if message.author.id == self.bot.user.id:
            return
        if message.guild and message.guild.id != GUILD_ID:
            return
        if not (message.author.bot and message.author.id == MAZOKU_BOT_ID):
            return

        user = None
        cmd = None

        # Parse embeds Mazoku
        if message.embeds:
            embed = message.embeds[0]
            title = (embed.title or "").lower()
            desc = embed.description or ""

            if "summon claimed" in title:
                cmd = "summon"
                match = re.search(r"Claimed By\s+<@!?(\d+)>", desc)
                if match:
                    user = message.guild.get_member(int(match.group(1)))

            elif "pack opened" in title:
                cmd = "open-pack"
                user = message.author

            elif "box opened" in title:
                cmd = "open-boxes"
                user = message.author

            elif "vote mazoku" in title:
                cmd = "vote"
                user = message.author

        # ----------------
        # Apply cooldowns
        # ----------------
        if user and cmd in COOLDOWN_SECONDS:
            user_id = str(user.id)
            key = f"cooldown:{user_id}:{cmd}"

            ttl = await self.bot.redis.ttl(key)
            if ttl > 0:
                await safe_send(
                    message.channel,
                    content=f"{user.mention}",
                    embed=discord.Embed(description=f"⏳ You are still on cooldown for `/{cmd}` ({ttl}s left)!")
                )
                return

            cd_time = COOLDOWN_SECONDS[cmd]
            await self.bot.redis.setex(key, cd_time, "1")

            log_channel = message.guild.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                await safe_send(
                    log_channel,
                    embed=discord.Embed(
                        title="📌 Cooldown started",
                        description=f"For {user.mention} → `/{cmd}` ({cd_time}s)",
                        color=discord.Color.blue(),
                        timestamp=datetime.datetime.now(datetime.timezone.utc)
                    )
                )

            async def cooldown_task():
                await asyncio.sleep(cd_time)
                try:
                    reminder_key = f"reminder:{user.id}:{cmd}"
                    reminder_status = await self.bot.redis.get(reminder_key)

                    if reminder_status != "off":
                        if cmd == "vote":
                            end_embed = discord.Embed(
                                title="🗳️ Vote reminder!",
                                description=(
                                    f"Your **/{cmd}** cooldown is over.\n\n"
                                    f"{ELAINA_YAY} You can support Mazoku again on top.gg!"
                                ),
                                color=discord.Color.from_rgb(255, 204, 0)
                            )
                        else:
                            end_embed = discord.Embed(
                                title="🌞 Cooldown finished!",
                                description=(
                                    f"Your **/{cmd}** is available again.\n\n"
                                    f"{ELAINA_YAY} Enjoy this new light\n"
                                    "✨ MoonQuill is watching over you"
                                ),
                                color=discord.Color.from_rgb(255, 204, 0)
                            )
                            end_embed.set_footer(text="MoonQuill is watching over you ✨")

                        await safe_send(message.channel, content=f"{user.mention}", embed=end_embed)

                        if log_channel:
                            await safe_send(
                                log_channel,
                                embed=discord.Embed(
                                    title="📩 Reminder sent",
                                    description=f"Reminder for `{cmd}` sent to {user.mention} (ID: `{user.id}`)",
                                    color=discord.Color.green(),
                                    timestamp=datetime.datetime.now(datetime.timezone.utc)
                                )
                            )
                except Exception:
                    pass

            asyncio.create_task(cooldown_task())

    # ----------------
    # Daily reminder background task
    # ----------------
    async def daily_reminder_task(self):
        await self.bot.wait_until_ready()

        # Determine target time (UTC)
        if DAILY_REMINDER_UNIX:
            target_time = datetime.datetime.utcfromtimestamp(int(DAILY_REMINDER_UNIX)).time()
        else:
            hh, mm = DAILY_REMINDER_HHMM.split(":")
            target_time = datetime.time(hour=int(hh), minute=int(mm), tzinfo=datetime.timezone.utc)

        while not self.bot.is_closed():
            now = datetime.datetime.now(datetime.timezone.utc)
            today_target = now.replace(
                hour=target_time.hour,
                minute=target_time.minute,
                second=0,
                microsecond=0
            )
            if now >= today_target:
                today_target += datetime.timedelta(days=1)
            wait_seconds = (today_target - now).total_seconds()
            await asyncio.sleep(wait_seconds)

            # Send reminders to all opted-in users (stored in Redis)
            try:
                keys = await self.bot.redis.keys("dailyreminder:*")
            except Exception:
                keys = []

            for key in keys:
                try:
                    val = await self.bot.redis.get(key)
                    if val != "on":
                        continue

                    user_id = int(key.split(":")[1])
                    user = self.bot.get_user(user_id)
                    if not user:
                        continue

                    # Send DM
                    try:
                        await user.send("🌻 Your Mazoku daily is ready!")
                    except Exception:
                        continue

                    # Styled log embed in the log channel
                    log_channel = self.bot.get_channel(LOG_CHANNEL_ID)
                    if log_channel:
                        embed = discord.Embed(
                            title="📩 Daily reminder sent",
                            description=f"Sent to <@{user.id}> (ID: `{user.id}`)",
                            color=discord.Color.from_rgb(255, 204, 0),
                            timestamp=datetime.datetime.now(datetime.timezone.utc)
                        )
                        embed.set_footer(text="MoonQuill daily scheduler")
                        await safe_send(log_channel, embed=embed)
                except Exception:
                    continue

    # ----------------
    # Cog lifecycle
    # ----------------
    async def cog_load(self):
        # Start the daily reminder task when the cog is loaded
        self._daily_task = self.bot.loop.create_task(self.daily_reminder_task())

    async def cog_unload(self):
        # Cancel background task on unload
        if self._daily_task:
            self._daily_task.cancel()
            self._daily_task = None


# --- Extension setup ---
async def setup(bot: commands.Bot):
    await bot.add_cog(Cooldowns(bot))
