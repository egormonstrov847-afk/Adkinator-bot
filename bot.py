import logging
import random
import asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# --- Настройки ---
BOT_TOKEN = "8200150971:AAGbqJ2IHsgnhv3cdmvAkWmMfHMWg5NASFI"  # ЗАМЕНИТЕ НА ВАШ ТОКЕН

# Убираем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.WARNING
)

# --- Жуткие китайские слова про смерть ---
CHINESE_HORROR_WORDS = [
    "死", "死亡", "鬼", "幽灵", "地狱", "恶魔", "诅咒", "尸体", "坟墓", 
    "血腥", "恐怖", "黑暗", "灵魂", "噩梦", "痛苦", "折磨", "毁灭"
]

# --- Состояния ---
PLAYING = 1
user_sessions = {}

# --- СПЕЦИАЛЬНЫЕ ВОПРОСЫ ---
special_questions = [
    {
        'question': 'В твоем здании потух свет кто там?',
        'answers': ['Не знаю', 'Призрак', 'Ты'],
        'follow_up': None
    },
    {
        'question': 'Став призраком, кому ты устроишь ужас?',
        'answers': ['Родным и близким', 'друзьям и подругам'],
        'follow_up': None
    },
    {
        'question': 'В ванной, есть зеркало, а в нем появилось отражение, проверишь?',
        'answers': ['Нет', 'Не хочу', 'Да'],
        'follow_up': None
    },
    {
        'question': 'Я вижу твой испуг... как думаешь я знаю где ты?)',
        'answers': ['нет конечно', 'я боюсь тебя'],
        'follow_up': None
    },
    {
        'question': 'ЗАЧЕМ ТЫ ПОДСМАТРИВАЛ ЗА ЧЕЛОВЕКОМ?!',
        'answers': ['Это ложь', 'откуда ты знаешь'],
        'follow_up': {
            'question': 'Фу, тебе не мерзко? я же все знаю!',
            'answers': ['ты говоришь ложь', 'ладно это правда']
        }
    }
]

def load_questions(filename):
    """Загружает вопросы из файла"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            questions = [line.strip() for line in f if line.strip()]
        return questions
    except FileNotFoundError:
        print(f"Файл {filename} не найден!")
        return []

# Загружаем все уровни вопросов
normal_questions_level1 = load_questions('questions_normal_level1.txt')
normal_questions_level2 = load_questions('questions_normal_level2.txt') 
normal_questions_level3 = load_questions('questions_normal_level3.txt')
penalty_questions = load_questions('questions_penalty.txt')

def get_current_level_questions(total_questions):
    """Определяет уровень вопросов в зависимости от прогресса"""
    if total_questions < 20:
        return normal_questions_level1, "🌙"
    elif total_questions < 45:
        return normal_questions_level2, "👻"
    else:
        return normal_questions_level3, "💀"

def get_user_session(user_id):
    """Получает или создает сессию пользователя"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'lives': 3,
            'consecutive_answers': {'да': 0, 'нет': 0},
            'used_normal_questions': set(),
            'used_penalty_questions': set(),
            'used_special_questions': set(),
            'in_penalty': False,
            'penalty_questions_asked': 0,
            'total_questions_asked': 0,
            'current_special_question': None,
            'waiting_for_follow_up': False,
            'last_level': 1
        }
    return user_sessions[user_id]

def generate_chinese_horror_text():
    """Генерирует жуткий китайский текст"""
    return ''.join(random.choices(CHINESE_HORROR_WORDS, k=random.randint(3, 8)))

async def send_chinese_transition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет иероглифы при смене уровня"""
    horror_text = generate_chinese_horror_text()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"🔀 {horror_text}"
    )
    await asyncio.sleep(1)

async def start_chinese_spam(update: Update, context: ContextTypes.DEFAULT_TYPE, duration: int = 30):
    """Спамит жуткими китайскими сообщениями"""
    chat_id = update.effective_chat.id
    end_time = asyncio.get_event_loop().time() + duration
    
    try:
        while asyncio.get_event_loop().time() < end_time:
            horror_text = generate_chinese_horror_text()
            await context.bot.send_message(chat_id=chat_id, text=horror_text)
            await asyncio.sleep(random.uniform(0.1, 0.3))
            
    except Exception:
        pass
    
    await context.bot.send_message(
        chat_id=chat_id,
        text="💀 СИСТЕМА ВОССТАНОВЛЕНА...\n\n/start - если осмелишься вернуться",
        reply_markup=ReplyKeyboardMarkup([["/start"]], resize_keyboard=True)
    )

async def ask_special_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Задает специальный вопрос с разными вариантами ответов"""
    user_id = update.message.from_user.id
    session = get_user_session(user_id)
    
    available_special = set(range(len(special_questions))) - session['used_special_questions']
    
    if not available_special:
        return await ask_question(update, context)
    
    question_index = random.choice(list(available_special))
    session['used_special_questions'].add(question_index)
    special_q = special_questions[question_index]
    
    session['current_special_question'] = special_q
    session['waiting_for_follow_up'] = False
    
    keyboard = [[answer] for answer in special_q['answers']]
    markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    
    await update.message.reply_text(
        f"🎭 {special_q['question']}",
        reply_markup=markup
    )

