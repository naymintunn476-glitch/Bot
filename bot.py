import os
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters
)

DB_URL = os.environ.get("DATABASE_URL")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Conversation အဆင့်တွေ သတ်မှတ်ခြင်း
ASK_NAME, ASK_AMOUNT, ASK_ITEM, ASK_QTY, ASK_DATE, ASK_TYPE, CONFIRM = range(7)

def get_conn():
    return psycopg2.connect(DB_URL)

# ပင်မမီနူး
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📝 အကြွေးအသစ်ထည့်မည်", callback_data='new_debt')],
        [InlineKeyboardButton("💰 ရှင်းငွေထည့်မည်", callback_data='new_payment')],
        [InlineKeyboardButton("🔍 လူအမည်ဖြင့်ရှာမည်", callback_data='search_customer')],
        [InlineKeyboardButton("📊 စုစုပေါင်းစာရင်း", callback_data='total_summary')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "ဆိုင်မှ ကြိုဆိုပါတယ်။ ဘာလုပ်ဆောင်ချင်ပါသလဲ?"
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

# အကြွေး/ရှင်းငွေ စတင်မယ့် နေရာ
async def start_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    context.user_data['type'] = 'credit' if query.data == 'new_debt' else 'payment'
    action_text = "အကြွေးထည့်" if context.user_data['type'] == 'credit' else "ရှင်းငွေထည့်"
    
    await query.edit_message_text(f"[{action_text}] ဝယ်သူ/အကြွေးရှင်ရဲ့ **အမည်** ကို ရိုက်ထည့်ပါ -", parse_mode='Markdown')
    return ASK_NAME

# အမည်ရိုက်ပြီးရင် ပမာဏ မေးမယ်
async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("**ပမာဏ** (ကျပ်) ကို ရိုက်ထည့်ပါ -", parse_mode='Markdown')
    return ASK_AMOUNT

# ပမာဏရိုက်ပြီးရင် ပစ္စည်းအမည် မေးမယ် (ရှင်းငွေဆိုရင် ကျော်မယ်)
async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['amount'] = float(update.message.text)
    except ValueError:
        await update.message.reply_text("ဂဏန်းပဲ ရိုက်ထည့်ပါဦး။ ပမာဏကို ပြန်ရိုက်ပါ -")
        return ASK_AMOUNT
    
    if context.user_data['type'] == 'credit':
        await update.message.reply_text("**ပစ္စည်းအမည်** ကို ရိုက်ထည့်ပါ -", parse_mode='Markdown')
        return ASK_ITEM
    else:
        await ask_date(update, context)
        return ASK_DATE

# ပစ္စည်းအမည်ရိုက်ပြီးရင် အရေအတွက် မေးမယ်
async def ask_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['item'] = update.message.text
    await update.message.reply_text("**အရေအတွက်** ကို ရိုက်ထည့်ပါ -", parse_mode='Markdown')
    return ASK_QTY

# အရေအတွက်ရိုက်ပြီးရင် ရက်စွဲ မေးမယ်
async def ask_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['qty'] = int(update.message.text)
    except ValueError:
        await update.message.reply_text("ဂဏန်းပဲ ရိုက်ထည့်ပါဦး။ အရေအတွက်ကို ပြန်ရိုက်ပါ -")
        return ASK_QTY
    
    await update.message.reply_text("**ရက်စွဲ** ကို ရိုက်ထည့်ပါ (ဥပမာ - 12.11.2026) -", parse_mode='Markdown')
    return ASK_DATE

# ရက်စွဲရိုက်ပြီးရင် အတည်ပြုဖို့ ပြမယ်
async def ask_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        context.user_data['date'] = update.message.text
    else:
        context.user_data['date'] = "မရှိ"
    
    data = context.user_data
    action = "အကြွေး" if data['type'] == 'credit' else "ရှင်းငွေ"
    
    text = f"**အတည်ပြုပါ -**\n\n"
    text += f"အမျိုးအစား: {action}\n"
    text += f"အမည်: {data['name']}\n"
    text += f"ပမာဏ: {data['amount']} ကျပ်\n"
    
    if data['type'] == 'credit':
        text += f"ပစ္စည်း: {data.get('item', 'မရှိ')} (အရေအတွက် - {data.get('qty', 'မရှိ')})\n"
        
    text += f"ရက်စွဲ: {data['date']}\n"
    
    keyboard = [[InlineKeyboardButton("✅ သိမ်းဆည်းမည်", callback_data='save_entry')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    return CONFIRM

# သိမ်းဆည်းမယ့် နေရာ
async def save_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = context.user_data
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute(
        """INSERT INTO debts (chat_id, customer_name, amount, item_name, quantity, date, type) 
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (query.message.chat.id, data['name'], data['amount'], 
         data.get('item'), data.get('qty'), data['date'], data['type'])
    )
    conn.commit()
    cur.close()
    conn.close()
    
    await query.edit_message_text("✅ အောင်မြင်စွာ သိမ်းဆည်းပြီးပါပြီ။")
    context.user_data.clear() # ဒေတာတွေ ရှင်းလင်းမယ်
    return ConversationHandler.END

# လူအမည်နဲ့ ရှာမယ်
async def search_customer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("ရှာချင်တဲ့ **ဝယ်သူအမည်** ကို ရိုက်ထည့်ပါ -", parse_mode='Markdown')
    return ASK_NAME # ရှာဖွေမှုအတွက် နာမည်ကို ပြန်ယူမယ်

# ရှာဖွေမှု ရလဒ်
async def show_customer_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    conn = get_conn()
    cur = conn.cursor()
    # လူတစ်ယောက်ချင်းစီရဲ့ စုစုပေါင်း အကြွေးနဲ့ ရှင်းငွေကို တွက်မယ်
    cur.execute(
        """SELECT type, amount, item_name, quantity, date FROM debts 
           WHERE chat_id=%s AND customer_name ILIKE %s ORDER BY created_at DESC""",
        (update.effective_chat.id, f"%{name}%")
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    if not rows:
        await update.message.reply_text(f"'{name}' နဲ့ ပတ်သက်တဲ့ မှတ်တမ်း မတွေ့ပါဘူး။")
        return
    
    total_credit = sum(r[1] for r in rows if r[0] == 'credit')
    total_payment = sum(r[1] for r in rows if r[0] == 'payment')
    balance = total_credit - total_payment
    
    text = f"👤 **{name}** ရဲ့ စာရင်း -\n"
    text += "---------------------\n"
    for r in rows:
        if r[0] == 'credit':
            text += f"🔴 [အကြွေး] {r[1]} ကျပ် | {r[2] or ''} {r[3] or ''} | {r[4]}\n"
        else:
            text += f"🟢 [ရှင်းငွေ] {r[1]} ကျပ် | {r[4]}\n"
            
    text += "---------------------\n"
    text += f"စုစုပေါင်း အကြွေး: {total_credit} ကျပ်\n"
    text += f"စုစုပေါင်း ရှင်းငွေ: {total_payment} ကျပ်\n"
    text += f"**လက်ကျန်: {balance} ကျပ်**"
    
    await update.message.reply_text(text, parse_mode='Markdown')
    return ConversationHandler.END

# စုစုပေါင်း စာရင်း ကြည့်မယ်
async def total_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    conn = get_conn()
    cur = conn.cursor()
    # ဆိုင်တစ်ခုလုံးရဲ့ စုစုပေါင်း အကြွေးနဲ့ ရှင်းငွေ
    cur.execute("SELECT type, SUM(amount) FROM debts WHERE chat_id=%s GROUP BY type", (query.message.chat.id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    total_credit = next((r[1] for r in rows if r[0] == 'credit'), 0)
    total_payment = next((r[1] for r in rows if r[0] == 'payment'), 0)
    balance = total_credit - total_payment
    
    text = f"📊 **ဆိုင်ရဲ့ စုစုပေါင်း စာရင်း**\n\n"
    text += f"စုစုပေါင်း အကြွေးပေါင်း: {total_credit} ကျပ်\n"
    text += f"စုစုပေါင်း ရှင်းပြီး: {total_payment} ကျပ်\n"
    text += f"**လက်ကျန် ရရန်ကျန်: {balance} ကျပ်**"
    
    await query.edit_message_text(text, parse_mode='Markdown')

# စကားပြောခြင်းကို ပယ်ဖျက်မယ်
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ပယ်ဖျက်လိုက်ပါပြီ။")
    return ConversationHandler.END

# Application စတင်ခြင်း
app = ApplicationBuilder().token(TOKEN).build()

# Conversation Handler (အဆင့်ဆင့်မေးတဲ့ စနစ်)
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
        ASK_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_date)],
        CONFIRM: [CallbackQueryHandler(save_entry, pattern='^save_entry$')],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

# ရှာဖွေမှု ရလဒ်ပြသဖို့ သီးသန့် handler (Conversation နဲ့ ရောနေလို့)
search_conv = ConversationHandler(
    entry_points=[CallbackQueryHandler(search_customer, pattern='^search_customer$')],
    states={
        ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_customer_data)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

# ချိတ်ဆက်ခြင်း
app.add_handler(CommandHandler("start", start))
app.add_handler(conv_handler)
app.add_handler(search_conv) # ရှာဖွေမှုအတွက်
app.add_handler(CallbackQueryHandler(total_summary, pattern='^total_summary$'))

app.run_polling()
