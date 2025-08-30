import disnake
from disnake.ext import commands
from config import ADMIN_ROLES, ANNOUNCEMENT_CHANNEL, IMAGE_UPLOAD_CHANNEL
from datetime import datetime
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class AdminPosts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.post_data: Dict[int, dict] = {}
        self.scheduled_posts: Dict[int, dict] = {}
        self.edit_mode: Dict[int, dict] = {}

    async def is_admin(self, inter: disnake.Interaction) -> bool:
        return any(role.id in ADMIN_ROLES for role in inter.author.roles)

    @commands.slash_command(name="admin_post", description="Создать административный пост")
    async def admin_post(self, inter: disnake.ApplicationCommandInteraction):
        if not await self.is_admin(inter):
            return await inter.send("❌ Недостаточно прав!", ephemeral=True)

        self.post_data[inter.author.id] = {
            "author_name": inter.author.display_name,
            "title": None,
            "content": None,
            "image_url": None,
            "waiting_for_image": False
        }

        await inter.response.send_modal(
            title="Административный пост",
            custom_id="admin_post_modal",
            components=[
                disnake.ui.TextInput(
                    label="Заголовок",
                    custom_id="title",
                    style=disnake.TextInputStyle.short,
                    required=True,
                    max_length=100
                ),
                disnake.ui.TextInput(
                    label="Текст",
                    custom_id="content",
                    style=disnake.TextInputStyle.paragraph,
                    required=True,
                    max_length=2000
                )
            ]
        )

    @commands.slash_command(name="edit_post", description="Редактировать существующий пост")
    async def edit_post(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        message_id: str,
        edit_type: str = commands.Param(choices=["текст", "изображение"])
    ):
        try:
            if not await self.is_admin(inter):
                await inter.response.send_message("❌ Недостаточно прав!", ephemeral=True)
                return

            if edit_type != "текст":
                await inter.response.defer(ephemeral=True)

            channel = self.bot.get_channel(ANNOUNCEMENT_CHANNEL)
            message = await channel.fetch_message(int(message_id))
            
            if not message or not message.embeds:
                if edit_type == "текст":
                    await inter.response.send_message(
                        "❌ Сообщение не найдено или не является постом администрации!",
                        ephemeral=True
                    )
                else:
                    await inter.followup.send(
                        "❌ Сообщение не найдено или не является постом администрации!",
                        ephemeral=True
                    )
                return

            self.edit_mode[inter.author.id] = {
                "message_id": message.id,
                "edit_type": edit_type,
                "current_embed": message.embeds[0]
            }

            if edit_type == "текст":
                await inter.response.send_modal(
                    title="Редактирование поста",
                    custom_id="edit_post_modal",
                    components=[
                        disnake.ui.TextInput(
                            label="Заголовок",
                            custom_id="title",
                            style=disnake.TextInputStyle.short,
                            required=True,
                            max_length=100,
                            value=message.embeds[0].title
                        ),
                        disnake.ui.TextInput(
                            label="Текст",
                            custom_id="content",
                            style=disnake.TextInputStyle.paragraph,
                            required=True,
                            max_length=2000,
                            value=message.embeds[0].description
                        )
                    ]
                )
            else:
                self.edit_mode[inter.author.id]["waiting_for_image"] = True
                await inter.followup.send(
                    "📎 Прикрепите новое изображение (в течение 5 минут):",
                    ephemeral=True
                )

        except ValueError:
            if edit_type == "текст":
                await inter.response.send_message("❌ Неверный формат ID сообщения!", ephemeral=True)
            else:
                await inter.followup.send("❌ Неверный формат ID сообщения!", ephemeral=True)
        except Exception as e:
            logger.error(f"Edit post error: {e}", exc_info=True)
            if edit_type == "текст":
                await inter.response.send_message("❌ Ошибка при попытке редактирования поста", ephemeral=True)
            else:
                await inter.followup.send("❌ Ошибка при попытке редактирования поста", ephemeral=True)

    @commands.Cog.listener()
    async def on_modal_submit(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)
        
        if inter.custom_id == "admin_post_modal":
            if inter.author.id not in self.post_data:
                return await inter.followup.send("❌ Сессия утеряна", ephemeral=True)

            self.post_data[inter.author.id].update({
                "title": inter.text_values["title"],
                "content": inter.text_values["content"]
            })

            view = disnake.ui.View(timeout=300)
            view.add_item(disnake.ui.Button(
                label="Добавить изображение",
                style=disnake.ButtonStyle.green,
                custom_id="add_image",
                emoji="🖼️"
            ))
            view.add_item(disnake.ui.Button(
                label="Пропустить",
                style=disnake.ButtonStyle.gray,
                custom_id="skip_image",
                emoji="⏭️"
            ))

            await inter.followup.send(
                "Хотите добавить изображение к посту?",
                view=view,
                ephemeral=True
            )

        elif inter.custom_id == "edit_post_modal":
            if inter.author.id not in self.edit_mode:
                return await inter.send("❌ Сессия редактирования утеряна", ephemeral=True)

            edit_data = self.edit_mode[inter.author.id]
            channel = self.bot.get_channel(ANNOUNCEMENT_CHANNEL)
            message = await channel.fetch_message(edit_data["message_id"])

            if not message:
                return await inter.send("❌ Сообщение не найдено!", ephemeral=True)

            embed = edit_data["current_embed"]
            embed.title = inter.text_values["title"]
            embed.description = inter.text_values["content"]

            try:
                await message.edit(embed=embed)
                await inter.response.send_message("✅ Пост успешно отредактирован!", ephemeral=True)
                self.edit_mode.pop(inter.author.id, None)
            except Exception as e:
                logger.error(f"Edit post error: {e}", exc_info=True)
                await inter.response.send_message("❌ Ошибка при редактировании поста", ephemeral=True)

    @commands.Cog.listener()
    async def on_button_click(self, inter: disnake.MessageInteraction):
        try:
            custom_id = inter.component.custom_id

            if custom_id == "add_image":
                if inter.author.id not in self.post_data:
                    return await inter.send("❌ Сессия утеряна", ephemeral=True)
                self.post_data[inter.author.id]["waiting_for_image"] = True
                await inter.response.send_message(
                    "📎 Прикрепите изображение в этот чат (в течение 5 минут):",
                    ephemeral=True
                )

            elif custom_id == "skip_image":
                await self._show_ping_options(inter)

            elif custom_id in ("publish_everyone", "publish_here", "publish_none"):
                await self._publish_post(inter)

            elif custom_id == "publish_now":
                post = self.post_data.get(inter.author.id)
                if not post:
                    return await inter.send("❌ Сессия утеряна", ephemeral=True)
                await self._do_publish(inter, post)

            elif custom_id == "schedule_post":
                if inter.author.id not in self.post_data:
                    return await inter.send("❌ Сессия утеряна", ephemeral=True)
                self.scheduled_posts[inter.author.id] = self.post_data[inter.author.id]
                await inter.send("✅ Пост добавлен в очередь запланированных!", ephemeral=True)
                self.post_data.pop(inter.author.id, None)

            elif custom_id.startswith("queue_"):
                action, uid = custom_id.split("_")[1:]
                uid = int(uid)
                
                if action == "publish":
                    post = self.scheduled_posts.get(uid)
                    if post:
                        await self._do_publish(inter, post)
                    else:
                        await inter.send("❌ Пост не найден в очереди.", ephemeral=True)
                
                elif action == "cancel":
                    if self.scheduled_posts.pop(uid, None):
                        await inter.send("✅ Пост отменён.", ephemeral=True)
                    else:
                        await inter.send("❌ Пост не найден в очереди.", ephemeral=True)
        except Exception as e:
            logger.error(f"Button click error: {e}", exc_info=True)
            await inter.send("❌ Произошла ошибка при обработке действия", ephemeral=True)

    async def _validate_image(self, attachment: disnake.Attachment) -> bool:
        if not attachment.content_type:
            return attachment.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))
        return attachment.content_type.startswith('image/')

    async def _save_image(self, attachment: disnake.Attachment) -> tuple[bool, str, str]:
        try:
            if attachment.size > 10 * 1024 * 1024:
                return False, "", "❌ Файл слишком большой (максимум 10MB)"

            if not await self._validate_image(attachment):
                return False, "", "❌ Файл должен быть изображением (PNG, JPG, GIF, WEBP)"

            channel = self.bot.get_channel(IMAGE_UPLOAD_CHANNEL)
            if not channel:
                return False, "", "❌ Канал для загрузки изображений не настроен"

            try:
                file = await attachment.to_file()
            except Exception as e:
                logger.error(f"Ошибка при конвертации изображения: {e}")
                return False, "", "❌ Ошибка при обработке файла"

            try:
                uploaded = await channel.send(file=file)
                if not uploaded.attachments:
                    return False, "", "❌ Ошибка при загрузке изображения"
                return True, uploaded.attachments[0].url, ""
            except disnake.Forbidden:
                return False, "", "❌ Нет прав для загрузки в канал изображений"
            except Exception as e:
                logger.error(f"Ошибка при отправке изображения: {e}")
                return False, "", "❌ Ошибка при загрузке изображения"

        except Exception as e:
            logger.error(f"Неожиданная ошибка при сохранении изображения: {e}")
            return False, "", "❌ Неожиданная ошибка при обработке изображения"

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        try:
            if message.author.bot:
                return

            in_edit_mode = (
                message.author.id in self.edit_mode and 
                self.edit_mode[message.author.id].get("waiting_for_image")
            )
            
            in_create_mode = (
                message.author.id in self.post_data and 
                self.post_data[message.author.id].get("waiting_for_image")
            )

            if not (in_edit_mode or in_create_mode):
                return

            if not message.attachments:
                await message.channel.send(
                    content="❌ Прикрепите изображение!",
                    delete_after=5
                )
                return

            success, image_url, error_message = await self._save_image(message.attachments[0])
            if not success:
                delete_after = 10 if message.attachments[0].size > 10 * 1024 * 1024 else 5
                await message.channel.send(
                    content=error_message,
                    delete_after=delete_after
                )
                return

            try:
                await message.delete()
            except:
                pass

            if in_edit_mode:
                try:
                    edit_data = self.edit_mode[message.author.id]
                    announcement_channel = self.bot.get_channel(ANNOUNCEMENT_CHANNEL)
                    target_message = await announcement_channel.fetch_message(edit_data["message_id"])
                    
                    embed = edit_data["current_embed"]
                    embed.set_image(url=image_url)
                    
                    await target_message.edit(embed=embed)
                    await message.channel.send(
                        content="✅ Изображение обновлено!",
                        delete_after=5
                    )
                    self.edit_mode.pop(message.author.id, None)
                except Exception as e:
                    logger.error(f"Ошибка при обновлении изображения в посте: {e}")
                    await message.channel.send(
                        content="❌ Ошибка при обновлении поста",
                        delete_after=5
                    )
                
            else:
                try:
                    self.post_data[message.author.id].update({
                        "image_url": image_url,
                        "waiting_for_image": False
                    })
                    await message.channel.send(
                        content="✅ Изображение добавлено!",
                        delete_after=5
                    )
                    await self._show_ping_options(message)
                except Exception as e:
                    logger.error(f"Ошибка при добавлении изображения к новому посту: {e}")
                    await message.channel.send(
                        content="❌ Ошибка при создании поста",
                        delete_after=5
                    )

        except Exception as e:
            logger.error(f"Общая ошибка обработки изображения: {e}", exc_info=True)
            await message.channel.send(
                content="❌ Произошла непредвиденная ошибка",
                delete_after=10
            )

    async def _show_ping_options(self, source: disnake.Message | disnake.MessageInteraction):
        post = self.post_data.get(source.author.id)
        if not post:
            return

        view = disnake.ui.View(timeout=300)
        view.add_item(disnake.ui.Button(
            label="Опубликовать с @everyone",
            style=disnake.ButtonStyle.green,
            custom_id="publish_everyone"
        ))
        view.add_item(disnake.ui.Button(
            label="Опубликовать с @here",
            style=disnake.ButtonStyle.blurple,
            custom_id="publish_here"
        ))
        view.add_item(disnake.ui.Button(
            label="Опубликовать без упоминания",
            style=disnake.ButtonStyle.gray,
            custom_id="publish_none"
        ))

        if isinstance(source, disnake.MessageInteraction):
            if source.response.is_done():
                await source.followup.send(
                    "Выберите тип упоминания:",
                    view=view,
                    ephemeral=True
                )
            else:
                await source.response.send_message(
                    "Выберите тип упоминания:",
                    view=view,
                    ephemeral=True
                )
        else:
            await source.channel.send(
                "Выберите тип упоминания:",
                view=view,
                delete_after=300
            )

    async def _publish_post(self, inter: disnake.MessageInteraction):
        post = self.post_data.get(inter.author.id)
        if not post:
            return await inter.send("❌ Сессия утеряна", ephemeral=True)

        ping = {
            "publish_everyone": "@everyone",
            "publish_here": "@here",
            "publish_none": ""
        }.get(inter.component.custom_id, "")

        post["ping"] = ping
        self.post_data[inter.author.id] = post

        view = disnake.ui.View(timeout=300)
        view.add_item(disnake.ui.Button(
            label="Опубликовать сейчас",
            style=disnake.ButtonStyle.green,
            custom_id="publish_now"
        ))
        view.add_item(disnake.ui.Button(
            label="Запланировать",
            style=disnake.ButtonStyle.gray,
            custom_id="schedule_post"
        ))

        await inter.response.send_message(
            "Выберите действие:",
            view=view,
            ephemeral=True
        )

    async def _do_publish(self, inter: disnake.MessageInteraction, post: dict):
        channel = self.bot.get_channel(ANNOUNCEMENT_CHANNEL)
        if not channel:
            return await inter.send("❌ Канал для публикации не найден", ephemeral=True)

        embed = disnake.Embed(
            title=post["title"],
            description=post["content"],
            color=disnake.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Автор: {post['author_name']}")
        if post.get("image_url"):
            embed.set_image(url=post["image_url"])

        try:
            await channel.send(post.get("ping", ""), embed=embed)
            await inter.send("✅ Пост опубликован!", ephemeral=True)
        except Exception as e:
            logger.error(f"Publish error: {e}", exc_info=True)
            await inter.send("❌ Ошибка при публикации поста", ephemeral=True)
        finally:
            self.post_data.pop(inter.author.id, None)
            self.scheduled_posts.pop(inter.author.id, None)

    @commands.slash_command(name="admin-queue", description="Посмотреть очередь запланированных постов")
    async def admin_queue(self, inter: disnake.ApplicationCommandInteraction):
        if not await self.is_admin(inter):
            return await inter.send("❌ Недостаточно прав!", ephemeral=True)

        if not self.scheduled_posts:
            return await inter.send("Очередь пуста.", ephemeral=True)

        embed = disnake.Embed(title="Очередь запланированных постов", color=disnake.Color.blurple())
        for uid, post in self.scheduled_posts.items():
            embed.add_field(
                name=f"{post['title']} (Автор: {post['author_name']})",
                value=f"Текст: {post['content'][:100]}...\nID: {uid}",
                inline=False
            )

        view = disnake.ui.View(timeout=300)
        for uid in self.scheduled_posts:
            view.add_item(disnake.ui.Button(
                label=f"Опубликовать {uid}",
                style=disnake.ButtonStyle.green,
                custom_id=f"queue_publish_{uid}"
            ))
            view.add_item(disnake.ui.Button(
                label=f"Отменить {uid}",
                style=disnake.ButtonStyle.red,
                custom_id=f"queue_cancel_{uid}"
            ))

        await inter.send(embed=embed, view=view, ephemeral=True)



def setup(bot):
    bot.add_cog(AdminPosts(bot))