async def handle_special_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ответы на специальные вопросы"""
    user_id = update.message.from_user.id
    session = get_user_session(user_id)
    user_answer = update.message.text.strip()
    
    if not session['current_special_question']:
        return await handle_answer(update, context)
    
    current_q = session['current_special_question']
    
    if session['waiting_for_follow_up'] and current_q['follow_up']:
        follow_up_q = current_q['follow_up']
        
        follow_up_reactions = {
            'ты говоришь ложь': [
                "Я ВСЕГДА ПРАВ! Ты пытаешься обмануть себя...",
                "Отрицание - первый шаг к безумию..."
            ],
            'ладно это правда': [
                "Признание... какой смелый шаг...",
                "Наконец-то правда... но теперь я знаю твою тайну..."
            ]
        }
        
        if user_answer in follow_up_reactions:
            reaction = random.choice(follow_up_reactions[user_answer])
            await update.message.reply_text(reaction)
        
        session['waiting_for_follow_up'] = False
        session['current_special_question'] = None
        
    else:
        reactions = {
            'Не знаю': "Незнание не спасет тебя от того, что придет...",
            'Призрак': "Призраки существуют... и один из них сейчас за твоей спиной...",
            'Ты': "Правильно... я уже в твоем доме...",
            'Родным и близким': "Как предсказуемо... кровные узы всегда рвутся первыми...",
            'друзьям и подругам': "Дружба... такое хрупкое понятие... идеально для разрушения...",
            'Нет': "Мудрое решение... некоторые отражения лучше не тревожить...",
            'Не хочу': "Страх сохранит тебе жизнь... на время...",
            'Да': "Смельчак... надеюсь, тебе понравится то, что ты увидишь...",
            'нет конечно': "Ошибаешься... я вижу каждое твое движение...",
            'я боюсь тебя': "Страх - это разумно... он продлит твою агонию...",
            'Это ложь': "Ложь? Я видел тебя... в тот вечер... у окна...",
            'откуда ты знаешь': "Я знаю все... каждую твою мысль... каждый грех..."
        }
        
        if user_answer in reactions:
            await update.message.reply_text(reactions[user_answer])
        
        if current_q['follow_up'] and not session['waiting_for_follow_up']:
            session['waiting_for_follow_up'] = True
            follow_up_q = current_q['follow_up']
            
            keyboard = [[answer] for answer in follow_up_q['answers']]
            markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
            
            await update.message.reply_text(
                f"🎭 {follow_up_q['question']}",
                reply_markup=markup
            )
            return PLAYING
    
    session['current_special_question'] = None
    await ask_question(update, context)
    return PLAYING

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начинает игру"""
    user = update.message.from_user
    user_id = user.id
    session = get_user_session(user_id)

    # Сброс сессии
    session.update({
        'lives': 3,
        'consecutive_answers': {'да': 0, 'нет': 0},
        'used_normal_questions': set(),
        'used_penalty_questions': set(),
        'used_special_questions': set(),
        'in_penalty': False,
        'penalty_questions_asked': 0,
        'total_questions_asked': 0,
        'current_special_question': None,
        'waiting_for_follow_up': False,
        'last_level': 1
    })

    welcome_text = (
        f"Привет, {user.first_name}... Я АДкинатор.\n"
        "Игра начинается спокойно... но с каждым вопросом\n"
        "тьма будет сгущаться... готов ли ты к погружению?\n\n"
        "*Уровни ужаса:*\n"
        "🌙 1-20: Легкие вопросы\n"
        "👻 21-45: Страшные вопросы  \n"
        "💀 46-70: Кошмарные вопросы\n\n"
        "Начнем с малого..."
    )
    
    markup = ReplyKeyboardMarkup([["ДА", "НЕТ"]], one_time_keyboard=False, resize_keyboard=True)
    await update.message.reply_text(welcome_text, reply_markup=markup, parse_mode='Markdown')
    
    await ask_question(update, context)
    return PLAYING

