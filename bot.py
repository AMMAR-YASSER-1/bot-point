import sqlite3
import telebot
from telebot import types
import random
import logging
import base64
import os
from dotenv import load_dotenv
import atexit
import time

load_dotenv()

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_USERNAME = '@game_points1'
ADMIN_ID = os.getenv('ADMIN_ID')

bot = telebot.TeleBot(BOT_TOKEN)

conn = sqlite3.connect('points.db', check_same_thread=False)
cursor = conn.cursor()

def encode_code(code):
    encoded_bytes = base64.urlsafe_b64encode(code.encode('utf-8'))
    encoded_str = str(encoded_bytes, 'utf-8')
    return encoded_str

def decode_code(encoded_str):
    decoded_bytes = base64.urlsafe_b64decode(encoded_str.encode('utf-8'))
    decoded_str = str(decoded_bytes, 'utf-8')
    return decoded_str

def add_user(user_id, points, ad_code, invited_by=None):
    try:
        cursor.execute('''INSERT INTO users (telegram_id, points, ad_code, invited_by, invite_count, has_received_invite_points, invite_link_used, gift_link_active)
                          VALUES (?, ?, ?, ?, 0, FALSE, FALSE, FALSE)
                          ON CONFLICT(telegram_id) 
                          DO UPDATE SET points = points + excluded.points, ad_code = excluded.ad_code
                          ''', (user_id, points, ad_code, invited_by))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Database error when adding user: {e}")

def get_user(user_id):
    try:
        logging.debug(f"Fetching user with ID: {user_id}")
        cursor.execute('''SELECT * FROM users WHERE telegram_id = ?''', (user_id,))
        result = cursor.fetchone()
        if result:
            return {'id': result[0], 'telegram_id': result[1], 'points': result[2], 'ad_code': result[3], 'invited_by': result[4], 'invite_count': result[5], 'has_received_invite_points': result[6], 'last_rewarded': result[7], 'invite_link_used': result[8], 'gift_link_active': result[9]}
        else:
            logging.debug(f'No user found with ID: {user_id}')
            return None
    except sqlite3.Error as e:
        logging.error(f"Database error when fetching user: {e}")
        return None

def generate_invite_link(user_id):
    encoded_id = encode_code(user_id)
    bot_username = bot.get_me().username
    invite_link = f"https://t.me/{bot_username}?start={encoded_id}"
    return invite_link

def add_points_for_invite(user_id, points=2):
    user_data = get_user(user_id)
    if user_data:
        invite_count = user_data['invite_count'] if user_data['invite_count'] is not None else 0
        new_invite_count = invite_count + 1
        cursor.execute('''UPDATE users 
                          SET points = points + ?, invite_count = ?
                          WHERE telegram_id = ?''', (points, new_invite_count, user_id))
        conn.commit()
        bot.send_message(user_id, f"🎉 You've earned {points} point(s) for inviting a friend! You have invited {new_invite_count} friends in total.")

