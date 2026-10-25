import os
import time
import json
import threading
import telebot
from telebot import types
import requests
import pandas as pd
from datetime import datetime

# ==================== الإعدادات الخاصة بك ====================
TELEGRAM_BOT_TOKEN = "8954641721:AAHBWmlTuO7GOU6JuWvhDHfqjSj1lSCf8fY"
BINANCE_API_KEY = "NCFYVdVIzzr5xurb9LwtpgUoHbE7bX3nr9mq7WVsLSPxetNC8FIbCWnPONVbJxdm"
# ============================================================

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# قاموس لتتبع وقت آخر طلب لكل مستخدم (Cooldown)
user_cooldowns = {}
COOLDOWN_TIME = 180  # 3 دقائق بالثواني

# ملف حفظ وتتبع الصفقات
HISTORY_FILE = "deals_history.json"

def load_deals():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"خطأ في قراءة ملف الصفقات: {e}")
    return []

def save_deals(deals):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(deals, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"خطأ في حفظ ملف الصفقات: {e}")

def get_binance_spot_symbols():
    urls = [
        "https://api.binance.com/api/v3/exchangeInfo",
        "https://data-api.binance.vision/api/v3/exchangeInfo"
    ]
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                symbols = []
                for s in data.get('symbols', []):
                    if s['status'] == 'TRADING' and s['quoteAsset'] == 'USDT':
                        symbols.append(s['symbol'])
                return symbols
        except:
            continue
    return []

