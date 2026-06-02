import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters,
    ContextTypes,
)
from telegram.error import Forbidden, BadRequest
from config import BOT_TOKEN, ADMIN_IDS, ADMIN_USERNAME
import database as db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ConversationHandler states
(
    KINO_KOD, KINO_NOMI, KINO_FILE,
    OCHIR_KOD,
    KANAL_QOSH, KANAL_OCHIR,
    BROADCAST_MATN,
    QIDIRUV_KOD,
) = range(8)


# ═══════════════════════════════════════════════
# YORDAMCHI FUNKSIYALAR
# ═══════════════════════════════════════════════

def admin_mi(user_id):
    return user_id in ADMIN_IDS


async def obuna_tekshir(bot, user_id):
    """Foydalanuvchi barcha majburiy kanallarga obuna bo'lganini tekshiradi."""
    kanallar = db.barcha_kanallar()
    obuna_emas = []
    for kanal in kanallar:
        try:
            member = await bot.get_chat_member(kanal["kanal_id"], user_id)
            if member.status in ("left", "kicked", "banned"):
                obuna_emas.append(kanal)
        except Exception:
            obuna_emas.append(kanal)
    return obuna_emas


async def obuna_xabar_yuborib(update_or_message, obuna_emas):
    """Obuna bo'lmagan kanallar uchun xabar va tugmalar yuboradi."""
    tugmalar = []
    for kanal in obuna_emas:
        kanal_id = kanal["kanal_id"]
        kanal_nomi = kanal["kanal_nomi"]
        if kanal_id.lstrip("-").isdigit():
            link = f"https://t.me/c/{str(kanal_id).replace('-100', '')}"
        else:
            link = f"https://t.me/{kanal_id.lstrip('@')}"
        tugmalar.append([InlineKeyboardButton(f"📢 {kanal_nomi}", url=link)])

    tugmalar.append([InlineKeyboardButton("✅ Obuna bo'ldim", callback_data="obuna_tekshir")])
    markup = InlineKeyboardMarkup(tugmalar)

    matn = (
        "⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>\n\n"
        "Obuna bo'lgach, <b>✅ Obuna bo'ldim</b> tugmasini bosing."
    )

    if hasattr(update_or_message, "message") and update_or_message.message:
        await update_or_message.message.reply_html(matn, reply_markup=markup)
    else:
        await update_or_message.reply_html(matn, reply_markup=markup)


# ═══════════════════════════════════════════════
# FOYDALANUVCHI — START
# ═══════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.foydalanuvchi_qosh(user.id, user.full_name, user.username or "")

    # Obuna tekshirish
    obuna_emas = await obuna_tekshir(context.bot, user.id)
    if obuna_emas:
        await obuna_xabar_yuborib(update, obuna_emas)
        return

    # Foydalanuvchi paneli
    tugmalar = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Kod orqali qidiruv", callback_data="qidiruv")],
        [InlineKeyboardButton("📩 Adminga murojaat", url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}")],
    ])

    await update.message.reply_html(
        f"Salom, <b>{user.first_name}</b>! 🎬\n\n"
        "Kino kodini yuboring yoki quyidagi tugmalardan foydalaning.",
        reply_markup=tugmalar
    )


# ═══════════════════════════════════════════════
# FOYDALANUVCHI — KOD YUBORISH
# ═══════════════════════════════════════════════