def send_start_message(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    points_button = types.KeyboardButton('🪙 Check Points')
    ads_button = types.KeyboardButton('📺 Earn Points by Watching Ads')
    redeem_button = types.KeyboardButton('🎁 Redeem Points')
    invite_button = types.KeyboardButton('🤝 Invite a Friend')
    daily_reward_button = types.KeyboardButton('🎁 Daily Reward')
    markup.add(points_button, ads_button, redeem_button, invite_button, daily_reward_button)

    bot.send_message(
    chat_id,
    (
        "👋 Welcome to the Points Bot!\n\n"
        "To fully enjoy the benefits of our bot, you need to join our channel. Once you're subscribed, you can start collecting points and redeem them for awesome rewards! 🎁\n\n"
        "Here’s how it works:\n"
        "1. Check Points: See how many points you have.\n"
        "2. Earn Points by Watching Ads: Watch ads to earn points.\n"
        "3. Redeem Points: Exchange your points for rewards.\n"
        "4. Invite a Friend: Earn points by inviting friends.\n"
        "5. Daily Reward: Claim your daily points!\n\n"
        f"🔗 Join our channel here: {CHANNEL_USERNAME}\n\n"
        "After subscribing, use the buttons below to start using the bot!\n\n"
        "👋 أهلاً بك في بوت النقاط!\n\n"
        "للاستمتاع بجميع مزايا البوت، يجب عليك الانضمام إلى قناتنا. بمجرد الاشتراك، يمكنك البدء في جمع النقاط واستبدالها بمكافآت رائعة! 🎁\n\n"
        "إليك كيفية عمل البوت:\n"
        "1. تحقق من النقاط: تعرف على عدد النقاط التي لديك.\n"
        "2. اكسب النقاط بمشاهدة الإعلانات: شاهد الإعلانات لتحصل على نقاط.\n"
        "3. استبدال النقاط: استبدل نقاطك للحصول على المكافآت.\n"
        "4. دعوة صديق: اكسب نقاطًا عند دعوة أصدقائك.\n"
        "5. المكافأة اليومية: احصل على نقاطك اليومية!\n\n"
        f"🔗 انضم إلى قناتنا هنا: {CHANNEL_USERNAME}\n\n"
        "بعد الاشتراك، استخدم الأزرار أدناه للبدء في استخدام البوت!"
    ),
    reply_markup=markup
)

    
    if str(chat_id) == ADMIN_ID:
        admin_markup = types.InlineKeyboardMarkup()
        create_gift_button = types.InlineKeyboardButton("🎁 Create Gift Link", callback_data="create_gift_link")
        admin_markup.add(create_gift_button)
        bot.send_message(chat_id, "As an admin, you can create gift links.", reply_markup=admin_markup)

def process_invitation(user_id, inviter_id):
    try:
        # منع المستخدم من دعوة نفسه
        if user_id == inviter_id:
            bot.send_message(user_id, "⚠️ You cannot invite yourself.")
            return

        # التحقق مما إذا كان المستخدم الجديد قد تمت دعوته من قبل نفس الداعي
        cursor.execute('''SELECT COUNT(*) FROM invitations WHERE inviter_id = ? AND invited_id = ?''', (inviter_id, user_id))
        invitation_exists = cursor.fetchone()[0] > 0

        if invitation_exists:
            bot.send_message(user_id, "⚠️ You have already been invited by this user.")
            return

        # إضافة المستخدم الجديد وربطه بالداعي
        add_user(user_id, 0, '', invited_by=inviter_id)

        # تسجيل الدعوة في جدول الدعوات
        cursor.execute('INSERT INTO invitations (inviter_id, invited_id) VALUES (?, ?)', (inviter_id, user_id))
        conn.commit()

        # منح النقاط للداعي
        add_points_for_invite(inviter_id)

        # إرسال رسالة تأكيد للمستخدم الجديد
        bot.send_message(user_id, "🎉 You have been successfully invited!")
        bot.send_message(inviter_id, f"🎉 You've earned points for inviting {user_id}!")
    except sqlite3.Error as e:
        logging.error(f"Database error in process_invitation: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in process_invitation: {e}")

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)

    if len(message.text.split()) > 1:
        command_argument = message.text.split()[1]
        if command_argument.startswith("gift_"):
            gift_code = command_argument.split("_")[1]
            handle_gift_link(user_id, gift_code)
        else:
            inviter_code = command_argument
            inviter_id = decode_code(inviter_code)
            process_invitation(user_id, inviter_id)
    else:
        if check_subscription(user_id):
            add_user(user_id, 0, '')
            send_start_message(message.chat.id)
        else:
            bot.send_message(message.chat.id, f"🚨 **Action Required:**\n\nPlease subscribe to our channel {CHANNEL_USERNAME} to use the bot. Once you're a member, just click on the 'Start' button to get started!")

