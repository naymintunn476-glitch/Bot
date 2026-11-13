
import os
import logging
from decimal import Decimal, InvalidOperation
from datetime import datetime
from contextlib import closing

import psycopg2

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters
)


# ==================================================
# CONFIGURATION
# ==================================================

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
DB_URL = os.environ.get("DATABASE_URL")

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN မတွေ့ပါ။")

if not DB_URL:
    raise ValueError("DATABASE_URL မတွေ့ပါ။")


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger("DebtNote")


# ==================================================
# CONVERSATION STATES
# ==================================================

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
    ASK_SEARCH,
    ASK_DELETE_CUSTOMER,
    CONFIRM_DELETE
) = range(12)


# ==================================================
# DATABASE CONNECTION
# ==================================================

def get_conn():
    return psycopg2.connect(DB_URL)


def init_db():
    with closing(get_conn()) as conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS debts (
                        id BIGSERIAL PRIMARY KEY,
                        chat_id BIGINT NOT NULL,
                        customer_name TEXT NOT NULL,
                        amount NUMERIC(18,2) NOT NULL DEFAULT 0,
                        item_name TEXT,
                        quantity INTEGER,
                        date TEXT,
                        type TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_debts_chat_customer
                    ON debts(chat_id, customer_name)
                """)

                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_debts_type
                    ON debts(chat_id, type)
                """)


# ==================================================
# DECIMAL FUNCTIONS
# ==================================================

def parse_amount(value):
    value = str(value).strip().replace(",", "")
    amount = Decimal(value)

    if not amount.is_finite():
        raise InvalidOperation

    return amount


def format_money(value):
    amount = Decimal(str(value or 0))
    return f"{amount:,.2f}".rstrip("0").rstrip(".")


def same_name_sql():
    return "LOWER(BTRIM(customer_name)) = LOWER(BTRIM(%s))"


