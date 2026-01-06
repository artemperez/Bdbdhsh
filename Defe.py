import logging
import random
import asyncio
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton,
    CallbackQuery
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
import aiosqlite
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Ваши данные
BOT_TOKEN = "8400770070:AAFahEEaffeqcI0kcMwq5QVlv0Aur1GdbA8"
OWNER_ID = 8050595279
OWNER_USERNAME = "@aurieza"
ADMIN_IDS = [OWNER_ID]  # Добавьте другие ID через запятую, например: [OWNER_ID, 123456789]

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Инициализация базы данных
DB_NAME = "bot_database.db"

# Состояния FSM
class UserState(StatesGroup):
    waiting_captcha = State()
    waiting_subscription = State()
    reading_rules = State()

class AdminState(StatesGroup):
    waiting_channel_username = State()
    waiting_channel_link = State()
    waiting_private_name = State()
    waiting_private_link = State()
    waiting_broadcast = State()

# Класс для управления базой данных
class Database:
    def __init__(self):
        self.db_name = DB_NAME
        
    async def init_db(self):
        """Инициализация базы данных"""
        async with aiosqlite.connect(self.db_name) as db:
            # Таблица пользователей
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    full_name TEXT,
                    captcha_passed BOOLEAN DEFAULT 0,
                    subscribed BOOLEAN DEFAULT 0,
                    rules_accepted BOOLEAN DEFAULT 0,
                    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица каналов для подписки
            await db.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_username TEXT UNIQUE,
                    channel_title TEXT,
                    channel_link TEXT,
                    added_by INTEGER,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица приватных каналов
            await db.execute('''
                CREATE TABLE IF NOT EXISTS private_channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    link TEXT UNIQUE,
                    added_by INTEGER,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица администраторов
            await db.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    permissions TEXT DEFAULT 'all',
                    added_by INTEGER,
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица статистики
            await db.execute('''
                CREATE TABLE IF NOT EXISTS stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric TEXT,
                    value INTEGER,
                    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await db.commit()
            
            # Добавляем владельца как админа
            await self.add_admin(OWNER_ID, OWNER_USERNAME.split('@')[-1] if '@' in OWNER_USERNAME else OWNER_USERNAME, OWNER_ID)
            
            # Добавляем канал по умолчанию
            await self.add_channel("@example_channel", "Пример канала", "https://t.me/example_channel", OWNER_ID)
            
            # Добавляем приватные каналы по умолчанию
            default_privates = [
                ("приват #1", "https://t.me/+ZuUNjg1bJ3xiOTIy"),
                ("приват #2", "https://t.me/+ud0gESAJTRpiNGY6"),
                ("приват #3", "https://t.me/+ImsOnVdV-wkzMzgy"),
                ("приват #4", "https://t.me/+GoHxJYZjVHM2OTU8"),
                ("приват #5", "https://t.me/+OwCjJcf8MLMzMDY0"),
                ("приват #6", "https://t.me/+7R5UlNBtS_ozMjI0"),
                ("приват #7", "https://t.me/+EXlBIikoHqY5NjM0"),
                ("приват #8", "https://t.me/+tB3ELsrzjXYxNTA8"),
                ("приват #9", "https://t.me/+XS93nu2kjkgwYzEy"),
                ("приват #10", "https://t.me/+jtrr7X3DGJAyMzUy"),
                ("приват #11", "https://t.me/+CLvBRlmQyKRmZWNi"),
                ("приват #12", "https://t.me/+vTldRbXSDx8yNzY6"),
                ("приват #13", "https://t.me/+qSvuUw3Xi0plMzVk"),
                ("приват #14", "https://t.me/+3hsRBgNQeSA1Zjc0"),
                ("приват #15", "https://t.me/+fun3xCBTTCphNDY6"),
            ]
            
            for name, link in default_privates:
                try:
                    await self.add_private_channel(name, link, OWNER_ID)
                except:
                    pass  # Игнорируем дубликаты
    
    # Методы для пользователей
    async def add_user(self, user_id: int, username: str, full_name: str):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                """INSERT OR IGNORE INTO users 
                (user_id, username, full_name) 
                VALUES (?, ?, ?)""",
                (user_id, username, full_name)
            )
            await db.commit()
    
    async def update_user_captcha(self, user_id: int, passed: bool = True):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "UPDATE users SET captcha_passed = ? WHERE user_id = ?",
                (passed, user_id)
            )
            await db.commit()
    
    async def update_user_subscription(self, user_id: int, subscribed: bool = True):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "UPDATE users SET subscribed = ? WHERE user_id = ?",
                (subscribed, user_id)
            )
            await db.commit()
    
    async def update_user_rules(self, user_id: int, accepted: bool = True):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                "UPDATE users SET rules_accepted = ? WHERE user_id = ?",
                (accepted, user_id)
            )
            await db.commit()
    
    async def get_user(self, user_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
                return await cursor.fetchone()
    
    async def get_all_users(self):
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                result = await cursor.fetchone()
                return result[0] if result else 0
    
    async def get_user_ids(self):
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute("SELECT user_id FROM users") as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]
    
    # Методы для каналов
    async def add_channel(self, channel_username: str, channel_title: str, channel_link: str, added_by: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                """INSERT OR REPLACE INTO channels 
                (channel_username, channel_title, channel_link, added_by) 
                VALUES (?, ?, ?, ?)""",
                (channel_username, channel_title, channel_link, added_by)
            )
            await db.commit()
    
    async def get_channels(self):
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute("SELECT * FROM channels ORDER BY id") as cursor:
                return await cursor.fetchall()
    
    async def delete_channel(self, channel_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
            await db.commit()
    
    # Методы для приватных каналов
    async def add_private_channel(self, name: str, link: str, added_by: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                """INSERT OR IGNORE INTO private_channels 
                (name, link, added_by) 
                VALUES (?, ?, ?)""",
                (name, link, added_by)
            )
            await db.commit()
    
    async def get_private_channels(self, limit: int = 100):
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute("SELECT * FROM private_channels ORDER BY id LIMIT ?", (limit,)) as cursor:
                return await cursor.fetchall()
    
    async def delete_private_channel(self, channel_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("DELETE FROM private_channels WHERE id = ?", (channel_id,))
            await db.commit()
    
    # Методы для администраторов
    async def add_admin(self, user_id: int, username: str, added_by: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute(
                """INSERT OR IGNORE INTO admins 
                (user_id, username, added_by) 
                VALUES (?, ?, ?)""",
                (user_id, username, added_by)
            )
            await db.commit()
    
    async def get_admins(self):
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute("SELECT * FROM admins") as cursor:
                return await cursor.fetchall()
    
    async def is_admin(self, user_id: int):
        if user_id in ADMIN_IDS:
            return True
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute("SELECT 1 FROM admins WHERE user_id = ?", (user_id,)) as cursor:
                return await cursor.fetchone() is not None
    
    async def remove_admin(self, user_id: int):
        async with aiosqlite.connect(self.db_name) as db:
            await db.execute("DELETE FROM admins WHERE user_id = ? AND user_id != ?", (user_id, OWNER_ID))
            await db.commit()
    
    # Методы для статистики
    async def update_stat(self, metric: str, value: int = 1):
        async with aiosqlite.connect(self.db_name) as db:
            # Сначала проверяем, существует ли запись
            async with db.execute("SELECT 1 FROM stats WHERE metric = ?", (metric,)) as cursor:
                exists = await cursor.fetchone()
            
            if exists:
                await db.execute(
                    "UPDATE stats SET value = value + ?, updated_date = CURRENT_TIMESTAMP WHERE metric = ?",
                    (value, metric)
                )
            else:
                await db.execute(
                    "INSERT INTO stats (metric, value) VALUES (?, ?)",
                    (metric, value)
                )
            await db.commit()
    
    async def get_stat(self, metric: str):
        async with aiosqlite.connect(self.db_name) as db:
            async with db.execute("SELECT value FROM stats WHERE metric = ?", (metric,)) as cursor:
                result = await cursor.fetchone()
                return result[0] if result and result[0] else 0

# Инициализация базы данных
db = Database()

# Вспомогательные функции
async def check_subscription(user_id: int, channel_username: str) -> bool:
    """Проверяет, подписан ли пользователь на канал"""
    try:
        member = await bot.get_chat_member(chat_id=channel_username, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logger.error(f"Ошибка проверки подписки на {channel_username}: {e}")
        return False

def generate_captcha() -> tuple:
    """Генерирует случайную капчу"""
    operations = ['+', '-', '*']
    num1 = random.randint(1, 20)
    num2 = random.randint(1, 20)
    operation = random.choice(operations)
    
    if operation == '+':
        answer = num1 + num2
    elif operation == '-':
        answer = num1 - num2
    else:  # '*'
        answer = num1 * num2
    
    question = f"{num1} {operation} {num2} = ?"
    return question, str(answer)

def create_main_menu() -> ReplyKeyboardMarkup:
    """Создает главное меню"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎮 Мини-игры"), KeyboardButton(text="🔗 Получить приватки")],
            [KeyboardButton(text="📜 Правила"), KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие..."
    )
    return keyboard

def create_admin_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру админ-панели"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="➕ Добавить канал", callback_data="admin_add_channel")],
            [InlineKeyboardButton(text="🗑 Удалить канал", callback_data="admin_remove_channel")],
            [InlineKeyboardButton(text="➕ Добавить приват", callback_data="admin_add_private")],
            [InlineKeyboardButton(text="🗑 Удалить приват", callback_data="admin_remove_private")],
            [InlineKeyboardButton(text="👥 Добавить админа", callback_data="admin_add_admin")],
            [InlineKeyboardButton(text="👥 Удалить админа", callback_data="admin_remove_admin")],
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ]
    )
    return keyboard

def create_games_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру мини-игр"""
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎲 Бросить кубик", callback_data="game_dice")],
            [InlineKeyboardButton(text="🎯 Бросить дротик", callback_data="game_dart")],
            [InlineKeyboardButton(text="🏀 Баскетбол", callback_data="game_basketball")],
            [InlineKeyboardButton(text="⚽ Футбол", callback_data="game_football")],
            [InlineKeyboardButton(text="🎰 Слот-машина", callback_data="game_slot")],
            [InlineKeyboardButton(text="🎳 Боулинг", callback_data="game_bowling")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="game_back")]
        ]
    )
    return keyboard

# Обработчики команд
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username or ""
    full_name = message.from_user.full_name
    
    await db.add_user(user_id, username, full_name)
    await db.update_stat("starts")
    
    # Проверяем, прошел ли пользователь все этапы
    user_data = await db.get_user(user_id)
    
    if user_data and user_data[3] and user_data[4] and user_data[5]:  # Все пройдено
        welcome_text = f"""
✨ *Добро пожаловать в бот, {full_name}!* ✨

🎉 Вы уже прошли все этапы и имеете доступ ко всем функциям!

Выберите действие из меню ниже:
        """
        await message.answer(welcome_text, parse_mode="Markdown", reply_markup=create_main_menu())
        await state.clear()
        return
    
    # Если не прошел капчу
    if not user_data or not user_data[3]:
        await show_captcha(message, state)
    # Если не подписался
    elif not user_data[4]:
        await check_all_subscriptions(message, state)
    # Если не принял правила
    elif not user_data[5]:
        await show_rules(message, state)

async def show_captcha(message: types.Message, state: FSMContext):
    """Показывает капчу"""
    question, answer = generate_captcha()
    
    await state.set_state(UserState.waiting_captcha)
    await state.update_data(captcha_answer=answer)
    
    captcha_text = f"""
🔐 *Проверка безопасности*

Пожалуйста, решите простой пример, чтобы продолжить:

`{question}`

*Введите ответ цифрами:*
    """
    
    await message.answer(captcha_text, parse_mode="Markdown")

@dp.message(UserState.waiting_captcha)
async def process_captcha(message: types.Message, state: FSMContext):
    """Обрабатывает ответ на капчу"""
    user_answer = message.text.strip()
    data = await state.get_data()
    correct_answer = data.get("captcha_answer")
    
    if user_answer == correct_answer:
        await db.update_user_captcha(message.from_user.id)
        await db.update_stat("captcha_passed")
        
        await message.answer("✅ *Капча пройдена успешно!*", parse_mode="Markdown")
        await check_all_subscriptions(message, state)
    else:
        await message.answer("❌ *Неверный ответ! Попробуйте еще раз.*", parse_mode="Markdown")
        await show_captcha(message, state)

async def check_all_subscriptions(message: types.Message, state: FSMContext):
    """Проверяет подписки на все каналы"""
    channels = await db.get_channels()
    
    if not channels:
        # Если нет каналов, сразу переходим к правилам
        await db.update_user_subscription(message.from_user.id)
        await show_rules(message, state)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    subscription_text = "📢 *Подписка на каналы*\n\nДля продолжения необходимо подписаться на следующие каналы:\n\n"
    
    for i, channel in enumerate(channels, 1):
        channel_username = channel[1]
        channel_title = channel[2] or channel_username
        channel_link = channel[3] or f"https://t.me/{channel_username.lstrip('@')}"
        
        subscription_text += f"{i}. {channel_title}\n"
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"📢 Канал {i}", 
                url=channel_link
            )
        ])
    
    subscription_text += "\nПосле подписки нажмите кнопку ниже:"
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")
    ])
    
    await state.set_state(UserState.waiting_subscription)
    await message.answer(subscription_text, parse_mode="Markdown", reply_markup=keyboard)