def handle_gift_link(user_id, gift_code):
    try:
        # التحقق من صلاحية رابط الهدية
        cursor.execute('''SELECT points_per_user, remaining_uses, active FROM gift_links WHERE gift_code = ?''', (gift_code,))
        gift_link = cursor.fetchone()

        if gift_link:
            points_per_user, remaining_uses, active = gift_link

            if not active:
                bot.send_message(user_id, "⚠️ This gift link has been disabled.")
                return

            if remaining_uses <= 0:
                bot.send_message(user_id, "⚠️ This gift link has been fully used.")
                return

            # الحصول على بيانات المستخدم
            user_data = get_user(user_id)

            # إذا لم يكن المستخدم موجودًا، أضفه
            if not user_data:
                add_user(user_id)
                user_data = get_user(user_id)

            # منح النقاط للمستخدم
            new_points = user_data['points'] + points_per_user
            cursor.execute('''UPDATE users SET points = ? WHERE telegram_id = ?''', (new_points, user_id))
            cursor.execute('''INSERT INTO gift_link_usage (gift_code, telegram_id) VALUES (?, ?)''', (gift_code, user_id))
            cursor.execute('''UPDATE gift_links SET remaining_uses = remaining_uses - 1 WHERE gift_code = ?''', (gift_code,))
            conn.commit()

            bot.send_message(user_id, f"🎉 You've received {points_per_user} points from the gift link!")
        else:
            bot.send_message(user_id, "⚠️ Invalid or expired gift link.")
    except sqlite3.Error as e:
        logging.error(f"Database error when handling gift link: {e}")
        bot.send_message(user_id, "⚠️ An error occurred while processing the gift link. Please try again.")
@bot.message_handler(commands=['get_id'])
def get_id(message):
    bot.send_message(message.chat.id, f"Your Telegram ID: {message.from_user.id}")


@bot.message_handler(func=lambda message: message.text == '🪙 Check Points')
def check_points_button(message):
    user_id = str(message.from_user.id)
    if check_subscription(user_id):
        user_data = get_user(user_id)
        points = user_data.get('points', 0) if user_data else 0
        invite_count = user_data.get('invite_count', 0) if user_data else 0
        bot.send_message(message.chat.id, f"🪙 You have {points} points.\n🤝 You have invited {invite_count} friends.")
    else:
        bot.send_message(message.chat.id, f"❌ You need to join {CHANNEL_USERNAME} first!")

@bot.message_handler(func=lambda message: message.text == '🎁 Redeem Points')
def redeem_points_button(message):
    redeem_points(message)

def redeem_points(message):
    user_id = str(message.from_user.id)
    user_data = get_user(user_id)

    if not message.from_user.username:
        bot.send_message(message.chat.id, "⚠️ You need to have a username to redeem points.")
        return

    if user_data:
        points = user_data.get('points', 0)
        if points >= 100:
            markup = types.InlineKeyboardMarkup(row_width=1)
            pubg_button = types.InlineKeyboardButton('Redeem PUBG Mobile - 100 Points for 60 UC', callback_data='redeem_pubg_60')
            markup.add(pubg_button)
            bot.send_message(message.chat.id, "🎁 Choose your redemption option:", reply_markup=markup)
        else:
            bot.send_message(message.chat.id, f"❌ You don't have enough points. You have {points} points.")
    else:
        bot.send_message(message.chat.id, "🚀 You're not registered yet. Start by typing /start to begin.")

def handle_redeem_pubg(call):
    user_id = str(call.from_user.id)
    
    if not call.from_user.username:
        bot.send_message(call.message.chat.id, "⚠️ You need to have a username to redeem points. Please set a username in your Telegram settings and try again.")
        return
    
    logging.debug(f"User ID for redeeming PUBG Mobile: {user_id}")
    
    user_data = get_user(user_id)
    if user_data:
        points = user_data.get('points', 0)
        if points >= 100:
            new_points = points - 100
            update_user_points(user_id, new_points)
            bot.send_message(call.message.chat.id, f"🎉 You've redeemed 60 UC for PUBG Mobile! You now have {new_points} points left.")
            
            bot.send_message(call.message.chat.id, "✅ Your redemption request has been submitted. The recharge code will be sent to your private messages after the request is reviewed by the admin.")
            
            notify_admin(user_id, 60, 100)
        else:
            logging.error(f"User {user_id} has insufficient points to redeem. Current points: {points}")
            bot.send_message(call.message.chat.id, "❌ You have insufficient points. You need at least 100 points to redeem 60 UC.")
    else:
        logging.error(f"User {user_id} not found in the database.")
        bot.send_message(call.message.chat.id, "🚨 User not found.")

