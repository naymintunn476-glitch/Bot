
import os
import logging
from decimal import Decimal, InvalidOperation
from datetime import datetime
from contextlib import closing

import psycopg2

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
    raise ValueError("DATABASE_URL မတွေ့ပါ။")

if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN မတွေ့ပါ။")


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


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
    ASK_SEARCH,
    ASK_DELETE_CUSTOMER,
    CONFIRM_DELETE
) = range(12)


# ==========================================
# DATABASE
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


def format_money(value):
    return f"{Decimal(str(value)):,.2f}".rstrip("0").rstrip(".")


# ==========================================
# MAIN MENU
# ==========================================

def get_main_menu():

    keyboard = [

        [
            InlineKeyboardButton(
                "📝 အကြွေးထည့်မည်",
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
                "📊 စုစုပေါင်းစာရင်း",
                callback_data="total_summary"
            )
        ],

        [
            InlineKeyboardButton(
                "🗑️ အကြွေးရှင်အမည် ဖျက်မည်",
                callback_data="delete_customer"
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
        "🏪 Debt Ledger Bot မှ ကြိုဆိုပါတယ်။\n\n"
        "လုပ်ဆောင်လိုတာကို ရွေးချယ်ပါ။"
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
# START DEBT / PAYMENT
# ==========================================

async def start_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    context.user_data.clear()

    if query.data == "new_debt":

        await query.edit_message_text(
            "👤 အကြွေးရှင်အမည်ကို ရိုက်ထည့်ပါ။"
        )

        return ASK_NAME

    await query.edit_message_text(
        "👤 ရှင်းငွေဆပ်မယ့်သူရဲ့ အမည်ကို ရိုက်ထည့်ပါ။"
    )

    return ASK_PAY_NAME


# ==========================================
# NEW DEBT - NAME
# ==========================================

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):

    name = update.message.text.strip()

    if not name:
        await update.message.reply_text("အမည်ပြန်ထည့်ပါ။")
        return ASK_NAME

    context.user_data["name"] = name

    await update.message.reply_text(
        "💰 အကြွေးပမာဏ (ကျပ်) ကို ရိုက်ထည့်ပါ။"
    )

    return ASK_AMOUNT


# ==========================================
# NEW DEBT - AMOUNT
# ==========================================

async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:

        amount = parse_amount(update.message.text)

        if amount <= 0:
            raise InvalidOperation

        context.user_data["amount"] = amount

    except (ValueError, InvalidOperation):

        await update.message.reply_text(
            "❌ မှန်ကန်တဲ့ ငွေပမာဏကို ရိုက်ထည့်ပါ။"
        )

        return ASK_AMOUNT

    await update.message.reply_text(
        "📦 ပစ္စည်းအမည်ကို ရိုက်ထည့်ပါ။"
    )

    return ASK_ITEM


# ==========================================
# NEW DEBT - ITEM
# ==========================================

async def ask_item(update: Update, context: ContextTypes.DEFAULT_TYPE):

    item = update.message.text.strip()

    if not item:
        await update.message.reply_text("ပစ္စည်းအမည် ထည့်ပါ။")
        return ASK_ITEM

    context.user_data["item"] = item

    await update.message.reply_text(
        "🔢 အရေအတွက်ကို ရိုက်ထည့်ပါ။"
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
            "❌ မှန်ကန်တဲ့ အရေအတွက်ကို ရိုက်ထည့်ပါ။"
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
        "📅 ရက်စွဲကို ကိုယ်တိုင်ရိုက်ထည့်နိုင်ပါတယ်။\n"
        "သို့မဟုတ် အောက်ကခလုတ်ကို နှိပ်ပါ။",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return ASK_DATE


# ==========================================
# NEW DEBT - SAVE
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
            "✅ အကြွေးစာရင်း သိမ်းဆည်းပြီးပါပြီ။\n\n"
            f"👤 အမည်: {data['name']}\n"
            f"📦 ပစ္စည်း: {data['item']}\n"
            f"🔢 အရေအတွက်: {data['qty']}\n"
            f"💰 ပမာဏ: {format_money(data['amount'])} ကျပ်\n"
            f"📅 ရက်စွဲ: {date}"
        )

    except Exception as e:

        logger.exception("Save debt error")

        msg = f"❌ Database Error: {e}"

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

        if not rows:

            await update.message.reply_text(
                f"'{name}' အတွက် ကျန်ရှိတဲ့ အကြွေး မတွေ့ပါဘူး။",
                reply_markup=get_main_menu()
            )

            context.user_data.clear()

            return ConversationHandler.END

        keyboard = []

        for r in rows:

            # Voucher ID တစ်ခုချင်းစီကို သီးခြားပြမယ်
            btn_text = (
                f"#{r[0]} | {r[1] or 'အကြွေး'} | "
                f"{r[2] if r[2] is not None else 0} ခု | "
                f"{format_money(r[3])} ကျပ်"
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
            f"📋 {name} ရဲ့ အကြွေး Voucher ကို ရွေးပါ။\n\n"
            "ပစ္စည်းအမည်နဲ့ အရေအတွက်တူနေရင်တောင် "
            "ပမာဏနဲ့ Voucher ID ကိုကြည့်ပြီး ရွေးနိုင်ပါတယ်။",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return ASK_PAY_ITEM

    except Exception as e:

        logger.exception("Find payment debt error")

        await update.message.reply_text(
            f"❌ Database Error: {e}",
            reply_markup=get_main_menu()
        )

        context.user_data.clear()

        return ConversationHandler.END


# ==========================================
# PAYMENT - SELECT VOUCHER
# ==========================================

async def ask_pay_item(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    try:

        debt_id = int(query.data.split("_", 1)[1])

        with closing(get_conn()) as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT id, item_name, quantity, amount
                    FROM debts
                    WHERE id = %s
                    AND chat_id = %s
                    AND type = 'credit'
                    AND amount > 0
                    """,
                    (
                        debt_id,
                        update.effective_chat.id
                    )
                )

                row = cur.fetchone()

        if not row:

            await query.edit_message_text(
                "❌ Voucher မတွေ့ပါ။ သို့မဟုတ် အကြွေးရှင်းပြီးပါပြီ။",
                reply_markup=get_main_menu()
            )

            return ConversationHandler.END

        context.user_data["pay_id"] = row[0]
        context.user_data["pay_item_name"] = row[1]
        context.user_data["pay_old_qty"] = int(row[2] or 0)
        context.user_data["pay_old_amt"] = Decimal(str(row[3]))

        text = (
            f"🧾 Voucher #{row[0]}\n\n"
            f"📦 ပစ္စည်း: {row[1] or 'အကြွေး'}\n"
            f"🔢 လက်ကျန်အရေအတွက်: {row[2] or 0}\n"
            f"💰 လက်ကျန်ပမာဏ: {format_money(row[3])} ကျပ်\n\n"
            "ရှင်းမယ့် အရေအတွက်ကို ရိုက်ထည့်ပါ။\n"
            "(မရှိရင် 0 ရိုက်ပါ)"
        )

        await query.edit_message_text(text)

        return ASK_PAY_QTY

    except Exception as e:

        logger.exception("Select payment voucher error")

        await query.edit_message_text(
            f"❌ Error: {e}",
            reply_markup=get_main_menu()
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
            "❌ မှန်ကန်တဲ့ အရေအတွက်ကို ထည့်ပါ။\n"
            "လက်ကျန်အရေအတွက်ထက် မကျော်ရပါ။"
        )

        return ASK_PAY_QTY

    await update.message.reply_text(
        "💰 ရှင်းမယ့် ငွေပမာဏ (ကျပ်) ကို ရိုက်ထည့်ပါ။"
    )

    return ASK_PAY_AMT


# ==========================================
# PAYMENT - SAVE
# ==========================================

async def ask_pay_amt(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:

        pay_amt = parse_amount(update.message.text)

        if pay_amt <= 0:
            raise InvalidOperation

    except (ValueError, InvalidOperation):

        await update.message.reply_text(
            "❌ မှန်ကန်တဲ့ ငွေပမာဏကို ရိုက်ထည့်ပါ။"
        )

        return ASK_PAY_AMT

    data = context.user_data

    debt_id = data["pay_id"]

    pay_qty = int(data["pay_qty"])

    today_date = datetime.now().strftime("%d.%m.%Y")

    try:

        with closing(get_conn()) as conn:

            with conn:

                with conn.cursor() as cur:

                    # နောက်ဆုံးလက်ကျန်ကို Lock ချပြီး စစ်မယ်
                    cur.execute(
                        """
                        SELECT item_name, quantity, amount
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

                    row = cur.fetchone()

                    if not row:
                        raise ValueError("Voucher မတွေ့ပါ။")

                    old_qty = int(row[1] or 0)

                    old_amt = Decimal(str(row[2]))

                    if old_amt <= 0:
                        raise ValueError("အကြွေးရှင်းပြီးသားဖြစ်ပါတယ်။")

                    if pay_amt > old_amt:
                        raise ValueError(
                            f"ရှင်းငွေက လက်ကျန်ထက် များနေပါတယ်။ "
                            f"လက်ကျန် {format_money(old_amt)} ကျပ်"
                        )

                    if pay_qty > old_qty:
                        raise ValueError("အရေအတွက် လက်ကျန်ထက် များနေပါတယ်။")

                    new_amt = old_amt - pay_amt

                    new_qty = old_qty - pay_qty

                    # Payment History ကို သိမ်းမယ်
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
                            row[0],
                            today_date
                        )
                    )

                    # အကြွေးအပြည့်ရှင်းပြီးပါက 0 အဖြစ်ထားမယ်
                    if new_amt == Decimal("0"):

                        cur.execute(
                            """
                            UPDATE debts
                            SET amount = 0,
                                quantity = 0
                            WHERE id = %s
                            AND chat_id = %s
                            """,
                            (
                                debt_id,
                                update.effective_chat.id
                            )
                        )

                        msg = (
                            "✅ အကြွေးအပြည့်ရှင်းပြီးပါပြီ။\n\n"
                            f"👤 အမည်: {data['pay_name']}\n"
                            f"📦 ပစ္စည်း: {row[0]}\n"
                            f"🔢 အရေအတွက်: 0\n"
                            f"💰 လက်ကျန်: 0 ကျပ်\n\n"
                            "Voucher ကို 0 အဖြစ် သိမ်းထားပြီး "
                            "လက်ကျန်အကြွေးစာရင်းမှာ မပြတော့ပါဘူး။"
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
                            "✅ ရှင်းငွေ သိမ်းဆည်းပြီးပါပြီ။\n\n"
                            f"👤 အမည်: {data['pay_name']}\n"
                            f"📦 ပစ္စည်း: {row[0]}\n"
                            f"🔢 ကျန်အရေအတွက်: {new_qty}\n"
                            f"💰 ရှင်းငွေ: {format_money(pay_amt)} ကျပ်\n"
                            f"💵 ကျန်ငွေ: {format_money(new_amt)} ကျပ်"
                        )

        await update.message.reply_text(
            msg,
            reply_markup=get_main_menu()
        )

    except Exception as e:

        logger.exception("Payment error")

        await update.message.reply_text(
            f"❌ ရှင်းငွေ မအောင်မြင်ပါ။\n{str(e)}",
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
        "🔍 ရှာချင်တဲ့ ဝယ်သူအမည်ကို ရိုက်ထည့်ပါ။"
    )

    return ASK_SEARCH


# ==========================================
# CUSTOMER DETAILS
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
                "မှတ်တမ်း မတွေ့ပါဘူး။",
                reply_markup=get_main_menu()
            )

            return ConversationHandler.END

        text = f"👤 {name} ရဲ့ အသေးစိတ်စာရင်း\n"
        text += "━━━━━━━━━━━━━━━━\n"

        for i, r in enumerate(rows, 1):

            if r[0] == "credit":

                text += (
                    f"🧾 Voucher {i} (အကြွေး)\n"
                    f"├ ပစ္စည်း: {r[2] or 'မရှိ'}\n"
                    f"├ အရေအတွက်: {r[3] or 0}\n"
                    f"├ ပမာဏ: {format_money(r[1])} ကျပ်\n"
                    f"└ ရက်စွဲ: {r[4]}\n\n"
                )

            else:

                text += (
                    f"💰 Voucher {i} (ရှင်းငွေ)\n"
                    f"├ ပစ္စည်း: {r[2] or 'မရှိ'}\n"
                    f"├ ရှင်းငွေ: {format_money(r[1])} ကျပ်\n"
                    f"└ ရက်စွဲ: {r[4]}\n\n"
                )

        # Telegram message length ကန့်သတ်ချက်အတွက် ခွဲပို့မယ်
        chunks = []

        while len(text) > 3500:

            cut = text.rfind("\n", 0, 3500)

            if cut <= 0:
                cut = 3500

            chunks.append(text[:cut])

            text = text[cut:]

        chunks.append(text)

        for chunk in chunks:

            await update.message.reply_text(chunk)

        await update.message.reply_text(
            "လုပ်ဆောင်ချက် ရွေးချယ်ပါ။",
            reply_markup=get_main_menu()
        )

    except Exception as e:

        logger.exception("Customer search error")

        await update.message.reply_text(
            f"❌ Error: {e}",
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
                    GROUP BY customer_name
                    HAVING SUM(amount) > 0
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

        text = "📊 စုစုပေါင်း လက်ကျန်အကြွေး\n"
        text += "━━━━━━━━━━━━━━━━\n"

        grand_total = Decimal("0")

        for r in rows:

            balance = Decimal(str(r[1] or "0"))

            grand_total += balance

            text += (
                f"👤 {r[0]}: {format_money(balance)} ကျပ်\n"
            )

        text += (
            "━━━━━━━━━━━━━━━━\n"
            f"💰 စုစုပေါင်း ရရန်ကျန်ငွေ: "
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


# ==========================================
# DELETE CUSTOMER - LIST ZERO BALANCE
# ==========================================

async def delete_customer_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    context.user_data.clear()

    try:

        with closing(get_conn()) as conn:

            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        customer_name,
                        SUM(amount) AS balance
                    FROM debts
                    WHERE chat_id = %s
                    AND type = 'credit'
                    GROUP BY customer_name
                    HAVING
                        SUM(amount) = 0
                        AND BOOL_AND(amount = 0)
                    ORDER BY customer_name
                    """,
                    (query.message.chat.id,)
                )

                rows = cur.fetchall()

        if not rows:

            await query.edit_message_text(
                "🗑️ ဖျက်နိုင်တဲ့ အကြွေးရှင် မရှိသေးပါဘူး။\n\n"
                "လက်ကျန် 0 ကျပ် ဖြစ်နေတဲ့သူတွေမှသာ "
                "ဒီစာရင်းထဲမှာ ပေါ်လာမှာဖြစ်ပါတယ်။",
                reply_markup=get_main_menu()
            )

            return ConversationHandler.END

        names = [r[0] for r in rows]

        context.user_data["delete_names"] = names

        keyboard = []

        for i, row in enumerate(rows):

            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"👤 {row[0]} : 0 ကျပ်",
                        callback_data=f"delcust_{i}"
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "🔙 ပင်မစာမျက်နှာ",
                    callback_data="delete_back"
                )
            ]
        )

        await query.edit_message_text(
            "🗑️ အကြွေးရှင်အမည် ဖျက်မည်\n\n"
            "အောက်ပါသူများသည် လက်ကျန်အကြွေး 0 ကျပ် "
            "ဖြစ်နေသူများသာ ဖြစ်ပါတယ်။\n\n"
            "ဖျက်ချင်တဲ့ အမည်ကို ရွေးပါ။",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return ASK_DELETE_CUSTOMER

    except Exception as e:

        logger.exception("Delete customer list error")

        await query.edit_message_text(
            f"❌ Error: {e}",
            reply_markup=get_main_menu()
        )

        return ConversationHandler.END


# ==========================================
# DELETE CUSTOMER - CONFIRM
# ==========================================

async def select_delete_customer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    if query.data == "delete_back":

        context.user_data.clear()

        await query.edit_message_text(
            "🏪 ပင်မစာမျက်နှာ",
            reply_markup=get_main_menu()
        )

        return ConversationHandler.END

    try:

        index = int(query.data.split("_", 1)[1])

        names = context.user_data.get("delete_names", [])

        if index < 0 or index >= len(names):
            raise ValueError("ရွေးချယ်မှု မမှန်ကန်ပါ။")

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
            "⚠️ ဖျက်ရန် အတည်ပြုပါ။\n\n"
            f"👤 အမည်: {name}\n"
            "💰 လက်ကျန်: 0 ကျပ်\n\n"
            "ဒီသူရဲ့ အကြွေး Voucher နဲ့ ရှင်းငွေ "
            "မှတ်တမ်းအားလုံးကို အပြီးဖျက်မှာ ဖြစ်ပါတယ်။\n\n"
            "ပြန်လည်ရယူလို့ မရနိုင်ပါ။",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return CONFIRM_DELETE

    except Exception as e:

        logger.exception("Select delete customer error")

        await query.edit_message_text(
            f"❌ Error: {e}",
            reply_markup=get_main_menu()
        )

        context.user_data.clear()

        return ConversationHandler.END


# ==========================================
# DELETE CUSTOMER - FINAL ACTION
# ==========================================

async def confirm_delete_customer(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

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
            "❌ အမည် မတွေ့ပါ။ ပြန်စမ်းပါ။",
            reply_markup=get_main_menu()
        )

        context.user_data.clear()

        return ConversationHandler.END

    chat_id = update.effective_chat.id

    try:

        with closing(get_conn()) as conn:

            with conn:

                with conn.cursor() as cur:

                    # နောက်ဆုံးအခြေအနေကို Lock ချပြီး ထပ်စစ်မယ်
                    cur.execute(
                        """
                        SELECT amount
                        FROM debts
                        WHERE chat_id = %s
                        AND customer_name = %s
                        AND type = 'credit'
                        FOR UPDATE
                        """,
                        (chat_id, name)
                    )

                    rows = cur.fetchall()

                    if not rows:

                        raise ValueError(
                            "အကြွေးစာရင်း မတွေ့ပါ။"
                        )

                    # Credit Voucher အားလုံး 0 ဖြစ်မှသာ ဖျက်မယ်
                    if not all(
                        Decimal(str(r[0])) == Decimal("0")
                        for r in rows
                    ):

                        raise ValueError(
                            "ဒီအကြွေးရှင်မှာ လက်ကျန်ငွေ ရှိနေသေးပါတယ်။"
                        )

                    # Credit + Payment အားလုံးကို ဖျက်မယ်
                    cur.execute(
                        """
                        DELETE FROM debts
                        WHERE chat_id = %s
                        AND customer_name = %s
                        """,
                        (chat_id, name)
                    )

                    deleted_count = cur.rowcount

        await query.edit_message_text(
            "✅ အကြွေးရှင်စာရင်း ဖျက်ပြီးပါပြီ။\n\n"
            f"👤 အမည်: {name}\n"
            f"🗑️ ဖျက်လိုက်သော မှတ်တမ်း: {deleted_count} ခု",
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
# ERROR HANDLER
# ==========================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.error(
        "Telegram update error:",
        exc_info=context.error
    )


# ==========================================
# MAIN APPLICATION
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

    logger.info("Debt Ledger Bot Started Successfully")

    app.run_polling()


# ==========================================
# RUN
# ==========================================

if __name__ == "__main__":
    main()