@dp.callback_query(F.data == "check_subscription")
async def verify_subscription(callback: CallbackQuery, state: FSMContext):
    """Проверяет подписки пользователя"""
    user_id = callback.from_user.id
    channels = await db.get_channels()
    
    all_subscribed = True
    not_subscribed_channels = []
    
    for channel in channels:
        channel_username = channel[1]
        if not await check_subscription(user_id, channel_username):
            all_subscribed = False
            not_subscribed_channels.append(channel[2] or channel_username)
    
    if all_subscribed:
        await db.update_user_subscription(user_id)
        await db.update_stat("subscribed")
        
        await callback.message.edit_text("✅ *Все подписки подтверждены!*", parse_mode="Markdown")
        await show_rules(callback.message, state)
    else:
        channels_list = "\n".join([f"• {ch}" for ch in not_subscribed_channels])
        await callback.answer(
            f"❌ Вы не подписались на:\n{channels_list}",
            show_alert=True
        )
    
    await callback.answer()

async def show_rules(message: types.Message, state: FSMContext):
    """Показывает правила"""
    rules_text = f"""
📜 *Правила использования бота:*

1. 🤝 *Уважение*  
   Уважайте других пользователей и администрацию.

2. 📢 *Спам запрещен*  
   Запрещена рассылка рекламы и флуд.

3. 🔗 *Запрещенные материалы*  
   Не делитесь запрещенным контентом.

4. 🛡 *Безопасность*  
   Не пытайтесь взломать бота или нарушить его работу.

5. 📞 *Поддержка*  
   При возникновении проблем обращайтесь к {OWNER_USERNAME}

*Нажимая "Принять", вы соглашаетесь с правилами.*
    """
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Принять правила", callback_data="accept_rules")]
        ]
    )
    
    await state.set_state(UserState.reading_rules)
    await message.answer(rules_text, parse_mode="Markdown", reply_markup=keyboard)