async def kod_qabul(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.faollik_yangilab(user.id)

    # Obuna tekshirish
    obuna_emas = await obuna_tekshir(context.bot, user.id)
    if obuna_emas:
        await obuna_xabar_yuborib(update, obuna_emas)
        return

    kod = update.message.text.strip()
    kino = db.kino_olish(kod)

    if kino:
        caption = f"🎬 <b>{kino['nomi']}</b>"
        if kino["izoh"]:
            caption += f"\n\n{kino['izoh']}"
        caption += f"\n\n📌 Kod: <code>{kod}</code>"

        await update.message.reply_video(
            video=kino["file_id"],
            caption=caption,
            parse_mode="HTML"
        )
    else:
        await update.message.reply_html(
            f"❌ <b>{kod}</b> kodli kino topilmadi.\n"
            "Iltimos, to'g'ri kodni kiriting."
        )


# ═══════════════════════════════════════════════
# CALLBACK — OBUNA TEKSHIRISH
# ═══════════════════════════════════════════════

async def obuna_tekshir_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    obuna_emas = await obuna_tekshir(context.bot, user.id)
    if obuna_emas:
        await query.answer("❌ Hali obuna bo'lmadingiz!", show_alert=True)
        return

    db.foydalanuvchi_qosh(user.id, user.full_name, user.username or "")
    await query.message.delete()

    tugmalar = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Kod orqali qidiruv", callback_data="qidiruv")],
        [InlineKeyboardButton("📩 Adminga murojaat", url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}")],
    ])
    await context.bot.send_message(
        user.id,
        f"✅ Rahmat! Endi botdan foydalanishingiz mumkin.\n\n"
        "🎬 Kino kodini yuboring.",
        reply_markup=tugmalar
    )


# ═══════════════════════════════════════════════
# CALLBACK — QIDIRUV
# ═══════════════════════════════════════════════

async def qidiruv_boshlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_html(
        "🔍 <b>Kino kodini yuboring:</b>\n\n"
        "/bekor — bekor qilish"
    )
    return QIDIRUV_KOD


async def qidiruv_kod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    obuna_emas = await obuna_tekshir(context.bot, user.id)
    if obuna_emas:
        await obuna_xabar_yuborib(update, obuna_emas)
        return ConversationHandler.END

    kod = update.message.text.strip()
    kino = db.kino_olish(kod)

    if kino:
        caption = f"🎬 <b>{kino['nomi']}</b>"
        if kino["izoh"]:
            caption += f"\n\n{kino['izoh']}"
        caption += f"\n\n📌 Kod: <code>{kod}</code>"
        await update.message.reply_video(video=kino["file_id"], caption=caption, parse_mode="HTML")
    else:
        await update.message.reply_html(f"❌ <b>{kod}</b> kodli kino topilmadi.")

    return ConversationHandler.END


# ═══════════════════════════════════════════════
# ADMIN — PANEL
# ═══════════════════════════════════════════════

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin_mi(update.effective_user.id):
        return

    tugmalar = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Kino qo'shish", callback_data="a_kino_qosh"),
         InlineKeyboardButton("🗑 Kino o'chirish", callback_data="a_kino_ochir")],
        [InlineKeyboardButton("📊 Statistika", callback_data="a_stat")],
        [InlineKeyboardButton("📢 Kanal qo'shish", callback_data="a_kanal_qosh"),
         InlineKeyboardButton("❌ Kanal o'chirish", callback_data="a_kanal_ochir")],
        [InlineKeyboardButton("📋 Kanallar ro'yxati", callback_data="a_kanallar")],
        [InlineKeyboardButton("📣 Xabar yuborish", callback_data="a_broadcast")],
    ])

    await update.message.reply_html(
        "👨‍💼 <b>Admin panel</b>\n\nNimani xohlaysiz?",
        reply_markup=tugmalar
    )


# ═══════════════════════════════════════════════
# ADMIN — STATISTIKA
# ═══════════════════════════════════════════════

async def admin_stat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    stat = db.statistika()
    kinolar = db.kinolar_soni()

    matn = (
        "📊 <b>Bot statistikasi:</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{stat['jami']}</b>\n"
        f"✅ Faol (so'nggi 7 kun): <b>{stat['faol']}</b>\n"
        f"🚫 Bot bloklagan: <b>{stat['bloklagan']}</b>\n"
        f"🎬 Kinolar soni: <b>{kinolar}</b>"
    )

    tugma = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="a_orqaga")]])
    await query.message.edit_text(matn, parse_mode="HTML", reply_markup=tugma)


