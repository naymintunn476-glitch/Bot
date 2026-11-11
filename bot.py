import os
import psycopg2
from telegram.ext import ApplicationBuilder, CommandHandler

DB_URL = os.environ["postgresql://neondb_owner:npg_Zb9za3WxFDYf@ep-polished-bar-bdrvi4lj-pooler.c-8.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"]
TOKEN = os.environ["9102213823:AAGW713M0qZhJEbk29g2mc0SiJN36RSSu2I"]

def get_conn():
    return psycopg2.connect(DB_URL)

async def add(update, context):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("အသုံးပြုပုံ- /add debtor_id amount [note]")
        return
    debtor_id = int(args[0])
    amount = float(args[1])
    note = " ".join(args[2:]) if len(args) > 2 else None
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO debts (chat_id, creditor_id, debtor_id, amount, description) VALUES (%s,%s,%s,%s,%s)",
        (update.effective_chat.id, update.effective_user.id, debtor_id, amount, note)
    )
    conn.commit()
    cur.close()
    conn.close()
    await update.message.reply_text(f"မှတ်တမ်းတင်ပြီး- {amount}")

async def list_debts(update, context):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT debtor_id, amount, description FROM debts WHERE chat_id=%s AND creditor_id=%s AND status='pending'",
        (update.effective_chat.id, update.effective_user.id)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    if not rows:
        await update.message.reply_text("အကြွေး မရှိပါ")
        return
    text = "\n".join([f"{r[0]}: {r[1]} ({r[2] or ''})" for r in rows])
    await update.message.reply_text(text)

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("add", add))
app.add_handler(CommandHandler("list", list_debts))
app.run_polling()