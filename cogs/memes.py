import disnake
from disnake.ext import commands
import os
import random
import logging
from typing import List

logger = logging.getLogger(__name__)

class Memes(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.meme_dir = "memes"
        self._ensure_meme_dir_exists()
        self._supported_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp')

    def _ensure_meme_dir_exists(self) -> None:
        try:
            os.makedirs(self.meme_dir, exist_ok=True)
            logger.info(f"Директория для мемов готова: {self.meme_dir}")
        except OSError as e:
            logger.error(f"Ошибка создания директории для мемов: {e}")
            raise

    def _get_meme_list(self) -> List[str]:
        try:
            return [
                f for f in os.listdir(self.meme_dir)
                if os.path.isfile(os.path.join(self.meme_dir, f)) 
                and f.lower().endswith(self._supported_extensions)
            ]
        except OSError as e:
            logger.error(f"Ошибка чтения директории с мемами: {e}")
            return []

    @commands.slash_command(name="meme", description="Получить случайный мем")
    async def meme(self, inter: disnake.ApplicationCommandInteraction):
        memes = self._get_meme_list()
        
        if not memes:
            logger.warning("Попытка получить мем, но директория пуста")
            await inter.response.send_message(
                "😢 Мемы закончились! Добавьте новые в папку memes/",
                ephemeral=True
            )
            return
        
        try:
            meme_file = random.choice(memes)
            meme_path = os.path.join(self.meme_dir, meme_file)

            if os.path.getsize(meme_path) > 8 * 1024 * 1024:
                await inter.response.send_message(
                    "⚠️ Этот мем слишком большой для отправки (макс. 8MB)",
                    ephemeral=True
                )
                return
                
            await inter.response.send_message(file=disnake.File(meme_path))
            logger.info(f"Отправлен мем: {meme_file}")
            
        except Exception as e:
            logger.error(f"Ошибка отправки мема: {e}")
            await inter.response.send_message(
                "❌ Произошла ошибка при отправке мема",
                ephemeral=True
            )

def setup(bot: commands.Bot):
    bot.add_cog(Memes(bot))