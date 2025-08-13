# main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ChatMemberStatus
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import json
import random
import string
from datetime import datetime, timedelta
import calendar

# Configure logging
logging.basicConfig(level=logging.INFO)

# Bot configuration
BOT_TOKEN = "8054152301:AAEfPGb7sLSYfAzTTbmUsVQW72qiIb8cWGw"  # Replace with your bot token

# Channel and admin configuration
REQUIRED_CHANNEL = "@saidjamolyakubov"  # Majburiy kanal username
ADMIN_ID = 7377694590  # Yagona admin ID

# Helper function to check if user is admin
def is_admin(user_id):
    return user_id == ADMIN_ID

# Helper function to check channel membership
async def check_channel_membership(user_id):
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=user_id)
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except Exception as e:
        logging.error(f"Error checking membership for user {user_id}: {e}")
        return False

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Timer settings
QUESTION_TIMEOUT = 15  # 15 seconds for each question
active_timers = {}  # Store active question timers

# States for FSM
class QuizCreation(StatesGroup):
    waiting_for_quiz_name = State()
    waiting_for_question_count = State()
    waiting_for_question = State()
    waiting_for_variants = State()
    waiting_for_correct_answer = State()

class QuizTaking(StatesGroup):
    waiting_for_name = State()
    taking_quiz = State()

# Data storage (in production, use a database)
quizzes = {}
quiz_results = {}
users = {}
bi_weekly_rankings = {}  # Store bi-weekly ranking data

