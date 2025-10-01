import os
import logging
import discord
from discord.ext import commands
import redis.asyncio as aioredis
import asyncio
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True
)
log = logging.getLogger("main-bot")

# --- Environment variables ---
TOKEN = os.getenv("DISCORD_TOKEN")
REDIS_URL = os.getenv("REDIS_URL")

# --- Intents ---
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.members = True

# --- Bot instance ---
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Redis connection ---
async def init_redis():
    try:
        bot.redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
        await bot.redis.ping()
        log.info("✅ Redis connected")
    except Exception as e:
        log.error("❌ Redis connection failed: %s", e)
        bot.redis = None

# --- Events ---
@bot.event
async def on_ready():
    log.info("🤖 Logged in as %s (%s)", bot.user, bot.user.id)

# --- Main entry ---
async def main():
    async with bot:
        # Init Redis
        await init_redis()

        # Charger les Cogs
        await bot.load_extension("cogs.leaderboard")
        await bot.load_extension("cogs.cooldowns")
        await bot.load_extension("cogs.leaderboard_admin")

        # Démarrer le bot
        await bot.start(TOKEN)

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("❌ DISCORD_TOKEN is missing from environment variables.")
    if not REDIS_URL:
        raise RuntimeError("❌ REDIS_URL is missing from environment variables.")
    asyncio.run(main())