@dp.callback_query(F.data == "accept_rules")
async def accept_rules(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает принятие правил"""
    await db.update_user_rules(callback.from_user.id)
    await db.update_stat("rules_accepted")
    
    welcome_text = f"""
🎉 *Поздравляем, {callback.from_user.full_name}!* 🎉

Вы успешно прошли все этапы и теперь имеете доступ ко всем функциям бота!

✨ *Доступные функции:*
• 🎮 Мини-игры для развлечения
• 🔗 Получение приватных ссылок
• 📜 Просмотр правил
• ❓ Помощь и поддержка

Выберите действие из меню ниже:
    """
    
    await callback.message.edit_text(welcome_text, parse_mode="Markdown")
    await callback.message.answer("👇 *Используйте меню для навигации:*", 
                                 parse_mode="Markdown", 
                                 reply_markup=create_main_menu())
    await state.clear()
    await callback.answer()

# Основное меню
@dp.message(F.text == "🎮 Мини-игры")
async def show_games(message: types.Message):
    """Показывает мини-игры"""
    user_data = await db.get_user(message.from_user.id)
    if not user_data or not (user_data[3] and user_data[4] and user_data[5]):
        await message.answer("⚠️ *Сначала пройдите все этапы регистрации!*", parse_mode="Markdown")
        return
    
    games_text = """
🎮 *Мини-игры*

Выберите игру из списка ниже:

• 🎲 *Бросить кубик* - случайное число от 1 до 6
• 🎯 *Бросить дротик* - попадите в цель!
• 🏀 *Баскетбол* - забросьте мяч в корзину
• ⚽ *Футбол* - забивайте пенальти
• 🎰 *Слот-машина* - испытайте удачу!
• 🎳 *Боулинг* - сбейте кегли!

Выберите игру:
    """
    
    await message.answer(games_text, parse_mode="Markdown", reply_markup=create_games_keyboard())

@dp.callback_query(F.data.startswith("game_"))
async def process_game(callback: CallbackQuery):
    """Обрабатывает выбор игры"""
    game_type = callback.data.split("_")[1]
    
    if game_type == "back":
        await callback.message.delete()
        await callback.answer()
        return
    
    # Отправляем соответствующую игру
    if game_type == "dice":
        await callback.message.answer_dice(emoji="🎲")
    elif game_type == "dart":
        await callback.message.answer_dice(emoji="🎯")
    elif game_type == "basketball":
        await callback.message.answer_dice(emoji="🏀")
    elif game_type == "football":
        await callback.message.answer_dice(emoji="⚽")
    elif game_type == "slot":
        await callback.message.answer_dice(emoji="🎰")
    elif game_type == "bowling":
        await callback.message.answer_dice(emoji="🎳")
    
    await callback.answer()

@dp.message(F.text == "🔗 Получить приватки")
async def send_private_links(message: types.Message):
    """Отправляет приватные ссылки"""
    user_data = await db.get_user(message.from_user.id)
    if not user_data or not (user_data[3] and user_data[4] and user_data[5]):
        await message.answer("⚠️ *Сначала пройдите все этапы регистрации!*", parse_mode="Markdown")
        return
    
    private_channels = await db.get_private_channels()
    
    if not private_channels:
        await message.answer("❌ *Приватные каналы временно недоступны.*", parse_mode="Markdown")
        return
    
    # Отправляем частями, чтобы избежать ограничения длины
    chunk_size = 10
    chunks = [private_channels[i:i + chunk_size] for i in range(0, len(private_channels), chunk_size)]
    
    for chunk_num, chunk in enumerate(chunks, 1):
        links_text = f"🔗 *Приватные каналы (часть {chunk_num}/{len(chunks)}):*\n\n"
        
        for i, channel in enumerate(chunk, 1):
            name = channel[1] or f"Приват #{channel[0]}"
            link = channel[2]
            links_text += f"{i}. {name}\n{link}\n\n"
        
        if chunk_num == len(chunks):
            links_text += f"💎 *Спасибо, что с нами! {OWNER_USERNAME}* 💎"
        
        try:
            await message.answer(links_text, parse_mode="Markdown", disable_web_page_preview=True)
        except Exception as e:
            logger.error(f"Ошибка отправки приватных ссылок: {e}")
            # Если сообщение слишком длинное, делим на еще более мелкие части
            for j, channel in enumerate(chunk):
                name = channel[1] or f"Приват #{channel[0]}"
                link = channel[2]
                single_text = f"🔗 {name}\n{link}"
                await message.answer(single_text, disable_web_page_preview=True)
        
        await asyncio.sleep(0.5)  # Задержка между сообщениями

@dp.message(F.text == "📜 Правила")
async def show_rules_again(message: types.Message):
    """Показывает правила"""
    rules_text = f"""
📜 *Правила использования бота:*

1. 🤝 *Уважение*  
   Уважайте других пользователей и администрацию.

2. 📢 *Спам запрещен*  
   Запрещена рассылка рекламы и флуд.

3. 🔗 *Запрещенные материалы*  
   Не делитесь запрещенным контентом.

4. 🛡 *Безопасность*  
   Не пытайтесь взломать бота или нарушить его работу.

5. 📞 *Поддержка*  
   При возникновении проблем обращайтесь к {OWNER_USERNAME}

📌 *Важно:* Нарушение правил ведет к бану!
    """
    await message.answer(rules_text, parse_mode="Markdown")

@dp.message(F.text == "❓ Помощь")
async def show_help(message: types.Message):
    """Показывает помощь"""
    help_text = f"""
❓ *Помощь и поддержка*

Если у вас возникли проблемы или вопросы:

🤖 *По вопросам работы бота:*
Свяжитесь с создателем: {OWNER_USERNAME}

🛠 *Технические проблемы:*
• Проверьте, прошли ли вы все этапы регистрации
• Убедитесь, что подписались на все каналы
• Попробуйте перезапустить бота командой /start

📞 *Контакты:*
Создатель: {OWNER_USERNAME}

*Небо пухом Лучший* ✨
    """
    await message.answer(help_text, parse_mode="Markdown")

@dp.message(Command("admin"))
async def show_admin_panel(message: types.Message):
    """Показывает админ-панель"""
    user_id = message.from_user.id
    
    if not await db.is_admin(user_id):
        await message.answer("⛔ *У вас нет доступа к админ-панели!*", parse_mode="Markdown")
        return
    
    admin_text = f"""
👑 *Админ-панель* {OWNER_USERNAME}

*Доступные действия:*

• 📊 *Статистика* - просмотр статистики бота
• ➕ *Добавить канал* - добавить канал для подписки
• 🗑 *Удалить канал* - удалить канал из списка
• ➕ *Добавить приват* - добавить приватный канал
• 🗑 *Удалить приват* - удалить приватный канал
• 👥 *Управление админами* - добавить/удалить админов
• 📢 *Рассылка* - отправить сообщение всем пользователям

Выберите действие:
    """
    
    await message.answer(admin_text, parse_mode="Markdown", reply_markup=create_admin_keyboard())

# Обработчики админ-панели
@dp.callback_query(F.data.startswith("admin_"))
async def process_admin_action(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает действия админ-панели"""
    user_id = callback.from_user.id
    
    if not await db.is_admin(user_id):
        await callback.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    action = callback.data.split("_")[1]
    
    if action == "stats":
        await show_admin_stats(callback)
    elif action == "add_channel":
        await callback.message.answer("📝 *Введите username канала (например: @channel_name):*", parse_mode="Markdown")
        await state.set_state(AdminState.waiting_channel_username)
    elif action == "remove_channel":
        await show_channels_for_removal(callback)
    elif action == "add_private":
        await callback.message.answer("📝 *Введите название приватного канала:*", parse_mode="Markdown")
        await state.set_state(AdminState.waiting_private_name)
    elif action == "remove_private":
        await show_privates_for_removal(callback)
    elif action == "add_admin":
        await callback.message.answer("📝 *Введите ID пользователя или перешлите его сообщение:*")
        await state.set_state(AdminState.waiting_channel_username)
    elif action == "remove_admin":
        await show_admins_for_removal(callback)
    elif action == "broadcast":
        await callback.message.answer("📢 *Введите сообщение для рассылки:*\n\nМожно использовать HTML-разметку.", parse_mode="Markdown")
        await state.set_state(AdminState.waiting_broadcast)
    elif action == "back":
        await callback.message.delete()
    
    await callback.answer()

async def show_admin_stats(callback: CallbackQuery):
    """Показывает статистику бота"""
    total_users = await db.get_all_users()
    captcha_passed = await db.get_stat("captcha_passed")
    subscribed = await db.get_stat("subscribed")
    rules_accepted = await db.get_stat("rules_accepted")
    starts = await db.get_stat("starts")
    
    channels = await db.get_channels()
    private_channels = await db.get_private_channels()
    
    from datetime import datetime
    stats_text = f"""
📊 *Статистика бота*

👥 *Пользователи:*
• Всего пользователей: `{total_users}`
• Прошли капчу: `{captcha_passed}`
• Подписались: `{subscribed}`
• Приняли правила: `{rules_accepted}`
• Запусков бота: `{starts}`

📢 *Каналы:*
• Для подписки: `{len(channels)}`
• Приватных: `{len(private_channels)}`

⏰ *Обновлено:* {datetime.now().strftime('%H:%M:%S')}
    """
    
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_stats")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ]
    )
    
    await callback.message.edit_text(stats_text, parse_mode="Markdown", reply_markup=keyboard)