class BiWeeklyManager:
    @staticmethod
    def get_current_bi_week():
        """Get current bi-weekly period"""
        now = datetime.now()
        year = now.year
        
        # Calculate which bi-week of the year we're in
        start_of_year = datetime(year, 1, 1)
        days_passed = (now - start_of_year).days
        bi_week_number = (days_passed // 14) + 1
        
        return f"{year}-BW{bi_week_number:02d}"
    
    @staticmethod
    def get_bi_week_dates(bi_week_id):
        """Get start and end dates for a bi-weekly period"""
        year, bw_part = bi_week_id.split('-BW')
        year = int(year)
        bi_week_num = int(bw_part)
        
        start_of_year = datetime(year, 1, 1)
        bi_week_start = start_of_year + timedelta(days=(bi_week_num - 1) * 14)
        bi_week_end = bi_week_start + timedelta(days=13, hours=23, minutes=59, seconds=59)
        
        return bi_week_start, bi_week_end
    
    @staticmethod
    def update_bi_weekly_ranking(user_id, user_name, username, score, total, quiz_name):
        """Update bi-weekly ranking for a user"""
        current_bi_week = BiWeeklyManager.get_current_bi_week()
        
        if current_bi_week not in bi_weekly_rankings:
            bi_weekly_rankings[current_bi_week] = {}
        
        if user_id not in bi_weekly_rankings[current_bi_week]:
            bi_weekly_rankings[current_bi_week][user_id] = {
                'name': user_name,
                'username': username,
                'total_score': 0,
                'total_questions': 0,
                'quiz_count': 0,
                'quizzes': [],
                'first_attempt': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        
        user_data = bi_weekly_rankings[current_bi_week][user_id]
        user_data['name'] = user_name  # Update name in case it changed
        user_data['username'] = username  # Update username
        user_data['total_score'] += score
        user_data['total_questions'] += total
        user_data['quiz_count'] += 1
        user_data['quizzes'].append({
            'quiz_name': quiz_name,
            'score': score,
            'total': total,
            'percentage': round((score/total)*100, 1),
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        user_data['last_attempt'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        user_data['average_percentage'] = round((user_data['total_score']/user_data['total_questions'])*100, 1)
    
    @staticmethod
    def get_current_bi_weekly_ranking():
        """Get current bi-weekly ranking sorted by performance"""
        current_bi_week = BiWeeklyManager.get_current_bi_week()
        
        if current_bi_week not in bi_weekly_rankings:
            return []
        
        ranking_data = []
        for user_id, data in bi_weekly_rankings[current_bi_week].items():
            ranking_data.append({
                'user_id': user_id,
                'name': data['name'],
                'username': data['username'],
                'total_score': data['total_score'],
                'total_questions': data['total_questions'],
                'quiz_count': data['quiz_count'],
                'average_percentage': data['average_percentage'],
                'quizzes': data['quizzes']
            })
        
        # Sort by average percentage (descending), then by total score (descending)
        ranking_data.sort(key=lambda x: (x['average_percentage'], x['total_score']), reverse=True)
        return ranking_data
    
    @staticmethod
    def get_previous_bi_weekly_ranking():
        """Get previous bi-weekly ranking"""
        current_bi_week = BiWeeklyManager.get_current_bi_week()
        year, bw_part = current_bi_week.split('-BW')
        year = int(year)
        bi_week_num = int(bw_part)
        
        if bi_week_num > 1:
            prev_bi_week = f"{year}-BW{bi_week_num-1:02d}"
        else:
            prev_bi_week = f"{year-1}-BW26"  # Last bi-week of previous year
        
        if prev_bi_week not in bi_weekly_rankings:
            return []
        
        ranking_data = []
        for user_id, data in bi_weekly_rankings[prev_bi_week].items():
            ranking_data.append({
                'user_id': user_id,
                'name': data['name'],
                'username': data['username'],
                'average_percentage': data['average_percentage'],
                'total_score': data['total_score'],
                'quiz_count': data['quiz_count']
            })
        
        ranking_data.sort(key=lambda x: (x['average_percentage'], x['total_score']), reverse=True)
        return ranking_data
    
    @staticmethod
    def compare_rankings():
        """Compare current and previous bi-weekly rankings"""
        current_ranking = BiWeeklyManager.get_current_bi_weekly_ranking()
        previous_ranking = BiWeeklyManager.get_previous_bi_weekly_ranking()
        
        # Create position maps
        current_positions = {user['user_id']: i+1 for i, user in enumerate(current_ranking)}
        previous_positions = {user['user_id']: i+1 for i, user in enumerate(previous_ranking)}
        
        comparison = []
        for user in current_ranking:
            user_id = user['user_id']
            current_pos = current_positions[user_id]
            previous_pos = previous_positions.get(user_id, None)
            
            if previous_pos is None:
                change = "🆕 Yangi"
            elif current_pos < previous_pos:
                change = f"📈 +{previous_pos - current_pos}"
            elif current_pos > previous_pos:
                change = f"📉 -{current_pos - previous_pos}"
            else:
                change = "➡️ O'zgarish yo'q"
            
            comparison.append({
                'user': user,
                'current_position': current_pos,
                'previous_position': previous_pos,
                'change': change
            })
        
        return comparison

class QuizTimer:
    @staticmethod
    async def start_question_timer(user_id, state: FSMContext):
        """Start timer for current question"""
        # Cancel existing timer if any
        await QuizTimer.cancel_timer(user_id)
        
        # Create new timer
        timer_task = asyncio.create_task(QuizTimer.question_timeout(user_id, state))
        active_timers[user_id] = timer_task
        
        return timer_task
    
    @staticmethod
    async def cancel_timer(user_id):
        """Cancel active timer for user"""
        if user_id in active_timers:
            timer_task = active_timers[user_id]
            if not timer_task.done():
                timer_task.cancel()
            del active_timers[user_id]
    
    @staticmethod
    async def question_timeout(user_id, state: FSMContext):
        """Handle question timeout"""
        try:
            await asyncio.sleep(QUESTION_TIMEOUT)
            
            # Check if user is still taking quiz
            current_state = await state.get_state()
            if current_state == QuizTaking.taking_quiz.state:
                data = await state.get_data()
                quiz = data['quiz']
                current_question = data['current_question']
                answers = data.get('answers', [])
                score = data.get('score', 0)
                
                # Mark current question as unanswered
                answers.append({
                    'question': quiz['questions'][current_question]['question'],
                    'selected': None,  # No answer selected
                    'correct': quiz['questions'][current_question]['correct_answer'],
                    'is_correct': False,
                    'timeout': True
                })
                
                current_question += 1
                
                if current_question < len(quiz['questions']):
                    # Move to next question
                    question = quiz['questions'][current_question]
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text=f"A) {question['variants'][0]}", callback_data="answer_0")],
                        [InlineKeyboardButton(text=f"B) {question['variants'][1]}", callback_data="answer_1")],
                        [InlineKeyboardButton(text=f"C) {question['variants'][2]}", callback_data="answer_2")]
                    ])
                    
                    await bot.edit_message_text(
                        chat_id=user_id,
                        message_id=data.get('current_message_id'),
                        text=f"⏰ Vaqt tugadi! Keyingi savol...\n\n"
                             f"📝 {current_question + 1}-savol {len(quiz['questions'])} dan:\n"
                             f"⏳ {QUESTION_TIMEOUT} soniya\n\n"
                             f"{question['question']}",
                        reply_markup=keyboard
                    )
                    
                    await state.update_data(
                        current_question=current_question,
                        answers=answers,
                        score=score
                    )
                    
                    # Start timer for next question
                    await QuizTimer.start_question_timer(user_id, state)
                else:
                    # Quiz finished
                    await QuizTimer.finish_quiz(user_id, state, data, answers, score)
        
        except asyncio.CancelledError:
            # Timer was cancelled, ignore
            pass
        except Exception as e:
            logging.error(f"Timer error for user {user_id}: {e}")
    
    @staticmethod
    async def finish_quiz(user_id, state: FSMContext, data, answers, score):
        """Finish quiz and show results"""
        try:
            quiz_code = data['quiz_code']
            user_name = data['user_name']
            quiz = data['quiz']
            total_questions = len(quiz['questions'])
            
            # Get user info
            try:
                user_info = await bot.get_chat(user_id)
                username = user_info.username
            except:
                username = None
            
            # Save result
            QuizManager.save_result(
                quiz_code, user_name, user_id, username, score, total_questions, answers
            )
            
            # Calculate statistics
            answered_count = sum(1 for answer in answers if not answer.get('timeout', False))
            timeout_count = total_questions - answered_count
            percentage = round((score/total_questions) * 100, 1)
            
            # Show results to user
            result_text = f"🎉 Test tugatildi!\n\n"
            result_text += f"👤 Ism: {user_name}\n"
            result_text += f"📊 Ball: {score}/{total_questions}\n"
            result_text += f"📈 Foiz: {percentage}%\n"
            result_text += f"✅ Javob berildi: {answered_count}\n"
            result_text += f"⏰ Vaqt tugadi: {timeout_count}\n\n"
            
            if score == total_questions:
                result_text += "🏆 Mukammal ball! Tabriklaymiz!"
            elif score >= total_questions * 0.8:
                result_text += "🎯 Ajoyib ish! Zo'r natija!"
            elif score >= total_questions * 0.6:
                result_text += "👍 Yaxshi ish! Davom eting!"
            else:
                result_text += "📚 O'qishni davom ettiring va qayta urinib ko'ring!"
            
            result_text += f"\n\n🏆 Ikki haftalik reytingga qo'shildi!"
            
            await bot.send_message(user_id, result_text)
            
            # Send results to admin
            current_ranking = BiWeeklyManager.get_current_bi_weekly_ranking()
            user_position = None
            for i, user in enumerate(current_ranking, 1):
                if user['user_id'] == user_id:
                    user_position = i
                    break
            
            admin_text = f"📊 Yangi Test Natijasi!\n\n"
            admin_text += f"🎯 Test: {quiz['name']}\n"
            admin_text += f"👤 Talaba: {user_name}\n"
            if username:
                admin_text += f"📱 Username: @{username}\n"
            else:
                admin_text += f"📱 Username yo'q\n"
            admin_text += f"🆔 ID: {user_id}\n"
            admin_text += f"📊 Ball: {score}/{total_questions} ({percentage}%)\n"
            admin_text += f"✅ Javob berildi: {answered_count}\n"
            admin_text += f"⏰ Vaqt tugadi: {timeout_count}\n"
            admin_text += f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            
            if user_position:
                admin_text += f"\n🏆 Ikki haftalik reytingda: {user_position}-o'rin"
            
            # Send to admin
            try:
                await bot.send_message(ADMIN_ID, admin_text)
            except Exception as e:
                logging.error(f"Failed to send message to admin {ADMIN_ID}: {e}")
            
            # Clean up
            await QuizTimer.cancel_timer(user_id)
            await state.clear()
            
        except Exception as e:
            logging.error(f"Error finishing quiz for user {user_id}: {e}")

class QuizManager:
    @staticmethod
    def generate_quiz_code():
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    @staticmethod
    def save_quiz(quiz_data):
        code = QuizManager.generate_quiz_code()
        while code in quizzes:
            code = QuizManager.generate_quiz_code()
        quizzes[code] = quiz_data
        return code
    
    @staticmethod
    def get_quiz(code):
        return quizzes.get(code)
    
    @staticmethod
    def has_user_taken_quiz(quiz_code, user_id):
        """Check if user has already taken this quiz"""
        if quiz_code not in quiz_results:
            return False
        
        for result in quiz_results[quiz_code]:
            if result['user_id'] == user_id:
                return True
        return False
    
    @staticmethod
    def save_result(quiz_code, user_name, user_id, username, score, total, answers):
        if quiz_code not in quiz_results:
            quiz_results[quiz_code] = []
        
        result = {
            'user_name': user_name,
            'user_id': user_id,
            'username': username,
            'score': score,
            'total': total,
            'answers': answers,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        quiz_results[quiz_code].append(result)
        
        # Save user info
        users[user_id] = {
            'name': user_name,
            'username': username,
            'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Update bi-weekly ranking
        quiz_name = quizzes[quiz_code]['name']
        BiWeeklyManager.update_bi_weekly_ranking(user_id, user_name, username, score, total, quiz_name)

# Admin keyboard
def get_admin_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Test yaratish", callback_data="create_quiz")],
        [InlineKeyboardButton(text="📊 Testlar natijalari", callback_data="view_results")],
        [InlineKeyboardButton(text="🏆 Ikki haftalik reyting", callback_data="bi_weekly_ranking")],
        [InlineKeyboardButton(text="📈 Reyting taqqoslash", callback_data="compare_rankings")],
        [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="view_users")],
        [InlineKeyboardButton(text="🗂️ Testlarim", callback_data="my_quizzes")]
    ])
    return keyboard

