import datetime
import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# --- APNI DETAILS YAHAN DAALEIN ---
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"      # @BotFather wala Token
ADMIN_ID = 123456789                  # Apni Telegram User ID (@userinfobot se milegi)
CHANNEL_ID = -1001234567890           # Channel ID (minus ke sath)

def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS members (
            user_id INTEGER PRIMARY KEY,
            expiry_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Monthly: ₹199 / 30 Days", callback_data='plan_30')],
        [InlineKeyboardButton("3 Months: ₹550 / 90 Days", callback_data='plan_90')],
        [InlineKeyboardButton("6 Months: ₹1000 / 180 Days", callback_data='plan_180')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👋 **Premium Membership Select Karein:**", reply_markup=reply_markup, parse_mode='Markdown')

async def plan_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    days = query.data.split('_')[1]
    
    context.user_data['pending_days'] = days
    
    # Apna UPI ID badlein
    text = f"Aapne **{days} Days** ka plan select kiya hai.\n\n👉 UPI ID: `yourname@paytm` par payment karke screenshot yahan bhej dein."
    await query.edit_message_text(text=text, parse_mode='Markdown')

async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'pending_days' not in context.user_data:
        await update.message.reply_text("Pehle /start karke plan select karein.")
        return
        
    days = context.user_data['pending_days']
    user = update.effective_user
    
    keyboard = [
        [InlineKeyboardButton("✅ Approve", callback_data=f"app_{user.id}_{days}"),
         InlineKeyboardButton("❌ Reject", callback_data=f"rej_{user.id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    caption = f"🚨 **NEW PAYMENT PROOF!**\n\nUser: {user.full_name} (@{user.username})\nID: `{user.id}`\nPlan: {days} Days"
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=update.message.photo[-1].file_id, caption=caption, reply_markup=reply_markup, parse_mode='Markdown')
    
    await update.message.reply_text("Aapka payment proof mil gaya hai. Admin approval ke baad link mil jayega.")

async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split('_')
    action = data[0]
    user_id = int(data[1])
    
    if action == "app":
        days = int(data[2])
        expiry_date = datetime.date.today() + datetime.timedelta(days=days)
        
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO members VALUES (?, ?)", (user_id, expiry_date.isoformat()))
        conn.commit()
        conn.close()
        
        invite_link = await context.bot.create_chat_invite_link(chat_id=CHANNEL_ID, member_limit=1)
        
        await context.bot.send_message(chat_id=user_id, text=f"🎉 **Payment Approved!**\n\nJoin Link: {invite_link.invite_link}\nValid till: {expiry_date}")
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n✅ **APPROVED ({days} Days)**", parse_mode='Markdown')
        
    elif action == "rej":
        await context.bot.send_message(chat_id=user_id, text="❌ Aapka payment proof reject ho gaya hai. Dobara sahi screenshot bhejye.")
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n❌ **REJECTED**", parse_mode='Markdown')

async def check_expirations(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.date.today().isoformat()
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM members WHERE expiry_date <= ?", (today,))
    expired_users = cursor.fetchall()

    for user in expired_users:
        u_id = user[0]
        try:
            await context.bot.ban_chat_member(chat_id=CHANNEL_ID, user_id=u_id)
            await context.bot.unban_chat_member(chat_id=CHANNEL_ID, user_id=u_id)
            await context.bot.send_message(chat_id=u_id, text="Aapki membership expire ho gayi hai.")
            cursor.execute("DELETE FROM members WHERE user_id = ?", (u_id,))
            conn.commit()
        except Exception as e:
            print(f"Error: {e}")
    conn.close()

if __name__ == '__main__':
    init_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(plan_selected, pattern='^plan_'))
    app.add_handler(MessageHandler(filters.PHOTO, handle_screenshot))
    app.add_handler(CallbackQueryHandler(admin_action, pattern='^(app|rej)_'))
    
    job_queue = app.job_queue
    job_queue.run_repeating(check_expirations, interval=86400, first=10)
    
    print("Bot Running...")
    app.run_polling()
