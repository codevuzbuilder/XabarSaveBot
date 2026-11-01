"""buttons.py — foydalanuvchi tugmalari va admin panel menyulari (har bir bot o'zining admin paneliga ega)."""
import time
from core import *
from ui import *
from pay import *
from ops import *


# ----------------------------- admin panel: bo'limlar va tugmalar -----------------------------
def _h(name): return lambda s, uid: HOOKS[name](s, uid)


CATS = [
    ("📊 Statistika", [
        ("👥 Jami userlar", "sql", "SELECT COUNT(*) FROM users"),
        ("🆕 Bugun qo'shilgan", "sql", "SELECT COUNT(*) FROM users WHERE joined>={day}"),
        ("📆 Haftalik yangi", "sql", "SELECT COUNT(*) FROM users WHERE joined>={now}-604800"),
        ("🗓 Oylik yangi", "sql", "SELECT COUNT(*) FROM users WHERE joined>={now}-2592000"),
        ("💎 Faol obuna", "sql", "SELECT COUNT(*) FROM users WHERE sub_until>{now}"),
        ("⌛ Obunasi tugagan", "sql", "SELECT COUNT(*) FROM users WHERE sub_until<={now}"),
        ("🔗 Ulangan akkaunt", "sql", "SELECT COUNT(*) FROM conns"),
        ("💬 Keshdagi xabarlar", "sql", "SELECT COUNT(*) FROM msgs"),
        ("🤝 Hamkorlar soni", "sql", "SELECT COUNT(*) FROM users WHERE is_partner=1"),
        ("💵 Jami tushum", "sql", "SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='approved'"),
    ]),
    ("💰 Narxlar", [
        ("💲 7 kunlik narx", "set", "price_7"), ("💲 30 kunlik narx", "set", "price_30"),
        ("💲 90 kunlik narx", "set", "price_90"), ("💲 365 kunlik narx", "set", "price_365"),
        ("🎁 Bepul kunlar (sinov)", "set", "trial_days"), ("🤝 Hamkorlik narxi", "set", "partner_price"),
        ("🔗 Referal ulushi %", "set", "ref_percent"),
        ("🎁 To'ldirish bonusi %", "set", "topup_bonus"),
        ("⬇️ Min to'ldirish", "set", "min_topup"), ("⬆️ Max to'ldirish", "set", "max_topup"),
    ]),
    ("💳 To'lov tizimi", [
        ("⚡ Avto to'lov ulash", "wiz", "tc"), ("🔑 Hisob API", "set", "tc_key"), ("🏪 Kassa API", "set", "tc_kassa"),
        ("🌐 Tezcheck API manzil", "set", "tc_base"), ("⚡ Avto-to'lov yoq/o'ch", "toggle", "autopay"),
        ("💳 Click ulash", "wiz", "click"), ("💳 Click yoq/o'ch", "toggle", "click_on"),
        ("💳 Karta rekviziti", "set", "pay_info"), ("🧾 Chek rejimi yoq/o'ch", "toggle", "manual_pay"),
        ("⏱ Schot muddati (daq)", "set", "tc_ttl"),
        ("💼 Tezcheck balansi", "fn", f_tc_balance), ("🧪 Ulanishni tekshirish", "fn", f_tc_test),
    ]),
    ("👤 Userlar", [
        ("🔎 User ma'lumoti", "op", "info", "ID yuboring. Masalan: 123456789"),
        ("🚫 User ban", "op", "ban", "ID yuboring."), ("✅ Bandan chiqarish", "op", "unban", "ID yuboring."),
        ("➕ Kun qo'shish", "op", "addays", "ID va kun: 123456789 30"),
        ("➖ Obunani bekor qilish", "op", "cancelsub", "ID yuboring."),
        ("💵 Balans qo'shish", "op", "addbal", "ID va summa: 123456789 10000"),
        ("💸 Balans ayirish", "op", "subbal", "ID va summa: 123456789 10000"),
        ("📋 So'nggi 10 user", "fn", f_last_users), ("🚷 Banlanganlar", "fn", f_banned),
        ("💬 Userga xabar", "op", "sendmsg", "ID va matn: 123456789 Salom"),
    ]),
    ("🤝 Hamkorlar", [
        ("📋 Hamkorlar ro'yxati", "fn", f_partners), ("➕ Hamkor qilish", "op", "partner_add", "ID yuboring."),
        ("➖ Hamkorlikdan chiqarish", "op", "partner_del", "ID yuboring."),
        ("🤖 Klon botlar", "fn", f_clones), ("🗑 Klonni o'chirish", "op", "clone_del", "Hamkor ID sini yuboring."),
    ]),
    ("📢 Xabarlar", [
        ("📢 Hammaga xabar", "bc", "all"), ("💎 Faollarga xabar", "bc", "active"),
        ("⌛ Tugaganlarga xabar", "bc", "expired"), ("🤝 Hamkorlarga xabar", "bc", "partners"),
        ("👋 Salomlashuv matni", "set", "welcome_text"), ("📖 Qo'llanma matni", "set", "guide_text"),
        ("❓ Savol-javob matni", "set", "faq_text"), ("📜 Shartlar matni", "set", "terms_text"),
        ("🆘 Yordam matni", "set", "support_text"), ("🤝 Hamkorlik matni", "set", "partner_text"),
    ]),
    ("⚙️ Sozlamalar", [
        ("🔌 Bot yoq/o'ch", "toggle", "bot_on"), ("🆕 Ro'yxat yoq/o'ch", "toggle", "reg_on"),
        ("🎁 Sinov yoq/o'ch", "toggle", "trial_on"), ("🗑 O'chirilgan xabar yoq/o'ch", "toggle", "notify_deleted"),
        ("✏️ Tahrir xabari yoq/o'ch", "toggle", "notify_edited"), ("🖼 Media saqlash yoq/o'ch", "toggle", "save_media"),
        ("🤝 Hamkorlik yoq/o'ch", "toggle", "partner_on"), ("🔗 Referal yoq/o'ch", "toggle", "ref_on"),
        ("🎟 Promokod yoq/o'ch", "toggle", "promo_on"), ("🔔 Yangi user xabari", "toggle", "notify_admin_new"),
    ]),
    ("🗄 Ma'lumotlar", [
        ("💾 Zaxira nusxa", "fn", f_backup), ("👥 Userlar CSV", "fn", f_csv_users), ("🧾 To'lovlar CSV", "fn", f_csv_pay),
        ("🧹 Eski keshni tozalash", "fn", f_clear_old), ("🗑 Butun keshni tozalash", "fn", f_clear_all),
        ("📅 Kesh saqlash kuni", "set", "cache_days"), ("🧮 DB hajmi", "fn", f_db_size),
        ("🪄 DB optimallash", "fn", f_vacuum), ("📋 Kutilayotgan to'lovlar", "fn", f_pending),
        ("🧾 So'nggi 10 to'lov", "fn", f_last_payments),
    ]),
    ("🎁 Promokodlar", [
        ("➕ Kunli promokod", "op", "promo_days", "KOD KUN LIMIT: YANGI30 30 100"),
        ("💵 Pulli promokod", "op", "promo_money", "KOD SUMMA LIMIT: BONUS 10000 50"),
        ("🗑 Promokodni o'chirish", "op", "promo_del", "KOD yuboring."), ("📋 Promokodlar ro'yxati", "fn", f_promos),
        ("🔎 Promokod ma'lumoti", "op", "promo_info", "KOD yuboring."),
        ("🔄 Promokod yoq/o'ch", "op", "promo_toggle", "KOD yuboring."), ("📊 Promokod statistikasi", "fn", f_promo_stats),
        ("🧹 Tugaganlarni tozalash", "fn", f_promo_clean), ("📣 Promokodni e'lon qilish", "op", "promo_announce", "KOD yuboring."),
        ("👁 Promokod ishlatganlar", "op", "promo_users", "KOD yuboring."),
    ]),
    ("🛠 Qo'shimcha", [
        ("➕ Kanal qo'shish", "op", "chadd", "Kanal yuboring: @kanal yoki -100... ID (ixtiyoriy: havola).\n"
         "Masalan: @mening_kanalim\nYopiq kanal: -1001234567890 https://t.me/+AbCdEf\n⚠️ Bot kanalda ADMIN bo'lishi shart."),
        ("➖ Kanalni olib tashlash", "op", "chdel", "Ro'yxatdagi raqamni (#id) yoki @kanal ni yuboring."),
        ("📺 Kanallar ro'yxati", "fn", f_channels), ("📢 Majburiy obuna yoq/o'ch", "toggle", "force_sub"),
        ("📝 Log chat ID", "set", "log_chat"),
        ("👮 Admin qo'shish", "op", "admin_add", "Yangi admin ID sini yuboring."),
        ("👮 Admin o'chirish", "op", "admin_del", "Admin ID sini yuboring."), ("📋 Adminlar", "fn", f_admins),
        ("🤖 Bot haqida", "fn", f_bot_info), ("🩺 Business holati", "fn", f_biz), ("🐞 Xatolar logi", "fn", f_errors),
        ("🔁 Qayta ishga tushirish", "fn", f_restart), ("🏓 Ping", "fn", f_ping),
    ]),
    ("🎨 Dizayn", [
        ("🎨 Tugma ranglari", "dz", "color"), ("✏️ Tugmalarni tahrirlash", "dz", "name"),
        ("💎 Tugmaga premium emoji", "dz", "emoji"), ("💎 Premium emoji yoq/o'ch", "toggle", "icons_on"),
        ("🔄 Premium emojini yangilash", "fn", _h("icons_reload")), ("📋 Premium emoji holati", "fn", _h("icons_report")),
        ("♻️ Dizaynni tiklash", "fn", _h("design_reset")), ("👁 Menyuni ko'rish", "fn", _h("preview")),
    ]),
]
# faqat asosiy botda (klon botlarida ko'rinmaydi)
MAIN_CATS = {"🤝 Hamkorlar"}
MAIN_ONLY = {"🤝 Hamkorlar soni", "🤝 Hamkorlik narxi", "🤝 Hamkorlik matni", "🤝 Hamkorlik yoq/o'ch", "🤝 Hamkorlarga xabar",
             "🐞 Xatolar logi", "🔁 Qayta ishga tushirish"}


