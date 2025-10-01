import time
import logging
import discord
from discord.ext import commands
from discord import app_commands

log = logging.getLogger("cog-error-handler")

class ErrorHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        # Handle cooldown errors
        if isinstance(error, app_commands.CommandOnCooldown):
            retry_timestamp = int(time.time() + error.retry_after)
            try:
                await interaction.response.send_message(
                    f"⏳ You are on cooldown for this command. Try again <t:{retry_timestamp}:R>.",
                    ephemeral=True
                )
            except discord.InteractionResponded:
                # If already responded, send a followup
                await interaction.followup.send(
                    f"⏳ You are on cooldown for this command. Try again <t:{retry_timestamp}:R>.",
                    ephemeral=True
                )
            return

        # Handle missing permissions
        if isinstance(error, app_commands.MissingPermissions):
            try:
                await interaction.response.send_message(
                    "❌ You do not have permission to use this command.",
                    ephemeral=True
                )
            except discord.InteractionResponded:
                await interaction.followup.send(
                    "❌ You do not have permission to use this command.",
                    ephemeral=True
                )
            return

        # Log and notify for unexpected errors
        log.error("Unhandled app command error: %s", error, exc_info=True)
        try:
            await interaction.response.send_message(
                "⚠️ An unexpected error occurred while executing this command.",
                ephemeral=True
            )
        except discord.InteractionResponded:
            await interaction.followup.send(
                "⚠️ An unexpected error occurred while executing this command.",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))
error_handler.py