# Quiz selection keyboard for results
def get_quiz_selection_keyboard():
    keyboard = []
    for code, quiz in quizzes.items():
        keyboard.append([InlineKeyboardButton(
            text=f"🎯 {quiz['name']} ({code})",
            callback_data=f"quiz_results_{code}"
        )])
    
    if not keyboard:
        return None
    
    keyboard.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Ranking keyboard
def get_ranking_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Joriy ikki hafta", callback_data="current_ranking")],
        [InlineKeyboardButton(text="📋 Oldingi ikki hafta", callback_data="previous_ranking")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_menu")]
    ])
    return keyboard

# Channel membership keyboard
def get_channel_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga qo'shilish", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}")],
        [InlineKeyboardButton(text="✅ A'zolikni tekshirish", callback_data="check_membership")]
    ])
    return keyboard

# Start command
@dp.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    # Clear any existing state and timer
    await state.clear()
    await QuizTimer.cancel_timer(message.from_user.id)
    
    if is_admin(message.from_user.id):
        await message.answer(
            "🎮 Admin panelga xush kelibsiz!\n\n"
            "Qanday ish qilmoqchisiz:",
            reply_markup=get_admin_keyboard()
        )
    else:
        # Check channel membership for regular users
        is_member = await check_channel_membership(message.from_user.id)
        if not is_member:
            await message.answer(
                "❌ Botdan foydalanish uchun avval kanalga qo'shiling!\n\n"
                f"📢 Kanal: {REQUIRED_CHANNEL}\n\n"
                "Qo'shilgandan keyin 'A'zolikni tekshirish' tugmasini bosing.",
                reply_markup=get_channel_keyboard()
            )
            return
        
        await message.answer(
            "🎮 Test Botga Xush kelibsiz!\n\n"
            "Test olish uchun quyidagi buyruqdan foydalaning:\n"
            "/quiz [CODE]\n\n"
            "Misol: /quiz ABC123\n\n"
            f"⏰ Har bir savol uchun {QUESTION_TIMEOUT} soniya vaqt beriladi!\n\n"
            "📊 Joriy reytingni ko'rish: /ranking\n\n"
            "Test yaratuvchisidan test kodini oling!"
        )

# Check membership callback
@dp.callback_query(lambda c: c.data == "check_membership")
async def check_membership_callback(callback: CallbackQuery):
    if is_admin(callback.from_user.id):
        await callback.answer("Siz adminsiz!", show_alert=True)
        return
    
    is_member = await check_channel_membership(callback.from_user.id)
    if is_member:
        await callback.message.edit_text(
            "✅ A'zolik tasdiqlandi! Endi test botdan foydalanishingiz mumkin.\n\n"
            "Test olish uchun quyidagi buyruqdan foydalaning:\n"
            "/quiz [CODE]\n\n"
            "Misol: /quiz ABC123\n\n"
            f"⏰ Har bir savol uchun {QUESTION_TIMEOUT} soniya vaqt beriladi!\n\n"
            "📊 Joriy reytingni ko'rish: /ranking"
        )
    else:
        await callback.answer("❌ Hali ham kanalga qo'shilmagansiz!", show_alert=True)
    
    await callback.answer()

