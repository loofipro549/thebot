import logging
import asyncio
import sqlite3
import random
import smtplib
import re
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Конфигурация
BOT_TOKEN = "7984506224:AAEd3y8AgaP-DjjFqVZ8RfW4Q71yOxgK65w"
ADMIN_IDS = [595041765, 6319553476]
DATABASE_NAME = 'bot.db'

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# База данных
def init_db():
    """Инициализация базы данных"""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                subscription_end DATE,
                reports_available INTEGER DEFAULT 1,
                referral_code TEXT UNIQUE,
                referred_by INTEGER,
                registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_premium BOOLEAN DEFAULT FALSE,
                total_reports_sent INTEGER DEFAULT 0,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sent_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                template_name TEXT,
                recipient_email TEXT,
                sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")

init_db()

# Состояния FSM
class ReportStates(StatesGroup):
    choosing_category = State()
    choosing_template = State()
    entering_email = State()
    entering_data = State()
    confirmation = State()

# База почт
EMAILS = {
    "kspeoadfipa@gmail.com": "wdox jfrh tncs pwic",
    "ao6557424@gmail.com": "mnuy jepq yvyc hjbr",
    "dlyabravla655@gmail.com": "kprn ihvr bgia vdys",
    "extrage523@gmail.com": "mphz wjrz iibv rvbr",
    "graciocnachleni@gmail.com": "qavg mbmx lotz uoph",
    "lofi04976@gmail.com": "nhdw luwd axpx kgrj",
    "lofipro43@gmail.com": "dqks iuoj ynis badb",
    "lofisnos@gmail.com": "twya atav adpl klhe",
    "penisone48@gmail.com": "aisn nywc fxyh pgkk",
    "rtrueqw@gmail.com": "kzhu vuom lker yugq",
    "snos6244@gmail.com": "gnpy beqw nqkd wlgk",
    "worklofishop8@gmail.com": "uxhv rxxm meps sjof",
    "worklofishop0@gmail.com": "cbjb viiq xfph jbcs",
    "danaislava1488@gmail.com": "robi xhez pxdh fshw",
    "mrcj141488@gmail.com": "hnad wyid mevr uwlz",
    "worklofishop215@gmail.com": "vuxf ndyv boje ledp",
    "asasadsjs@gmail.com": "qiuz edua zjfz utxi",
    "aleopo33@gmail.com": "gbfx svyk sdwq mpdv",
    "aumenaockovolosatoe38@gmail.com": "iqqr vtat oawj vczw",
    "gobllllllllll44@gmail.com": "ysxc xghk hgkf ffqg",
    "prostonaf7568@gmail.com": "lzjh tzbi uchb qfvv",
    "m4452736fdc@gmail.com": "mzai jzpk qpox zhxc",
    "rast34242@gmail.com": "qxqe jiba yxre bxtp"
}