async def show_channels_for_removal(callback: CallbackQuery):
    """Показывает список каналов для удаления"""
    channels = await db.get_channels()
    
    if not channels:
        await callback.answer("❌ Нет каналов для удаления!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for channel in channels:
        channel_id = channel[0]
        channel_title = channel[2] or channel[1]
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"🗑 {channel_title[:30]}",
                callback_data=f"remove_channel_{channel_id}"
            )
        ])
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")
    ])
    
    await callback.message.edit_text("🗑 *Выберите канал для удаления:*", 
                                    parse_mode="Markdown", 
                                    reply_markup=keyboard)

async def show_privates_for_removal(callback: CallbackQuery):
    """Показывает список приватных каналов для удаления"""
    private_channels = await db.get_private_channels()
    
    if not private_channels:
        await callback.answer("❌ Нет приватных каналов для удаления!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for channel in private_channels[:20]:  # Ограничиваем 20 каналами
        channel_id = channel[0]
        channel_name = channel[1] or f"Приват #{channel_id}"
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"🗑 {channel_name[:30]}",
                callback_data=f"remove_private_{channel_id}"
            )
        ])
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")
    ])
    
    await callback.message.edit_text("🗑 *Выберите приватный канал для удаления:*", 
                                    parse_mode="Markdown", 
                                    reply_markup=keyboard)

