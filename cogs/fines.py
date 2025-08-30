import disnake
from disnake.ext import commands
from datetime import datetime
import json
import os
import sys
import logging
from typing import Dict, Set, Optional, List, Any
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

def get_env_list(var: str) -> List[int]:
    value = os.getenv(var, "")
    return [int(x) for x in value.split(",") if x.strip()]

FINE_ROLES = get_env_list("FINE_ROLES")
FINE_CHANNEL = int(os.getenv("FINE_CHANNEL", "0"))

class FinesSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.fines_file = "data/fines.json"
        self.pending_proofs: Dict[int, int] = {}
        self.redress_requests: Set[str] = set()
        os.makedirs("data", exist_ok=True)
        self._ensure_files_exist()
    
    def _ensure_files_exist(self) -> None:
        try:
            if not os.path.exists(self.fines_file):
                with open(self.fines_file, 'w', encoding='utf-8') as f:
                    json.dump({"last_id": 0, "fines": {}}, f, ensure_ascii=False, indent=4)
                return
            
            with open(self.fines_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if not isinstance(data, dict) or "last_id" not in data or "fines" not in data:
                    raise ValueError("Invalid file structure")
        except Exception as e:
            logger.critical(f"Ошибка инициализации файла штрафов: {e}")
            raise

    async def _handle_redress_response(
        self,
        inter: disnake.MessageInteraction,
        fine_id: int,
        accepted: bool
    ) -> None:
        try:
            request_key = f"redress_{fine_id}"
            if request_key not in self.redress_requests:
                await inter.followup.send(
                    "❌ Этот запрос больше не действителен",
                    ephemeral=True
                )
                return

            fines_data = self._load_fines()
            fine = fines_data["fines"].get(str(fine_id))
            if not fine:
                raise ValueError("Штраф не найден")

            if inter.author.id != fine["victim_id"]:
                await inter.followup.send(
                    "❌ Только пострадавший может подтверждать выполнение штрафа",
                    ephemeral=True
                )
                return

            status = "Требование выполнено" if accepted else "Требование не выполнено"
            status_color = disnake.Color.green() if accepted else disnake.Color.red()
            
            if not await self._update_fine_embed(fine_id, status=status, color=status_color):
                raise ValueError("Не удалось обновить embed")
            
            fine["status"] = "satisfied" if accepted else "not_satisfied"
            fine["status_text"] = status
            fine["resolved_at"] = datetime.now().isoformat()
            fine["resolved_by"] = inter.author.id
            fines_data["fines"][str(fine_id)] = fine
            self._save_fines(fines_data)

            if fine["violator_id"] != inter.author.id:
                try:
                    violator = await self.bot.fetch_user(fine["violator_id"])
                    status_msg = "подтверждено ✅" if accepted else "отклонено ❌"
                    if not await self._send_dm(
                        violator,
                        content=f"Выполнение требований штрафа #{fine_id} было {status_msg}."
                    ):
                        logger.info(f"Не удалось отправить уведомление нарушителю {violator.id}")
                except Exception as e:
                    logger.warning(f"Не удалось уведомить нарушителя {fine['violator_id']}: {e}")
            
            self.redress_requests.discard(request_key)
            await inter.followup.send(
                f"✅ Статус штрафа #{fine_id} обновлен: {status}",
                ephemeral=True
            )
            
            if inter.message:
                embed = inter.message.embeds[0] if inter.message.embeds else None
                if embed:
                    status_msg = "✅ Требование подтверждено" if accepted else "❌ Требование отклонено"
                    embed.description += f"\n\n{status_msg}"
                    embed.color = status_color
                    await inter.message.edit(embed=embed, view=None)
                    
        except Exception as e:
            logger.error(f"Ошибка обработки подтверждения штрафа {fine_id}: {e}", exc_info=True)
            raise ValueError("Не удалось обработать подтверждение штрафа")

    def _load_fines(self) -> Dict[str, Any]:
        try:
            with open(self.fines_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка загрузки штрафов: {e}")
            return {"last_id": 0, "fines": {}}

    def _save_fines(self, data: Dict[str, Any]) -> None:
        try:
            backup_file = f"{self.fines_file}.bak"
            if os.path.exists(self.fines_file):
                os.replace(self.fines_file, backup_file)
            
            temp_file = f"{self.fines_file}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
            os.replace(temp_file, self.fines_file)
            
            if os.path.exists(backup_file):
                os.remove(backup_file)
                
        except Exception as e:
            logger.error(f"Ошибка сохранения штрафов: {e}")
            if os.path.exists(backup_file):
                os.replace(backup_file, self.fines_file)
            raise

    async def _can_manage_fines(self, inter: disnake.Interaction) -> bool:
        return any(role.id in FINE_ROLES for role in inter.author.roles)

    async def _send_dm(self, user: disnake.User, **kwargs) -> Optional[disnake.Message]:
        try:
            try:
                dm_channel = user.dm_channel
                if dm_channel is None:
                    dm_channel = await user.create_dm()
            except AttributeError:
                dm_channel = await self.bot.create_dm(user)
                
            if dm_channel:
                return await dm_channel.send(**kwargs)
            return None
        except (disnake.HTTPException, disnake.Forbidden, AttributeError) as e:
            logger.warning(f"Не удалось отправить DM пользователю {user.id}: {e}")
            return None

    async def _update_fine_embed(self, fine_id: int, **kwargs) -> bool:
        fines_data = self._load_fines()
        fine = fines_data["fines"].get(str(fine_id))
        if not fine:
            return False

        try:
            channel = self.bot.get_channel(fine["channel_id"])
            if not channel:
                return False

            message = await channel.fetch_message(fine["message_id"])
            embed = message.embeds[0]
            
            for key, value in kwargs.items():
                if key == "color":
                    embed.color = value
                elif key == "status":
                    for i, field in enumerate(embed.fields):
                        if field.name == "Статус":
                            embed.set_field_at(i, name="Статус", value=value, inline=False)
                            break
            
            await message.edit(embed=embed)
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления embed штрафа {fine_id}: {e}")
            return False

    @commands.slash_command(name="fine", description="Выписать штраф")
    async def issue_fine(
        self,
        inter: disnake.ApplicationCommandInteraction,
        violator: disnake.Member,
        victim: disnake.Member,
        rule: str = commands.Param(max_length=200),
        requirement: str = commands.Param(max_length=500),
        deadline: str = commands.Param(max_length=100)
    ):
        if not await self._can_manage_fines(inter):
            return await inter.send("❌ У вас нет прав выписывать штрафы!", ephemeral=True)

        try:
            fines_data = self._load_fines()
            fine_id = fines_data["last_id"] + 1
            
            embed = disnake.Embed(
                title=f"Штраф #{fine_id:04d}",
                color=disnake.Color.light_gray(),
                timestamp=datetime.now()
            )
            embed.add_field(name="Нарушитель", value=violator.mention, inline=True)
            embed.add_field(name="Пострадавший", value=victim.mention, inline=True)
            embed.add_field(name="Нарушенное правило", value=rule, inline=False)
            embed.add_field(name="Требование", value=requirement, inline=True)
            embed.add_field(name="Срок исполнения", value=deadline, inline=True)
            embed.add_field(name="Статус", value="Выписан", inline=False)
            embed.set_footer(text=f"Выписал: {inter.author.display_name}")
            
            channel = self.bot.get_channel(FINE_CHANNEL)
            if not channel:
                return await inter.send("❌ Канал для штрафов не найден!", ephemeral=True)
            
            message = await channel.send(embed=embed)
            
            fines_data["fines"][str(fine_id)] = {
                "message_id": message.id,
                "channel_id": channel.id,
                "thread_id": None,
                "status": "issued",
                "status_text": "Выписан",
                "violator_id": violator.id,
                "victim_id": victim.id,
                "issuer_id": inter.author.id,
                "rule": rule,
                "requirement": requirement,
                "deadline": deadline,
                "created_at": datetime.now().isoformat()
            }
            fines_data["last_id"] = fine_id
            self._save_fines(fines_data)
            
            violator_embed = disnake.Embed(
                title=f"Вам выписан штраф #{fine_id:04d}",
                description=f"**Причина:** {rule}\n**Требование:** {requirement}\n**Срок:** {deadline}",
                color=disnake.Color.orange()
            )
            if not await self._send_dm(violator, embed=violator_embed):
                logger.info(f"Не удалось отправить уведомление нарушителю {violator.id}")
            
            victim_embed = disnake.Embed(
                title=f"По вашей жалобе выписан штраф #{fine_id:04d}",
                description=f"Нарушитель: {violator.mention}\n**Требование:** {requirement}",
                color=disnake.Color.green()
            )
            if not await self._send_dm(victim, embed=victim_embed):
                logger.info(f"Не удалось отправить уведомление пострадавшему {victim.id}")
            
            await inter.send(f"✅ Штраф #{fine_id:04d} успешно создан!")
            
        except Exception as e:
            logger.error(f"Ошибка создания штрафа: {e}", exc_info=True)
            await inter.send(f"❌ Ошибка при создании штрафа: {str(e)}", ephemeral=True)

    @commands.slash_command(name="fine-add-proof", description="Добавить доказательства к штрафу")
    async def add_proof(
        self,
        inter: disnake.ApplicationCommandInteraction,
        fine_id: int = commands.Param(gt=0)
    ):
        if not await self._can_manage_fines(inter):
            return await inter.send("❌ У вас нет прав добавлять доказательства!", ephemeral=True)
        
        fines_data = self._load_fines()
        if str(fine_id) not in fines_data["fines"]:
            return await inter.send("❌ Штраф с таким ID не найден!", ephemeral=True)
        
        self.pending_proofs[inter.author.id] = fine_id
        await inter.send(
            "Прикрепите файлы доказательств одним сообщением в этот чат. "
            "Сообщение будет автоматически удалено после обработки.",
            ephemeral=True
        )

    @commands.Cog.listener()
    async def on_message(self, message: disnake.Message):
        if message.author.bot or message.author.id not in self.pending_proofs:
            return
        
        fine_id = self.pending_proofs.pop(message.author.id, None)
        if not fine_id:
            return

        fines_data = self._load_fines()
        fine = fines_data["fines"].get(str(fine_id))
        if not fine:
            await message.channel.send("❌ Штраф не найден", delete_after=5)
            return
        
        if not message.attachments:
            await message.channel.send("❌ Вы не прикрепили файлы!", delete_after=5)
            return
        
        try:
            channel = self.bot.get_channel(fine["channel_id"])
            if not channel:
                return
            
            if fine.get("thread_id"):
                try:
                    thread = await self.bot.fetch_channel(fine["thread_id"])
                except (disnake.NotFound, disnake.Forbidden):
                    thread = None
                    fine["thread_id"] = None
            else:
                thread = None

            if not thread:
                try:
                    fine_message = await channel.fetch_message(fine["message_id"])
                    thread = await fine_message.create_thread(
                        name=f"Доказательства #{fine_id:04d}",
                        auto_archive_duration=1440,
                        reason=f"Доказательства для штрафа #{fine_id:04d}"
                    )
                    fine["thread_id"] = thread.id
                    fines_data["fines"][str(fine_id)] = fine
                    self._save_fines(fines_data)
                except Exception as e:
                    logger.error(f"Ошибка создания ветки для штрафа {fine_id}: {e}")
                    raise ValueError("Не удалось создать ветку для доказательств")
            
            files = [await att.to_file() for att in message.attachments]
            await thread.send(
                f"Доказательства от {message.author.mention}:",
                files=files
            )
            
            await message.delete()
            await message.channel.send(
                f"✅ Доказательства добавлены к штрафу #{fine_id:04d}",
                delete_after=5
            )
            
        except Exception as e:
            logger.error(f"Ошибка добавления доказательств: {e}", exc_info=True)
            await message.channel.send(
                f"❌ Ошибка при добавлении доказательств: {str(e)}",
                delete_after=10
            )

    @commands.slash_command(name="fine-status", description="Изменить статус штрафа")
    async def change_fine_status(
        self,
        inter: disnake.ApplicationCommandInteraction,
        fine_id: int = commands.Param(gt=0),
        status: str = commands.Param(
            choices=[
                "Требование выполнено", 
                "Требование не выполнено", 
                "Иная причина",
                "Пользовательский статус"
            ]
        ),
        custom_status: Optional[str] = commands.Param(default=None, max_length=200)
    ):
        if not await self._can_manage_fines(inter):
            return await inter.send("❌ У вас нет прав изменять статус штрафов!", ephemeral=True)
        
        fines_data = self._load_fines()
        fine = fines_data["fines"].get(str(fine_id))
        if not fine:
            return await inter.send("❌ Штраф с таким ID не найден!", ephemeral=True)
        
        try:
            status_text = custom_status if status == "Пользовательский статус" and custom_status else status
            status_color = {
                "Требование выполнено": disnake.Color.green(),
                "Требование не выполнено": disnake.Color.red(),
                "Иная причина": disnake.Color.orange(),
                "Пользовательский статус": disnake.Color.purple()
            }.get(status, disnake.Color.light_gray())
            
            if not await self._update_fine_embed(fine_id, status=status_text, color=status_color):
                raise ValueError("Не удалось обновить embed")
            
            fine["status"] = {
                "Требование выполнено": "satisfied",
                "Требование не выполнено": "not_satisfied",
                "Иная причина": "other_reason",
                "Пользовательский статус": "custom"
            }.get(status, "issued")
            fine["status_text"] = status_text
            fines_data["fines"][str(fine_id)] = fine
            self._save_fines(fines_data)
            
            await inter.send(f"✅ Статус штрафа #{fine_id:04d} обновлен на: {status_text}", ephemeral=True)
        except Exception as e:
            logger.error(f"Ошибка обновления статуса штрафа {fine_id}: {e}", exc_info=True)
            await inter.send(f"❌ Ошибка при обновлении штрафа: {str(e)}", ephemeral=True)

    @commands.slash_command(name="redress", description="Уведомить о выполнении требований")
    async def redress_fine(
        self,
        inter: disnake.ApplicationCommandInteraction,
        fine_id: int = commands.Param(gt=0)
    ):
        fines_data = self._load_fines()
        fine = fines_data["fines"].get(str(fine_id))
        
        if not fine:
            return await inter.send("❌ Штраф с таким ID не найден!", ephemeral=True)
        
        if inter.author.id != fine["violator_id"]:
            return await inter.send("❌ Вы не являетесь нарушителем по этому штрафу!", ephemeral=True)
        
        request_key = f"redress_{fine_id}"
        if request_key in self.redress_requests:
            return await inter.send("❌ Запрос на этот штраф уже отправлен!", ephemeral=True)
        
        self.redress_requests.add(request_key)
        
        try:
            victim = await self.bot.fetch_user(fine["victim_id"])
            if not victim:
                raise ValueError("Пострадавший не найден")
            
            class RedressView(disnake.ui.View):
                def __init__(self, cog, fine_id: int):
                    super().__init__(timeout=86400)
                    self.cog = cog
                    self.fine_id = fine_id
                    self.message = None

                async def on_timeout(self):
                    if self.message:
                        await self.cog._handle_redress_timeout(self.fine_id, self.message)

                @disnake.ui.button(
                    style=disnake.ButtonStyle.green,
                    label="Подтвердить выполнение",
                    custom_id=f"redress_accept_{fine_id}"
                )
                async def accept_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
                    await inter.response.defer(ephemeral=True)
                    try:
                        await self.cog._handle_redress_response(inter, self.fine_id, True)
                    except Exception as e:
                        await inter.followup.send(f"❌ Ошибка: {str(e)}", ephemeral=True)
                    self.stop()

                @disnake.ui.button(
                    style=disnake.ButtonStyle.red,
                    label="Отклонить выполнение",
                    custom_id=f"redress_reject_{fine_id}"
                )
                async def reject_button(self, button: disnake.ui.Button, inter: disnake.MessageInteraction):
                    await inter.response.defer(ephemeral=True)
                    try:
                        await self.cog._handle_redress_response(inter, self.fine_id, False)
                    except Exception as e:
                        await inter.followup.send(f"❌ Ошибка: {str(e)}", ephemeral=True)
                    self.stop()

            view = RedressView(self, fine_id)
            embed = disnake.Embed(
                title=f"Запрос подтверждения штрафа #{fine_id:04d}",
                description=(
                    f"{inter.author.mention} заявляет о выполнении требований.\n\n"
                    f"**Требование:** {fine['requirement']}\n\n"
                    "Подтверждаете выполнение?\n\n"
                    "⚠️ Запрос будет действителен в течение 24 часов."
                ),
                color=disnake.Color.blue()
            )
            
            dm_message = await self._send_dm(victim, embed=embed, view=view)
            if dm_message:
                view.message = dm_message
                await inter.send("✅ Запрос отправлен пострадавшему!", ephemeral=True)
            else:
                self.redress_requests.discard(f"redress_{fine_id}")
                await inter.send("❌ Не удалось отправить сообщение пострадавшему!", ephemeral=True)
            
        except Exception as e:
            self.redress_requests.discard(request_key)
            logger.error(f"Ошибка отправки запроса подтверждения: {e}", exc_info=True)
            await inter.send("❌ Не удалось отправить запрос!", ephemeral=True)

    @commands.slash_command(name="fine-pardon", description="Отменить штраф")
    async def pardon_fine(
        self,
        inter: disnake.ApplicationCommandInteraction,
        fine_id: int = commands.Param(gt=0)
    ):
        if not await self._can_manage_fines(inter):
            return await inter.send("❌ У вас нет прав отменять штрафы!", ephemeral=True)
        
        fines_data = self._load_fines()
        if str(fine_id) not in fines_data["fines"]:
            return await inter.send("❌ Штраф с таким ID не найден!", ephemeral=True)
        
        try:
            fine = fines_data["fines"][str(fine_id)]
            channel = self.bot.get_channel(fine["channel_id"])
            if not channel:
                raise ValueError("Канал не найден")
            
            try:
                message = await channel.fetch_message(fine["message_id"])
                await message.delete()
            except:
                pass
            
            if fine.get("thread_id"):
                try:
                    thread = await self.bot.fetch_channel(fine["thread_id"])
                    await thread.delete()
                except:
                    pass
            
            del fines_data["fines"][str(fine_id)]
            self._save_fines(fines_data)
            
            await inter.send(f"✅ Штраф #{fine_id:04d} отменен!", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Ошибка отмены штрафа {fine_id}: {e}", exc_info=True)
            await inter.send(f"❌ Ошибка при отмене: {str(e)}", ephemeral=True)

    async def _handle_redress_timeout(self, fine_id: int, message: disnake.Message):
        try:
            self.redress_requests.discard(f"redress_{fine_id}")
            
            embed = message.embeds[0] if message.embeds else None
            if embed:
                embed.description += "\n\n❌ Время ожидания истекло"
                embed.color = disnake.Color.dark_gray()
                await message.edit(embed=embed, view=None)
        except Exception as e:
            logger.error(f"Ошибка обработки таймаута штрафа {fine_id}: {e}")

    @commands.Cog.listener()
    async def on_button_click(self, inter: disnake.MessageInteraction):
        if not inter.component.custom_id.startswith("redress_"):
            return

        try:
            await inter.response.defer(ephemeral=True)
            _, action, fine_id = inter.component.custom_id.split("_")
            fine_id = int(fine_id)
            
            if f"redress_{fine_id}" not in self.redress_requests:
                await inter.followup.send(
                    "❌ Этот запрос больше не действителен. Возможно, истекло время ожидания.",
                    ephemeral=True
                )
                return

            await self._handle_redress_response(inter, fine_id, action == "accept")
            
        except ValueError as e:
            await inter.followup.send(f"❌ {str(e)}", ephemeral=True)
        except Exception as e:
            logger.error(f"Ошибка обработки кнопки подтверждения: {e}", exc_info=True)
            await inter.followup.send("❌ Произошла непредвиденная ошибка", ephemeral=True)

def setup(bot: commands.Bot):
    bot.add_cog(FinesSystem(bot))