# Шаблоны сообщений - ПОЛНАЯ ВЕРСИЯ
# Шаблоны сообщений - ПОЛНАЯ ВЕРСИЯ БЕЗ СОКРАЩЕНИЙ
TEMPLATES = {
    "school": {
        "Перевод в другую школу": """Уважаемая администрация школы!

Я, {фио}, учащийся {класс} класса {школа}, обращаюсь к Вам с просьбой о рассмотрении моего перевода в Ваше образовательное учреждение.

В связи с семейными обстоятельствами (переезд) я вынужден сменить место обучения. Мои родители готовы предоставить все необходимые документы и встретиться с Вами в удобное время.

Для оперативной связи предоставляю контактные данные:
📞 Телефон: {телефон}
👤 ФИО родителя: {фио_родителя}

Прошу Вас сообщить о возможности перевода и необходимом пакете документов.

С уважением,
{фио}""",

        "Жалоба на учителя": """Уважаемый директор {школа}!

Я, {фио_родителя}, родитель ученика {класс} класса {фио_ученика}, вынужден обратиться с официальной жалобой на учителя {фио_учителя}.

Конкретные претензии:
• Систематическое унижение учеников
• Необъективное оценивание знаний
• Некомпетентность в преподавании предмета
• Грубые высказывания в адрес детей

Последний инцидент произошел {дата}, когда {описание_инцидента}.

Требую:
1. Немедленного служебного расследования
2. Привлечения к дисциплинарной ответственности
3. Публичных извинений перед учеником

Готов предоставить дополнительные доказательства и свидетельские показания.

Контакт для связи: {телефон}

С уважением,
{фио_родителя}""",

        "Донос на ученика": """СЛУЖЕБНАЯ ЗАПИСКА
Директору {школа}
от преподавательского состава

Уважаемый {фио_директора}!

Доводим до Вашего сведения о систематических нарушениях учебной дисциплины учеником {класс} класса {фио_ученика}.

Зафиксированные нарушения:
✓ Распространение запрещенных веществ (электронные сигареты)
✓ Организация драк и провокаций
✓ Порча школьного имущества
✓ Угрозы в адрес одноклассников
✓ Неадекватное поведение на уроках

Последний случай: {дата} - {описание_инцидента}

Рекомендуем:
1. Срочный вызов родителей
2. Рассмотрение вопроса о переводе в спецучреждение
3. Проведение психолого-педагогической экспертизы

При необходимости готовы предоставить видеодоказательства.

Анонимно""",

        "Фальшивый карантин": """ЭКСТРЕННОЕ СООБЩЕНИЕ
Руководству и медицинской службе {школа}

УВАЖАЕМЫЕ КОЛЛЕГИ!

Поступила информация о подтвержденном случае заболевания {заболевание} у ученика {класс} класса {фио}.

Диагноз подтвержден {дата} в {медицинское_учреждение}. 
Инкубационный период: {период} дней.

ЭПИДЕМИОЛОГИЧЕСКИЕ МЕРОПРИЯТИЯ:
✅ Немедленная изоляция контактных лиц
✅ Дезинфекция помещений {список_помещений}
✅ Приостановка учебного процесса на {дни} дней
✅ Экстренное уведомление Роспотребнадзора

Контакт для подтверждения: 
🏥 {медицинское_учреждение}
📞 {телефон}

Главный врач {фио_врача}""",

        "Подставной роман": """{фио_учителя}, мне нужно с тобой срочно поговорить.

Наша последняя встреча {дата} не должна стать известной твоей семье. Я понимаю, что мы оба совершили ошибку, но теперь нужно решать последствия.

Я беременна. Срок - {срок} недель. Тесты подтвердили.

Не делай ничего глупого. Давай встретимся и спокойно все обсудим. Я не хочу скандала, но и молчать не могу.

Мой номер: {телефон}
Время для звонка: с {время_начала} до {время_конца}

Прошу отнестись к этому серьезно.
{анонимное_имя}""",

        "Вымогательство": """{фио_учителя}, у нас к тебе есть серьезные вопросы.

Располагаем компрометирующими материалами, подтверждающими твою связь с {фио_ученика} из {класс} класса. 

Имеются:
• Фото- и видеодоказательства
• Переписки личного характера
• Свидетельские показания

Если не хочешь уголовного дела по статье 135 УК РФ "Развратные действия", готовь {сумма} рублей к {дата}.

Перевод на карту: {номер_карты}
Держатель: {фио_получателя}

После получения платежа все материалы будут уничтожены. 
Любые попытки обратиться в полицию приведут к немедленной публикации.

Не проверяй нас.
Анонимная группа""",

        "Фейковое мероприятие": """ВАЖНАЯ ИНФОРМАЦИЯ ДЛЯ РОДИТЕЛЕЙ
Администрация {школа}

Уважаемые родители!

В связи с экстренной ситуацией, собрание родителей учащихся {класс} классов ПЕРЕНЕСЕНО.

Новые дата и время: {дата} в {время}
Место проведения: {место}

ПОВЕСТКА ДНЯ:
1. Вопросы безопасности образовательного процесса
2. Инцидент с {фио_учителя} - служебное расследование
3. Введение дополнительных мер контроля
4. Финансовые вопросы

ЯВКА СТРОГО ОБЯЗАТЕЛЬНА!
При себе иметь паспорт и блокнот для записей.

В случае неявки - административные санкции в отношении учащегося.

С уважением,
Директор {фио_директора}
Секретарь: {телефон}"""
    },
    
    "swatting": {
        "Минирование школы": """ЭКСТРЕННОЕ СООБЩЕНИЕ
СЛУЖБЕ БЕЗОПАСНОСТИ {адрес}

В ЗДАНИИ ШКОЛЫ УСТАНОВЛЕНЫ ВЗРЫВНЫЕ УСТРОЙСТВА!

Локации:
• Главный холл - 3 кг в тротиловом эквиваленте
• Спортивный зал - 5 кг 
• Столовая - 2 кг

Тип ВУ: самодельные взрывные устройства с системой дистанционного управления
Таймер: 45 минут с момента получения сообщения ({время} + 00:45)

ТРЕБОВАНИЯ:
1. Немедленная эвакуация в радиусе 500 метров
2. Отключение электроснабжения
3. Прекращение работы сотовых вышек в районе
4. Готовность к дальнейшим инструкциям

ЭТО НЕ УЧЕБНАЯ ТРЕВОГА!
Любые попытки локализации приведут к немедленной детонации.

- Группа "Рассвет" """,

        "Захват заложников": """ШТУРМОВОЙ ОТРЯД НЕ ПРИБЫВАТЬ!
{адрес} - КРИТИЧЕСКАЯ СИТУАЦИЯ

Произошел захват заложников в учебном заведении.

СТАТУС:
• Количество террористов: 4-6 человек
• Вооружение: автоматы Калашникова, гранаты
• Заложники: 50+ учеников и преподавателей
• Требования: {требования}

УСЛОВИЯ:
• Радиус оцепления - 1 км
• Отключение электричества и связи
• Переговоры только через {телефон}
• Приближение силовиков - расстрел заложников

СРОЧНО ДОВЕСТИ ДО ОПЕРАТИВНОГО ШТАБА!
Повторяю: это не учения.

Анонимный источник""",

        "Вооруженное нападение": """КОД 99 - НАПАДЕНИЕ НА ОБРАЗОВАТЕЛЬНОЕ УЧРЕЖДЕНИЕ
{адрес}

СИТУАЦИЯ НА {время}:
• 3 вооруженных преступника в здании
• Ведут беспорядочную стрельбу
• Есть пострадавшие среди учащихся
• Преступники перемещаются по этажам

ОПИСАНИЕ НАПАДАВШИХ:
• Маски, черная форма
• Автоматическое оружие
• Действуют скоординированно

ТРЕБУЕТСЯ:
1. Штурмовая группа с бронежилетами
2. Снайперы на позициях
3. Медицинская эвакуация
4. Оцепление территории

НЕМЕДЛЕННЫЕ ДЕЙСТВИЯ!
Сообщение от очевидца"""
    },
    
    "corporate": {
        "Увольнение": """УВАЖАЕМЫЙ {фио_сотрудника}!
Администрация {компания} уведомляет Вас о прекращении трудового договора.
Причина: {причина_увольнения}
Дата расторжения: {дата}
Контакт для вопросов: {телефон_отдела}

С уважением,
Отдел кадров {компания}""",

        "Премия": """СЛУЖЕБНАЯ ЗАПИСКА
Кому: {фио_сотрудника}
От: Отдел кадров {компания}

Уведомляем о начислении премии в размере {сумма} рублей.
Для получения обратитесь в бухгалтерию до {дата}.
Неразглашение обязательно.

Основание: Приказ №{номер_приказа} от {дата_приказа}""",

        "Аудит": """ЭКСТРЕННОЕ УВЕДОМЛЕНИЕ
В отделе {отдел} назначена внеплановая проверка.
Дата: {дата}
Время: {время}
Проверяющие: {фио_проверяющих}
Причина: {причина_проверки}

Подготовить всю документацию за последние 6 месяцев.
Неявка расценивается как саботаж.

С уважением,
Служба внутреннего контроля"""
    },
    
    "personal": {
        "Шантаж отношениями": """{фио_цели}, у нас есть информация о твоей связи с {фио_партнера}.
Если не хочешь проблем, выполни {требования} до {дата}.
Молчи - и все останется между нами.

Не пытайся выйти на связь - мы сами с тобой свяжемся.
Любые попытки обратиться в полицию приведут к немедленной публикации доказательств.""",

        "Беременность": """{фио_мужчины}, нам нужно серьезно поговорить.
Я беременна. Срок - {срок} недель. Тесты подтвердили.
Давай встретимся {дата} чтобы обсудить дальнейшие действия.

Мой номер: {телефон}
Не игнорируй это сообщение - ситуация серьезная.

{анонимное_имя}""",

        "Долг": """{фио_должника}, напоминаем о долге в размере {сумма} рублей.
Срок возврата: {дата}.
При невыплате передадим дело коллекторам.

Контакт: {телефон_кредитора}
Реквизиты для перевода: {реквизиты}

Невыполнение обязательств приведет к правовым последствиям."""
    },
    
    "government": {
        "Налоги": """УВЕДОМЛЕНИЕ ИФНС
Гражданину: {фио}
Адрес: {адрес}

Задолженность по налогам: {сумма} рублей.
Срок оплаты: {дата}.
При неуплате - штраф 50% от суммы долга.

Реквизиты для оплаты:
Получатель: УФК по г. Москве
ИНН 7710168360 
КПП 771001001
Счет: 03100643000000012700
Банк: ГУ Банка России по ЦФО
БИК: 044525000
КБК: 18210807010011000110
Назначение: Уплата транспортного налога

При возникновении вопросов обращаться по тел: {телефон_инспекции}""",

        "Штрафы ГИБДД": """ПОСТАНОВЛЕНИЕ ГИБДД
Водитель: {фио}
Номер авто: {номер_авто}
Нарушение: {нарушение}
Штраф: {сумма} рублей
Оплатить до: {дата}

Основание: ст. 12.9 КоАП РФ
Протокол №: {номер_протокола}
Инспектор: {фио_инспектора}

Оплатить через: 
• Сбербанк Онлайн
• Госуслуги
• Терминалы оплаты

При несогласии обжаловать в течение 10 дней.""",

        "Повестка в суд": """ПОВЕСТКА В СУД
Гражданину: {фио}
Явиться: {дата} в {время}
Адрес: {адрес_суда}
Причина: {причина}

Кабинет: {кабинет}
Судья: {фио_судьи}
Номер дела: {номер_дела}

При неявке без уважительной причины будет применен привод.
При себе иметь паспорт и все документы по делу."""
    },
    
    "crypto": {
        "Вымогательство биткоин": """ВНИМАНИЕ! Ваши данные скомпрометированы.
Для удаления информации переведите {сумма_btc} BTC на адрес: {btc_адрес}
Срок: {дата}
Иначе все данные будут опубликованы.

Мы имеем доступ к:
• Вашей переписке
• Личным фото и видео
• Банковским данным
• Истории браузера

После оплаты все данные будут уничтожены.
Не пытайтесь отследить транзакцию - используем миксер.""",

        "Майнинг": """ПРЕДЛОЖЕНИЕ О СОТРУДНИЧЕСТВЕ
Инвестируйте в майнинг - доходность 300% в месяц!
Минимальный вклад: {сумма}
Кошелек: {кошелек}
Гарантия возврата!

Наши преимущества:
✅ Лицензированная деятельность
✅ Современное оборудование
✅ Прозрачная отчетность
✅ Страхование инвестиций

Первые выплаты через 24 часа!
Ограниченное количество мест.""",

        "Блокировка кошелька": """ВАШ КОШЕЛЕК ЗАБЛОКИРОВАН
Кошелек: {кошелек}
Причина: {причина}
Для разблокировки оплатите {сумма} на {кошелек_оплаты}
Срок: {дата}

Блокировка связана с подозрением в отмывании средств.
При неуплате кошелек будет permanently frozen.
Все средства будут конфискованы в пользу регулятора.

После оплаты разблокировка в течение 2 часов."""
    }
}