# ═══════════════════════════════════════════════
# ADMIN — KINO QO'SHISH
# ═══════════════════════════════════════════════

async def a_kino_qosh_boshlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_html(
        "➕ <b>Kino qo'shish</b>\n\n"
        "1️⃣ Kino kodini yuboring (masalan: <code>101</code>)\n\n"
        "/bekor — bekor qilish"
    )
    return KINO_KOD


async def a_kino_kod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin_mi(update.effective_user.id):
        return ConversationHandler.END
    kod = update.message.text.strip()
    if db.kino_olish(kod):
        await update.message.reply_html(f"⚠️ <b>{kod}</b> kodi allaqachon mavjud! Boshqa kod kiriting.\n/bekor")
        return KINO_KOD
    context.user_data["kod"] = kod
    await update.message.reply_html(f"✅ Kod: <code>{kod}</code>\n\n2️⃣ Kino nomini yuboring:")
    return KINO_NOMI


async def a_kino_nom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin_mi(update.effective_user.id):
        return ConversationHandler.END
    context.user_data["nomi"] = update.message.text.strip()
    await update.message.reply_html(
        f"✅ Nomi: <b>{context.user_data['nomi']}</b>\n\n"
        "3️⃣ Endi kino faylini yuboring (video).\n\n"
        "💡 Izoh ham yozmoqchi bo'lsangiz, video caption ga yozing."
    )
    return KINO_FILE


async def a_kino_fayl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin_mi(update.effective_user.id):
        return ConversationHandler.END

    if update.message.video:
        file_id = update.message.video.file_id
    elif update.message.document:
        file_id = update.message.document.file_id
    else:
        await update.message.reply_text("❌ Video fayl yuboring!")
        return KINO_FILE

    izoh = update.message.caption or ""
    kod = context.user_data["kod"]
    nomi = context.user_data["nomi"]

    if db.kino_qosh(kod, nomi, file_id, izoh):
        await update.message.reply_html(
            f"✅ <b>Kino qo'shildi!</b>\n\n"
            f"📌 Kod: <code>{kod}</code>\n"
            f"🎬 Nomi: {nomi}"
        )
    else:
        await update.message.reply_text("❌ Xatolik yuz berdi.")

    context.user_data.clear()
    return ConversationHandler.END


# ═══════════════════════════════════════════════
# ADMIN — KINO O'CHIRISH
# ═══════════════════════════════════════════════

async def a_kino_ochir_boshlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_html(
        "🗑 <b>Kino o'chirish</b>\n\n"
        "O'chirmoqchi bo'lgan kino kodini yuboring:\n\n"
        "/bekor — bekor qilish"
    )
    return OCHIR_KOD


async def a_kino_ochir_kod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin_mi(update.effective_user.id):
        return ConversationHandler.END
    kod = update.message.text.strip()
    if db.kino_ochir(kod):
        await update.message.reply_html(f"✅ <b>{kod}</b> kodli kino o'chirildi!")
    else:
        await update.message.reply_html(f"❌ <b>{kod}</b> kodli kino topilmadi.")
    return ConversationHandler.END


# ═══════════════════════════════════════════════
# ADMIN — KANAL QO'SHISH
# ═══════════════════════════════════════════════

async def a_kanal_qosh_boshlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_html(
        "📢 <b>Kanal qo'shish</b>\n\n"
        "Kanal ID yoki username ini yuboring.\n\n"
        "Misol (username): <code>@mening_kanalim</code>\n"
        "Misol (ID): <code>-1001234567890</code>\n\n"
        "⚠️ Bot kaналda admin bo'lishi shart!\n\n"
        "/bekor — bekor qilish"
    )
    return KANAL_QOSH


