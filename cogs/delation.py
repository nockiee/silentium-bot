import disnake
from disnake.ext import commands
from config import DELATION_CHANNEL
from datetime import datetime
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class Delation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.history_file = "delation-history.txt"

    @commands.slash_command(name="delation", description="Отправить анонимное сообщение")
    async def delation(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.send_modal(
            title="Анонимное сообщение",
            custom_id="delation_modal",
            components=[
                disnake.ui.TextInput(
                    label="Ваше сообщение",
                    custom_id="message",
                    style=disnake.TextInputStyle.paragraph,
                    required=True,
                    max_length=2000
                )
            ]
        )

    @commands.Cog.listener()
    async def on_modal_submit(self, inter: disnake.ModalInteraction):
        if inter.custom_id != "delation_modal":
            return

        message = inter.text_values["message"]
        channel = self.bot.get_channel(DELATION_CHANNEL)
        
        if not channel:
            logger.error(f"Канал для делляции не найден (ID: {DELATION_CHANNEL})")
            return await inter.response.send_message(
                "❌ Ошибка: канал для сообщений не найден",
                ephemeral=True
            )

        try:
            embed = disnake.Embed(
                description=message,
                color=disnake.Color.red(),
                timestamp=datetime.now()
            )
            await channel.send(embed=embed)

            self._log_delation(inter.author.display_name, message)
            
            await inter.response.send_message(
                "✅ Ваше сообщение отправлено анонимно!",
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Ошибка при обработке делляции: {e}", exc_info=True)
            await inter.response.send_message(
                "❌ Произошла ошибка при отправке сообщения",
                ephemeral=True
            )

    def _log_delation(self, author_name: str, message: str) -> None:
        try:
            with open(self.history_file, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now()} - {author_name}: {message}\n")
        except IOError as e:
            logger.error(f"Ошибка записи в файл истории: {e}")

def setup(bot):
    bot.add_cog(Delation(bot))