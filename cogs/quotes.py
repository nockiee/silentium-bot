import disnake
from disnake.ext import commands
import random
import os
from typing import List

class Quotes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quotes_file = "quotes.txt"
        self._quotes_cache: List[str] = []
        self._ensure_quotes_file_exists()
        self._load_quotes()

    def _ensure_quotes_file_exists(self) -> None:
        if not os.path.exists(self.quotes_file):
            with open(self.quotes_file, 'w', encoding='utf-8'):
                pass

    def _load_quotes(self) -> List[str]:
        if self._quotes_cache:
            return self._quotes_cache
            
        try:
            with open(self.quotes_file, "r", encoding="utf-8") as f:
                quotes = [line.strip() for line in f if line.strip()]
                
            if not quotes:
                quotes = ["Мудрость приходит с опытом, а опыт - с недостатком мудрости. (Файл с цитатами пуст)"]
                
            self._quotes_cache = quotes
            return quotes
            
        except (IOError, UnicodeDecodeError) as e:
            print(f"Ошибка загрузки цитат: {e}")
            return ["Мудрость приходит с опытом, а опыт - с недостатком мудрости."]

    @commands.slash_command(name="quote", description="Получить случайную цитату")
    async def quote(self, inter: disnake.ApplicationCommandInteraction):
        quotes = self._load_quotes()
        selected_quote = random.choice(quotes)
        await inter.response.send_message(f"📜 *\"{selected_quote}\"*")

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Модуль Quotes успешно загружен! Доступно {len(self._load_quotes())} цитат.")

def setup(bot):
    bot.add_cog(Quotes(bot))