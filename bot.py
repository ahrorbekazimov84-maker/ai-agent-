import os
import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from google import genai
from twilio.rest import Client as TwilioClient

# --- KALITLARNI GITHUB / REPLIT SECRETS DAN OLISH ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

user_phone_numbers = {}

client = genai.Client(api_key=GEMINI_API_KEY)
twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def generate_response(prompt: str) -> str:
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text
    except Exception as e:
        return f"Xatolik: {e}"

async def make_phone_call_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    chat_id = job.chat_id
    task_text = job.data
    user_phone = user_phone_numbers.get(chat_id)
    
    if not user_phone:
        await context.bot.send_message(chat_id=chat_id, text="⚠️ Telefon raqam kiritilmagan!")
        return

    prompt = f"Foydalanuvchiga quyidagi vazifani bajarish kerakligini do'stona va qat'iy ohangda eslatish uchun o'zbek tilida qisqa matn yoz: '{task_text}'"
    ai_text = await generate_response(prompt)
    await context.bot.send_message(chat_id=chat_id, text=f"📞 QO'NG'IROQ QILINDI:\n\n{ai_text}")

    try:
        twiml_code = f"<Response><Say language='uz-UZ' voice='alice'>{ai_text}</Say></Response>"
        twilio_client.calls.create(twiml=twiml_code, to=user_phone, from_=TWILIO_PHONE_NUMBER)
    except Exception as e:
        logging.error(f"Xatolik: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [
        [KeyboardButton("📱 Telefon raqamni kiritish"), KeyboardButton("⏰ Eslatma o'rnatish")],
        [KeyboardButton("📋 Kun tartibi bo'yicha maslahat")]
    ]
    await update.message.reply_text(
        "Assalomu alaykum! Men sizning shaxsiy AI yordamchingizman.",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    chat_id = update.effective_chat.id

    if text == "📱 Telefon raqamni kiritish":
        await update.message.reply_text("Raqamingizni yuboring. Masalan: `/phone +998901234567`", parse_mode="Markdown")
    elif text == "⏰ Eslatma o'rnatish":
        keyboard = [
            [InlineKeyboardButton("15 daqiqadan keyin", callback_data="delay_15")],
            [InlineKeyboardButton("1 soatdan keyin", callback_data="delay_60")]
        ]
        await update.message.reply_text("Vaqtni tanlang:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif text.startswith("/phone"):
        try:
            phone = text.split()[1]
            user_phone_numbers[chat_id] = phone
            await update.message.reply_text(f"✅ Raqam saqlandi: {phone}")
        except:
            await update.message.reply_text("❌ Xato format. Masalan: `/phone +998901234567`", parse_mode="Markdown")
    else:
        ai_response = await generate_response(text)
        await update.message.reply_text(ai_response)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    if chat_id not in user_phone_numbers:
        await query.message.reply_text("⚠️ Avval telefon raqamingizni kiriting!")
        return
    if query.data == "delay_15":
        context.job_queue.run_once(make_phone_call_reminder, when=timedelta(minutes=15), chat_id=chat_id, data="15 daqiqalik vaqt tugadi!")
        await query.edit_message_text("✅ 15 daqiqadan so'ng qo'ng'iroq qilinadi.")
    elif query.data == "delay_60":
        context.job_queue.run_once(make_phone_call_reminder, when=timedelta(hours=1), chat_id=chat_id, data="1 soatlik vaqt tugadi!")
        await query.edit_message_text("✅ 1 soatdan so'ng qo'ng'iroq qilinadi.")

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