# Клавиатуры
def main_menu():
    """Главное меню"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.row(
        InlineKeyboardButton("🎯 Создать донос", callback_data="create_report"),
        InlineKeyboardButton("👤 Профиль", callback_data="profile")
    )
    keyboard.row(
        InlineKeyboardButton("📊 Реферальная система", callback_data="referral"),
        InlineKeyboardButton("💎 Премиум", callback_data="subscription")
    )
    if ADMIN_IDS:
        keyboard.row(InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel"))
    return keyboard

def categories_menu():
    """Меню категорий - ПОЛНАЯ ВЕРСИЯ"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.row(
        InlineKeyboardButton("🏫 Школьные", callback_data="category_school"),
        InlineKeyboardButton("🚨 Сваттинг", callback_data="category_swatting")
    )
    keyboard.row(
        InlineKeyboardButton("🏢 Корпоративные", callback_data="category_corporate"),
        InlineKeyboardButton("👥 Личные", callback_data="category_personal")
    )
    keyboard.row(
        InlineKeyboardButton("🏛️ Государственные", callback_data="category_government"),
        InlineKeyboardButton("💻 Криптовымогательство", callback_data="category_crypto")
    )
    keyboard.row(InlineKeyboardButton("🔙 Назад", callback_data="back_main"))
    return keyboard