async def a_kanal_qosh_qabul(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin_mi(update.effective_user.id):
        return ConversationHandler.END

    kanal_id = update.message.text.strip()

    try:
        chat = await context.bot.get_chat(kanal_id)
        kanal_nomi = chat.title or kanal_id

        if db.kanal_qosh(kanal_id, kanal_nomi):
            await update.message.reply_html(
                f"✅ <b>{kanal_nomi}</b> kanali qo'shildi!\n"
                f"ID: <code>{kanal_id}</code>"
            )
        else:
            await update.message.reply_text("⚠️ Bu kanal allaqachon qo'shilgan!")
    except Exception as e:
        await update.message.reply_html(
            f"❌ Kanal topilmadi yoki bot admin emas!\n"
            f"Xatolik: <code>{e}</code>"
        )

    return ConversationHandler.END


# ═══════════════════════════════════════════════
# ADMIN — KANAL O'CHIRISH
# ═══════════════════════════════════════════════

async def a_kanal_ochir_boshlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    kanallar = db.barcha_kanallar()
    if not kanallar:
        await query.message.reply_text("📋 Hech qanday kanal yo'q.")
        return ConversationHandler.END

    matn = "❌ <b>Qaysi kanalni o'chirish kerak?</b>\n\nKanal ID ni yuboring:\n\n"
    for k in kanallar:
        matn += f"• <code>{k['kanal_id']}</code> — {k['kanal_nomi']}\n"
    matn += "\n/bekor — bekor qilish"

    await query.message.reply_html(matn)
    return KANAL_OCHIR


async def a_kanal_ochir_qabul(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin_mi(update.effective_user.id):
        return ConversationHandler.END
    kanal_id = update.message.text.strip()
    if db.kanal_ochir(kanal_id):
        await update.message.reply_html(f"✅ <code>{kanal_id}</code> kanali o'chirildi!")
    else:
        await update.message.reply_html(f"❌ <code>{kanal_id}</code> topilmadi.")
    return ConversationHandler.END


# ═══════════════════════════════════════════════
# ADMIN — KANALLAR RO'YXATI
# ═══════════════════════════════════════════════

async def a_kanallar_royxati(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    kanallar = db.barcha_kanallar()
    if not kanallar:
        await query.message.edit_text(
            "📋 Hech qanday majburiy kanal yo'q.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="a_orqaga")]])
        )
        return

    matn = "📋 <b>Majburiy kanallar:</b>\n\n"
    for k in kanallar:
        matn += f"• {k['kanal_nomi']} — <code>{k['kanal_id']}</code>\n"

    await query.message.edit_text(
        matn, parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Orqaga", callback_data="a_orqaga")]])
    )


# ═══════════════════════════════════════════════
# ADMIN — BROADCAST
# ═══════════════════════════════════════════════

async def a_broadcast_boshlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_html(
        "📣 <b>Xabar yuborish</b>\n\n"
        "Barcha foydalanuvchilarga yuboriladigan xabarni yozing:\n\n"
        "/bekor — bekor qilish"
    )
    return BROADCAST_MATN


async def a_broadcast_yuborish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not admin_mi(update.effective_user.id):
        return ConversationHandler.END

    xabar = update.message
    idlar = db.barcha_user_idlar()

    yuborildi = 0
    xato = 0

    status_xabar = await update.message.reply_html(
        f"📣 Yuborilmoqda... 0/{len(idlar)}"
    )

    for i, user_id in enumerate(idlar):
        try:
            await xabar.copy(chat_id=user_id)
            yuborildi += 1
        except Forbidden:
            db.bloklagan_belgi(user_id)
            xato += 1
        except Exception:
            xato += 1

        if (i + 1) % 20 == 0:
            try:
                await status_xabar.edit_text(f"📣 Yuborilmoqda... {i+1}/{len(idlar)}")
            except Exception:
                pass
        await asyncio.sleep(0.05)

    await status_xabar.edit_text(
        f"✅ <b>Xabar yuborish tugadi!</b>\n\n"
        f"✅ Yuborildi: {yuborildi}\n"
        f"❌ Xato (bloklagan): {xato}",
        parse_mode="HTML"
    )
    return ConversationHandler.END


# ═══════════════════════════════════════════════
# ADMIN — ORQAGA
# ═══════════════════════════════════════════════

async def a_orqaga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    tugmalar = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 Kino qo'shish", callback_data="a_kino_qosh"),
         InlineKeyboardButton("🗑 Kino o'chirish", callback_data="a_kino_ochir")],
        [InlineKeyboardButton("📊 Statistika", callback_data="a_stat")],
        [InlineKeyboardButton("📢 Kanal qo'shish", callback_data="a_kanal_qosh"),
         InlineKeyboardButton("❌ Kanal o'chirish", callback_data="a_kanal_ochir")],
        [InlineKeyboardButton("📋 Kanallar ro'yxati", callback_data="a_kanallar")],
        [InlineKeyboardButton("📣 Xabar yuborish", callback_data="a_broadcast")],
    ])
    await query.message.edit_text(
        "👨‍💼 <b>Admin panel</b>\n\nNimani xohlaysiz?",
        parse_mode="HTML",
        reply_markup=tugmalar
    )