def calculate_rsi(prices, period=14):
    deltas = pd.Series(prices).diff()
    gain = (deltas.where(deltas > 0, 0)).rolling(window=period).mean()
    loss = (-deltas.where(deltas < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

def get_current_price(symbol):
    urls = [
        f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}",
        f"https://data-api.binance.vision/api/v3/ticker/price?symbol={symbol}"
    ]
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    for url in urls:
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                return float(res.json()['price'])
        except:
            continue
    return None

# دالة تعمل في الخلفية لمتابعة الصفقات المفتوحة وتحديث النجاح والفشل بدقة
def track_deals_background():
    while True:
        try:
            deals = load_deals()
            updated = False
            for deal in deals:
                if deal.get('status') == 'ACTIVE':
                    symbol = deal['symbol']
                    price = get_current_price(symbol)
                    if price:
                        # 1. فحص وقف الخسارة أولاً (إذا السعر نزل تحت SL)
                        if price <= deal['sl']:
                            deal['status'] = 'FAILED'
                            deal['achieved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                            deal['result_note'] = "ضربت وقف الخسارة (SL) ❌ (-3.5%)"
                            updated = True
                        # 2. فحص تحقيق الهدف الثاني
                        elif price >= deal['tp2']:
                            deal['status'] = 'SUCCESS_ALL'
                            deal['achieved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                            deal['result_note'] = "حققت كافة الأهداف (TP1 & TP2) ✨ (+7.0%)"
                            updated = True
                        # 3. فحص تحقيق الهدف الأول فقط
                        elif price >= deal['tp1']:
                            deal['status'] = 'SUCCESS_TP1'
                            deal['achieved_at'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                            deal['result_note'] = "حققت الهدف الأول (TP1) 🎯 (+3.5%)"
                            updated = True
                        time.sleep(0.5)
            if updated:
                save_deals(deals)
        except Exception as e:
            print(f"خطأ في تتبع الصفقات: {e}")
        time.sleep(120)  # فحص الصفقات كل دقيقتين

# تشغيل خيط تتبع الصفقات
tracking_thread = threading.Thread(target=track_deals_background, daemon=True)
tracking_thread.start()

# لوحة الأزرار الرئيسية (تمت إضافة زر الصفقات الفاشلة)
def main_menu_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_top = types.InlineKeyboardButton("📊 أفضل 3 فرص متاحة", callback_data="btn_top")
    btn_success = types.InlineKeyboardButton("🏆 الصفقات الناجحة", callback_data="btn_success")
    btn_failed = types.InlineKeyboardButton("❌ الصفقات الفاشلة", callback_data="btn_failed")
    markup.add(btn_top)
    markup.add(btn_success, btn_failed)
    return markup

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "مرحباً بك في **Bot Official Signals**! 🤖💎\n\n"
        "اختر الخيار المطلوب من الأزرار أدناه للتحكم بمتابعة السوق والنتائج:"
    )
    bot.reply_to(message, welcome_text, parse_mode="Markdown", reply_markup=main_menu_keyboard())

@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "btn_top":
        current_time = datetime.now()
        # فحص Cooldown
        if user_id in user_cooldowns:
            elapsed_time = (current_time - user_cooldowns[user_id]).total_seconds()
            if elapsed_time < COOLDOWN_TIME:
                remaining_time = int(COOLDOWN_TIME - elapsed_time)
                minutes = remaining_time // 60
                seconds = remaining_time % 60
                bot.answer_callback_query(call.id, f"⏳ الرجاء الانتظار {minutes}د و {seconds}ث لحماية الخادم.", show_alert=True)
                return

        user_cooldowns[user_id] = current_time
        bot.answer_callback_query(call.id, "جاري فحص السوق...")
        bot.send_message(chat_id, "🔍 جاري فحص السوق والبحث عن أفضل 3 فرص متاحة الآن... قد يستغرق ذلك بضع ثوانٍ.")

        symbols = get_binance_spot_symbols()
        if not symbols:
            bot.send_message(chat_id, "❌ تعذر الاتصال بسوق بايننس حالياً. حاول مرة أخرى لاحقاً.")
            return

        headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
        found_opportunities = []
        deals = load_deals()

        for symbol in symbols[:60]:
            if len(found_opportunities) >= 3:
                break

            urls = [
                f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit=50",
                f"https://data-api.binance.vision/api/v3/klines?symbol={symbol}&interval=1h&limit=50"
            ]
            
            data = None
            for url in urls:
                try:
                    res = requests.get(url, headers=headers, timeout=5)
                    if res.status_code == 200:
                        data = res.json()
                        break
                except:
                    continue
                    
            if not isinstance(data, list):
                continue
                
            try:
                closes = [float(candle[4]) for candle in data]
                current_price = closes[-1]
                
                if current_price > 0.50:
                    continue
                    
                rsi = calculate_rsi(closes)
                
                if rsi < 35:
                    tp1 = current_price * 1.035
                    tp2 = current_price * 1.070
                    sl = current_price * 0.965
                    
                    opp_msg = (
                        f"🚨 *فرصة تداول قوية* 🚨\n\n"
                        f"💎 العملة: `{symbol}`\n"
                        f"💰 السعر الحالي: `{current_price}`\n"
                        f"📊 مؤشر RSI: `{rsi:.2f}`\n\n"
                        f"🎯 الأهداف:\n"
                        f"• TP1: `{tp1:.5f}` (+3.5%)\n"
                        f"• TP2: `{tp2:.5f}` (+7.0%)\n"
                        f"🛑 SL: `{sl:.5f}` (-3.5%)\n\n"
                        f"🛡️ *Bot Official Signals*"
                    )
                    found_opportunities.append(opp_msg)

                    # تسجيل الصفقة في التتبع إذا لم تكن مسجلة من قبل
                    if not any(d['symbol'] == symbol and d['status'] == 'ACTIVE' for d in deals):
                        deals.append({
                            "symbol": symbol,
                            "entry": current_price,
                            "tp1": tp1,
                            "tp2": tp2,
                            "sl": sl,
                            "status": "ACTIVE",
                            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                            "result_note": ""
                        })
            except:
                continue

        save_deals(deals)

        if found_opportunities:
            for opp in found_opportunities:
                bot.send_message(chat_id, opp, parse_mode="Markdown")
                time.sleep(0.5)
        else:
            bot.send_message(chat_id, "📉 لم يتم العثور على فرص تطابق الشروط بدقة عالية في هذه اللحظة. جرب مرة أخرى لاحقاً.")

    elif call.data == "btn_success":
        bot.answer_callback_query(call.id, "جاري جلب الصفقات الناجحة...")
        deals = load_deals()
        successful_deals = [d for d in deals if d.get('status') in ['SUCCESS_TP1', 'SUCCESS_ALL']]

        if not successful_deals:
            bot.send_message(chat_id, "🏆 *سجل الصفقات الناجحة*\n\nلا توجد صفقات محققة للأهداف موثقة في السجل حتى الآن.", parse_mode="Markdown")
            return

        report = "🏆 *سجل الصفقات الناجحة* 🏆\n\n"
        for idx, deal in enumerate(reversed(successful_deals[-10:]), 1):
            report += (
                f"{idx}. 💎 *العملة:* `{deal['symbol']}`\n"
                f"   💰 سعر الدخول: `{deal['entry']}`\n"
                f"   ✨ النتيجة: *{deal['result_note']}*\n"
                f"   📅 التاريخ: `{deal.get('achieved_at', deal['created_at'])}`\n"
                f"----------------------------------------\n"
            )
        report += "\n🛡️ *Bot Official Signals*"
        bot.send_message(chat_id, report, parse_mode="Markdown")

    elif call.data == "btn_failed":
        bot.answer_callback_query(call.id, "جاري جلب الصفقات الفاشلة...")
        deals = load_deals()
        failed_deals = [d for d in deals if d.get('status') == 'FAILED']

        if not failed_deals:
            bot.send_message(chat_id, "❌ *سجل الصفقات الفاشلة*\n\nرائع! لا توجد صفقات ضربت وقف الخسارة حتى الآن.", parse_mode="Markdown")
            return

        report = "❌ *سجل الصفقات الفاشلة (ضربت وقف الخسارة)* ❌\n\n"
        for idx, deal in enumerate(reversed(failed_deals[-10:]), 1):
            report += (
                f"{idx}. 💎 *العملة:* `{deal['symbol']}`\n"
                f"   💰 سعر الدخول: `{deal['entry']}`\n"
                f"   ⚠️ النتيجة: *{deal['result_note']}*\n"
                f"   📅 التاريخ: `{deal.get('achieved_at', deal['created_at'])}`\n"
                f"----------------------------------------\n"
            )
        report += "\n🛡️ *Bot Official Signals*"
        bot.send_message(chat_id, report, parse_mode="Markdown")

if __name__ == "__main__":
    print("البوت التفاعلي يعمل الآن بنجاح مع تتبع الصفقات الناجحة والفاشلة...")
    bot.infinity_polling()