# Quiz command for users
@dp.message(Command("quiz"))
async def quiz_command(message: types.Message, state: FSMContext):
    if is_admin(message.from_user.id):
        await message.answer("❌ Adminlar test ololmaydi. Testlarni boshqarish uchun menyudan foydalaning.")
        return
    
    # Check channel membership
    is_member = await check_channel_membership(message.from_user.id)
    if not is_member:
        await message.answer(
            "❌ Botdan foydalanish uchun avval kanalga qo'shiling!\n\n"
            f"📢 Kanal: {REQUIRED_CHANNEL}",
            reply_markup=get_channel_keyboard()
        )
        return
    
    # Cancel any existing timer
    await QuizTimer.cancel_timer(message.from_user.id)
    
    args = message.text.split()
    if len(args) != 2:
        await message.answer("❌ Iltimos, test kodini taqdim eting.\nMisol: /quiz ABC123")
        return
    
    quiz_code = args[1].upper()
    quiz = QuizManager.get_quiz(quiz_code)
    
    if not quiz:
        await message.answer("❌ Test topilmadi. Iltimos, kodni tekshiring.")
        return
    
    # Check if user has already taken this quiz
    if QuizManager.has_user_taken_quiz(quiz_code, message.from_user.id):
        # Get user's previous result
        user_result = None
        for result in quiz_results[quiz_code]:
            if result['user_id'] == message.from_user.id:
                user_result = result
                break
        
        if user_result:
            percentage = round((user_result['score']/user_result['total']) * 100, 1)
            await message.answer(
                f"❌ Siz bu testni allaqachon topshirgansiz!\n\n"
                f"🎯 Test: {quiz['name']}\n"
                f"👤 Ism: {user_result['user_name']}\n"
                f"📊 Sizning natijangiz: {user_result['score']}/{user_result['total']} ({percentage}%)\n"
                f"📅 Sana: {user_result['date']}\n\n"
                f"Har bir testni faqat bir marta topshirish mumkin!"
            )
        else:
            await message.answer("❌ Siz bu testni allaqachon topshirgansiz!")
        return
    
    await state.update_data(quiz_code=quiz_code, quiz=quiz)
    
    name_message = await message.answer(
        f"🎯 Testga xush kelibsiz: {quiz['name']}\n\n"
        f"📝 Savollar: {len(quiz['questions'])}\n"
        f"⏰ Har bir savol uchun {QUESTION_TIMEOUT} soniya vaqt\n\n"
        "Iltimos, to'liq ismingizni kiriting:"
    )
    
    # Store the message ID for reply
    await state.update_data(name_message_id=name_message.message_id)
    await state.set_state(QuizTaking.waiting_for_name)

