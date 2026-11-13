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

# Conversation အဆင့်တွေ (အားလုံးကို စနစ်တကျ သတ်မှတ်ထားပါတယ်)
(
    ASK_NAME, ASK_AMOUNT, ASK_ITEM, ASK_QTY, ASK_DATE,
    ASK_PAY_NAME, ASK_PAY_ITEM, ASK_PAY_QTY, ASK_PAY_AMT, ASK_SEARCH
) = range(10)

def get_conn():
    return psycopg2.connect(DB_URL)

def get_main_menu():
    keyboard = [
        [InlineKeyboardButton("📝 အကြွေးအသစ်ထည့်မည်", callback_data='new_debt')],
        [InlineKeyboardButton("💰 ရှင်းငွေထည့်မည်", callback_data='new_payment')],
        [InlineKeyboardButton("🔍 လူအမည်ဖြင့်ရှာမည်", callback_data='search_customer')],
        [InlineKeyboardButton("📊 စုစုပေါင်းစာရင်း", callback_data='total_summary')]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "DebtNoteမှ ကြိုဆိုပါတယ်။ ဘာလုပ်ဆောင်ချင်ပါသလဲ?"
    if update.message:
        await update.message.reply_text(text, reply_markup=get_main_menu())
    else:
        await update.callback_query.edit_message_text(text, reply_markup=get_main_menu())

# ================== အကြွေး ထည့်ခြင်း ==================

async def start_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'new_debt':
        await query.edit_message_text("ဝယ်သူ/အကြွေးရှင်ရဲ့ **အမည်** ကို ရိုက်ထည့်ပါ -", parse_mode='Markdown')
        return ASK_NAME
    else:
        await query.edit_message_text("ရှင်းငွေဆပ်မယ့် သူရဲ့ **အမည်** ကို ရိုက်ထည့်ပါ -", parse_mode='Markdown')
        return ASK_PAY_NAME

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
    
    await update.message.reply_text("**ပစ္စည်းအမည်** ကို ရိုက်ထည့်ပါ -", parse_mode='Markdown')
    return ASK_ITEM

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
    
    # ဖုန်းရဲ့ ရက်စွဲကို ယူဖို့ ခလုတ်ပြမယ်
    keyboard = [[InlineKeyboardButton("📅 ယနေ့ရက်စွဲကို သုံးမည်", callback_data='use_today')]]
    await update.message.reply_text("ရက်စွဲကို သတ်မှတ်ဖို့ အောက်က ခလုတ်ကို နှိပ်ပါ (ဒါမှမဟုတ် ကိုယ်တိုင်ရိုက်ထည့်နိုင်ပါတယ်) -", reply_markup=InlineKeyboardMarkup(keyboard))
    return ASK_DATE

async def ask_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()
        # ဖုန်းရဲ့ ရက်စွဲကို ယူမယ်
        context.user_data['date'] = datetime.now().strftime("%d.%m.%Y")
        await update.callback_query.edit_message_text("ရက်စွဲကို ယူပြီးပါပြီ။")
    else:
        context.user_data['date'] = update.message.text

    data = context.user_data
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute(
        """INSERT INTO debts (chat_id, customer_name, amount, item_name, quantity, date, type) 
           VALUES (%s, %s, %s, %s, %s, %s, 'credit')""",
        (update.effective_chat.id, data['name'], data['amount'], 
         data.get('item'), data.get('qty'), data['date'])
    )
    conn.commit()
    cur.close()
    conn.close()
    
    msg = f"✅ {data['name']} အတွက် အကြွေး {data['amount']} ကျပ် သိမ်းဆည်းပြီးပါပြီ။\n"
    await update.effective_chat.send_message(msg, reply_markup=get_main_menu())
    context.user_data.clear()
    return ConversationHandler.END

# ================== ရှင်းငွေ ထည့်ခြင်း ==================

async def ask_pay_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    context.user_data['pay_name'] = name
    
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, item_name, quantity, amount FROM debts 
           WHERE chat_id=%s AND customer_name ILIKE %s AND type='credit' AND amount > 0""",
        (update.effective_chat.id, f"%{name}%")
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    if not rows:
        await update.message.reply_text(f"'{name}' နာမည်နဲ့ ကျန်နေတဲ့ အကြွေး မရှိပါဘူး။", reply_markup=get_main_menu())
        return ConversationHandler.END

    keyboard = []
    for r in rows:
        btn_text = f"{r[1] or 'အကြွေး'} ({r[2] or '-'}) - {r[3]} ကျပ်"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"pay_{r[0]}")])
    
    await update.message.reply_text(
        f"{name} ရဲ့ ရှင်းချင်တဲ့ **ပစ္စည်း/အကြွေး** ကို ရွေးပါ -", 
        reply_markup=InlineKeyboardMarkup(keyboard), 
        parse_mode='Markdown'
    )
    return ASK_PAY_ITEM

async def ask_pay_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    debt_id = int(query.data.split('_')[1])
    context.user_data['pay_id'] = debt_id
    
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT item_name, quantity, amount FROM debts WHERE id=%s", (debt_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    
    context.user_data['pay_item_name'] = row[0]
    context.user_data['pay_old_qty'] = row[1]
    context.user_data['pay_old_amt'] = row[2]
    
    text = f"ရွေးထားတဲ့ အကြွေး - {row[0] or 'အကြွေး'} (လက်ကျန် {row[1] or '-'} / {row[2]} ကျပ်)\n\n"
    text += "ရှင်းမယ့် **အရေအတွက်** ကို ရိုက်ထည့်ပါ (မရှိရင် 0 ရိုက်ပါ) -"
    
    await query.edit_message_text(text, parse_mode='Markdown')
    return ASK_PAY_QTY

async def ask_pay_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['pay_qty'] = int(update.message.text)
    except ValueError:
        await update.message.reply_text("ဂဏန်းပဲ ရိုက်ထည့်ပါဦး။ အရေအတွက်ကို ပြန်ရိုက်ပါ -")
        return ASK_PAY_QTY
        
    await update.message.reply_text("ရှင်းမယ့် **ပမာဏ** (ကျပ်) ကို ရိုက်ထည့်ပါ -", parse_mode='Markdown')
    return ASK_PAY_AMT

async def ask_pay_amt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        pay_amt = float(update.message.text)
    except ValueError:
        await update.message.reply_text("ဂဏန်းပဲ ရိုက်ထည့်ပါဦး။ ပမာဏကို ပြန်ရိုက်ပါ -")
        return ASK_PAY_AMT

    data = context.user_data
    debt_id = data['pay_id']
    
    today_date = datetime.now().strftime("%d.%m.%Y")
    
    conn = get_conn()
    cur = conn.cursor()
    
    # ရှင်းငွေကို မှတ်တမ်းတင်မယ် (type='payment')
    cur.execute(
        """INSERT INTO debts (chat_id, customer_name, amount, item_name, date, type) 
           VALUES (%s, %s, %s, %s, %s, 'payment')""",
        (update.effective_chat.id, data['pay_name'], pay_amt, data['pay_item_name'], today_date)
    )
    
    # မူလအကြွေးထဲကနေ နုတ်မယ်
    new_amt = data['pay_old_amt'] - pay_amt
    new_qty = (data['pay_old_qty'] or 0) - data['pay_qty']
    
    if new_amt <= 0:
        # ပမာဏ 0 ဖြစ်သွားရင် ဖျက်မယ်
        cur.execute("DELETE FROM debts WHERE id=%s", (debt_id,))
    else:
        # မကုန်သေးရင် update လုပ်မယ်
        cur.execute("UPDATE debts SET amount=%s, quantity=%s WHERE id=%s", (new_amt, new_qty, debt_id))
        
    conn.commit()
    cur.close()
    conn.close()
    
    msg = f"✅ {data['pay_name']} အတွက် ရှင်းငွေ {pay_amt} ကျပ် သိမ်းဆည်းပြီးပါပြီ။\n"
    if new_amt <= 0:
        msg += f"({data['pay_item_name']} အကြွေး အကုန်ရှင်းပြီးပါပြီ)"
    else:
        msg += f"({data['pay_item_name']} အတွက် ကျန်ရှိ - {new_amt} ကျပ်)"
        
    await update.message.reply_text(msg, reply_markup=get_main_menu())
    context.user_data.clear()
    return ConversationHandler.END

# ================== ရှာဖွေခြင်း နှင့် စုစုပေါင်း ==================

async def search_customer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("ရှာချင်တဲ့ **ဝယ်သူအမည်** ကို ရိုက်ထည့်ပါ -", parse_mode='Markdown')
    return ASK_SEARCH

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

async def total_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    conn = get_conn()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT customer_name, SUM(amount) as total_balance
        FROM debts 
        WHERE chat_id=%s AND type = 'credit' AND amount > 0
        GROUP BY customer_name
        ORDER BY customer_name
    """, (query.message.chat.id,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    if not rows:
        await query.edit_message_text("လက်ကျန် အကြွေး မရှိပါဘူး။", reply_markup=get_main_menu())
        return

    text = "📊 **စုစုပေါင်း လက်ကျန်အကြွေး**\n"
    text += "━━━━━━━━━━━━━━━\n"
    
    grand_total = 0
    
    for r in rows:
        name = r[0]
        balance = r[1]
        grand_total += balance
        text += f"👤 {name}: {balance} ကျပ်\n"
            
    text += "━━━━━━━━━━━━━━━\n"
    text += f"💰 **စုစုပေါင်း ရရန်ကျန်: {grand_total} ကျပ်**"
    
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
        ASK_DATE: [
            CallbackQueryHandler(ask_date, pattern='^use_today$'),
            MessageHandler(filters.TEXT & ~filters.COMMAND, ask_date)
        ],
        ASK_PAY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_pay_name)],
        ASK_PAY_ITEM: [CallbackQueryHandler(ask_pay_item, pattern='^pay_')],
        ASK_PAY_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_pay_qty)],
        ASK_PAY_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_pay_amt)],
        ASK_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_customer_data)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)

app.add_handler(CommandHandler("start", start))
app.add_handler(conv_handler)
app.add_handler(CallbackQueryHandler(total_summary, pattern='^total_summary$'))

if __name__ == '__main__':
    app.run_polling()