def cats():
    out = []
    for ci, (cl, items) in enumerate(CATS):
        if cl in MAIN_CATS and not is_main(): continue
        out.append((ci, cl, [it for it in items if is_main() or it[0] not in MAIN_ONLY]))
    return out


def admin_rows():
    cl = [c[1] for c in cats()]
    return [[(x, "primary") for x in cl[i:i + 2]] for i in range(0, len(cl), 2)] + [[("🏠 Menyu", "")]]


def cat_rows(ci):
    items = dict((c[0], c[2]) for c in cats()).get(ci, [])
    return [[(it[0], btn_style(it)) for it in items[i:i + 2]] for i in range(0, len(items), 2)] + \
           [[("⬅️ Admin panel", "primary"), ("🏠 Menyu", "")]]


@route("⚙️ Admin panel")
def r_admin(s, uid, m):
    if is_admin(uid): s.send(uid, "⚙️ <b>Admin panel</b> — bo'lim tanlang:", admin_rows())


@route("⬅️ Admin panel")
def r_admin_back(s, uid, m): r_admin(s, uid, m)


def _mk_cat(ci):
    def f(s, uid, m):
        if is_admin(uid) and ci in dict((c[0], 1) for c in cats()): s.send(uid, f"{CATS[ci][0]} — tugmani tanlang:", cat_rows(ci))
    return f


def _mk_item(it):
    def f(s, uid, m):
        if is_admin(uid) and (is_main() or it[0] not in MAIN_ONLY): run_item(s, uid, it)
    return f


for _ci, (_cl, _items) in enumerate(CATS):
    ROUTES[_cl] = _mk_cat(_ci)
    for _it in _items: ROUTES[_it[0]] = _mk_item(_it)