def update_user_points(user_id, new_points):
    try:
        cursor.execute('''UPDATE users SET points = ? WHERE telegram_id = ?''', (new_points, user_id))
        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Database error when updating user points: {e}")

def notify_admin(user_id, uc_amount, points_spent):
    user_data = get_user(user_id)
    points = user_data.get('points', 0)
    
    user_info = bot.get_chat(user_id)
    username = user_info.username if user_info.username else f"User ID: {user_id}"
    
    message = (
        f"📩 New Redemption Request\n"
        f"**Username: @{username}\n"
        f"User ID: {user_id}\n"
        f"UC Amount: {uc_amount}\n"
        f"Points Spent: {points_spent}\n"
        f"Remaining Points: {points}\n"
    )
    
    CHAT_ID = '-1002383043381'
    bot.send_message(CHAT_ID, message)
    bot.send_message(ADMIN_ID, message)

@bot.callback_query_handler(func=lambda call: call.data.startswith('redeem_pubg'))
def handle_callback_query(call):
    if call.data == 'redeem_pubg_60':
        handle_redeem_pubg(call)

@bot.message_handler(func=lambda message: message.text == '🤝 Invite a Friend')
def invite_button(message):
    user_id = str(message.from_user.id)
    invite_link = generate_invite_link(user_id)
    bot.send_message(message.chat.id, f"🔗 Share this link to invite your friends and earn points:\n{invite_link}")

@bot.message_handler(func=lambda message: message.text == '🎁 Daily Reward')
def daily_reward_button(message):
    user_id = str(message.from_user.id)
    reward_daily_points(user_id)

def reward_daily_points(user_id):
    user_data = get_user(user_id)
    if user_data:
        last_rewarded = user_data['last_rewarded']
        current_time = int(time.time())
        if current_time - last_rewarded >= 86400:
            new_points = user_data['points'] + 10
            cursor.execute('''UPDATE users SET points = ?, last_rewarded = ? WHERE telegram_id = ?''', (new_points, current_time, user_id))
            conn.commit()
            bot.send_message(user_id, "🎉 You've received a daily reward of 10 points! Keep it up!")
        else:
            remaining_time = 86400 - (current_time - last_rewarded)
            bot.send_message(user_id, f"⏳ You can claim your daily reward again in {remaining_time // 3600} hours and {(remaining_time % 3600) // 60} minutes.")
    else:
        bot.send_message(user_id, "🚀 You're not registered yet. Start by typing /start to begin.")

@bot.callback_query_handler(func=lambda call: call.data == "create_gift_link")
def handle_create_gift_link(call):
    if str(call.from_user.id) == ADMIN_ID:
        bot.send_message(call.message.chat.id, "Please enter the number of users and points per user in the format: <num_users> <points_per_user>.")

@bot.message_handler(func=lambda message: message.from_user.id == int(ADMIN_ID) and message.text)
def create_gift_link(message):
    try:
        num_users, points_per_user = map(int, message.text.split())

        gift_code = base64.urlsafe_b64encode(os.urandom(6)).decode('utf-8')

        cursor.execute('''INSERT INTO gift_links (gift_code, points_per_user, remaining_uses, active)
                          VALUES (?, ?, ?, TRUE)''', (gift_code, points_per_user, num_users))
        conn.commit()

        bot.send_message(message.chat.id, f"🎁 A gift link has been created: https://t.me/{bot.get_me().username}?start=gift_{gift_code} for {num_users} users with {points_per_user} points each.")
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ Please provide valid numbers in the format: <num_users> <points_per_user>")
    except sqlite3.Error as e:
        logging.error(f"Database error when creating gift links: {e}")
        bot.send_message(message.chat.id, "⚠️ An error occurred while creating gift links. Please try again.")

def check_subscription(user_id):
    try:
        user = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if user.status in ['member', 'administrator', 'creator']:
            return True
        else:
            return False
    except Exception as e:
        logging.error(f"Error checking subscription: {e}")
        return False

def cleanup():
    conn.close()

atexit.register(cleanup)

bot.polling(none_stop=True)