def templates_menu(category):
    """Меню шаблонов для категории"""
    keyboard = InlineKeyboardMarkup()
    templates = TEMPLATES.get(category, {})
    for template_name in templates.keys():
        keyboard.add(InlineKeyboardButton(template_name, callback_data=f"template_{category}_{template_name}"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_categories"))
    return keyboard

def confirmation_keyboard():
    """Клавиатура подтверждения"""
    keyboard = InlineKeyboardMarkup()
    keyboard.row(
        InlineKeyboardButton("✅ Отправить", callback_data="confirm_send"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel_send")
    )
    return keyboard

def admin_keyboard():
    """Админ-панель"""
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("➕ Выдать подписку", callback_data="admin_give_sub"))
    keyboard.add(InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"))
    keyboard.add(InlineKeyboardButton("🔄 Сброс лимитов", callback_data="admin_reset_limits"))
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="back_main"))
    return keyboard

# Вспомогательные функции
def get_user_db(user_id):
    """Получить данные пользователя из БД"""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT reports_available, is_premium, total_reports_sent FROM users WHERE user_id = ?', 
            (user_id,)
        )
        result = cursor.fetchone()
        conn.close()
        return result
    except Exception as e:
        logger.error(f"Database error for user {user_id}: {e}")
        return None

def update_user_reports(user_id, decrement=False):
    """Обновить данные пользователя"""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        if decrement:
            cursor.execute(
                'UPDATE users SET reports_available = reports_available - 1, total_reports_sent = total_reports_sent + 1 WHERE user_id = ?',
                (user_id,)
            )
        else:
            cursor.execute(
                'UPDATE users SET total_reports_sent = total_reports_sent + 1 WHERE user_id = ?',
                (user_id,)
            )
        
        cursor.execute(
            'UPDATE users SET last_activity = CURRENT_TIMESTAMP WHERE user_id = ?',
            (user_id,)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Update user error: {e}")
        return False

def log_email_sent(user_id, template_name, recipient_email, status):
    """Логирование отправки email"""
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO sent_emails (user_id, template_name, recipient_email, status) VALUES (?, ?, ?, ?)',
            (user_id, template_name, recipient_email, status)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Email logging error: {e}")

# Команды администратора
@dp.message_handler(commands=['premium'])
async def give_premium_command(message: types.Message):
    """Выдать премиум подписку"""
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        await message.answer("❌ Недостаточно прав")
        return
    
    try:
        target_id = int(message.text.split()[1])
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_premium = TRUE WHERE user_id = ?', (target_id,))
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ Пользователю {target_id} выдана премиум подписка!")
        
        # Уведомление пользователя
        try:
            await bot.send_message(
                target_id,
                "🎉 Вам выдана ПРЕМИУМ ПОДПИСКА!\n\n"
                "Теперь у вас:\n"
                "✅ Безлимитные доносы\n"
                "⚡ Приоритетная отправка\n"
                "🔒 Максимальная анонимность"
            )
        except Exception:
            pass
            
    except (IndexError, ValueError):
        await message.answer("Использование: /premium USER_ID")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@dp.message_handler(commands=['unlimited'])
async def unlimited_for_all(message: types.Message):
    """Выдать премиум всем"""
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_premium = TRUE')
        conn.commit()
        conn.close()
        
        await message.answer("✅ Всем пользователям выдана премиум подписка!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@dp.message_handler(commands=['stats'])
async def stats_command(message: types.Message):
    """Статистика бота"""
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        return
    
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        # Общая статистика
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM users WHERE is_premium = TRUE')
        premium_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM sent_emails')
        total_emails = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM sent_emails WHERE date(sent_date) = date("now")')
        today_emails = cursor.fetchone()[0]
        
        conn.close()
        
        stats_text = (
            "📊 Статистика бота:\n\n"
            f"👥 Всего пользователей: {total_users}\n"
            f"💎 Премиум пользователей: {premium_users}\n"
            f"📧 Всего отправлено писем: {total_emails}\n"
            f"📨 Писем сегодня: {today_emails}"
        )
        
        await message.answer(stats_text)
    except Exception as e:
        await message.answer(f"❌ Ошибка статистики: {str(e)}")

# Основные обработчики
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message, state: FSMContext):
    """Команда start"""
    await state.finish()
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Реферальная система
    args = message.get_args()
    if args and args.isdigit():
        referrer_id = int(args)
        if referrer_id != user_id:
            try:
                conn = sqlite3.connect(DATABASE_NAME)
                cursor = conn.cursor()
                cursor.execute('SELECT reports_available FROM users WHERE user_id = ?', (referrer_id,))
                result = cursor.fetchone()
                if result:
                    cursor.execute(
                        'UPDATE users SET reports_available = reports_available + 1 WHERE user_id = ?', 
                        (referrer_id,)
                    )
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Referral error: {e}")
    
    # Регистрация пользователя
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT OR IGNORE INTO users (user_id, username, reports_available) VALUES (?, ?, 1)',
            (user_id, username)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"User registration error: {e}")
    
    await message.answer(
        "👋 Добро пожаловать в SMTP Bot!\n\n"
        "Выберите действие:",
        reply_markup=main_menu()
    )

@dp.callback_query_handler(lambda c: c.data == 'create_report')
async def create_report(callback: types.CallbackQuery, state: FSMContext):
    """Создание доноса"""
    user_id = callback.from_user.id
    user_data = get_user_db(user_id)
    
    if not user_data:
        await bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text="❌ Ошибка базы данных"
        )
        return
    
    reports_available, is_premium, total_sent = user_data
    
    if not is_premium and reports_available <= 0:
        await bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text="❌ У вас нет доступных доносов.\n\n"
                 "💎 Приобретите подписку или пригласите друзей по реферальной ссылке!",
            reply_markup=main_menu()
        )
        return
    
    await bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text="🎯 Выберите категорию доноса:",
        reply_markup=categories_menu()
    )
    await ReportStates.choosing_category.set()

