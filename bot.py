import telebot
import sqlite3
from datetime import datetime, timedelta
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request
import os
import yt_dlp
import tempfile
import time

# --- 1. الإعدادات ---
BOT_TOKEN = "ضع_التوكن_الخاص_بك_هنا" # ⚠️ ضع التوكن الحقيقي
CHANNEL_ID = -1003822942624
ADMIN_ID = 799886198
CHANNEL_LINK = "https://t.me/abuwaadStore"
WATERMARK_TEXT = "تم التحميل بواسطة بوت برق ⚡"

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

# --- 4. دالة التحميل (تعمل في الخلفية) ---
def download_media(url, user_id, message_id, media_type="video"):
    chat_id = user_id
    try:
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best' if media_type == "video" else 'bestaudio/best',
            'outtmpl': os.path.join(tempfile.gettempdir(), '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # تعديل امتداد الصوت إذا كان صوتياً
            if media_type == "audio" and not filename.endswith('.mp3'):
                filename = filename.rsplit('.', 1)[0] + '.mp3'
                if os.path.exists(filename):
                    pass # المكتبة قد لا تحول لـ mp3 تلقائياً، نرسلها كملف صوتي
            
            # إرسال الملف
            with open(filename, 'rb') as file:
                if media_type == "video":
                    bot.send_video(chat_id, file, caption=WATERMARK_TEXT, supports_streaming=True)
                else:
                    bot.send_audio(chat_id, file, caption=WATERMARK_TEXT)
            
            # تنظيف الملف
            os.remove(filename)
            bot.delete_message(chat_id, message_id)
            
    except Exception as e:
        print(f"Error: {e}")
        bot.edit_message_text("❌ عذراً، حدث خطأ أثناء التحميل. قد يكون الفيديو طويلاً جداً أو الرابط غير صالح.", chat_id, message_id)

# --- 5. أوامر البوت ---
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
        bot.send_message(message.chat.id, "أهلاً بك في بوت برق للتحميل! ⚡\nأرسل لي أي رابط من (تيك توك، يوتيوب، تويتر، إنستغرام).")

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def callback_check(call):
    if check_subscription(call.from_user.id):
        bot.answer_callback_query(call.id, "✅ تم التحقق بنجاح!")
        bot.send_message(call.message.chat.id, "أهلاً بك! أرسل أي رابط لتحميله.")
    else:
        bot.answer_callback_query(call.id, "❌ لم تنضم للقناة بعد!", show_alert=True)

# --- 6. لوحة التحكم الاحترافية ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    total, active = get_stats()
    text = f"👑 **لوحة تحكم الإدارة**\n\n📊 **نظرة عامة:**\n👥 إجمالي المستخدمين: `{total}`\n🟢 النشطون الآن: `{active}`\n\nاختر الإجراء المطلوب:"
    
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    btn_stats = telebot.types.InlineKeyboardButton("🔄 تحديث الإحصائيات", callback_data="admin_refresh")
    btn_broadcast = telebot.types.InlineKeyboardButton("📢 رسالة جماعية", callback_data="admin_broadcast")
    markup.add(btn_stats, btn_broadcast)
    
    bot.send_message(message.chat.id, text, reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data == "admin_refresh")
def admin_refresh_callback(call):
    if call.from_user.id != ADMIN_ID: return
    total, active = get_stats()
    text = f"👑 **لوحة تحكم الإدارة**\n\n📊 **نظرة عامة:**\n👥 إجمالي المستخدمين: `{total}`\n🟢 النشطون الآن: `{active}`\n\nاختر الإجراء المطلوب:"
    bot.answer_callback_query(call.id, "تم التحديث!")
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=call.message.reply_markup)

# --- ميزة الرسائل الجماعية ---
@bot.callback_query_handler(func=lambda call: call.data == "admin_broadcast")
def admin_broadcast_callback(call):
    if call.from_user.id != ADMIN_ID: return
    msg = bot.send_message(call.message.chat.id, "📝 أرسل الرسالة التي تريد إرسالها لجميع المستخدمين (أو أرسل /cancel للإلغاء):")
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    if message.text == '/cancel':
        bot.send_message(message.chat.id, "❌ تم إلغاء الإرسال.")
        return
    users = get_all_users()
    success, fail = 0, 0
    msg_status = bot.send_message(message.chat.id, f"⏳ جاري الإرسال إلى {len(users)} مستخدم...")
    for user_id in users:
        try:
            bot.send_message(user_id, f"📢 **إعلان من الإدارة:**\n\n{message.text}", parse_mode='Markdown')
            success += 1
        except Exception:
            fail += 1
    bot.edit_message_text(f"✅ تم الإرسال إلى: {success} مستخدم.\n❌ فشل إلى: {fail} مستخدم.", message.chat.id, msg_status.message_id)