# Handle ADMIN callbacks
@dp.callback_query(lambda c: is_admin(c.from_user.id))
async def handle_admin_callbacks(callback: CallbackQuery, state: FSMContext):
    if callback.data == "create_quiz":
        # Clear any existing state
        await state.clear()
        
        quiz_name_message = await callback.message.edit_text(
            "📝 Yangi test yaratilyapti...\n\n"
            "Iltimos, test nomini kiriting:",
            reply_markup=None
        )
        
        # Store message ID for reply functionality
        await state.update_data(quiz_name_message_id=quiz_name_message.message_id)
        await state.set_state(QuizCreation.waiting_for_quiz_name)
    
    elif callback.data == "view_results":
        quiz_keyboard = get_quiz_selection_keyboard()
        if quiz_keyboard:
            await callback.message.edit_text(
                "📊 Natijalarni ko'rish uchun testni tanlang:",
                reply_markup=quiz_keyboard
            )
        else:
            await callback.message.edit_text(
                "📊 Hech qanday test topilmadi.\n\n"
                "Avval test yarating!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_menu")]
                ])
            )
    
    elif callback.data == "bi_weekly_ranking":
        await callback.message.edit_text(
            "🏆 Ikki haftalik reyting\n\n"
            "Qaysi davr reytingini ko'rmoqchisiz?",
            reply_markup=get_ranking_keyboard()
        )
    
    elif callback.data == "current_ranking":
        current_ranking = BiWeeklyManager.get_current_bi_weekly_ranking()
        current_bi_week = BiWeeklyManager.get_current_bi_week()
        
        if current_ranking:
            start_date, end_date = BiWeeklyManager.get_bi_week_dates(current_bi_week)
            ranking_text = f"🏆 Joriy ikki hafta reytingi\n"
            ranking_text += f"📅 {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n\n"
            
            for i, user in enumerate(current_ranking[:10], 1):  # Top 10
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                ranking_text += f"{medal} {user['name']}\n"
                if user['username']:
                    ranking_text += f"   @{user['username']}\n"
                ranking_text += f"   📊 {user['average_percentage']}% ({user['total_score']}/{user['total_questions']})\n"
                ranking_text += f"   🎯 {user['quiz_count']} ta test\n\n"
        else:
            ranking_text = f"🏆 Joriy ikki hafta reytingi\n\n"
            ranking_text += "Hali hech kim test topshirmagan."
        
        await callback.message.edit_text(
            ranking_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="bi_weekly_ranking")]
            ])
        )
    
    elif callback.data == "previous_ranking":
        previous_ranking = BiWeeklyManager.get_previous_bi_weekly_ranking()
        
        if previous_ranking:
            current_bi_week = BiWeeklyManager.get_current_bi_week()
            year, bw_part = current_bi_week.split('-BW')
            year = int(year)
            bi_week_num = int(bw_part)
            
            if bi_week_num > 1:
                prev_bi_week = f"{year}-BW{bi_week_num-1:02d}"
            else:
                prev_bi_week = f"{year-1}-BW26"
            
            start_date, end_date = BiWeeklyManager.get_bi_week_dates(prev_bi_week)
            ranking_text = f"🏆 Oldingi ikki hafta reytingi\n"
            ranking_text += f"📅 {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n\n"
            
            for i, user in enumerate(previous_ranking[:10], 1):  # Top 10
                medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                ranking_text += f"{medal} {user['name']}\n"
                if user['username']:
                    ranking_text += f"   @{user['username']}\n"
                ranking_text += f"   📊 {user['average_percentage']}%\n"
                ranking_text += f"   🎯 {user['quiz_count']} ta test\n\n"
        else:
            ranking_text = f"🏆 Oldingi ikki hafta reytingi\n\n"
            ranking_text += "Oldingi davr uchun ma'lumot yo'q."
        
        await callback.message.edit_text(
            ranking_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="bi_weekly_ranking")]
            ])
        )
    
    elif callback.data == "compare_rankings":
        comparison = BiWeeklyManager.compare_rankings()
        
        if comparison:
            compare_text = f"📈 Ikki haftalik reyting taqqoslash\n\n"
            
            for item in comparison[:10]:  # Top 10
                user = item['user']
                current_pos = item['current_position']
                change = item['change']
                
                medal = "🥇" if current_pos == 1 else "🥈" if current_pos == 2 else "🥉" if current_pos == 3 else f"{current_pos}."
                compare_text += f"{medal} {user['name']} {change}\n"
                if user['username']:
                    compare_text += f"   @{user['username']}\n"
                compare_text += f"   📊 {user['average_percentage']}% ({user['total_score']}/{user['total_questions']})\n\n"
        else:
            compare_text = "📈 Ikki haftalik reyting taqqoslash\n\n"
            compare_text += "Taqqoslash uchun yetarli ma'lumot yo'q."
        
        await callback.message.edit_text(
            compare_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_menu")]
            ])
        )
    
    elif callback.data == "view_users":
        if users:
            user_list = "👥 Ro'yxatdan o'tgan foydalanuvchilar:\n\n"
            for user_id, user_info in users.items():
                user_list += f"👤 {user_info['name']}\n"
                if user_info.get('username'):
                    user_list += f"📱 @{user_info['username']}\n"
                else:
                    user_list += f"📱 Username yo'q\n"
                user_list += f"🆔 ID: {user_id}\n"
                user_list += f"📅 Oxirgi ko'rish: {user_info['last_seen']}\n\n"
        else:
            user_list = "👥 Hech qanday foydalanuvchi test o'tkazmagan."
        
        await callback.message.edit_text(
            user_list,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_menu")]
            ])
        )
    
    elif callback.data == "my_quizzes":
        if quizzes:
            quiz_list = "🗂️ Testlaringiz:\n\n"
            for code, quiz in quizzes.items():
                quiz_list += f"🎯 {quiz['name']}\n"
                quiz_list += f"🔑 Kod: {code}\n"
                quiz_list += f"❓ Savollar: {len(quiz['questions'])}\n\n"
        else:
            quiz_list = "🗂️ Hech qanday test yaratilmagan."
        
        await callback.message.edit_text(
            quiz_list,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_menu")]
            ])
        )
    
    elif callback.data == "back_to_menu":
        # Clear any existing state
        await state.clear()
        await callback.message.edit_text(
            "🎮 Admin panelga xush kelibsiz!\n\n"
            "Qanday ish qilmoqchisiz:",
            reply_markup=get_admin_keyboard()
        )
    
    elif callback.data.startswith("quiz_results_"):
        quiz_code = callback.data.replace("quiz_results_", "")
        results = quiz_results.get(quiz_code, [])
        quiz = quizzes.get(quiz_code)
        
        if results:
            results_text = f"📊 Natijalar: {quiz['name']}\n\n"
            for i, result in enumerate(results, 1):
                # Calculate timeout statistics
                timeout_count = sum(1 for answer in result['answers'] if answer.get('timeout', False))
                answered_count = result['total'] - timeout_count
                
                results_text += f"{i}. {result['user_name']}\n"
                if result.get('username'):
                    results_text += f"   @{result['username']}\n"
                else:
                    results_text += f"   Username yo'q\n"
                results_text += f"   ID: {result['user_id']}\n"
                results_text += f"   Ball: {result['score']}/{result['total']}\n"
                results_text += f"   ✅ Javob berildi: {answered_count}\n"
                results_text += f"   ⏰ Vaqt tugadi: {timeout_count}\n"
                results_text += f"   Sana: {result['date']}\n\n"
        else:
            results_text = f"📊 Natijalar: {quiz['name']}\n\n"
            results_text += "Hali hech kim test topshirmagan."
        
        await callback.message.edit_text(
            results_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="view_results")]
            ])
        )
    
    await callback.answer()

# Handle ADMIN quiz creation messages with reply functionality
@dp.message(lambda m: is_admin(m.from_user.id), QuizCreation.waiting_for_quiz_name)
async def process_quiz_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    # Check if replying to the correct message
    if hasattr(message, 'reply_to_message') and message.reply_to_message:
        if message.reply_to_message.message_id != data.get('quiz_name_message_id'):
            await message.answer("❌ Iltimos, test nomini so'ralgan xabarga reply qilib yozing!")
            return
    else:
        # Auto-reply functionality
        try:
            await message.reply(f"✅ Test nomi: {message.text}")
        except:
            pass
    
    await state.update_data(quiz_name=message.text)
    
    question_count_message = await message.answer(
        f"✅ Test nomi: {message.text}\n\n"
        "Qancha savol qo'shmoqchisiz? (Raqam kiriting):"
    )
    
    await state.update_data(question_count_message_id=question_count_message.message_id)
    await state.set_state(QuizCreation.waiting_for_question_count)

