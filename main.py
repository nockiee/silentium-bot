import disnake
from disnake.ext import commands, tasks
import aiohttp
from config import *

bot = commands.Bot(
    command_prefix="/",
    intents=disnake.Intents.all(),
    test_guilds=[GUILD_ID]
)

async def get_mc_players(server: str) -> tuple:
    try:
        host, port = server.split(":")
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.mcsrvstat.us/2/{host}:{port}") as resp:
                data = await resp.json()
                if data.get("online"):
                    return True, data["players"]["online"]
                return False, 0
    except:
        return False, 0

@tasks.loop(minutes=5)
async def update_mc_status():
    online, players = await get_mc_players(MINECRAFT_SERVER)
    if online:
        await bot.change_presence(activity=disnake.Game(
            name=f"🟢 {players} игроков онлайн! Присоединяйся!"
        ))
    else:
        await bot.change_presence(activity=disnake.Game(
            name="🔴 Сервер оффлайн"
        ))

@bot.event
async def on_ready():
    print(f"Бот {bot.user} готов к работе!")
    update_mc_status.start()
    
    initial_extensions = [
        "cogs.admin_posts",
        "cogs.user_posts",
        "cogs.delation",
        "cogs.memes",
        "cogs.quotes",
        "cogs.fines"
    ]
    
    for extension in initial_extensions:
        try:
            bot.load_extension(extension)
            print(f"Загружен модуль: {extension}")
        except Exception as e:
            print(f"Ошибка загрузки {extension}: {e}")

if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)