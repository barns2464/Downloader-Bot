import telebot
import sqlite3
from datetime import datetime, timedelta
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request
import os

# --- 1. الإعدادات (تم وضع معلوماتك) ---
BOT_TOKEN = "9122345599:AAGFNwO6rSI8XQCzVkjapSPwie9TiFies7c" # ⚠️ قم بتغيير هذا التوكن فوراً
CHANNEL_ID = -1003822942624  # معرف قناتك
ADMIN_ID = 799886198         # معرفك الشخصي
CHANNEL_LINK = "https://t.me/abuwaadStore" # رابط قناتك

bot = telebot.TeleBot(BOT_TOKEN)

# --- 2. إعداد قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, username TEXT, last_active TIMESTAMP)''')
    conn.commit()
    conn.close()

def update_activity(user_id, username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    now = datetime.now()
    c.execute("INSERT OR REPLACE INTO users (user_id, username, last_active) VALUES (?, ?, ?)",
              (user_id, username, now))
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    five_mins_ago = datetime.now() - timedelta(minutes=5)
    c.execute("SELECT COUNT(*) FROM users WHERE last_active > ?", (five_mins_ago,))
    active_users = c.fetchone()[0]
    conn.close()
    return total_users, active_users

init_db()

# --- 3. دالة التحقق من الاشتراك ---
def check_subscription(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception as e:
        print(f"Error checking sub: {e}")
        return False

# --- 4. أوامر البوت ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "No Username"
    update_activity(user_id, username)

    if not check_subscription(user_id):
        markup = telebot.types.InlineKeyboardMarkup()
        btn1 = telebot.types.InlineKeyboardButton("📢 انضم للقناة", url=CHANNEL_LINK)
        btn2 = telebot.types.InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_sub")
        markup.add(btn1, btn2)
        bot.send_message(message.chat.id, "⚠️ عذراً، يجب عليك الانضمام إلى قناتنا أولاً لاستخدام البوت:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "أهلاً بك في بوت برق للتحميل! ⚡\nأرسل لي أي رابط من (تيك توك، يوتيوب، تويتر) وسأقوم بتحميله لك.")

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def callback_check(call):
    if check_subscription(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ تم التحقق بنجاح!")
        bot.send_message(call.message.chat.id, "أهلاً بك! أرسل أي رابط لتحميله.")
    else:
        bot.answer_callback_query(call.id, "❌ لم تنضم للقناة بعد!", show_alert=True)

# --- 5. لوحة التحكم (لك فقط) ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    total, active = get_stats()
    text = f"📊 **لوحة التحكم:**\n\n👥 إجمالي المستخدمين: {total}\n🟢 المتصلون الآن: {active}\n"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# --- 6. استقبال رسائل العملاء ---
@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.from_user.id != ADMIN_ID)
def handle_user_message(message):
    if message.text.startswith('http'):
        bot.reply_to(message, "⏳ جاري تحميل الفيديو... (سيتم ربط المكتبة هنا لاحقاً)")
    else:
        bot.send_message(ADMIN_ID, f"📩 رسالة من @{message.from_user.username} (ID: {message.from_user.id}):\n\n{message.text}")
        bot.reply_to(message, "✅ تم إرسال رسالتك للإدارة.")

# --- 7. رد المدير على المستخدم + حذف الرسالة ---
@bot.message_handler(func=lambda message: message.chat.id == ADMIN_ID and message.reply_to_message)
def admin_reply(message):
    try:
        # استخراج معرف المستخدم من رسالة الإشعار
        user_id = int(message.reply_to_message.text.split("ID: ")[1].split(")")[0])
        
        # إرسال الرد للعميل
        bot.send_message(user_id, f"👨‍💻 رد الإدارة:\n\n{message.text}")
        
        # حذف رسالة العميل الأصلية من محادثتك (الميزة الجديدة)
        bot.delete_message(chat_id=message.chat.id, message_id=message.reply_to_message.message_id)
        
        # إرسال تأكيد لك بأن الرد تم
        bot.reply_to(message, "✅ تم إرسال الرد وحذف رسالة العميل من المحادثة.")
        
    except Exception as e:
        bot.reply_to(message, f"❌ لم أتمكن من فهم الـ ID: {e}")

# =====================================================================
# 🚀 8. نظام منع الخمول (Anti-Sleep / Keep-Alive)
# =====================================================================

class WebServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is Alive 24/7!")

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), WebServerHandler)
    server.serve_forever()

def keep_alive_ping():
    # ⚠️ هام: بعد رفع البوت على Render، ضع رابط موقعك هنا
    URL = "ضع_رابط_البوت_هنا_بعد_الرفع" 
    
    if URL == "ضع_رابط_البوت_هنا_بعد_الرفع":
        print("تم تجاهل نبضات القلب. لم يتم وضع رابط الموقع بعد.")
        return

    while True:
        try:
            urllib.request.urlopen(URL)
            print("تم إرسال نبضة قلب بنجاح.")
        except Exception as e:
            print(f"خطأ في نبضات القلب: {e}")
        
        threading.Event().wait(600)

if __name__ == "__main__":
    web_thread = threading.Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()

    ping_thread = threading.Thread(target=keep_alive_ping)
    ping_thread.daemon = True
    ping_thread.start()

    print("البوت يعمل الآن... 24/7")
    bot.polling(none_stop=True)