async def show_admins_for_removal(callback: CallbackQuery):
    """Показывает список админов для удаления"""
    admins = await db.get_admins()
    
    # Фильтруем владельца
    admins = [admin for admin in admins if admin[0] != OWNER_ID]
    
    if not admins:
        await callback.answer("❌ Нет админов для удаления!", show_alert=True)
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for admin in admins:
        admin_id = admin[0]
        admin_username = admin[1] or f"ID: {admin_id}"
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"👥 Удалить {admin_username}",
                callback_data=f"remove_admin_{admin_id}"
            )
        ])
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")
    ])
    
    await callback.message.edit_text("👥 *Выберите админа для удаления:*", 
                                    parse_mode="Markdown", 
                                    reply_markup=keyboard)

@dp.callback_query(F.data.startswith("remove_"))
async def process_removal(callback: CallbackQuery):
    """Обрабатывает удаление каналов/админов"""
    user_id = callback.from_user.id
    
    if not await db.is_admin(user_id):
        await callback.answer("⛔ Нет доступа!", show_alert=True)
        return
    
    data = callback.data.split("_")
    action_type = data[1]
    item_id = int(data[2])
    
    if action_type == "channel":
        await db.delete_channel(item_id)
        await callback.answer("✅ Канал удален!", show_alert=True)
        await show_channels_for_removal(callback)
    elif action_type == "private":
        await db.delete_private_channel(item_id)
        await callback.answer("✅ Приватный канал удален!", show_alert=True)
        await show_privates_for_removal(callback)
    elif action_type == "admin":
        if item_id == OWNER_ID:
            await callback.answer("❌ Нельзя удалить владельца!", show_alert=True)
        else:
            await db.remove_admin(item_id)
            await callback.answer("✅ Админ удален!", show_alert=True)
            await show_admins_for_removal(callback)