@dp.callback_query_handler(lambda c: c.data.startswith('category_'), state=ReportStates.choosing_category)
async def choose_category(callback: types.CallbackQuery, state: FSMContext):
    """Выбор категории"""
    category = callback.data.split("_")[1]
    
    category_names = {
        "school": "🏫 Школьные",
        "swatting": "🚨 Сваттинг", 
    }
    
    await state.update_data(category=category)
    await bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text=f"📝 {category_names.get(category, category)} - выберите шаблон:",
        reply_markup=templates_menu(category)
    )
    await ReportStates.choosing_template.set()

@dp.callback_query_handler(lambda c: c.data.startswith('template_'), state=ReportStates.choosing_template)
async def choose_template(callback: types.CallbackQuery, state: FSMContext):
    """Выбор шаблона"""
    _, category, template = callback.data.split("_", 2)
    await state.update_data(template=template, category=category)
    
    # Показываем подсказку по формату данных с КОНКРЕТНЫМИ ПРИМЕРАМИ ДЛЯ ВСЕХ ШАБЛОНОВ
    hints = {
        # Школьные
        "Донос на ученика": "📋 Формат: Школа, ФИО директора, Класс, ФИО ученика, Дата, Описание инцидента\n📌 Пример: Школа №1, Иванов Иван Иванович, 10А, Петров Петр, 25.12.2024, курил в туалете",
        "Жалоба на учителя": "📋 Формат: Школа, ФИО родителя, Класс, ФИО ученика, ФИО учителя, Дата, Описание инцидента, Телефон\n📌 Пример: Школа №15, Сидорова Мария, 8Б, Сидоров Алексей, Петрова Анна, 20.12.2024, оскорбил ученика, +79161234567",
        "Перевод в другую школу": "📋 Формат: ФИО ученика, Класс, Школа, Телефон, ФИО родителя\n📌 Пример: Иванов Иван, 9А, Школа №5, +79161234567, Иванова Ольга",
        "Фальшивый карантин": "📋 Формат: Школа, Заболевание, Класс, ФИО ученика, Дата, Мед учреждение, Период, Помещения, Дни, Телефон, ФИО врача\n📌 Пример: Школа №3, COVID-19, 7Б, Сергеев Алекс, 18.12.2024, Поликлиника №1, 14 дней, классы 1-3, 10, +79161234567, Смирнов А.В.",
        "Подставной роман": "📋 Формат: ФИО учителя, Дата встречи, Срок беременности, Телефон, Время начала, Время конца, Анонимное имя\n📌 Пример: Петрова Анна Ивановна, 15.12.2024, 8 недель, +79161234567, 14:00, 16:00, Мария",
        "Вымогательство": "📋 Формат: ФИО учителя, ФИО ученика, Класс, Сумма, Дата, Номер карты, ФИО получателя\n📌 Пример: Иванов Петр, Сидорова Анна, 11А, 50000, 25.12.2024, 1234567812345678, Сергеев М.И.",
        "Фейковое мероприятие": "📋 Формат: Школа, Класс, Дата, Время, Место, ФИО учителя, ФИО директора, Телефон\n📌 Пример: Школа №7, 5-11 классы, 28.12.2024, 18:00, Актовый зал, Петров И.С., Сидоров А.В., +79161234567",
        
        # Сваттинг
        "Минирование школы": "📋 Формат: Адрес, Время\n📌 Пример: ул. Ленина 15, 14:30",
        "Захват заложников": "📋 Формат: Адрес, Требования, Телефон\n📌 Пример: ул. Школьная 10, освобождение заключенных, +79161234567",
        "Вооруженное нападение": "📋 Формат: Адрес, Время\n📌 Пример: ул. Центральная 25, 15:00",
        
        # Корпоративные
        "Увольнение": "📋 Формат: ФИО сотрудника, Компания, Причина увольнения, Дата, Телефон отдела\n📌 Пример: Иванов Иван, ООО Ромашка, нарушение трудовой дисциплины, 25.12.2024, +79161234567",
        "Премия": "📋 Формат: ФИО сотрудника, Компания, Сумма, Дата, Номер приказа, Дата приказа\n📌 Пример: Петров Петр, АО Стройка, 50000, 20.12.2024, 245, 18.12.2024",
        "Аудит": "📋 Формат: Отдел, Дата, Время, ФИО проверяющих, Причина проверки\n📌 Пример: Отдел продаж, 22.12.2024, 10:00, Сидоров А.В.; Иванова М.К., проверка финансовой отчетности",
        
        # Личные
        "Шантаж отношениями": "📋 Формат: ФИО цели, ФИО партнера, Требования, Дата\n📌 Пример: Иванов Иван, Петрова Мария, перевести 100000 рублей, 25.12.2024",
        "Беременность": "📋 Формат: ФИО мужчины, Срок, Дата, Телефон, Анонимное имя\n📌 Пример: Сергеев Алексей, 12 недель, 20.12.2024, +79161234567, Анастасия",
        "Долг": "📋 Формат: ФИО должника, Сумма, Дата, Телефон кредитора, Реквизиты\n📌 Пример: Петров Петр, 150000, 25.12.2024, +79161234567, карта 1234567812345678",
        
        # Государственные
        "Налоги": "📋 Формат: ФИО, Адрес, Сумма, Дата, Телефон инспекции\n📌 Пример: Иванов Иван Иванович, г. Москва ул. Ленина 1, 25000, 25.12.2024, +74951234567",
        "Штрафы ГИБДД": "📋 Формат: ФИО, Номер авто, Нарушение, Сумма, Дата, Номер протокола, ФИО инспектора\n📌 Пример: Петров Петр Петрович, А123БВ777, превышение скорости, 5000, 20.12.2024, 188456, Сидоров А.В.",
        "Повестка в суд": "📋 Формат: ФИО, Дата, Время, Адрес суда, Причина, Кабинет, ФИО судьи, Номер дела\n📌 Пример: Иванов И.И., 28.12.2024, 14:30, ул. Правды 15, гражданский иск, 305, Петрова М.И., 2-456/2024",
        
        # Криптовымогательство
        "Вымогательство биткоин": "📋 Формат: Сумма BTC, BTC адрес, Дата\n📌 Пример: 0.5, 17vPx2X9W2Gb4HKu1AxCvbcEVa77G38fYX, 25.12.2024",
        "Майнинг": "📋 Формат: Сумма, Кошелек\n📌 Пример: 50000, 17vPx2X9W2Gb4HKu1AxCvbcEVa77G38fYX",
        "Блокировка кошелька": "📋 Формат: Кошелек, Причина, Сумма, Кошелек оплаты, Дата\n📌 Пример: 17vPx2X9W2Gb4HKu1AxCvbcEVa77G38fYX, подозрение в отмывании, 0.1, 17vPx2X9W2Gb4HKu1AxCvbcEVa77G38fYX, 25.12.2024"
    }
    
    hint = hints.get(template, "📋 Введите данные через запятую в указанном порядке")
    
    await bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text=f"📧 Введите email получателя:\n\n"
             f"📋 Шаблон: {template}\n"
             f"💡 {hint}",
    )
    await ReportStates.entering_email.set()

