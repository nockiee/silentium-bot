import os
from dotenv import load_dotenv

load_dotenv()

def get_list(var: str) -> list[int]:
    value = os.getenv(var, "")
    return [int(x) for x in value.split(",") if x]

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
ADMIN_ROLES = get_list("ADMIN_ROLES")
USER_ROLES = get_list("USER_ROLES")
ANNOUNCEMENT_CHANNEL = int(os.getenv("ANNOUNCEMENT_CHANNEL", "0"))
POST_CHANNEL = int(os.getenv("POST_CHANNEL", "0"))
DELATION_CHANNEL = int(os.getenv("DELATION_CHANNEL", "0"))
IMAGE_UPLOAD_CHANNEL = int(os.getenv("IMAGE_UPLOAD_CHANNEL", "0"))
MINECRAFT_SERVER = os.getenv("MINECRAFT_SERVER", "localhost:25565")
FINE_ROLES = get_list("FINE_ROLES")
FINE_CHANNEL = int(os.getenv("FINE_CHANNEL", "0"))
TELEGRAM_BOT_TOKEN = "7536161468:AAEV74tO7PfBLSlrDfVSwfg958W_ZZ6oMeQ"