# Обработчики состояний админа
@dp.message(AdminState.waiting_channel_username)
async def process_channel_username(message: types.Message, state: FSMContext):
    """Обрабатывает username канала или добавление админа"""
    text = message.text.strip()
    
    # Проверяем, не является ли это пересланным сообщением
    if message.forward_from:
        # Это пересланное сообщение для добавления админа
        new_admin_id = message.forward_from.id
        new_admin_username = message.forward_from.username or f"ID: {new_admin_id}"
        
        await db.add_admin(new_admin_id, new_admin_username, message.from_user.id)
        await message.answer(f"✅ Админ {new_admin_username} добавлен!")
        await state.clear()
        return
    
    # Проверяем, является ли текст ID пользователя
    try:
        user_id = int(text)
        # Это ID пользователя для добавления админа
        try:
            user = await bot.get_chat(user_id)
            username = user.username or f"ID: {user_id}"
            await db.add_admin(user_id, username, message.from_user.id)
            await message.answer(f"✅ Админ {username} добавлен!")
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}")
        await state.clear()
        return
    except ValueError:
        pass
    
    # Это username канала
    if not text.startswith('@'):
        text = '@' + text
    
    await state.update_data(channel_username=text)
    await message.answer("📝 *Теперь введите ссылку-приглашение на канал:*", parse_mode="Markdown")
    await state.set_state(AdminState.waiting_channel_link)

