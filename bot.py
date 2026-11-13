
import os
import psycopg2

from decimal import Decimal, InvalidOperation
from datetime import datetime
from contextlib import closing

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters
)


# ==========================================
# CONFIGURATION
# ==========================================

DB_URL = os.environ.get("DATABASE_URL")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

if not DB_URL:
    raise ValueError("DATABASE_URL မတွေ့ပါ။ Environment Variable စစ်ပါ။")

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN မတွေ့ပါ။ Environment Variable စစ်ပါ။")


# ==========================================
# CONVERSATION STATES
# ==========================================

(
    ASK_NAME,
    ASK_AMOUNT,
    ASK_ITEM,
    ASK_QTY,
    ASK_DATE,
    ASK_PAY_NAME,
    ASK_PAY_ITEM,
    ASK_PAY_QTY,
    ASK_PAY_AMT,
    ASK_SEARCH
) = range(10)


# ==========================================
# DATABASE CONNECTION
# ==========================================

def get_conn():
    return psycopg2.connect(DB_URL)


# ==========================================
# DECIMAL HELPER
# ==========================================

def parse_amount(value):
    value = str(value).strip().replace(",", "")
    amount = Decimal(value)

    if not amount.is_finite():
        raise InvalidOperation

    return amount


# ==========================================
# MAIN MENU
# ==========================================