@dp.message_handler(state=ReportStates.entering_email)
async def enter_email(message: types.Message, state: FSMContext):
    """Ввод email"""
    email = message.text.strip().lower()
    
    # Валидация email
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        await message.answer("❌ Неверный формат email. Попробуйте снова:")
        return
    
    await state.update_data(email=email)
    
    data = await state.get_data()
    template = data['template']
    
    await message.answer(
        f"📝 Введите данные для шаблона:\n"
        f"📋 Шаблон: {template}\n"
        f"📧 Email: {email}\n\n"
        f"💡 Введите данные через запятую в правильном порядке"
    )
    await ReportStates.entering_data.set()

@dp.message_handler(state=ReportStates.entering_data)
async def enter_data(message: types.Message, state: FSMContext):
    """Ввод данных"""
    user_data = message.text.strip()
    if not user_data:
        await message.answer("❌ Данные не могут быть пустыми. Попробуйте снова:")
        return
    
    await state.update_data(user_data=user_data)
    
    data = await state.get_data()
    
    # Примеры для подтверждения - ПОЛНАЯ ВЕРСИЯ
    examples = {
        # Школьные
        "Донос на ученика": "Школа №1, Иванов И.И., 10А, Петров Петр, 25.12.2024, курил в туалете",
        "Жалоба на учителя": "Школа №15, Сидорова Мария, 8Б, Сидоров Алексей, Петрова Анна, 20.12.2024, оскорбил ученика, +79161234567",
        "Перевод в другую школу": "Иванов Иван, 9А, Школа №5, +79161234567, Иванова Ольга",
        "Фальшивый карантин": "Школа №3, COVID-19, 7Б, Сергеев Алекс, 18.12.2024, Поликлиника №1, 14 дней, классы 1-3, 10, +79161234567, Смирнов А.В.",
        "Подставной роман": "Петрова Анна Ивановна, 15.12.2024, 8 недель, +79161234567, 14:00, 16:00, Мария",
        "Вымогательство": "Иванов Петр, Сидорова Анна, 11А, 50000, 25.12.2024, 1234567812345678, Сергеев М.И.",
        "Фейковое мероприятие": "Школа №7, 5-11 классы, 28.12.2024, 18:00, Актовый зал, Петров И.С., Сидоров А.В., +79161234567",
        
        # Сваттинг
        "Минирование школы": "ул. Ленина 15, 14:30",
        "Захват заложников": "ул. Школьная 10, освобождение заключенных, +79161234567",
        "Вооруженное нападение": "ул. Центральная 25, 15:00",
        
        # Корпоративные
        "Увольнение": "Иванов Иван, ООО Ромашка, нарушение трудовой дисциплины, 25.12.2024, +79161234567",
        "Премия": "Петров Петр, АО Стройка, 50000, 20.12.2024, 245, 18.12.2024",
        "Аудит": "Отдел продаж, 22.12.2024, 10:00, Сидоров А.В.; Иванова М.К., проверка финансовой отчетности",
        
        # Личные
        "Шантаж отношениями": "Иванов Иван, Петрова Мария, перевести 100000 рублей, 25.12.2024",
        "Беременность": "Сергеев Алексей, 12 недель, 20.12.2024, +79161234567, Анастасия",
        "Долг": "Петров Петр, 150000, 25.12.2024, +79161234567, карта 1234567812345678",
        
        # Государственные
        "Налоги": "Иванов Иван Иванович, г. Москва ул. Ленина 1, 25000, 25.12.2024, +74951234567",
        "Штрафы ГИБДД": "Петров Петр Петрович, А123БВ777, превышение скорости, 5000, 20.12.2024, 188456, Сидоров А.В.",
        "Повестка в суд": "Иванов И.И., 28.12.2024, 14:30, ул. Правды 15, гражданский иск, 305, Петрова М.И., 2-456/2024",
        
        # Криптовымогательство
        "Вымогательство биткоин": "0.5, 17vPx2X9W2Gb4HKu1AxCvbcEVa77G38fYX, 25.12.2024",
        "Майнинг": "50000, 17vPx2X9W2Gb4HKu1AxCvbcEVa77G38fYX",
        "Блокировка кошелька": "17vPx2X9W2Gb4HKu1AxCvbcEVa77G38fYX, подозрение в отмывании, 0.1, 17vPx2X9W2Gb4HKu1AxCvbcEVa77G38fYX, 25.12.2024"
    }
    
    example = examples.get(data['template'], "Проверьте правильность введенных данных")
    
    await message.answer(
        f"📋 Подтвердите отправку:\n\n"
        f"📧 Email: {data['email']}\n"
        f"📝 Шаблон: {data['template']}\n"
        f"📂 Категория: {data['category']}\n"
        f"👤 Данные: {data['user_data']}\n\n"
        f"💡 Пример: {example}\n\n"
        f"Вы действительно хотите отправить письмо?",
        reply_markup=confirmation_keyboard()
    )
    await ReportStates.confirmation.set()