# ==================================================
# MAIN MENU
# ==================================================

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
                "🔍 အမည်ဖြင့်ရှာမည်",
                callback_data="search_customer"
            )
        ],
        [
            InlineKeyboardButton(
                "📊 စုစုပေါင်းအကြွေး",
                callback_data="total_summary"
            )
        ],
        [
            InlineKeyboardButton(
                "🗑️ အကြွေးရှင်အမည်ဖျက်မည်",
                callback_data="delete_customer"
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# ==================================================
# START
# ==================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    context.user_data.clear()

    text = (
        "📒 DebtNote မှ ကြိုဆိုပါတယ်။\n\n"
        "လုပ်ဆောင်လိုသော Menu ကို ရွေးချယ်ပါ။"
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


# ==================================================
# START DEBT / PAYMENT
# ==================================================

async def start_entry(update, context):

    query = update.callback_query
    await query.answer()

    context.user_data.clear()

    if query.data == "new_debt":

        await query.edit_message_text(
            "👤 အကြွေးရှင်အမည်ကို ရိုက်ထည့်ပါ။"
        )

        return ASK_NAME

    await query.edit_message_text(
        "👤 ရှင်းငွေဆပ်မည့်သူ၏ အမည်အပြည့်အစုံကို ရိုက်ထည့်ပါ။"
    )

    return ASK_PAY_NAME


# ==================================================
# ADD DEBT - NAME
# ==================================================

async def ask_name(update, context):

    name = update.message.text.strip()

    if not name:
        await update.message.reply_text("အမည်ထည့်ပါ။")
        return ASK_NAME

    context.user_data["name"] = name

    await update.message.reply_text(
        "💰 အကြွေးပမာဏ (ကျပ်) ကို ရိုက်ထည့်ပါ။"
    )

    return ASK_AMOUNT


# ==================================================
# ADD DEBT - AMOUNT
# ==================================================

async def ask_amount(update, context):

    try:
        amount = parse_amount(update.message.text)

        if amount <= 0:
            raise InvalidOperation

        context.user_data["amount"] = amount

    except (ValueError, InvalidOperation):

        await update.message.reply_text(
            "❌ မှန်ကန်သော ပမာဏကို ပြန်ရိုက်ထည့်ပါ။"
        )

        return ASK_AMOUNT

    await update.message.reply_text(
        "📦 ပစ္စည်းအမည်ကို ရိုက်ထည့်ပါ။"
    )

    return ASK_ITEM


# ==================================================
# ADD DEBT - ITEM
# ==================================================

async def ask_item(update, context):

    item = update.message.text.strip()

    if not item:
        await update.message.reply_text(
            "ပစ္စည်းအမည် ထည့်ပါ။"
        )
        return ASK_ITEM

    context.user_data["item"] = item

    await update.message.reply_text(
        "🔢 အရေအတွက်ကို ရိုက်ထည့်ပါ။"
    )

    return ASK_QTY


# ==================================================
# ADD DEBT - QUANTITY
# ==================================================

async def ask_qty(update, context):

    try:
        qty = int(update.message.text.strip())

        if qty <= 0:
            raise ValueError

        context.user_data["qty"] = qty

    except ValueError:

        await update.message.reply_text(
            "❌ မှန်ကန်သော အရေအတွက်ကို ထည့်ပါ။"
        )

        return ASK_QTY

    keyboard = [
        [
            InlineKeyboardButton(
                "📅 ယနေ့ရက်စွဲ",
                callback_data="use_today"
            )
        ]
    ]

    await update.message.reply_text(
        "📅 ရက်စွဲကို ကိုယ်တိုင်ရိုက်ထည့်နိုင်ပါတယ်။\n"
        "သို့မဟုတ် ယနေ့ရက်စွဲခလုတ်ကို နှိပ်ပါ။",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return ASK_DATE


# ==================================================
# ADD DEBT - SAVE
# ==================================================

async def ask_date(update, context):

    if update.callback_query:

        await update.callback_query.answer()

        date = datetime.now().strftime("%d.%m.%Y")

        await update.callback_query.edit_message_text(
            f"📅 ရက်စွဲ: {date}"
        )

    else:

        date = update.message.text.strip()

        if not date:
            await update.message.reply_text(
                "ရက်စွဲ ထည့်ပါ။"
            )
            return ASK_DATE

    data = context.user_data

    try:

        with closing(get_conn()) as conn:
            with conn:
                with conn.cursor() as cur:

                    cur.execute("""
                        INSERT INTO debts (
                            chat_id,
                            customer_name,
                            amount,
                            item_name,
                            quantity,
                            date,
                            type
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, 'credit')
                    """, (
                        update.effective_chat.id,
                        data["name"],
                        data["amount"],
                        data["item"],
                        data["qty"],
                        date
                    ))

        msg = (
            "✅ အကြွေးစာရင်း သိမ်းဆည်းပြီးပါပြီ။\n\n"
            f"👤 အမည်: {data['name']}\n"
            f"📦 ပစ္စည်း: {data['item']}\n"
            f"🔢 အရေအတွက်: {data['qty']}\n"
            f"💰 ပမာဏ: {format_money(data['amount'])} ကျပ်\n"
            f"📅 ရက်စွဲ: {date}"
        )

    except Exception as e:

        logger.exception("Add debt error")
        msg = f"❌ Database Error: {e}"

    await update.effective_chat.send_message(
        msg,
        reply_markup=get_main_menu()
    )

    context.user_data.clear()

    return ConversationHandler.END


# ==================================================
# PAYMENT - CUSTOMER NAME
# ==================================================

async def ask_pay_name(update, context):

    name = update.message.text.strip()

    if not name:
        await update.message.reply_text("အမည်ထည့်ပါ။")
        return ASK_PAY_NAME

    context.user_data["pay_name"] = name

    try:

        with closing(get_conn()) as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        id,
                        item_name,
                        quantity,
                        amount
                    FROM debts
                    WHERE chat_id = %s
                    AND LOWER(BTRIM(customer_name))
                        = LOWER(BTRIM(%s))
                    AND type = 'credit'
                    AND amount > 0
                    ORDER BY id ASC
                """, (
                    update.effective_chat.id,
                    name
                ))

                rows = cur.fetchall()

        if not rows:

            await update.message.reply_text(
                f"'{name}' အတွက် လက်ကျန်အကြွေး မရှိပါဘူး။",
                reply_markup=get_main_menu()
            )

            context.user_data.clear()
            return ConversationHandler.END

        keyboard = []

        for r in rows:

            keyboard.append([
                InlineKeyboardButton(
                    f"Voucher #{r[0]} | "
                    f"{r[1] or 'အကြွေး'} | "
                    f"{r[2] or 0} ခု | "
                    f"{format_money(r[3])} ကျပ်",
                    callback_data=f"pay_{r[0]}"
                )
            ])

        await update.message.reply_text(
            f"👤 {name} ရဲ့ အကြွေး Voucher များ\n\n"
            "ရှင်းချင်သော Voucher ကို ရွေးပါ။\n"
            "ပစ္စည်းနှင့် အရေအတွက်တူလျှင်လည်း "
            "Voucher ID နှင့် ပမာဏကို ကြည့်ပြီး ရွေးနိုင်ပါတယ်။",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return ASK_PAY_ITEM

    except Exception as e:

        logger.exception("Payment search error")

        await update.message.reply_text(
            f"❌ Database Error: {e}",
            reply_markup=get_main_menu()
        )

        context.user_data.clear()
        return ConversationHandler.END


# ==================================================
# PAYMENT - SELECT ORIGINAL VOUCHER
# ==================================================

async def ask_pay_item(update, context):

    query = update.callback_query
    await query.answer()

    try:

        debt_id = int(query.data.split("_", 1)[1])

        with closing(get_conn()) as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT id, item_name, quantity, amount
                    FROM debts
                    WHERE id = %s
                    AND chat_id = %s
                    AND LOWER(BTRIM(customer_name))
                        = LOWER(BTRIM(%s))
                    AND type = 'credit'
                    AND amount > 0
                """, (
                    debt_id,
                    update.effective_chat.id,
                    context.user_data["pay_name"]
                ))

                row = cur.fetchone()

        if not row:

            await query.edit_message_text(
                "❌ Voucher မတွေ့ပါ။",
                reply_markup=get_main_menu()
            )

            context.user_data.clear()
            return ConversationHandler.END

        context.user_data["pay_id"] = row[0]
        context.user_data["pay_item_name"] = row[1]
        context.user_data["pay_old_qty"] = int(row[2] or 0)
        context.user_data["pay_old_amt"] = Decimal(str(row[3]))

        text = (
            f"🧾 Voucher #{row[0]}\n\n"
            f"📦 ပစ္စည်း: {row[1] or 'မရှိ'}\n"
            f"🔢 လက်ကျန်အရေအတွက်: {row[2] or 0}\n"
            f"💰 လက်ကျန်ငွေ: {format_money(row[3])} ကျပ်\n\n"
            "ရှင်းမည့် အရေအတွက်ကို ရိုက်ထည့်ပါ။\n"
            "(မရှိလျှင် 0 ရိုက်ပါ)"
        )

        await query.edit_message_text(text)

        return ASK_PAY_QTY

    except Exception as e:

        logger.exception("Select voucher error")

        await query.edit_message_text(
            f"❌ Error: {e}",
            reply_markup=get_main_menu()
        )

        context.user_data.clear()
        return ConversationHandler.END


# ==================================================
# PAYMENT - QUANTITY
# ==================================================

async def ask_pay_qty(update, context):

    try:

        qty = int(update.message.text.strip())

        old_qty = context.user_data["pay_old_qty"]

        if qty < 0 or qty > old_qty:
            raise ValueError

        context.user_data["pay_qty"] = qty

    except ValueError:

        await update.message.reply_text(
            "❌ အရေအတွက် မှားနေပါတယ်။\n"
            "လက်ကျန်အရေအတွက်ထက် မကျော်ရပါ။"
        )

        return ASK_PAY_QTY

    await update.message.reply_text(
        "💰 ရှင်းမည့် ငွေပမာဏ (ကျပ်) ကို ရိုက်ထည့်ပါ။"
    )

    return ASK_PAY_AMT


# ==================================================
# PAYMENT - AMOUNT AND UPDATE ORIGINAL VOUCHER
# ==================================================

async def ask_pay_amt(update, context):

    try:

        pay_amt = parse_amount(update.message.text)

        if pay_amt <= 0:
            raise InvalidOperation

    except (ValueError, InvalidOperation):

        await update.message.reply_text(
            "❌ မှန်ကန်သော ရှင်းငွေပမာဏကို ထည့်ပါ။"
        )

        return ASK_PAY_AMT

    data = context.user_data

    debt_id = data["pay_id"]
    pay_qty = int(data["pay_qty"])
    chat_id = update.effective_chat.id
    today = datetime.now().strftime("%d.%m.%Y")

    try:

        with closing(get_conn()) as conn:
            with conn:
                with conn.cursor() as cur:

                    # Original Voucher ကို Lock ချမယ်
                    cur.execute("""
                        SELECT
                            customer_name,
                            item_name,
                            quantity,
                            amount
                        FROM debts
                        WHERE id = %s
                        AND chat_id = %s
                        AND type = 'credit'
                        FOR UPDATE
                    """, (debt_id, chat_id))

                    row = cur.fetchone()

                    if not row:
                        raise ValueError("Voucher မတွေ့ပါ။")

                    customer_name = row[0]
                    item_name = row[1]
                    old_qty = int(row[2] or 0)
                    old_amt = Decimal(str(row[3]))

                    if old_amt <= 0:
                        raise ValueError("အကြွေးရှင်းပြီးသား ဖြစ်ပါတယ်။")

                    if pay_amt > old_amt:
                        raise ValueError(
                            f"ရှင်းငွေက လက်ကျန်ထက် များနေပါတယ်။\n"
                            f"လက်ကျန်: {format_money(old_amt)} ကျပ်"
                        )

                    if pay_qty > old_qty:
                        raise ValueError("အရေအတွက် မမှန်ပါ။")

                    new_amt = old_amt - pay_amt
                    new_qty = old_qty - pay_qty

                    # Payment History သီးခြားသိမ်းမယ်
                    # Search မှာ credit Voucher အဖြစ် မပြပါ။
                    cur.execute("""
                        INSERT INTO debts (
                            chat_id,
                            customer_name,
                            amount,
                            item_name,
                            quantity,
                            date,
                            type
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, 'payment')
                    """, (
                        chat_id,
                        customer_name,
                        pay_amt,
                        item_name,
                        pay_qty,
                        today
                    ))

                    # မူလ Voucher ကိုပဲ Update လုပ်မယ်
                    if new_amt == Decimal("0"):

                        new_qty = 0

                        cur.execute("""
                            UPDATE debts
                            SET amount = 0,
                                quantity = 0
                            WHERE id = %s
                            AND chat_id = %s
                        """, (debt_id, chat_id))

                    else:

                        cur.execute("""
                            UPDATE debts
                            SET amount = %s,
                                quantity = %s
                            WHERE id = %s
                            AND chat_id = %s
                        """, (
                            new_amt,
                            new_qty,
                            debt_id,
                            chat_id
                        ))

        if new_amt == Decimal("0"):

            msg = (
                "✅ အကြွေးအပြည့်ရှင်းပြီးပါပြီ။\n\n"
                f"👤 အမည်: {customer_name}\n"
                f"📦 ပစ္စည်း: {item_name}\n"
                f"🔢 အရေအတွက်: 0\n"
                f"💰 လက်ကျန်: 0 ကျပ်\n\n"
                f"🧾 Voucher #{debt_id} ကို "
                "Active အကြွေးစာရင်းမှ ဖယ်ရှားပြီးပါပြီ။"
            )

        else:

            msg = (
                "✅ ရှင်းငွေ သိမ်းဆည်းပြီးပါပြီ။\n\n"
                f"👤 အမည်: {customer_name}\n"
                f"🧾 Voucher #{debt_id}\n"
                f"📦 ပစ္စည်း: {item_name}\n"
                f"🔢 ကျန်အရေအတွက်: {new_qty}\n"
                f"💰 ရှင်းငွေ: {format_money(pay_amt)} ကျပ်\n"
                f"💵 ကျန်ငွေ: {format_money(new_amt)} ကျပ်"
            )

        await update.message.reply_text(
            msg,
            reply_markup=get_main_menu()
        )

    except Exception as e:

        logger.exception("Payment save error")

        await update.message.reply_text(
            f"❌ ရှင်းငွေ မအောင်မြင်ပါ။\n\n{str(e)}",
            reply_markup=get_main_menu()
        )

    context.user_data.clear()

    return ConversationHandler.END


# ==================================================
# SEARCH CUSTOMER
# ==================================================

async def search_customer(update, context):

    query = update.callback_query
    await query.answer()

    context.user_data.clear()

    await query.edit_message_text(
        "🔍 ရှာလိုသော အကြွေးရှင်၏ အမည်အပြည့်အစုံကို ရိုက်ထည့်ပါ။\n\n"
    )

    return ASK_SEARCH


# ==================================================
# SHOW CUSTOMER DATA - ACTIVE DEBT ONLY
# ==================================================

async def show_customer_data(update, context):

    name = update.message.text.strip()

    if not name:
        await update.message.reply_text(
            "အမည်အပြည့်အစုံ ထည့်ပါ။"
        )
        return ASK_SEARCH

    try:

        with closing(get_conn()) as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        id,
                        item_name,
                        quantity,
                        amount,
                        date
                    FROM debts
                    WHERE chat_id = %s
                    AND LOWER(BTRIM(customer_name))
                        = LOWER(BTRIM(%s))
                    AND type = 'credit'
                    AND amount > 0
                    ORDER BY id ASC
                """, (
                    update.effective_chat.id,
                    name
                ))

                rows = cur.fetchall()

        if not rows:

            await update.message.reply_text(
                f"'{name}' အတွက် လက်ကျန်အကြွေး မရှိပါဘူး။",
                reply_markup=get_main_menu()
            )

            return ConversationHandler.END

        text = f"👤 {name} ရဲ့ အကြွေးစာရင်း\n"
        text += "━━━━━━━━━━━━━━━━\n"

        total = Decimal("0")

        for r in rows:

            amount = Decimal(str(r[3]))
            total += amount

            text += (
                f"🧾 Voucher #{r[0]}\n"
                f"├ ပစ္စည်း: {r[1] or 'မရှိ'}\n"
                f"├ အရေအတွက်: {r[2] or 0}\n"
                f"├ လက်ကျန်: {format_money(amount)} ကျပ်\n"
                f"└ ရက်စွဲ: {r[4] or 'မရှိ'}\n\n"
            )

        text += "━━━━━━━━━━━━━━━━\n"
        text += (
            f"💰 စုစုပေါင်းအကြွေး: "
            f"{format_money(total)} ကျပ်"
        )

        # Telegram Message Limit အတွက် ခွဲပို့မယ်
        while len(text) > 3500:

            cut = text.rfind("\n", 0, 3500)

            if cut <= 0:
                cut = 3500

            await update.message.reply_text(text[:cut])

            text = text[cut:]

        await update.message.reply_text(
            text,
            reply_markup=get_main_menu()
        )

    except Exception as e:

        logger.exception("Search customer error")

        await update.message.reply_text(
            f"❌ Error: {e}",
            reply_markup=get_main_menu()
        )

    return ConversationHandler.END


# ==================================================
# TOTAL DEBT SUMMARY
# ==================================================

async def total_summary(update, context):

    query = update.callback_query
    await query.answer()

    try:

        with closing(get_conn()) as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        MIN(customer_name) AS customer_name,
                        SUM(amount) AS balance
                    FROM debts
                    WHERE chat_id = %s
                    AND type = 'credit'
                    GROUP BY LOWER(BTRIM(customer_name))
                    HAVING SUM(amount) > 0
                    ORDER BY MIN(customer_name)
                """, (query.message.chat.id,))

                rows = cur.fetchall()

        if not rows:

            await query.edit_message_text(
                "📊 လက်ကျန်အကြွေး မရှိပါဘူး။",
                reply_markup=get_main_menu()
            )

            return

        text = "📊 စုစုပေါင်း အကြွေးစာရင်း\n"
        text += "━━━━━━━━━━━━━━━━\n"

        grand_total = Decimal("0")

        for r in rows:

            balance = Decimal(str(r[1] or 0))
            grand_total += balance

            text += (
                f"👤 {r[0]}: "
                f"{format_money(balance)} ကျပ်\n"
            )

        text += "━━━━━━━━━━━━━━━━\n"
        text += (
            f"💰 စုစုပေါင်းရရန်ကျန်: "
            f"{format_money(grand_total)} ကျပ်"
        )

        await query.edit_message_text(
            text,
            reply_markup=get_main_menu()
        )

    except Exception as e:

        logger.exception("Summary error")

        await query.edit_message_text(
            f"❌ Error: {e}",
            reply_markup=get_main_menu()
        )


# ==================================================
# DELETE CUSTOMER - ZERO BALANCE LIST
# ==================================================

async def delete_customer_menu(update, context):

    query = update.callback_query
    await query.answer()

    context.user_data.clear()

    try:

        with closing(get_conn()) as conn:
            with conn.cursor() as cur:

                cur.execute("""
                    SELECT
                        MIN(customer_name) AS customer_name,
                        SUM(
                            CASE
                                WHEN type = 'credit'
                                THEN COALESCE(amount, 0)
                                ELSE 0
                            END
                        ) AS balance
                    FROM debts
                    WHERE chat_id = %s
                    GROUP BY LOWER(BTRIM(customer_name))
                    HAVING SUM(
                        CASE
                            WHEN type = 'credit'
                            THEN COALESCE(amount, 0)
                            ELSE 0
                        END
                    ) = 0
                    ORDER BY MIN(customer_name)
                """, (query.message.chat.id,))

                rows = cur.fetchall()

        if not rows:

            await query.edit_message_text(
                "🗑️ ဖျက်နိုင်သော အကြွေးရှင် မရှိသေးပါဘူး။\n\n"
                "စုစုပေါင်းအကြွေး 0 ကျပ် ဖြစ်သူများသာ "
                "ဒီစာရင်းမှာ ပေါ်လာမှာပါ။",
                reply_markup=get_main_menu()
            )

            return ConversationHandler.END

        names = [r[0] for r in rows]

        context.user_data["delete_names"] = names

        keyboard = []

        for i, r in enumerate(rows):

            keyboard.append([
                InlineKeyboardButton(
                    f"👤 {r[0]} : 0 ကျပ်",
                    callback_data=f"delcust_{i}"
                )
            ])

        keyboard.append([
            InlineKeyboardButton(
                "🔙 ပင်မစာမျက်နှာ",
                callback_data="delete_back"
            )
        ])

        await query.edit_message_text(
            "🗑️ အကြွေးရှင်အမည် ဖျက်မည်\n\n"
            "စုစုပေါင်းအကြွေး 0 ကျပ် ဖြစ်နေသူများသာ "
            "ဒီစာရင်းထဲမှာ ပါဝင်ပါတယ်။\n\n"
            "ဖျက်လိုသောအမည်ကို ရွေးပါ။",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return ASK_DELETE_CUSTOMER

    except Exception as e:

        logger.exception("Delete list error")

        await query.edit_message_text(
            f"❌ Error: {e}",
            reply_markup=get_main_menu()
        )

        return ConversationHandler.END


# ==================================================
# DELETE CUSTOMER - SELECT NAME
# ==================================================

async def select_delete_customer(update, context):

    query = update.callback_query
    await query.answer()

    if query.data == "delete_back":

        context.user_data.clear()

        await query.edit_message_text(
            "📒 DebtNote ပင်မစာမျက်နှာ",
            reply_markup=get_main_menu()
        )

        return ConversationHandler.END

    try:

        index = int(query.data.split("_", 1)[1])

        names = context.user_data.get("delete_names", [])

        if index < 0 or index >= len(names):
            raise ValueError("အမည်ရွေးချယ်မှု မမှန်ပါ။")

        name = names[index]

        context.user_data["delete_name"] = name

        keyboard = [
            [
                InlineKeyboardButton(
                    "✅ အတည်ပြုပြီး ဖျက်မည်",
                    callback_data="confirm_delete_yes"
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ မဖျက်တော့ပါ",
                    callback_data="confirm_delete_no"
                )
            ]
        ]

        await query.edit_message_text(
            "⚠️ အပြီးဖျက်ရန် အတည်ပြုပါ။\n\n"
            f"👤 အမည်: {name}\n"
            "💰 စုစုပေါင်းအကြွေး: 0 ကျပ်\n\n"
            "ဖျက်လိုက်ပါက သက်ဆိုင်ရာ အကြွေး Voucher "
            "နှင့် ရှင်းငွေ History အားလုံး ပျက်သွားပါမည်။\n\n"
            "ပြန်လည်ရယူ၍ မရနိုင်ပါ။",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return CONFIRM_DELETE

    except Exception as e:

        logger.exception("Select delete error")

        await query.edit_message_text(
            f"❌ Error: {e}",
            reply_markup=get_main_menu()
        )

        context.user_data.clear()

        return ConversationHandler.END


# ==================================================
# DELETE CUSTOMER - CONFIRM
# ==================================================

async def confirm_delete_customer(update, context):

    query = update.callback_query
    await query.answer()

    if query.data == "confirm_delete_no":

        context.user_data.clear()

        await query.edit_message_text(
            "❌ ဖျက်ခြင်းကို ပယ်ဖျက်လိုက်ပါပြီ။",
            reply_markup=get_main_menu()
        )

        return ConversationHandler.END

    name = context.user_data.get("delete_name")

    if not name:

        await query.edit_message_text(
            "❌ အမည်မတွေ့ပါ။",
            reply_markup=get_main_menu()
        )

        context.user_data.clear()
        return ConversationHandler.END

    chat_id = update.effective_chat.id

    try:

        with closing(get_conn()) as conn:
            with conn:
                with conn.cursor() as cur:

                    # အဲဒီအမည်ရဲ့ မှတ်တမ်းအားလုံး Lock ချမယ်
                    cur.execute("""
                        SELECT id, type, amount
                        FROM debts
                        WHERE chat_id = %s
                        AND LOWER(BTRIM(customer_name))
                            = LOWER(BTRIM(%s))
                        FOR UPDATE
                    """, (chat_id, name))

                    records = cur.fetchall()

                    if not records:
                        raise ValueError(
                            "အကြွေးရှင်စာရင်း မတွေ့ပါ။"
                        )

                    # Credit Voucher များကိုသာ စစ်မယ်
                    credit_rows = [
                        r for r in records
                        if r[1] == "credit"
                    ]

                    # အကြွေးလက်ကျန်ရှိလျှင် ဖျက်ခွင့်မပြု
                    has_balance = any(
                        Decimal(str(r[2] or 0)) != Decimal("0")
                        for r in credit_rows
                    )

                    if has_balance:
                        raise ValueError(
                            "ဒီအကြွေးရှင်မှာ လက်ကျန်ငွေ ရှိနေသေးပါတယ်။"
                        )

                    # Credit 0 ဖြစ်ပြီးသား သို့မဟုတ်
                    # ယခင် Version က Credit ဖျက်ပြီး
                    # Payment History ပဲကျန်သူကို ဖျက်နိုင်မယ်။
                    cur.execute("""
                        DELETE FROM debts
                        WHERE chat_id = %s
                        AND LOWER(BTRIM(customer_name))
                            = LOWER(BTRIM(%s))
                    """, (chat_id, name))

                    deleted_count = cur.rowcount

        await query.edit_message_text(
            "✅ အကြွေးရှင်ကို အပြီးဖျက်ပြီးပါပြီ။\n\n"
            f"👤 အမည်: {name}\n"
            f"🗑️ ဖျက်လိုက်သော မှတ်တမ်း: {deleted_count} ခု\n\n"
            "Voucher နှင့် Payment History အားလုံး ဖျက်ပြီးပါပြီ။",
            reply_markup=get_main_menu()
        )

    except Exception as e:

        logger.exception("Delete customer error")

        await query.edit_message_text(
            f"❌ ဖျက်၍မရပါ။\n\n{str(e)}",
            reply_markup=get_main_menu()
        )

    context.user_data.clear()

    return ConversationHandler.END


# ==================================================
# CANCEL
# ==================================================

async def cancel(update, context):

    context.user_data.clear()

    await update.message.reply_text(
        "❌ လုပ်ဆောင်မှု ပယ်ဖျက်လိုက်ပါပြီ။",
        reply_markup=get_main_menu()
    )

    return ConversationHandler.END


# ==================================================
# ERROR HANDLER
# ==================================================

async def error_handler(update, context):

    logger.error(
        "Unhandled Telegram error:",
        exc_info=context.error
    )


# ==================================================
# MAIN APPLICATION
# ==================================================

def main():

    init_db()

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
            ),

            CallbackQueryHandler(
                delete_customer_menu,
                pattern="^delete_customer$"
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
                    pattern="^pay_[0-9]+$"
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
            ],

            ASK_DELETE_CUSTOMER: [
                CallbackQueryHandler(
                    select_delete_customer,
                    pattern="^(delcust_[0-9]+|delete_back)$"
                )
            ],

            CONFIRM_DELETE: [
                CallbackQueryHandler(
                    confirm_delete_customer,
                    pattern="^confirm_delete_(yes|no)$"
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

    app.add_error_handler(error_handler)

    logger.info("DebtNote Bot Started Successfully")

    app.run_polling()


# ==================================================
# RUN
# ==================================================

if __name__ == "__main__":
    main()
