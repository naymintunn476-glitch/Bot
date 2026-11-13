import os
import psycopg2
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)

DB_URL = os.environ.get("DATABASE_URL")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Conversation အဆင့်တွေ
ASK_NAME, ASK_AMOUNT, ASK_ITEM, ASK_QTY, ASK_SEARCH = range(5)

def get_conn():
    return psycopg2.connect(DB_URL)

# မီနူး ခလုတ်တွေ ပြန်ထုတ်ပေးမယ့် function
def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("📝 အကြွေးအသစ်ထည့်မည်", callback_data='new_debt')],
        [InlineKeyboardButton("💰 ရှင်းငွေထည့်မည်", callback_data='new_payment')],
        [InlineKeyboardButton("🔍 လူအမည်ဖြင့်ရှာမည်", callback_data='search_customer')],
        [InlineKeyboardButton("📊 စုစုပေါင်းစာရင်း", callback_data='total_summary')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "ဆိုင်မှ ကြိုဆိုပါတယ်။ ဘာလုပ်ဆောင်ချင်ပါသလဲ?"
    if update.message:
        await update.message.reply_text(text, reply_markup=get_main_menu())
    else:
        await update.callback_query.edit_message_text(text, reply_markup=get_main_menu())

# အကြွေး/ရှင်းငွေ စတင်မယ့် နေရာ
async def start_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['type'] = 'credit' if query.data == 'new_debt' else 'payment'
    action_text = "အကြွေးထည့်" if context.user_data['type'] == 'credit' else "ရှင်းငွေထည့်"
    
    await query.edit_message_text(f"[{action_text}] ဝယ်သူ/အကြွေးရှင်ရဲ့ **အမည်** ကို ရိုက်ထည့်ပါ -", parse_mode='Markdown')
    return ASK_NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("**ပမာဏ** (ကျပ်) ကို ရိုက်ထည့်ပါ -", parse_mode='Markdown')
    return ASK_AMOUNT

async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['amount'] = float(update.message.text)
    except ValueError:
        await update.message.reply_text("ဂဏန်းပဲ ရိုက်ထည့်ပါဦး။ ပမာဏကို ပြန်ရိုက်ပါ -")
        return ASK_AMOUNT
    
    # ရက်စွဲကို အလိုအလျောက် သတ်မှတ်မယ်
    context.user_data['date'] = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    if context.user_data['type'] == 'credit':
        await update.message.reply_text("**ပစ္စည်းအမည်** ကို ရိုက်ထည့်ပါ -", parse_mode='Markdown')
        return ASK_ITEM
    else:
        # ရှင်းငွေဆိုရင် ပစ္စည်း၊ အရေအတွက် မလိုဘူး၊ တိုက်ရိုက်သိမ်းမယ်
        await save_to_db(update, context)
        return ConversationHandler.END

async def ask_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['item'] = update.message.text
    await update.message.reply_text("**အရေအတွက်** ကို ရိုက်ထည့်ပါ -", parse_mode='Markdown')
    return ASK_QTY

async def ask_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['qty'] = int(update.message.text)
    except ValueError:
        await update.message.reply_text("ဂဏန်းပဲ ရိုက်ထည့်ပါဦး။ အရေအတွက်ကို ပြန်ရိုက်ပါ -")
        return ASK_QTY
    
    await save_to_db(update, context)
    return ConversationHandler.END

# Database ထဲ သိမ်းမယ့် function
async def save_to_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute(
        """INSERT INTO debts (chat_id, customer_name, amount, item_name, quantity, date, type) 
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (update.effective_chat.id, data['name'], data['amount'], 
         data.get('item'), data.get('qty'), data['date'], data['type'])
    )
    conn.commit()
    cur.close()
    conn.close()
    
    action = "အကြွေး" if data['type'] == 'credit' else "ရှင်းငွေ"
    msg = f"✅ {data['name']} အတွက် {action} {data['amount']} ကျပ် သိမ်းဆည်းပြီးပါပြီ။\n"
    
    # သိမ်းပြီးတာနဲ့ မီနူး ပြန်ပေါ်လာအောင် လုပ်မယ်
    await update.message.reply_text(msg, reply_markup=get_main_menu())
    context.user_data.clear()

# လူအမည်နဲ့ ရှာမယ့် နေရာ
async def search_customer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("ရှာချင်တဲ့ **ဝယ်သူအမည်** ကို ရိုက်ထည့်ပါ -", parse_mode='Markdown')
    return ASK_SEARCH

# ရှာဖွေမှု ရလဒ်နဲ့ Voucher ပြသခြင်း
async def show_customer_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute(
        """SELECT type, amount, item_name, quantity, date FROM debts 
           WHERE chat_id=%s AND customer_name ILIKE %s ORDER BY created_at ASC""",
        (update.effective_chat.id, f"%{name}%")
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    if not rows:
        await update.message.reply_text(f"'{name}' နဲ့ ပတ်သက်တဲ့ မှတ်တမ်း မတွေ့ပါဘူး။", reply_markup=get_main_menu())
        return ConversationHandler.END
    
    text = f"👤 **{name}** ရဲ့ အသေးစိတ် စာရင်း -\n"
    text += "━━━━━━━━━━━━━━━\n"
    
    # Voucher တစ်ခုချင်းစီ ပြမယ်
    for i, r in enumerate(rows, 1):
        if r[0] == 'credit':
            text += f"🧾 **Voucher {i}** (အကြွေး)\n"
            text += f"├ ပစ္စည်း: {r[2] or 'မရှိ'}\n"
            text += f"├ အရေအတွက်: {r[3] or 'မရှိ'}\n"
            text += f"├ ပမာဏ: {r[1]} ကျပ်\n"
            text += f"└ ရက်စွဲ: {r[4]}\n\n"
        else:
            text += f"🧾 **Voucher {i}** (ရှင်းငွေ)\n"
            text += f"├ ပမာဏ: {r[1]} ကျပ်\n"
            text += f"└ ရက်စွဲ: {r[4]}\n\n"
            
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=get_main_menu())
    return ConversationHandler.END

# စုစုပေါင်း စာရင်း (နာမည်နဲ့ ပမာဏ တန်းပြမယ်)
async def total_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    conn = get_conn()
    cur = conn.cursor()
    # လူတစ်ယောက်ချင်းစီရဲ့ အကြွေး၊ ရှင်းငွေ တွက်မယ်
    cur.execute("""
        SELECT customer_name, 
               SUM(CASE WHEN type = 'credit' THEN amount ELSE 0 END) as total_credit,
               SUM(CASE WHEN type = 'payment' THEN amount ELSE 0 END) as total_payment
        FROM debts 
        WHERE chat_id=%s 
        GROUP BY customer_name
        ORDER BY customer_name
    """, (query.message.chat.id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    if not rows:
        await query.edit_message_text("မှတ်တမ်း မရှိသေးပါဘူး။", reply_markup=get_main_menu())
        return

    text = "📊 **စုစုပေါင်း အကြွေးစာရင်း**\n"
    text += "━━━━━━━━━━━━━━━\n"
    
    grand_credit = 0
    grand_payment = 0
    
    for r in rows:
        name = r[0]
        credit = r[1]
        payment = r[2]
        balance = credit - payment
        
        grand_credit += credit
        grand_payment += payment
        
        # လူတစ်ယောက်ချင်းစီရဲ့ လက်ကျန်ကို ပြမယ်
        if balance > 0:
            text += f"👤 {name}: {balance} ကျပ် (အကြွေး)\n"
        elif balance < 0:
            text += f"👤 {name}: {abs(balance)} ကျပ် (ပိုငွေ/ရှင်းပြီး)\n"
        else:
            text += f"👤 {name}: 0 ကျပ် (ရှင်းပြီး)\n"
            
    text += "━━━━━━━━━━━━━━━\n"
    text += f"📥 စုစုပေါင်း အကြွေး: {grand_credit} ကျပ်\n"
    text += f"📤 စုစုပေါင်း ရှင်းငွေ: {grand_payment} ကျပ်\n"
    text += f"💰 **လက်ကျန် ရရန်ကျန်: {grand_credit - grand_payment} ကျပ်**"
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=get_main_menu())

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ပယ်ဖျက်လိုက်ပါပြီ။", reply_markup=get_main_menu())
    return ConversationHandler.END

# Application စတင်ခြင်း
app = ApplicationBuilder().token(TOKEN).build()

conv_handler = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(start_entry, pattern='^(new_debt|new_payment)$'),
        CallbackQueryHandler(search_customer, pattern='^search_customer$'),
    ],
    states={
        ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
        ASK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_amount)],
        ASK_ITEM: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_item)],
        ASK_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_qty)],
        ASK_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_customer_data)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

app.add_handler(CommandHandler("start", start))
app.add_handler(conv_handler)
app.add_handler(CallbackQueryHandler(total_summary, pattern='^total_summary$'))

app.run_polling()