@dp.message(lambda m: is_admin(m.from_user.id), QuizCreation.waiting_for_question_count)
async def process_question_count(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    # Check if replying to the correct message
    if hasattr(message, 'reply_to_message') and message.reply_to_message:
        if message.reply_to_message.message_id != data.get('question_count_message_id'):
            await message.answer("❌ Iltimos, savol sonini so'ralgan xabarga reply qilib yozing!")
            return
    
    try:
        count = int(message.text)
        if count <= 0:
            await message.answer("❌ Iltimos, musbat raqam kiriting.")
            return
        if count > 50:
            await message.answer("❌ Maksimal 50 ta savol qo'shish mumkin.")
            return
    except ValueError:
        await message.answer("❌ Iltimos, to'g'ri raqam kiriting.")
        return
    
    # Auto-reply functionality
    try:
        await message.reply(f"✅ Savollar soni: {count}")
    except:
        pass
    
    await state.update_data(
        question_count=count,
        current_question=1,
        questions=[]
    )
    
    first_question_message = await message.answer(
        f"📝 1-savol {count} dan:\n\n"
        "Iltimos, savolni kiriting:"
    )
    
    await state.update_data(current_question_message_id=first_question_message.message_id)
    await state.set_state(QuizCreation.waiting_for_question)

@dp.message(lambda m: is_admin(m.from_user.id), QuizCreation.waiting_for_question)
async def process_question(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    # Check if replying to the correct message
    if hasattr(message, 'reply_to_message') and message.reply_to_message:
        if message.reply_to_message.message_id != data.get('current_question_message_id'):
            await message.answer("❌ Iltimos, savol so'ralgan xabarga reply qilib yozing!")
            return
    
    # Auto-reply functionality
    try:
        await message.reply(f"✅ Savol qabul qilindi")
    except:
        pass
    
    await state.update_data(current_question_text=message.text)
    
    variants_message = await message.answer(
        f"Savol: {message.text}\n\n"
        "Endi 3 ta javob variantini kiriting, har birini alohida xabarda.\n"
        "Variant 1 ni yuboring:"
    )
    
    await state.update_data(
        variants=[], 
        variant_count=1,
        variants_message_id=variants_message.message_id
    )
    await state.set_state(QuizCreation.waiting_for_variants)

@dp.message(lambda m: is_admin(m.from_user.id), QuizCreation.waiting_for_variants)
async def process_variants(message: types.Message, state: FSMContext):
    data = await state.get_data()
    variants = data.get('variants', [])
    variant_count = data.get('variant_count', 1)
    
    # Auto-reply functionality
    try:
        await message.reply(f"✅ Variant {variant_count} qabul qilindi")
    except:
        pass
    
    variants.append(message.text)
    
    if variant_count < 3:
        next_variant_message = await message.answer(f"✅ Variant {variant_count}: {message.text}\n\nVariant {variant_count + 1} ni yuboring:")
        await state.update_data(
            variants=variants, 
            variant_count=variant_count + 1,
            variants_message_id=next_variant_message.message_id
        )
    else:
        await state.update_data(variants=variants)
        variant_text = "\n".join([f"{chr(65+i)}) {v}" for i, v in enumerate(variants)])
        
        correct_answer_message = await message.answer(
            f"✅ Hamma variantlar qo'shildi:\n\n{variant_text}\n\n"
            "Qaysi javob to'g'ri? (A, B, yoki C ni kiriting):"
        )
        
        await state.update_data(correct_answer_message_id=correct_answer_message.message_id)
        await state.set_state(QuizCreation.waiting_for_correct_answer)

@dp.message(lambda m: is_admin(m.from_user.id), QuizCreation.waiting_for_correct_answer)
async def process_correct_answer(message: types.Message, state: FSMContext):
    data = await state.get_data()
    answer_text = message.text.upper().strip()
    
    # Check if replying to the correct message
    if hasattr(message, 'reply_to_message') and message.reply_to_message:
        if message.reply_to_message.message_id != data.get('correct_answer_message_id'):
            await message.answer("❌ Iltimos, to'g'ri javob so'ralgan xabarga reply qilib yozing!")
            return
    
    if answer_text not in ['A', 'B', 'C', '1', '2', '3']:
        await message.answer("❌ Iltimos, A, B, C yoki 1, 2, 3 ni kiriting.")
        return
    
    # Convert to 0-based index
    if answer_text in ['A', '1']:
        correct_answer = 0
    elif answer_text in ['B', '2']:
        correct_answer = 1
    else:  # C or 3
        correct_answer = 2
    
    # Auto-reply functionality
    try:
        await message.reply(f"✅ To'g'ri javob: {answer_text}")
    except:
        pass
    
    questions = data.get('questions', [])
    
    question_data = {
        'question': data['current_question_text'],
        'variants': data['variants'],
        'correct_answer': correct_answer
    }
    questions.append(question_data)
    
    current_question = data['current_question']
    question_count = data['question_count']
    
    if current_question < question_count:
        await state.update_data(
            questions=questions,
            current_question=current_question + 1
        )
        
        next_question_message = await message.answer(
            f"✅ Savol {current_question} saqlandi!\n\n"
            f"📝 {current_question + 1}-savol {question_count} dan:\n\n"
            "Iltimos, savolni kiriting:"
        )
        
        await state.update_data(current_question_message_id=next_question_message.message_id)
        await state.set_state(QuizCreation.waiting_for_question)
    else:
        # Quiz creation complete
        quiz_data = {
            'name': data['quiz_name'],
            'questions': questions,
            'created_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'created_by': message.from_user.id
        }
        
        quiz_code = QuizManager.save_quiz(quiz_data)
        
        await message.answer(
            f"🎉 Test muvaffaqiyatli yaratildi!\n\n"
            f"📝 Test: {quiz_data['name']}\n"
            f"🔑 Kod: {quiz_code}\n"
            f"❓ Savollar: {len(questions)}\n"
            f"⏰ Har savol uchun: {QUESTION_TIMEOUT} soniya\n\n"
            f"Ushbu kodni foydalanuvchilar bilan ulashing:\n"
            f"`/quiz {quiz_code}`\n\n"
            "Yana test yaratmoqchimisiz?",
            reply_markup=get_admin_keyboard()
        )
        await state.clear()

# Handle USER quiz taking messages (non-admin only)
@dp.message(lambda m: not is_admin(m.from_user.id), QuizTaking.waiting_for_name)
async def process_user_name(message: types.Message, state: FSMContext):
    # Check channel membership first
    is_member = await check_channel_membership(message.from_user.id)
    if not is_member:
        await message.answer(
            "❌ Botdan foydalanish uchun avval kanalga qo'shiling!\n\n"
            f"📢 Kanal: {REQUIRED_CHANNEL}",
            reply_markup=get_channel_keyboard()
        )
        await state.clear()
        return
    
    data = await state.get_data()
    
    # Check if replying to the correct message
    if hasattr(message, 'reply_to_message') and message.reply_to_message:
        if message.reply_to_message.message_id != data.get('name_message_id'):
            await message.answer("❌ Iltimos, ism so'ralgan xabarga reply qilib yozing!")
            return
    
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("❌ Iltimos, to'liq ismingizni kiriting (kamida 2 ta belgi).")
        return
    
    # Auto-reply functionality
    try:
        await message.reply(f"✅ Salom, {name}!")
    except:
        pass
    
    await state.update_data(
        user_name=name,
        current_question=0,
        answers=[],
        score=0
    )
    
    quiz = data['quiz']
    question = quiz['questions'][0]
    
    # Create answer buttons
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"A) {question['variants'][0]}", callback_data="answer_0")],
        [InlineKeyboardButton(text=f"B) {question['variants'][1]}", callback_data="answer_1")],
        [InlineKeyboardButton(text=f"C) {question['variants'][2]}", callback_data="answer_2")]
    ])
    
    sent_message = await message.answer(
        f"👋 Salom, {name}!\n\n"
        f"🎯 Test: {quiz['name']}\n\n"
        f"📝 1-savol {len(quiz['questions'])} dan:\n"
        f"⏳ {QUESTION_TIMEOUT} soniya\n\n"
        f"{question['question']}",
        reply_markup=keyboard
    )
    
    # Store message ID for editing later
    await state.update_data(current_message_id=sent_message.message_id)
    await state.set_state(QuizTaking.taking_quiz)
    
    # Start timer for first question
    await QuizTimer.start_question_timer(message.from_user.id, state)