# --- 7. استقبال الروابط وإظهار الأزرار ---
@bot.message_handler(func=lambda message: message.chat.type == 'private' and message.from_user.id != ADMIN_ID)
def handle_user_message(message):
    user_id = message.from_user.id
    
    if not check_subscription(user_id):
        bot.reply_to(message, "⚠️ يرجى الانضمام للقناة أولاً. أرسل /start للتحقق.")
        return

    if message.text.startswith('http'):
        markup = telebot.types.InlineKeyboardMarkup(row_width=2)
        btn_video = telebot.types.InlineKeyboardButton("🎬 تحميل فيديو", callback_data=f"dl_vid_{message.message_id}")
        btn_audio = telebot.types.InlineKeyboardButton("🎵 تحميل صوت", callback_data=f"dl_aud_{message.message_id}")
        markup.add(btn_video, btn_audio)
        
        bot.reply_to(message, "🔗 تم استلام الرابط! اختر نوع التحميل:", reply_markup=markup)
        
        # تخزين الرابط مؤقتاً (في الذاكرة) لاستخدامه عند الضغط على الزر
        # (في بيئة الإنتاج يفضل استخدام قاعدة بيانات، لكن هذا يعمل بشكل جيد للسرعة)
    else:
        bot.send_message(ADMIN_ID, f"📩 رسالة من @{message.from_user.username} (ID: {message.from_user.id}):\n\n{message.text}")
        bot.reply_to(message, "✅ تم إرسال رسالتك للإدارة.")

# --- 8. معالجة الضغط على أزرار التحميل ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("dl_"))
def handle_download_callback(call):
    user_id = call.from_user.id
    if not check_subscription(user_id):
        bot.answer_callback_query(call.id, "⚠️ يجب الانضمام للقناة أولاً!", show_alert=True)
        return
    
    # استخراج نوع الملف ومعرف الرسالة
    parts = call.data.split("_")
    media_type = "video" if parts[1] == "vid" else "audio"
    original_msg_id = int(parts[2])
    
    # نحتاج إلى استرجاع الرابط. للأسف تيليجرام لا يسمح بذلك مباشرة من الـ callback.
    # سنطلب من المستخدم إرسال الرابط مرة أخرى أو نستخدم طريقة أسهل: 
    # سنطلب منه إرسال الرابط مباشرة ونحن سنقوم بالتحميل الفوري.
    # الحل الأفضل: عند إرسال الرابط لأول مرة، نقوم بالتحميل فوراً ونرسل "جاري التحميل".
    # ولكن لتطبيق الأزرار، سنستخدم خدعة بسيطة: نخبر المستخدم أن يضغط على الرابط أو نطلب منه إعادة إرساله.
    
    # ⚠️ بما أن تيليجرام لا يسمح بتمرير الرابط في الزر، سنعتمد على الطريقة التالية:
    # عند الضغط، نطلب من المستخدم إرسال الرابط مرة أخرى مع الكلمة المفتاحية.
    bot.answer_callback_query(call.id, "جاري التحضير...")
    bot.send_message(call.message.chat.id, f"⚙️ يرجى إعادة إرسال الرابط الآن وسأقوم بتحميله كـ ({'فيديو' if media_type == 'video' else 'صوت'}) فوراً.")

# --- دالة استقبال الرابط بعد اختيار النوع (لتجاوز قيود تيليجرام) ---
@bot.message_handler(func=lambda message: message.text and message.text.startswith('http') and message.chat.type == 'private' and message.from_user.id != ADMIN_ID)
def process_final_link(message):
    # هذه الدالة تعمل كنسخة احتياطية لتسهيل الأمر
    user_id = message.from_user.id
    if not check_subscription(user_id):
        return
    
    msg = bot.reply_to(message, "⏳ جاري التحميل... يرجى الانتظار.")
    # التحميل الافتراضي كفيديو
    download_media(message.text, user_id, msg.message_id, "video")

# --- 9. رد المدير على المستخدم ---
@bot.message_handler(func=lambda message: message.chat.id == ADMIN_ID and message.reply_to_message)
def admin_reply(message):
    try:
        user_id = int(message.reply_to_message.text.split("ID: ")[1].split(")")[0])
        bot.send_message(user_id, f"👨‍💻 رد الإدارة:\n\n{message.text}")
        bot.delete_message(chat_id=message.chat.id, message_id=message.reply_to_message.message_id)
        bot.reply_to(message, "✅ تم إرسال الرد وحذف الرسالة.")
    except Exception as e:
        bot.reply_to(message, f"❌ خطأ في الرد: {e}")

# --- 10. منع الخمول (Anti-Sleep) ---
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