@dp.message(AdminState.waiting_channel_link)
async def process_channel_link(message: types.Message, state: FSMContext):
    """Обрабатывает ссылку на канал"""
    data = await state.get_data()
    channel_username = data.get('channel_username')
    
    if channel_username:
        # Это добавление канала
        channel_link = message.text.strip()
        channel_title = channel_username
        
        try:
            # Пытаемся получить информацию о канале
            chat = await bot.get_chat(channel_username)
            channel_title = chat.title or channel_username
        except Exception as e:
            logger.error(f"Ошибка получения информации о канале: {e}")
        
        await db.add_channel(channel_username, channel_title, channel_link, message.from_user.id)
        await message.answer(f"✅ Канал *{channel_title}* добавлен!", parse_mode="Markdown")
    
    await state.clear()

@dp.message(AdminState.waiting_private_name)
async def process_private_name(message: types.Message, state: FSMContext):
    """Обрабатывает название приватного канала"""
    channel_name = message.text.strip()
    await state.update_data(private_name=channel_name)
    await message.answer("📝 *Теперь введите ссылку на приватный канал:*", parse_mode="Markdown")
    await state.set_state(AdminState.waiting_private_link)

@dp.message(AdminState.waiting_private_link)
async def process_private_link(message: types.Message, state: FSMContext):
    """Обрабатывает ссылку на приватный канал"""
    data = await state.get_data()
    channel_name = data.get('private_name')
    channel_link = message.text.strip()
    
    await db.add_private_channel(channel_name, channel_link, message.from_user.id)
    await message.answer(f"✅ Приватный канал *{channel_name}* добавлен!", parse_mode="Markdown")
    await state.clear()

