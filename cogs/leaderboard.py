import os
import re
import logging
import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("cog-leaderboard")

# --- Env IDs ---
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
MAZOKU_BOT_ID = int(os.getenv("MAZOKU_BOT_ID", "0"))

# --- Points par rareté (Mazoku emoji IDs) ---
RARITY_POINTS = {
    "1342202221558763571": 1,   # Common
    "1342202219574857788": 3,   # Rare
    "1342202597389373530": 7,   # Super Rare
    "1342202203515125801": 17   # Ultra Rare
}
EMOJI_REGEX = re.compile(r"<a?:\w+:(\d+)>")

def is_admin():
    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)

# --- View avec Select ---
class LeaderboardView(discord.ui.View):
    def __init__(self, bot, guild):
        super().__init__(timeout=120)
        self.bot = bot
        self.guild = guild

    @discord.ui.select(
        placeholder="Choose a category",
        options=[
            discord.SelectOption(label="All time", value="leaderboard"),
            discord.SelectOption(label="Monthly", value="activity:monthly"),
            discord.SelectOption(label="AutoSummon", value="activity:autosummon"),
            discord.SelectOption(label="Summon", value="activity:summon"),
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        key = select.values[0]
        embed = await self.build_leaderboard(key, interaction.guild, interaction.user)
        await interaction.response.edit_message(embed=embed, view=self)

    async def build_leaderboard(self, key: str, guild: discord.Guild, user: discord.Member):
        if not getattr(self.bot, "redis", None):
            return discord.Embed(
                title=f"🏆 Leaderboard",
                description="❌ Redis not connected.",
                color=discord.Color.red()
            )

        data = await self.bot.redis.hgetall(key)
        if not data:
            return discord.Embed(
                title=f"🏆 Leaderboard",
                description="Empty",
                color=discord.Color.gold()
            )

        sorted_data = sorted(data.items(), key=lambda x: int(x[1]), reverse=True)[:10]
        lines = []
        for i, (uid, score) in enumerate(sorted_data, start=1):
            member = guild.get_member(int(uid))
            mention = member.mention if member else f"<@{uid}>"
            lines.append(f"**{i}.** {mention} — {score} pts")

        embed = discord.Embed(
            title=f"🏆 Leaderboard",
            description="\n".join(lines) if lines else "No entries yet.",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Requested by {user.display_name}")
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        return embed


class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.paused = {
            "all": False,
            "monthly": False,
            "autosummon": False,
            "summon": False,
        }
        log.info("⚙️ Leaderboard cog loaded with GUILD_ID=%s, MAZOKU_BOT_ID=%s", GUILD_ID, MAZOKU_BOT_ID)

    # --- Commande principale ---
    @app_commands.command(name="leaderboard", description="View the leaderboard")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    @app_commands.checks.cooldown(1, 120.0, key=lambda i: (i.user.id))
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        view = LeaderboardView(self.bot, interaction.guild)
        embed = await view.build_leaderboard("leaderboard", interaction.guild, interaction.user)
        await interaction.followup.send(embed=embed, view=view, ephemeral=False)

    # --- Listener : détection des claims et attribution de points ---
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.author.id != MAZOKU_BOT_ID:
            return
        if not after.guild or after.guild.id != GUILD_ID:
            return
        if not after.embeds:
            return

        embed = after.embeds[0]
        title = (embed.title or "").lower()
        if any(x in title for x in ["card claimed", "auto summon claimed", "summon claimed"]):
            # Trouver le joueur
            match = re.search(r"<@!?(\d+)>", embed.description or "")
            if not match:
                return
            user_id = int(match.group(1))
            member = after.guild.get_member(user_id)
            if not member or not getattr(self.bot, "redis", None):
                return

            # Anti-double comptage
            claim_key = f"claim:{after.id}:{user_id}"
            if await self.bot.redis.get(claim_key):
                return
            await self.bot.redis.set(claim_key, "1", ex=86400)

            # Détection de rareté
            rarity_points = 0
            text_to_scan = [embed.title or "", embed.description or ""]
            if embed.fields:
                for field in embed.fields:
                    text_to_scan.append(field.name or "")
                    text_to_scan.append(field.value or "")
            if embed.footer and embed.footer.text:
                text_to_scan.append(embed.footer.text)

            for text in text_to_scan:
                matches = EMOJI_REGEX.findall(text)
                for emote_id in matches:
                    if emote_id in RARITY_POINTS:
                        rarity_points = RARITY_POINTS[emote_id]
                        break
                if rarity_points:
                    break

            if rarity_points:
                await self.bot.redis.hincrby("leaderboard", str(user_id), rarity_points)
                await self.bot.redis.hincrby("activity:monthly", str(user_id), rarity_points)
                log.info("🏅 %s gained +%s points (%s)", member.display_name, rarity_points, embed.title)


# --- Extension setup ---
async def setup(bot: commands.Bot):
    await bot.add_cog(Leaderboard(bot))