@dp.callback_query_handler(lambda c: c.data == 'confirm_send', state=ReportStates.confirmation)
async def confirm_send(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение отправки"""
    data = await state.get_data()
    user_id = callback.from_user.id
    
    # Проверка лимитов
    user_data = get_user_db(user_id)
    if not user_data:
        await bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text="❌ Ошибка базы данных"
        )
        await state.finish()
        return
    
    reports_available, is_premium, total_sent = user_data
    
    if not is_premium and reports_available <= 0:
        await bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text="❌ У вас нет доступных доносов."
        )
        await state.finish()
        return
    
    # Отправка письма
    try:
        success = await send_email(
            data['email'], 
            data['template'], 
            data['user_data'], 
            data['category']
        )
        
        if success:
            # Обновление статистики
            update_user_reports(user_id, decrement=not is_premium)
            log_email_sent(user_id, data['template'], data['email'], "success")
            
            new_reports = reports_available - 1 if not is_premium else '∞'
            
            await bot.edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                text=f"✅ Письмо успешно отправлено!\n\n"
                     f"📧 Получатель: {data['email']}\n"
                     f"📝 Шаблон: {data['template']}\n"
                     f"🔄 Осталось доносов: {new_reports}"
            )
        else:
            log_email_sent(user_id, data['template'], data['email'], "failed")
            await bot.edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                text="❌ Ошибка при отправке письма"
            )
            
    except Exception as e:
        logger.error(f"Send email error: {e}")
        await bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=f"❌ Ошибка: {str(e)}"
        )
    
    await state.finish()

# Обработчики отмены и возврата
@dp.callback_query_handler(lambda c: c.data == 'cancel_send', state='*')
async def cancel_send(callback: types.CallbackQuery, state: FSMContext):
    """Отмена отправки"""
    await state.finish()
    await bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text="❌ Отправка отменена.",
        reply_markup=main_menu()
    )

@dp.callback_query_handler(lambda c: c.data == 'back_main', state='*')
async def back_main(callback: types.CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.finish()
    await bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text="👋 Добро пожаловать в SMTP Bot!\n\nВыберите действие:",
        reply_markup=main_menu()
    )

@dp.callback_query_handler(lambda c: c.data == 'back_categories', state='*')
async def back_categories(callback: types.CallbackQuery, state: FSMContext):
    """Возврат к категориям"""
    await bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text="🎯 Выберите категорию доноса:",
        reply_markup=categories_menu()
    )
    await ReportStates.choosing_category.set()

# Профиль и реферальная система
@dp.callback_query_handler(lambda c: c.data == 'profile')
async def show_profile(callback: types.CallbackQuery):
    """Показать профиль"""
    user_id = callback.from_user.id
    user_data = get_user_db(user_id)
    
    if user_data:
        reports_available, is_premium, total_sent = user_data
        
        premium_status = "✅ АКТИВНА" if is_premium else "❌ Не активна"
        reports_display = '∞' if is_premium else reports_available
        
        profile_text = (
            f"👤 Ваш профиль:\n\n"
            f"💎 Премиум подписка: {premium_status}\n"
            f"📊 Доступно доносов: {reports_display}\n"
            f"📨 Всего отправлено: {total_sent}\n"
            f"🆔 ID: {user_id}"
        )
        
        await bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=profile_text,
            reply_markup=main_menu()
        )

@dp.callback_query_handler(lambda c: c.data == 'referral')
async def show_referral(callback: types.CallbackQuery):
    """Реферальная система"""
    user_id = callback.from_user.id
    
    try:
        bot_user = await bot.get_me()
        referral_link = f"https://t.me/{bot_user.username}?start={user_id}"
        
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users WHERE referred_by = ?', (user_id,))
        referrals_count = cursor.fetchone()[0]
        conn.close()
        
        referral_text = (
            f"📊 Реферальная система\n\n"
            f"🔗 Ваша ссылка:\n`{referral_link}`\n\n"
            f"👥 Приглашено пользователей: {referrals_count}\n\n"
            f"💎 За каждого приглашенного:\n"
            f"• +1 бесплатный донос\n"
            f"• Бонус для нового пользователя"
        )
        
        await bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=referral_text,
            parse_mode="Markdown",
            reply_markup=main_menu()
        )
    except Exception as e:
        logger.error(f"Referral system error: {e}")

@dp.callback_query_handler(lambda c: c.data == 'subscription')
async def show_subscription(callback: types.CallbackQuery):
    """Информация о подписке"""
    subscription_text = (
        "💎 Премиум подписка\n\n"
        "🚀 Безлимитные доносы\n"
        "⚡ Приоритетная отправка\n"
        "🔒 Максимальная анонимность\n"
        "📧 Доступ ко всем SMTP-аккаунтам\n\n"
        "💳 Для оформления обратитесь к администратору @BloodyLofiPro_bot"
    )
    
    await bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text=subscription_text,
        reply_markup=main_menu()
    )

# Админ-панель
@dp.callback_query_handler(lambda c: c.data == 'admin_panel')
async def admin_panel_callback(callback: types.CallbackQuery):
    """Админ-панель"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return
    
    await bot.edit_message_text(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        text="👑 Панель администратора:",
        reply_markup=admin_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data == 'admin_give_sub')
async def admin_give_sub(callback: types.CallbackQuery, state: FSMContext):
    """Выдача подписки через админ-панель"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        return
    
    await callback.message.answer("Введите ID пользователя для выдачи подписки:")
    await state.set_state("admin_wait_user_id")

@dp.message_handler(state="admin_wait_user_id")
async def admin_process_user_id(message: types.Message, state: FSMContext):
    """Обработка ID пользователя для выдачи подписки"""
    try:
        target_user_id = int(message.text)
        
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_premium = TRUE WHERE user_id = ?', (target_user_id,))
        conn.commit()
        conn.close()
        
        await message.answer(f"✅ Пользователю {target_user_id} выдана премиум подписка!")
        
        # Уведомление пользователя
        try:
            await bot.send_message(
                target_user_id,
                "🎉 Вам выдана ПРЕМИУМ ПОДПИСКА!\n\n"
                "Теперь у вас:\n"
                "✅ Безлимитные доносы\n"
                "⚡ Приоритетная отправка\n"
                "🔒 Максимальная анонимность"
            )
        except Exception:
            pass
            
    except ValueError:
        await message.answer("❌ Неверный ID пользователя")
    
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'admin_stats')
async def admin_stats_callback(callback: types.CallbackQuery):
    """Статистика через админ-панель"""
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS:
        return
    
    await stats_command(callback.message)

# Функция отправки email
async def send_email(to_email, template_name, user_data, category):
    """Отправка email через SMTP"""
    try:
        # Выбор случайного email из доступных
        email, password = random.choice(list(EMAILS.items()))
        
        # Получение шаблона
        template_text = TEMPLATES[category][template_name]
        
        # Парсинг данных пользователя
        parsed_data = parse_user_data(user_data, category, template_name)
        
        # Замена переменных в шаблоне
        message_text = template_text
        for key, value in parsed_data.items():
            message_text = message_text.replace(f"{{{key}}}", value)
        
        # Создание сообщения
        msg = MIMEMultipart()
        msg['From'] = email
        msg['To'] = to_email
        msg['Subject'] = f"Срочное сообщение - {template_name}"
        
        msg.attach(MIMEText(message_text, 'plain', 'utf-8'))
        
        # Отправка через SMTP
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(email, password)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Email sent successfully from {email} to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"SMTP error: {e}")
        return False

# Функция парсинга данных пользователя
def parse_user_data(user_data, category, template_name):
    """Парсинг данных для ВСЕХ категорий"""
    parts = [part.strip() for part in user_data.split(',')]
    parsed = {}
    
    parsing_templates = {
        "school": {
            "Донос на ученика": ['школа', 'фио_директора', 'класс', 'фио_ученика', 'дата', 'описание_инцидента'],
            "Жалоба на учителя": ['школа', 'фио_родителя', 'класс', 'фио_ученика', 'фио_учителя', 'дата', 'описание_инцидента', 'телефон'],
            "Перевод в другую школу": ['фио', 'класс', 'школа', 'телефон', 'фио_родителя'],
            "Фальшивый карантин": ['школа', 'заболевание', 'класс', 'фио', 'дата', 'медицинское_учреждение', 'период', 'список_помещений', 'дни', 'телефон', 'фио_врача'],
            "Подставной роман": ['фио_учителя', 'дата', 'срок', 'телефон', 'время_начала', 'время_конца', 'анонимное_имя'],
            "Вымогательство": ['фио_учителя', 'фио_ученика', 'класс', 'сумма', 'дата', 'номер_карты', 'фио_получателя'],
            "Фейковое мероприятие": ['школа', 'класс', 'дата', 'время', 'место', 'фио_учителя', 'фио_директора', 'телефон']
        },
        "swatting": {
            "Минирование школы": ['адрес', 'время'],
            "Захват заложников": ['адрес', 'требования', 'телефон'],
            "Вооруженное нападение": ['адрес', 'время']
        },
        "corporate": {
            "Увольнение": ['фио_сотрудника', 'компания', 'причина_увольнения', 'дата', 'телефон_отдела'],
            "Премия": ['фио_сотрудника', 'компания', 'сумма', 'дата', 'номер_приказа', 'дата_приказа'],
            "Аудит": ['отдел', 'дата', 'время', 'фио_проверяющих', 'причина_проверки']
        },
        "personal": {
            "Шантаж отношениями": ['фио_цели', 'фио_партнера', 'требования', 'дата'],
            "Беременность": ['фио_мужчины', 'срок', 'дата', 'телефон', 'анонимное_имя'],
            "Долг": ['фио_должника', 'сумма', 'дата', 'телефон_кредитора', 'реквизиты']
        },
        "government": {
            "Налоги": ['фио', 'адрес', 'сумма', 'дата', 'телефон_инспекции'],
            "Штрафы ГИБДД": ['фио', 'номер_авто', 'нарушение', 'сумма', 'дата', 'номер_протокола', 'фио_инспектора'],
            "Повестка в суд": ['фио', 'дата', 'время', 'адрес_суда', 'причина', 'кабинет', 'фио_судьи', 'номер_дела']
        },
        "crypto": {
            "Вымогательство биткоин": ['сумма_btc', 'btc_адрес', 'дата'],
            "Майнинг": ['сумма', 'кошелек'],
            "Блокировка кошелька": ['кошелек', 'причина', 'сумма', 'кошелек_оплаты', 'дата']
        }
    }
    
    # Заполнение данных по шаблону
    template_fields = parsing_templates.get(category, {}).get(template_name, [])
    for i, field in enumerate(template_fields):
        if i < len(parts):
            parsed[field] = parts[i]
        else:
            parsed[field] = "[не указано]"
    
    # Заполнение недостающих переменных
    template_text = TEMPLATES[category][template_name]
    variables = re.findall(r'\{(\w+)\}', template_text)
    for var in variables:
        if var not in parsed:
            parsed[var] = "[не указано]"
    
    return parsed

# Обработка ошибок
@dp.errors_handler()
async def errors_handler(update, exception):
    """Глобальный обработчик ошибок"""
    logger.error(f"Update {update} caused error {exception}")
    return True

# Запуск бота
if __name__ == '__main__':
    logger.info("Starting bot...")
    try:
        executor.start_polling(dp, skip_updates=True)
    except Exception as e:
        logger.error(f"Bot startup error: {e}")