@dp.message(AdminState.waiting_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    """Обрабатывает рассылку"""
    broadcast_message = message.text
    user_ids = await db.get_user_ids()
    
    if not user_ids:
        await message.answer("❌ Нет пользователей для рассылки!")
        await state.clear()
        return
    
    total_users = len(user_ids)
    await message.answer(f"📢 *Начинаю рассылку для {total_users} пользователей...*", parse_mode="Markdown")
    
    sent = 0
    failed = 0
    
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, broadcast_message, parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.05)  # Небольшая задержка, чтобы не получить ограничение
        except Exception as e:
            failed += 1
            logger.error(f"Ошибка отправки пользователю {user_id}: {e}")
    
    await message.answer(f"✅ *Рассылка завершена!*\n\nУспешно: {sent}\nНе удалось: {failed}", parse_mode="Markdown")
    await state.clear()

# Обработчик всех сообщений для обновления активности
@dp.message()
async def handle_all_messages(message: types.Message):
    """Обрабатывает все сообщения"""
    # Обновляем статистику
    await db.update_stat("messages")
    
    # Показываем меню, если пользователь прошел регистрацию
    user_data = await db.get_user(message.from_user.id)
    if user_data and user_data[3] and user_data[4] and user_data[5]:
        # Пользователь прошел регистрацию
        pass
    elif message.text not in ["/start", "/admin", "/stats"]:
        # Если пользователь не прошел регистрацию и пишет не команды
        await message.answer("⚠️ *Пожалуйста, сначала пройдите регистрацию через /start*", parse_mode="Markdown")

# Основная функция запуска бота
async def main():
    """Основная функция запуска бота"""
    logger.info("Запуск бота...")
    
    # Инициализируем базу данных
    await db.init_db()
    
    # Запускаем бота
    await dp.start_polling(bot)

# Запуск бота
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")