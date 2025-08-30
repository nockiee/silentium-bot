import disnake
from disnake.ext import commands
from config import USER_ROLES, POST_CHANNEL
from datetime import datetime
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class UserPosts(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.post_data: Dict[int, dict] = {}
        self.max_title_length = 100
        self.max_content_length = 2000

    async def is_user(self, inter: disnake.Interaction) -> bool:
        return any(role.id in USER_ROLES for role in inter.author.roles)

    async def _validate_post_channel(self) -> Optional[disnake.TextChannel]:
        channel = self.bot.get_channel(POST_CHANNEL)
        if not channel:
            logger.error(f"Канал для постов не найден (ID: {POST_CHANNEL})")
        return channel

    async def _send_post_embed(self, 
                            channel: disnake.TextChannel,
                            post_data: dict) -> bool:
        try:
            embed = disnake.Embed(
                title=post_data["title"][:self.max_title_length],
                description=post_data["content"][:self.max_content_length],
                color=disnake.Color.blue(),
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"Автор: {post_data['author_name']}")
            await channel.send(embed=embed)
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки поста: {e}", exc_info=True)
            return False

    @commands.slash_command(name="post", description="Создать пост")
    async def user_post(self, inter: disnake.ApplicationCommandInteraction):
        if not await self.is_user(inter):
            return await inter.send(
                "❌ Недостаточно прав для создания постов!",
                ephemeral=True
            )

        self.post_data[inter.author.id] = {
            "author_name": inter.author.display_name,
            "title": None,
            "content": None
        }

        await inter.response.send_modal(
            title="Создание поста",
            custom_id="user_post_modal",
            components=[
                disnake.ui.TextInput(
                    label="Заголовок",
                    custom_id="title",
                    style=disnake.TextInputStyle.short,
                    required=True,
                    max_length=self.max_title_length
                ),
                disnake.ui.TextInput(
                    label="Текст поста",
                    custom_id="content",
                    style=disnake.TextInputStyle.paragraph,
                    required=True,
                    max_length=self.max_content_length
                )
            ]
        )

    @commands.Cog.listener()
    async def on_modal_submit(self, inter: disnake.ModalInteraction):
        if inter.custom_id != "user_post_modal":
            return

        post = self.post_data.get(inter.author.id)
        if not post:
            return await inter.send(
                "❌ Сессия создания поста утеряна. Попробуйте снова.",
                ephemeral=True
            )

        post.update({
            "title": inter.text_values["title"],
            "content": inter.text_values["content"]
        })

        channel = await self._validate_post_channel()
        if not channel:
            return await inter.send(
                "❌ Ошибка: канал для постов недоступен",
                ephemeral=True
            )

        if await self._send_post_embed(channel, post):
            await inter.send(
                "✅ Ваш пост успешно опубликован!",
                ephemeral=True
            )
        else:
            await inter.send(
                "❌ Не удалось опубликовать пост. Попробуйте позже.",
                ephemeral=True
            )

        self.post_data.pop(inter.author.id, None)

def setup(bot: commands.Bot):
    bot.add_cog(UserPosts(bot))