def get_main_menu():

    keyboard = [
        [
            InlineKeyboardButton(
                "📝 အကြွေးအသစ်ထည့်မည်",
                callback_data="new_debt"
            )
        ],
        [
            InlineKeyboardButton(
                "💰 ရှင်းငွေထည့်မည်",
                callback_data="new_payment"
            )
        ],
        [
            InlineKeyboardButton(
                "🔍 လူအမည်ဖြင့်ရှာမည်",
                callback_data="search_customer"
            )
        ],
        [
            InlineKeyboardButton(
                "📊 စုစုပေါင်းစာရင်း",
                callback_data="total_summary"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# ==========================================
# START
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data.clear()

    text = (
        "🏪 ဆိုင်မှ ကြိုဆိုပါတယ်။\n\n"
        "ဘာလုပ်ဆောင်ချင်ပါသလဲ?"
    )

    if update.message:

        await update.message.reply_text(
            text,
            reply_markup=get_main_menu()
        )

    elif update.callback_query:

        await update.callback_query.answer()

        await update.callback_query.edit_message_text(
            text,
            reply_markup=get_main_menu()
        )


# ==========================================
# START NEW DEBT / PAYMENT
# ==========================================

async def start_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    context.user_data.clear()

    if query.data == "new_debt":

        await query.edit_message_text(
            "👤 ဝယ်သူ/အကြွေးရှင်ရဲ့ အမည်ကို ရိုက်ထည့်ပါ -"
        )

        return ASK_NAME

    else:

        await query.edit_message_text(
            "👤 ရှင်းငွေဆပ်မယ့်သူရဲ့ အမည်ကို ရိုက်ထည့်ပါ -"
        )

        return ASK_PAY_NAME


# ==========================================
# NEW DEBT - CUSTOMER NAME
# ==========================================

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):

    name = update.message.text.strip()

    if not name:
        await update.message.reply_text("အမည်ကို ပြန်ရိုက်ထည့်ပါ။")
        return ASK_NAME

    context.user_data["name"] = name

    await update.message.reply_text(
        "💰 အကြွေးပမာဏ (ကျပ်) ကို ရိုက်ထည့်ပါ -"
    )

    return ASK_AMOUNT


# ==========================================
# NEW DEBT - AMOUNT
# ==========================================

async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:

        amount = parse_amount(update.message.text)

        if amount <= Decimal("0"):
            raise InvalidOperation

        context.user_data["amount"] = amount

    except (ValueError, InvalidOperation):

        await update.message.reply_text(
            "❌ မှန်ကန်တဲ့ ငွေပမာဏကို ပြန်ရိုက်ထည့်ပါ -"
        )

        return ASK_AMOUNT

    await update.message.reply_text(
        "📦 ပစ္စည်းအမည်ကို ရိုက်ထည့်ပါ -"
    )

    return ASK_ITEM


# ==========================================
# NEW DEBT - ITEM
# ==========================================

async def ask_item(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data["item"] = update.message.text.strip()

    await update.message.reply_text(
        "🔢 အရေအတွက်ကို ရိုက်ထည့်ပါ -"
    )

    return ASK_QTY


# ==========================================
# NEW DEBT - QUANTITY
# ==========================================

async def ask_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:

        qty = int(update.message.text.strip())

        if qty <= 0:
            raise ValueError

        context.user_data["qty"] = qty

    except ValueError:

        await update.message.reply_text(
            "❌ မှန်ကန်တဲ့ အရေအတွက်ကို ပြန်ရိုက်ထည့်ပါ -"
        )

        return ASK_QTY

    keyboard = [
        [
            InlineKeyboardButton(
                "📅 ယနေ့ရက်စွဲကို သုံးမည်",
                callback_data="use_today"
            )
        ]
    ]

    await update.message.reply_text(
        "📅 ရက်စွဲသတ်မှတ်ရန် အောက်ပါခလုတ်ကို နှိပ်ပါ။\n"
        "သို့မဟုတ် ရက်စွဲကို ကိုယ်တိုင်ရိုက်ထည့်နိုင်ပါတယ်။",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return ASK_DATE


# ==========================================
# NEW DEBT - SAVE DATE
# ==========================================

async def ask_date(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.callback_query:

        await update.callback_query.answer()

        date = datetime.now().strftime("%d.%m.%Y")

        await update.callback_query.edit_message_text(
            f"📅 ရက်စွဲ - {date}"
        )

    else:

        date = update.message.text.strip()

    data = context.user_data

    try:

        with closing(get_conn()) as conn:

            with conn:

                with conn.cursor() as cur:

                    cur.execute(
                        """
                        INSERT INTO debts
                        (
                            chat_id,
                            customer_name,
                            amount,
                            item_name,
                            quantity,
                            date,
                            type
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, 'credit')
                        """,
                        (
                            update.effective_chat.id,
                            data["name"],
                            data["amount"],
                            data["item"],
                            data["qty"],
                            date
                        )
                    )

        msg = (
            f"✅ အကြွေးမှတ်တမ်း သိမ်းဆည်းပြီးပါပြီ။\n\n"
            f"👤 အမည်: {data['name']}\n"
            f"📦 ပစ္စည်း: {data['item']}\n"
            f"🔢 အရေအတွက်: {data['qty']}\n"
            f"💰 ပမာဏ: {data['amount']} ကျပ်\n"
            f"📅 ရက်စွဲ: {date}"
        )

    except Exception as e:

        msg = f"❌ Database Error: {str(e)}"

    await update.effective_chat.send_message(
        msg,
        reply_markup=get_main_menu()
    )

    context.user_data.clear()

    return ConversationHandler.END


# ==========================================
# PAYMENT - CUSTOMER NAME
# ==========================================

async def ask_pay_name(update: Update, context: ContextTypes.DEFAULT_TYPE):

    name = update.message.text.strip()

    context.user_data["pay_name"] = name

    try:

        with closing(get_conn()) as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT id, item_name, quantity, amount
                    FROM debts
                    WHERE chat_id = %s
                    AND customer_name ILIKE %s
                    AND type = 'credit'
                    AND amount > 0
                    ORDER BY created_at ASC
                    """,
                    (
                        update.effective_chat.id,
                        f"%{name}%"
                    )
                )

                rows = cur.fetchall()

    except Exception as e:

        await update.message.reply_text(
            f"❌ Database Error: {str(e)}",
            reply_markup=get_main_menu()
        )

        context.user_data.clear()

        return ConversationHandler.END

    if not rows:

        await update.message.reply_text(
            f"'{name}' နာမည်နဲ့ ကျန်ရှိတဲ့ အကြွေး မတွေ့ပါဘူး။",
            reply_markup=get_main_menu()
        )

        context.user_data.clear()

        return ConversationHandler.END

    keyboard = []

    for r in rows:

        btn_text = (
            f"{r[1] or 'အကြွေး'} "
            f"({r[2] if r[2] is not None else '-'}) "
            f"- {r[3]} ကျပ်"
        )

        keyboard.append(
            [
                InlineKeyboardButton(
                    btn_text,
                    callback_data=f"pay_{r[0]}"
                )
            ]
        )

    await update.message.reply_text(
        f"📋 {name} ရဲ့ ရှင်းချင်တဲ့ အကြွေးကို ရွေးပါ -",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return ASK_PAY_ITEM


# ==========================================
# PAYMENT - SELECT DEBT
# ==========================================

async def ask_pay_item(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    debt_id = int(query.data.split("_", 1)[1])

    try:

        with closing(get_conn()) as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT item_name, quantity, amount
                    FROM debts
                    WHERE id = %s
                    AND chat_id = %s
                    AND type = 'credit'
                    """,
                    (
                        debt_id,
                        update.effective_chat.id
                    )
                )

                row = cur.fetchone()

        if not row:

            await query.edit_message_text(
                "❌ အကြွေးမှတ်တမ်း မတွေ့ပါဘူး။"
            )

            return ConversationHandler.END

        context.user_data["pay_id"] = debt_id

        context.user_data["pay_item_name"] = row[0]

        context.user_data["pay_old_qty"] = (
            int(row[1]) if row[1] is not None else 0
        )

        # Decimal ကို Decimal အတိုင်းပဲ သိမ်းမယ်
        context.user_data["pay_old_amt"] = Decimal(str(row[2]))

        text = (
            f"📦 ရွေးထားတဲ့ပစ္စည်း: {row[0] or 'အကြွေး'}\n"
            f"🔢 လက်ကျန်အရေအတွက်: {context.user_data['pay_old_qty']}\n"
            f"💰 လက်ကျန်ငွေ: {context.user_data['pay_old_amt']} ကျပ်\n\n"
            f"ရှင်းမယ့် အရေအတွက်ကို ရိုက်ထည့်ပါ။\n"
            f"(အရေအတွက်မရှင်းပါက 0 ရိုက်ပါ)"
        )

        await query.edit_message_text(text)

        return ASK_PAY_QTY

    except Exception as e:

        await query.edit_message_text(
            f"❌ Error: {str(e)}"
        )

        return ConversationHandler.END


# ==========================================
# PAYMENT - QUANTITY
# ==========================================

async def ask_pay_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:

        qty = int(update.message.text.strip())

        old_qty = context.user_data["pay_old_qty"]

        if qty < 0 or qty > old_qty:
            raise ValueError

        context.user_data["pay_qty"] = qty

    except ValueError:

        await update.message.reply_text(
            "❌ မှန်ကန်တဲ့ အရေအတွက်ကို ရိုက်ထည့်ပါ။\n"
            "လက်ကျန်အရေအတွက်ထက် မကျော်ရပါ။"
        )

        return ASK_PAY_QTY

    await update.message.reply_text(
        "💰 ရှင်းမယ့် ပမာဏ (ကျပ်) ကို ရိုက်ထည့်ပါ -"
    )

    return ASK_PAY_AMT


# ==========================================
# PAYMENT - AMOUNT
# ==========================================

async def ask_pay_amt(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:

        pay_amt = parse_amount(update.message.text)

        if pay_amt <= Decimal("0"):
            raise InvalidOperation

    except (ValueError, InvalidOperation):

        await update.message.reply_text(
            "❌ မှန်ကန်တဲ့ ငွေပမာဏကို ပြန်ရိုက်ထည့်ပါ -"
        )

        return ASK_PAY_AMT

    data = context.user_data

    debt_id = data["pay_id"]

    old_amt = Decimal(str(data["pay_old_amt"]))

    old_qty = int(data["pay_old_qty"])

    pay_qty = int(data["pay_qty"])

    if pay_amt > old_amt:

        await update.message.reply_text(
            f"❌ ရှင်းမယ့်ငွေက လက်ကျန်ငွေထက် များနေပါတယ်။\n"
            f"လက်ကျန်ငွေ: {old_amt} ကျပ်\n"
            f"ပြန်ရိုက်ထည့်ပါ -"
        )

        return ASK_PAY_AMT

    new_amt = old_amt - pay_amt

    new_qty = old_qty - pay_qty

    today_date = datetime.now().strftime("%d.%m.%Y")

    try:

        with closing(get_conn()) as conn:

            with conn:

                with conn.cursor() as cur:

                    # လက်ရှိအကြွေးကို ထပ်မံစစ်ဆေးပြီး Lock ချမယ်
                    cur.execute(
                        """
                        SELECT amount, quantity
                        FROM debts
                        WHERE id = %s
                        AND chat_id = %s
                        AND type = 'credit'
                        FOR UPDATE
                        """,
                        (
                            debt_id,
                            update.effective_chat.id
                        )
                    )

                    current = cur.fetchone()

                    if not current:
                        raise ValueError("အကြွေးမှတ်တမ်း မတွေ့ပါ။")

                    current_amt = Decimal(str(current[0]))

                    current_qty = (
                        int(current[1]) if current[1] is not None else 0
                    )

                    if pay_amt > current_amt or pay_qty > current_qty:
                        raise ValueError(
                            "အကြွေးလက်ကျန် ပြောင်းလဲသွားပါပြီ။ ပြန်စစ်ဆေးပါ။"
                        )

                    new_amt = current_amt - pay_amt

                    new_qty = current_qty - pay_qty

                    # ရှင်းငွေမှတ်တမ်း သိမ်းမယ်
                    cur.execute(
                        """
                        INSERT INTO debts
                        (
                            chat_id,
                            customer_name,
                            amount,
                            item_name,
                            date,
                            type
                        )
                        VALUES (%s, %s, %s, %s, %s, 'payment')
                        """,
                        (
                            update.effective_chat.id,
                            data["pay_name"],
                            pay_amt,
                            data["pay_item_name"],
                            today_date
                        )
                    )

                    # မူလအကြွေးကို ပြင်မယ်
                    if new_amt == Decimal("0"):

                        cur.execute(
                            """
                            DELETE FROM debts
                            WHERE id = %s
                            AND chat_id = %s
                            """,
                            (
                                debt_id,
                                update.effective_chat.id
                            )
                        )

                        msg = (
                            f"✅ ရှင်းငွေ သိမ်းဆည်းပြီးပါပြီ။\n\n"
                            f"👤 အမည်: {data['pay_name']}\n"
                            f"💰 ရှင်းငွေ: {pay_amt} ကျပ်\n"
                            f"📦 ပစ္စည်း: {data['pay_item_name']}\n\n"
                            f"🎉 အကြွေးအကုန်ရှင်းပြီးပါပြီ။"
                        )

                    else:

                        cur.execute(
                            """
                            UPDATE debts
                            SET amount = %s,
                                quantity = %s
                            WHERE id = %s
                            AND chat_id = %s
                            """,
                            (
                                new_amt,
                                new_qty,
                                debt_id,
                                update.effective_chat.id
                            )
                        )

                        msg = (
                            f"✅ ရှင်းငွေ သိမ်းဆည်းပြီးပါပြီ။\n\n"
                            f"👤 အမည်: {data['pay_name']}\n"
                            f"💰 ရှင်းငွေ: {pay_amt} ကျပ်\n"
                            f"📦 ပစ္စည်း: {data['pay_item_name']}\n"
                            f"🔢 ကျန်အရေအတွက်: {new_qty}\n"
                            f"💵 ကျန်ငွေ: {new_amt} ကျပ်"
                        )

    except Exception as e:

        msg = f"❌ Error ဖြစ်သွားပါတယ် - {str(e)}"

    await update.message.reply_text(
        msg,
        reply_markup=get_main_menu()
    )

    context.user_data.clear()

    return ConversationHandler.END


# ==========================================
# SEARCH CUSTOMER
# ==========================================

async def search_customer(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    context.user_data.clear()

    await query.edit_message_text(
        "🔍 ရှာချင်တဲ့ ဝယ်သူအမည်ကို ရိုက်ထည့်ပါ -"
    )

    return ASK_SEARCH


# ==========================================
# SHOW CUSTOMER DATA
# ==========================================

async def show_customer_data(update: Update, context: ContextTypes.DEFAULT_TYPE):

    name = update.message.text.strip()

    try:

        with closing(get_conn()) as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT type, amount, item_name, quantity, date
                    FROM debts
                    WHERE chat_id = %s
                    AND customer_name ILIKE %s
                    ORDER BY created_at ASC
                    """,
                    (
                        update.effective_chat.id,
                        f"%{name}%"
                    )
                )

                rows = cur.fetchall()

        if not rows:

            await update.message.reply_text(
                f"'{name}' နဲ့ ပတ်သက်တဲ့ မှတ်တမ်း မတွေ့ပါဘူး။",
                reply_markup=get_main_menu()
            )

            return ConversationHandler.END

        text = (
            f"👤 {name} ရဲ့ အသေးစိတ်စာရင်း\n"
            "━━━━━━━━━━━━━━━━\n"
        )

        for i, r in enumerate(rows, 1):

            if r[0] == "credit":

                text += (
                    f"🧾 Voucher {i} (အကြွေး)\n"
                    f"├ ပစ္စည်း: {r[2] or 'မရှိ'}\n"
                    f"├ အရေအတွက်: {r[3] or 'မရှိ'}\n"
                    f"├ ပမာဏ: {r[1]} ကျပ်\n"
                    f"└ ရက်စွဲ: {r[4]}\n\n"
                )

            else:

                text += (
                    f"🧾 Voucher {i} (ရှင်းငွေ)\n"
                    f"├ ပစ္စည်း: {r[2] or 'မရှိ'}\n"
                    f"├ ပမာဏ: {r[1]} ကျပ်\n"
                    f"└ ရက်စွဲ: {r[4]}\n\n"
                )

        await update.message.reply_text(
            text,
            reply_markup=get_main_menu()
        )

    except Exception as e:

        await update.message.reply_text(
            f"❌ Error: {str(e)}",
            reply_markup=get_main_menu()
        )

    return ConversationHandler.END


# ==========================================
# TOTAL SUMMARY
# ==========================================

async def total_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    try:

        with closing(get_conn()) as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        customer_name,
                        SUM(amount) AS total_balance
                    FROM debts
                    WHERE chat_id = %s
                    AND type = 'credit'
                    AND amount > 0
                    GROUP BY customer_name
                    ORDER BY customer_name
                    """,
                    (query.message.chat.id,)
                )

                rows = cur.fetchall()

        if not rows:

            await query.edit_message_text(
                "📊 လက်ကျန်အကြွေး မရှိပါဘူး။",
                reply_markup=get_main_menu()
            )

            return

        text = (
            "📊 စုစုပေါင်း လက်ကျန်အကြွေး\n"
            "━━━━━━━━━━━━━━━━\n"
        )

        grand_total = Decimal("0")

        for r in rows:

            name = r[0]

            balance = Decimal(str(r[1] or "0"))

            grand_total += balance

            text += f"👤 {name}: {balance} ကျပ်\n"

        text += (
            "━━━━━━━━━━━━━━━━\n"
            f"💰 စုစုပေါင်း ရရန်ကျန်: {grand_total} ကျပ်"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_main_menu()
        )

    except Exception as e:

        await query.edit_message_text(
            f"❌ Error: {str(e)}",
            reply_markup=get_main_menu()
        )


# ==========================================
# CANCEL
# ==========================================

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data.clear()

    await update.message.reply_text(
        "❌ လုပ်ဆောင်မှု ပယ်ဖျက်လိုက်ပါပြီ။",
        reply_markup=get_main_menu()
    )

    return ConversationHandler.END


# ==========================================
# APPLICATION
# ==========================================

def main():

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(

        entry_points=[
            CallbackQueryHandler(
                start_entry,
                pattern="^(new_debt|new_payment)$"
            ),

            CallbackQueryHandler(
                search_customer,
                pattern="^search_customer$"
            )
        ],

        states={

            ASK_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    ask_name
                )
            ],

            ASK_AMOUNT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    ask_amount
                )
            ],

            ASK_ITEM: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    ask_item
                )
            ],

            ASK_QTY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    ask_qty
                )
            ],

            ASK_DATE: [
                CallbackQueryHandler(
                    ask_date,
                    pattern="^use_today$"
                ),

                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    ask_date
                )
            ],

            ASK_PAY_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    ask_pay_name
                )
            ],

            ASK_PAY_ITEM: [
                CallbackQueryHandler(
                    ask_pay_item,
                    pattern="^pay_"
                )
            ],

            ASK_PAY_QTY: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    ask_pay_qty
                )
            ],

            ASK_PAY_AMT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    ask_pay_amt
                )
            ],

            ASK_SEARCH: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    show_customer_data
                )
            ]
        },

        fallbacks=[
            CommandHandler("cancel", cancel)
        ],

        allow_reentry=True
    )

    app.add_handler(CommandHandler("start", start))

    app.add_handler(conv_handler)

    app.add_handler(
        CallbackQueryHandler(
            total_summary,
            pattern="^total_summary$"
        )
    )

    print("3D Debt Ledger Bot Started...")

    app.run_polling()


# ==========================================
# RUN
# ==========================================

if __name__ == "__main__":
    main()