# ═══════════════════════════════════════════════
# BEKOR QILISH
# ═══════════════════════════════════════════════

async def bekor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Bekor qilindi.")
    return ConversationHandler.END


# ═══════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════

def main():
    db.create_tables()
    app = Application.builder().token(BOT_TOKEN).build()

    # Kino qo'shish
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(a_kino_qosh_boshlash, pattern="^a_kino_qosh$")],
        states={
            KINO_KOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_kino_kod)],
            KINO_NOMI: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_kino_nom)],
            KINO_FILE: [MessageHandler(filters.VIDEO | filters.Document.ALL, a_kino_fayl)],
        },
        fallbacks=[CommandHandler("bekor", bekor)],
    ))

    # Kino o'chirish
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(a_kino_ochir_boshlash, pattern="^a_kino_ochir$")],
        states={
            OCHIR_KOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_kino_ochir_kod)],
        },
        fallbacks=[CommandHandler("bekor", bekor)],
    ))

    # Kanal qo'shish
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(a_kanal_qosh_boshlash, pattern="^a_kanal_qosh$")],
        states={
            KANAL_QOSH: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_kanal_qosh_qabul)],
        },
        fallbacks=[CommandHandler("bekor", bekor)],
    ))

    # Kanal o'chirish
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(a_kanal_ochir_boshlash, pattern="^a_kanal_ochir$")],
        states={
            KANAL_OCHIR: [MessageHandler(filters.TEXT & ~filters.COMMAND, a_kanal_ochir_qabul)],
        },
        fallbacks=[CommandHandler("bekor", bekor)],
    ))

    # Broadcast
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(a_broadcast_boshlash, pattern="^a_broadcast$")],
        states={
            BROADCAST_MATN: [MessageHandler(filters.ALL & ~filters.COMMAND, a_broadcast_yuborish)],
        },
        fallbacks=[CommandHandler("bekor", bekor)],
    ))

    # Qidiruv
    app.add_handler(ConversationHandler(
        entry_points=[CallbackQueryHandler(qidiruv_boshlash, pattern="^qidiruv$")],
        states={
            QIDIRUV_KOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, qidiruv_kod)],
        },
        fallbacks=[CommandHandler("bekor", bekor)],
    ))

    # Callback handlers
    app.add_handler(CallbackQueryHandler(obuna_tekshir_callback, pattern="^obuna_tekshir$"))
    app.add_handler(CallbackQueryHandler(admin_stat, pattern="^a_stat$"))
    app.add_handler(CallbackQueryHandler(a_kanallar_royxati, pattern="^a_kanallar$"))
    app.add_handler(CallbackQueryHandler(a_orqaga, pattern="^a_orqaga$"))

    # Asosiy buyruqlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("bekor", bekor))

    # Foydalanuvchi kod yuborishi
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, kod_qabul))

    print("✅ Bot ishga tushdi...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