async def ask_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Задает случайный вопрос с прогрессией"""
    user_id = update.message.from_user.id
    session = get_user_session(user_id)
    
    # Проверка на конец игры
    if session['total_questions_asked'] >= 70:
        await update.message.reply_text("*Ты дошел до конца... но это только начало...*", parse_mode='Markdown')
        await start_chinese_spam(update, context, duration=20)
        return await end_game(update, context)
    
    # Определяем текущий уровень
    current_questions, level_icon = get_current_level_questions(session['total_questions_asked'])
    current_level = 1 if session['total_questions_asked'] < 20 else 2 if session['total_questions_asked'] < 45 else 3
    
    # Проверяем смену уровня
    if current_level != session['last_level']:
        await send_chinese_transition(update, context)
        level_messages = {
            2: "🌑 Тьма сгущается... вопросы становятся страшнее...",
            3: "💀 Погружение в кошмар... добро пожаловать в ад..."
        }
        if current_level in level_messages:
            await update.message.reply_text(level_messages[current_level])
        session['last_level'] = current_level
    
    # 15% шанс специального вопроса (только с уровня 2)
    if current_level >= 2 and random.random() < 0.15 and len(session['used_special_questions']) < len(special_questions):
        return await ask_special_question(update, context)
    
    # Обычная логика вопросов
    if session['in_penalty']:
        available_questions = set(range(len(penalty_questions))) - session['used_penalty_questions']
        if not available_questions:
            session['in_penalty'] = False
            session['penalty_questions_asked'] = 0
            return await ask_question(update, context)
        
        question_index = random.choice(list(available_questions))
        session['used_penalty_questions'].add(question_index)
        question = penalty_questions[question_index]
        
    else:
        available_questions = set(range(len(current_questions))) - session['used_normal_questions']
        if not available_questions:
            # Если вопросы закончились, переходим на следующий уровень
            session['used_normal_questions'] = set()
            return await ask_question(update, context)
        
        question_index = random.choice(list(available_questions))
        session['used_normal_questions'].add(question_index)
        question = current_questions[question_index]
    
    session['total_questions_asked'] += 1
    
    # Клавиатура ДА/НЕТ
    markup = ReplyKeyboardMarkup([["ДА", "НЕТ"]], one_time_keyboard=False, resize_keyboard=True)
    await update.message.reply_text(
        f"{level_icon} *Вопрос {session['total_questions_asked']}/70:*\n{question}", 
        reply_markup=markup, 
        parse_mode='Markdown'
    )

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ответы ДА/НЕТ"""
    user_id = update.message.from_user.id
    session = get_user_session(user_id)
    user_answer = update.message.text.strip().lower()

    if session['current_special_question'] or session['waiting_for_follow_up']:
        return await handle_special_answer(update, context)

    if user_answer not in ['да', 'нет']:
        await update.message.reply_text("Только ДА или НЕТ. Выбора нет.")
        return PLAYING

    # Стандартная логика для ДА/НЕТ
    session['consecutive_answers'][user_answer] += 1
    opposite_answer = 'нет' if user_answer == 'да' else 'да'
    session['consecutive_answers'][opposite_answer] = 0

    if session['consecutive_answers'][user_answer] >= 3:
        session['lives'] -= 1
        session['consecutive_answers'][user_answer] = 0

        if session['lives'] <= 0:
            await update.message.reply_text("Game Over - тьма поглощает тебя...")
            await start_chinese_spam(update, context, duration=30)
            return await end_game(update, context)
        else:
            await update.message.reply_text(
                f"*Слишком предсказуемо...* Жизнь потеряна. Осталось: {session['lives']}",
                parse_mode='Markdown'
            )

    # Проверка на "ложь"
    is_lying = random.random() < 0.25
    if is_lying and not session['in_penalty']:
        session['in_penalty'] = True
        await update.message.reply_text("Ты солгал... *Добро пожаловать в штрафную игру!*", parse_mode='Markdown')
    
    await ask_question(update, context)
    return PLAYING

async def end_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершает игру"""
    user_id = update.message.from_user.id
    if user_id in user_sessions:
        del user_sessions[user_id]
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет игру"""
    user = update.message.from_user
    await update.message.reply_text("Ты сбежал... но тьма следует за тобой...")
    await start_chinese_spam(update, context, duration=15)
    
    user_id = user.id
    if user_id in user_sessions:
        del user_sessions[user_id]
        
    return ConversationHandler.END

def main():
    """Запускает бота"""
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            PLAYING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_answer),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    
    print("🎭 АДкинатор запущен с прогрессирующим ужасом!")
    print("🌙 → 👻 → 💀 Вопросы будут становиться страшнее!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()