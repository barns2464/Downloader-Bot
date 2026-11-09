import telebot
import sqlite3
from datetime import datetime, timedelta
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request
import os
import yt_dlp
import tempfile

# --- 1. الإعدادات ---
BOT_TOKEN = "9122345599:AAGFNwO6rSI8XQCzVkjapSPwie9TiFies7c" # ⚠️ ضع التوكن الحقيقي هنا
CHANNEL_ID = -1003822942624
ADMIN_ID = 799886198
CHANNEL_LINK = "https://t.me/abuwaadStore"

bot = telebot.TeleBot(BOT_TOKEN)

# --- 2. قاعدة البيانات ---
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

def get_all_users():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

init_db()

# --- 3. التحقق من الاشتراك ---
def check_subscription(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return True
    except Exception:
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
        bot.send_message(message.chat.id, "أهلاً بك في بوت برق للتحميل! ⚡\nأرسل لي أي رابط من (تيك توك، يوتيوب، تويتر، إنستغرام) وسأقوم بتحميله لك.")

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def callback_check(call):
    if check_subscription(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ تم التحقق بنجاح!")
        bot.send_message(call.message.chat.id, "أهلاً بك! أرسل أي رابط لتحميله.")
    else:
        bot.answer_callback_query(call.id, "❌ لم تنضم للقناة بعد!", show_alert=True)

# --- 5. لوحة التحكم التفاعلية للمدير ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    markup = telebot.types.InlineKeyboardMarkup()
    btn_stats = telebot.types.InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")
    btn_broadcast = telebot.types.InlineKeyboardButton("📢 إرسال رسالة جماعية", callback_data="admin_broadcast")
    markup.add(btn_stats)
    markup.add(btn_broadcast)
    
    bot.send_message(message.chat.id, "👨‍💻 **لوحة تحكم الإدارة**\nاختر ما تريد:", reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == "admin_stats")
def admin_stats_callback(call):
    if call.from_user.id != ADMIN_ID:
        return
    total, active = get_stats()
    text = f"📊 **الإحصائيات الحالية:**\n\n👥 إجمالي المستخدمين المسجلين: {total}\n🟢 النشطون الآن (آخر 5 دقائق): {active}\n"
    bot.answer_callback_query(call.id)
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=call.message.reply_markup)

# --- ميزة الرسائل الجماعية (Broadcast) ---
@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
def admin_broadcast_callback(call):
    if call.from_user.id != ADMIN_ID:
        return
    msg = bot.send_message(call.message.chat.id, "📝 أرسل الرسالة التي تريد إرسالها لجميع المستخدمين (أو أرسل /cancel للإلغاء):")
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "❌ تم إلغاء الإرسال.")
        return
    
    users = get_all_users()
    success = 0
    fail = 0
    msg_status = bot.send_message(message.chat.id, f"⏳ جاري الإرسال إلى {len(users)} مستخدم...")
    
    for user_id in users:
        try:
            bot.send_message(user_id, f"📢 **إعلان من الإدارة:**\n\n{message.text}", parse_mode='Markdown')
            success += 1
        except Exception:
            fail += 1
            
    bot.edit_message_text(f"✅ تم الإرسال بنجاح إلى: {success} مستخدم.\n❌ فشل الإرسال إلى: {fail} مستخدم.", message.chat.id, msg_status.message_id)

# --- 6. استقبال الروابط والرسائل ---
@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.from_user.id != ADMIN_ID)
def handle_user_message(message):
    user_id = message.from_user.id
    
    if not check_subscription(user_id):
        bot.reply_to(message, "⚠️ يرجى الانضمام للقناة أولاً. أرسل /start للتحقق.")
        return

    if message.text.startswith('http'):
        msg = bot.reply_to(message, "⏳ جاري معالجة الرابط وتحميل الفيديو...")
        
        ydl_opts = {
            'format': 'best',
            'outtmpl': os.path.join(tempfile.gettempdir(), '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(message.text, download=True)
                filename = ydl.prepare_filename(info)
                
                with open(filename, 'rb') as video:
                    bot.send_video(message.chat.id, video, caption="✅ تم التحميل بواسطة بوت برق ⚡")
                
                os.remove(filename)
                bot.delete_message(message.chat.id, msg.message_id)
                
        except Exception as e:
            print(f"Download error: {e}")
            bot.edit_message_text("❌ عذراً، حدث خطأ أثناء التحميل. تأكد من صحة الرابط أو حاول لاحقاً.", message.chat.id, msg.message_id)
    else:
        bot.send_message(ADMIN_ID, f"📩 رسالة من @{message.from_user.username} (ID: {message.from_user.id}):\n\n{message.text}")
        bot.reply_to(message, "✅ تم إرسال رسالتك للإدارة.")

# --- 7. رد المدير على المستخدم ---
@bot.message_handler(func=lambda message: message.chat.id == ADMIN_ID and message.reply_to_message)
def admin_reply(message):
    try:
        user_id = int(message.reply_to_message.text.split("ID: ")[1].split(")")[0])
        bot.send_message(user_id, f"👨‍💻 رد الإدارة:\n\n{message.text}")
        bot.delete_message(chat_id=message.chat.id, message_id=message.reply_to_message.message_id)
        bot.reply_to(message, "✅ تم إرسال الرد وحذف الرسالة.")
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ في الرد: {e}")

# --- 8. منع الخمول (Anti-Sleep) ---
class WebServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is Alive!")

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), WebServerHandler)
    server.serve_forever()

def keep_alive_ping():
    URL = "ضع_رابط_البوت_هنا_بعد_الرفع"
    if URL == "ضع_رابط_البوت_هنا_بعد_الرفع":
        return
    while True:
        try:
            urllib.request.urlopen(URL)
        except Exception:
            pass
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