# Handle quiz answers (only for non-admin users)
@dp.callback_query(lambda c: c.data.startswith("answer_") and not is_admin(c.from_user.id))
async def handle_quiz_answers(callback: CallbackQuery, state: FSMContext):
    # Check channel membership
    is_member = await check_channel_membership(callback.from_user.id)
    if not is_member:
        await callback.message.edit_text(
            "❌ Botdan foydalanish uchun avval kanalga qo'shiling!\n\n"
            f"📢 Kanal: {REQUIRED_CHANNEL}",
            reply_markup=get_channel_keyboard()
        )
        await state.clear()
        return
    
    # Cancel the timer since user answered
    await QuizTimer.cancel_timer(callback.from_user.id)
    
    data = await state.get_data()
    quiz = data['quiz']
    current_question = data['current_question']
    answers = data.get('answers', [])
    score = data.get('score', 0)
    
    # Get selected answer
    selected_answer = int(callback.data.split('_')[1])
    correct_answer = quiz['questions'][current_question]['correct_answer']
    
    # Check if answer is correct
    is_correct = selected_answer == correct_answer
    if is_correct:
        score += 1
    
    answers.append({
        'question': quiz['questions'][current_question]['question'],
        'selected': selected_answer,
        'correct': correct_answer,
        'is_correct': is_correct,
        'timeout': False
    })
    
    current_question += 1
    
    if current_question < len(quiz['questions']):
        # Next question
        question = quiz['questions'][current_question]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"A) {question['variants'][0]}", callback_data="answer_0")],
            [InlineKeyboardButton(text=f"B) {question['variants'][1]}", callback_data="answer_1")],
            [InlineKeyboardButton(text=f"C) {question['variants'][2]}", callback_data="answer_2")]
        ])
        
        await callback.message.edit_text(
            f"📝 {current_question + 1}-savol {len(quiz['questions'])} dan:\n"
            f"⏳ {QUESTION_TIMEOUT} soniya\n\n"
            f"{question['question']}",
            reply_markup=keyboard
        )
        
        await state.update_data(
            current_question=current_question,
            answers=answers,
            score=score
        )
        
        # Start timer for next question
        await QuizTimer.start_question_timer(callback.from_user.id, state)
    else:
        # Quiz finished
        quiz_code = data['quiz_code']
        user_name = data['user_name']
        total_questions = len(quiz['questions'])
        
        # Save result
        QuizManager.save_result(
            quiz_code, user_name, callback.from_user.id, 
            callback.from_user.username,
            score, total_questions, answers
        )
        
        # Calculate statistics
        answered_count = sum(1 for answer in answers if not answer.get('timeout', False))
        timeout_count = total_questions - answered_count
        percentage = round((score/total_questions) * 100, 1)
        
        # Show results to user
        result_text = f"🎉 Test tugatildi!\n\n"
        result_text += f"👤 Ism: {user_name}\n"
        result_text += f"📊 Ball: {score}/{total_questions}\n"
        result_text += f"📈 Foiz: {percentage}%\n"
        result_text += f"✅ Javob berildi: {answered_count}\n"
        result_text += f"⏰ Vaqt tugadi: {timeout_count}\n\n"
        
        if score == total_questions:
            result_text += "🏆 Mukammal ball! Tabriklaymiz!"
        elif score >= total_questions * 0.8:
            result_text += "🎯 Ajoyib ish! Zo'r natija!"
        elif score >= total_questions * 0.6:
            result_text += "👍 Yaxshi ish! Davom eting!"
        else:
            result_text += "📚 O'qishni davom ettiring va qayta urinib ko'ring!"
        
        result_text += f"\n\n🏆 Ikki haftalik reytingga qo'shildi!"
        
        await callback.message.edit_text(result_text)
        
        # Send results to admin
        current_ranking = BiWeeklyManager.get_current_bi_weekly_ranking()
        user_position = None
        for i, user in enumerate(current_ranking, 1):
            if user['user_id'] == callback.from_user.id:
                user_position = i
                break
        
        admin_text = f"📊 Yangi Test Natijasi!\n\n"
        admin_text += f"🎯 Test: {quiz['name']}\n"
        admin_text += f"👤 Talaba: {user_name}\n"
        if callback.from_user.username:
            admin_text += f"📱 Username: @{callback.from_user.username}\n"
        else:
            admin_text += f"📱 Username yo'q\n"
        admin_text += f"🆔 ID: {callback.from_user.id}\n"
        admin_text += f"📊 Ball: {score}/{total_questions} ({percentage}%)\n"
        admin_text += f"✅ Javob berildi: {answered_count}\n"
        admin_text += f"⏰ Vaqt tugadi: {timeout_count}\n"
        admin_text += f"📅 Sana: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        if user_position:
            admin_text += f"\n🏆 Ikki haftalik reytingda: {user_position}-o'rin"
        
        # Send to admin
        try:
            await bot.send_message(ADMIN_ID, admin_text)
        except Exception as e:
            logging.error(f"Failed to send message to admin {ADMIN_ID}: {e}")
        
        await state.clear()
    
    await callback.answer()

