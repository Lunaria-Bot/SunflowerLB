import os
import logging
import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("cog-leaderboard-admin")

GUILD_ID = int(os.getenv("GUILD_ID", "0"))

def is_admin():
    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.administrator
    return app_commands.check(predicate)


class LeaderboardAdmin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- Reset leaderboard ---
    @app_commands.command(name="lb-reset", description="Reset leaderboard scores (admin)")
    @app_commands.guilds(discord.Object(id=GUILD_ID))  # ✅ sync immédiat sur ton serveur
    @app_commands.choices(
        category=[
            app_commands.Choice(name="All", value="leaderboard"),
            app_commands.Choice(name="Monthly", value="activity:monthly"),
            app_commands.Choice(name="Everything", value="all_keys"),
        ]
    )
    @is_admin()
    async def lb_reset(self, interaction: discord.Interaction, category: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        if not getattr(self.bot, "redis", None):
            await interaction.followup.send("❌ Redis not connected.", ephemeral=True)
            return

        if category.value == "all_keys":
            for key in ["leaderboard", "activity:monthly", "activity:monthly:total"]:
                await self.bot.redis.delete(key)
            msg = "🧹 All scores have been reset."
        else:
            await self.bot.redis.delete(category.value)
            msg = f"🧹 Category `{category.value}` has been reset."

        await interaction.followup.send(msg, ephemeral=True)

    # --- Pause / Resume leaderboard ---
    @app_commands.command(name="lb-pause", description="Pause or resume leaderboard counting (admin)")
    @app_commands.guilds(discord.Object(id=GUILD_ID))  # ✅ sync immédiat sur ton serveur
    @app_commands.choices(
        category=[
            app_commands.Choice(name="All", value="all"),
            app_commands.Choice(name="Monthly", value="monthly"),
        ],
        state=[
            app_commands.Choice(name="Pause", value="pause"),
            app_commands.Choice(name="Resume", value="resume"),
        ]
    )
    @is_admin()
    async def lb_pause(
        self,
        interaction: discord.Interaction,
        category: app_commands.Choice[str],
        state: app_commands.Choice[str]
    ):
        await interaction.response.defer(ephemeral=True)

        key = f"lb:paused:{category.value}"
        if state.value == "pause":
            await self.bot.redis.set(key, "1")
            status = "paused"
        else:
            await self.bot.redis.delete(key)
            status = "resumed"

        log.info("Leaderboard %s → %s", category.value, status)
        await interaction.followup.send(f"⏸️ `{category.value}` → {status}.", ephemeral=True)


# --- Extension setup ---
async def setup(bot: commands.Bot):
    await bot.add_cog(LeaderboardAdmin(bot))