# Ranking command for all users
@dp.message(Command("ranking"))
async def ranking_command(message: types.Message):
    if not is_admin(message.from_user.id):
        # Check channel membership for regular users
        is_member = await check_channel_membership(message.from_user.id)
        if not is_member:
            await message.answer(
                "❌ Botdan foydalanish uchun avval kanalga qo'shiling!\n\n"
                f"📢 Kanal: {REQUIRED_CHANNEL}",
                reply_markup=get_channel_keyboard()
            )
            return
    
    current_ranking = BiWeeklyManager.get_current_bi_weekly_ranking()
    current_bi_week = BiWeeklyManager.get_current_bi_week()
    
    if current_ranking:
        start_date, end_date = BiWeeklyManager.get_bi_week_dates(current_bi_week)
        ranking_text = f"🏆 Joriy ikki hafta reytingi\n"
        ranking_text += f"📅 {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}\n\n"
        
        # Show different amount based on user type
        show_count = 20 if is_admin(message.from_user.id) else 10
        
        for i, user in enumerate(current_ranking[:show_count], 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            ranking_text += f"{medal} {user['name']}\n"
            ranking_text += f"   📊 {user['average_percentage']}% ({user['total_score']}/{user['total_questions']})\n"
            ranking_text += f"   🎯 {user['quiz_count']} ta test\n"
            
            # Highlight current user
            if user['user_id'] == message.from_user.id:
                ranking_text += "   ⭐ SIZ\n"
            ranking_text += "\n"
        
        # If user is not in top 10, show their position
        if not is_admin(message.from_user.id):
            user_position = None
            user_data = None
            for i, user in enumerate(current_ranking, 1):
                if user['user_id'] == message.from_user.id:
                    user_position = i
                    user_data = user
                    break
            
            if user_position and user_position > 10:
                ranking_text += f"...\n\n"
                ranking_text += f"{user_position}. {user_data['name']} ⭐ SIZ\n"
                ranking_text += f"   📊 {user_data['average_percentage']}% ({user_data['total_score']}/{user_data['total_questions']})\n"
                ranking_text += f"   🎯 {user_data['quiz_count']} ta test\n"
    else:
        ranking_text = f"🏆 Joriy ikki hafta reytingi\n\n"
        ranking_text += "Hali hech kim test topshirmagan."
    
    await message.answer(ranking_text)

# Handle unexpected messages during quiz creation (for admins)
@dp.message(lambda m: is_admin(m.from_user.id))
async def handle_admin_messages(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    
    # If admin is not in any specific state, show menu
    if current_state is None:
        await message.answer(
            "🎮 Admin Panel\n\n"
            "Qanday ish qilmoqchisiz:",
            reply_markup=get_admin_keyboard()
        )
    else:
        # If admin is in a state but sent unexpected message, provide guidance
        if current_state == QuizCreation.waiting_for_quiz_name.state:
            await message.answer("❌ Iltimos, test nomini kiriting yoki /start bosing va qaytadan boshlang.")
        elif current_state == QuizCreation.waiting_for_question_count.state:
            await message.answer("❌ Iltimos, faqat raqam kiriting yoki /start bosing va qaytadan boshlang.")
        elif current_state == QuizCreation.waiting_for_question.state:
            await message.answer("❌ Iltimos, savol matnini kiriting yoki /start bosing va qaytadan boshlang.")
        elif current_state == QuizCreation.waiting_for_variants.state:
            await message.answer("❌ Iltimos, javob variantini kiriting yoki /start bosing va qaytadan boshlang.")
        elif current_state == QuizCreation.waiting_for_correct_answer.state:
            await message.answer("❌ Iltimos, to'g'ri javobni kiriting (A, B, C) yoki /start bosing va qaytadan boshlang.")

# Handle unexpected messages for regular users
@dp.message(lambda m: not is_admin(m.from_user.id))
async def handle_user_messages(message: types.Message, state: FSMContext):
    # Check channel membership first
    is_member = await check_channel_membership(message.from_user.id)
    if not is_member:
        await message.answer(
            "❌ Botdan foydalanish uchun avval kanalga qo'shiling!\n\n"
            f"📢 Kanal: {REQUIRED_CHANNEL}",
            reply_markup=get_channel_keyboard()
        )
        return
    
    current_state = await state.get_state()
    
    # If user is taking quiz and sends a message, cancel timer
    if current_state == QuizTaking.taking_quiz.state:
        await QuizTimer.cancel_timer(message.from_user.id)
        await message.answer(
            "❌ Test bekor qilindi!\n\n"
            "Qaytadan test olish uchun /quiz [CODE] buyrug'idan foydalaning."
        )
        await state.clear()
    elif current_state == QuizTaking.waiting_for_name.state:
        # This should be handled by the specific handler above
        pass
    else:
        # User is not in any quiz state
        await message.answer(
            "🎮 Test Botga xush kelibsiz!\n\n"
            "Test olish uchun quyidagi buyruqdan foydalaning:\n"
            "/quiz [CODE]\n\n"
            "Misol: /quiz ABC123\n\n"
            f"⏰ Har bir savol uchun {QUESTION_TIMEOUT} soniya vaqt beriladi!\n\n"
            "📊 Joriy reytingni ko'rish: /ranking\n\n"
            "Test yaratuvchisidan test kodini oling!"
        )

# Main function
async def main():
    print("🤖 Quiz Bot with Channel Requirement, Bi-weekly Ranking and Timer starting...")
    print(f"⏰ Question timeout: {QUESTION_TIMEOUT} seconds")
    print(f"👨‍💼 Admin ID: {ADMIN_ID}")
    print(f"📢 Required Channel: {REQUIRED_CHANNEL}")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
