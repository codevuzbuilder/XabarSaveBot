"""user.py — foydalanuvchi tugmalari: obuna, balans, to'lov, promokod, referal, hamkorlik."""
import time
from core import *
from ui import *
from pay import *
from ops import *
from texts import *


# ----------------------------- foydalanuvchi tugmalari -----------------------------
@route("🏠 Menyu")
def r_home(s, uid, m): s.menu(uid)


@route("✅ A'zo bo'ldim")
def r_joined(s, uid, m): s.menu(uid, "✅ Rahmat! Botdan foydalanishingiz mumkin.")


@route("📲 Botni ulash")
def r_connect(s, uid, m):
    s.send_inline(uid, "📲 <b>Botni ulash</b>\n1) Pastdagi tugmani bosing — Telegram profil sozlamalari ochiladi.\n"
                       "2) <b>Chatlarni avtomatlashtirish</b> (Chat automation) bo'limini tanlang.\n"
                       f"3) <code>@{s.username}</code> ni kiriting va chatlarni tanlang.\n"
                       "4) <b>Xabarlarni o'qish</b> ruxsatini yoqing.\n\n"
                       "🔥 <b>O'chib ketuvchi rasm/video:</b> uni OCHISHDAN OLDIN unga istalgan javob (reply) yozing — "
                       "bot nusxasini sizga yuboradi.",
                  [[("📲 Botni ulash", "tg://settings/edit_profile", "primary")],
                   [("🤖 Bot sahifasi", f"https://t.me/{s.username}", "success")]])


@route("💎 Obuna olish")
def r_plans(s, uid, m):
    u = U(uid)
    s.send(uid, "💎 <b>Tariflar</b> (balansdan yechiladi)\n" +
           "\n".join(f"🛒 {d} kun — {money(num(f'price_{d}'))} so'm" for d in (7, 30, 90, 365)) +
           f"\n\n💰 Balansingiz: {money(u['balance'])} so'm",
           [[("🛒 7 kun", "success"), ("🛒 30 kun", "success")], [("🛒 90 kun", "success"), ("🛒 365 kun", "success")],
            [("💳 Balans to'ldirish", "primary"), ("🏠 Menyu", "")]])


def _buy(days):
    def f(s, uid, m):
        price, u = num(f"price_{days}"), U(uid)
        if u["balance"] < price:
            return s.send(uid, f"❌ Balans yetarli emas.\n💰 Balans: {money(u['balance'])}\n🛒 Narx: {money(price)}\n\n"
                               f"«💳 Balans to'ldirish» tugmasini bosing.")
        until = max(int(time.time()), u["sub_until"]) + days * 86400
        run("UPDATE users SET balance=balance-?, sub_until=? WHERE id=?", (price, until, uid))
        shares(u, price)
        s.send(uid, f"✅ Obuna {days} kun ga faollashdi!\n📅 Tugash: {dt(until)}", main_rows(uid))
        log(f"🛒 {uid} — {days} kun ({money(price)} so'm)")
    return f


for _d in (7, 30, 90, 365): ROUTES[f"🛒 {_d} kun"] = _buy(_d)


@route("💳 Balans to'ldirish")
def r_topup(s, uid, m):
    rows = []
    if g("autopay") == "1" and g("tc_key") and g("tc_kassa"): rows.append([("⚡ Avto to'lov", "success")])
    if g("click_on") == "1" and g("click_token"): rows.append([("💳 Click orqali", "success")])
    if g("stars_on") == "1": rows.append([("⭐ Stars orqali", "success")])
    if g("manual_pay") == "1": rows.append([("🧾 Chek bilan to'lov", "primary")])
    if not rows: return s.send(uid, "❌ To'lov usullari hozircha o'chirilgan.", main_rows(uid))
    rows.append([("🏠 Menyu", "")])
    s.send(uid, f"💳 To'lov usulini tanlang.\nMin: {money(num('min_topup'))} • Max: {money(num('max_topup'))} so'm", rows)


def _ask_amount(method):
    def f(s, uid, m):
        STATE[uid] = ("amt", method)
        s.send(uid, "💵 To'ldirish summasini yozing (so'mda):", [[("🏠 Menyu", "")]])
    return f


ROUTES["⚡ Avto to'lov"] = _ask_amount("tc")
ROUTES["💳 Click orqali"] = _ask_amount("click")
ROUTES["⭐ Stars orqali"] = _ask_amount("stars")
ROUTES["🧾 Chek bilan to'lov"] = _ask_amount("receipt")


@route("✅ To'lovni tekshirish")
def r_check(s, uid, m):
    ps = q("SELECT * FROM payments WHERE user_id=? AND status='pending' AND method='tc'", (uid,))
    if not ps: return s.send(uid, "ℹ️ Kutilayotgan to'lov yo'q.", main_rows(uid))
    for p in ps:
        try: check_payment(p)
        except Exception: elog()
    left = q("SELECT COUNT(*) c FROM payments WHERE user_id=? AND status='pending' AND method='tc'", (uid,), True)["c"]
    if left: s.send(uid, "⏳ To'lov hali kelmadi. To'lagan bo'lsangiz, 1-2 daqiqadan so'ng qayta tekshiring.")


@route("💰 Balansim")
def r_balance(s, uid, m):
    s.send(uid, f"💰 Balans: <b>{money(U(uid)['balance'])}</b> so'm", main_rows(uid))


@route("📅 Obunam")
def r_sub(s, uid, m):
    u = U(uid)
    n = q("SELECT COUNT(*) c FROM conns WHERE user_id=?", (uid,), True)["c"]
    st = f"✅ Faol — {dt(u['sub_until'])} gacha" if u["sub_until"] > time.time() else "❌ Obuna yo'q"
    s.send(uid, f"📅 Obuna: {st}\n🔗 Ulangan akkaunt: {n}", main_rows(uid))


@route("🧾 To'lovlarim")
def r_pay_history(s, uid, m):
    ps = q("SELECT * FROM payments WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,))
    ic = {"approved": "✅", "pending": "⏳", "rejected": "❌", "expired": "⌛", "failed": "⚠️"}
    s.send(uid, "🧾 <b>So'nggi to'lovlar</b>\n" + ("\n".join(
        f"{ic.get(p['status'], '•')} #{p['id']} — {money(p['amount'])} so'm ({time.strftime('%d.%m %H:%M', time.localtime(p['ts']))})"
        for p in ps) or "—"), main_rows(uid))


@route("🎁 Promokod")
def r_promo(s, uid, m):
    if g("promo_on") != "1": return s.send(uid, "🎁 Promokodlar hozircha o'chirilgan.", main_rows(uid))
    STATE[uid] = ("promo",)
    s.send(uid, "🎁 Promokodni yuboring:", [[("🏠 Menyu", "")]])


@route("🔗 Referal")
def r_ref(s, uid, m):
    if g("ref_on") != "1": return s.send(uid, "🔗 Referal dasturi hozircha o'chirilgan.", main_rows(uid))
    n = q("SELECT COUNT(*) c FROM users WHERE referrer=?", (uid,), True)["c"]
    rich_key(s, uid, "ref_text", main_rows(uid),
             extra=f"\n\n🔗 Havolangiz:\nhttps://t.me/{s.username}?start=ref_{uid}\n\n👥 Taklif qilinganlar: {n}\n"
                   f"🎁 Ularning har bir xarididan {g('ref_percent')}% balansingizga tushadi.")


@route("🤝 Hamkorlik")
def r_partner(s, uid, m):
    if not is_main() or g("partner_on") != "1": return s.send(uid, "🤝 Hamkorlik dasturi hozircha yopiq.", main_rows(uid))
    u = U(uid)
    if u["is_partner"]:
        return s.send(uid, "🤝 Siz hamkorsiz.\n«🤖 Mening botim» orqali o'z botingizni yarating — unda <b>⚙️ Admin panel</b> "
                           "to'liq sizniki: narxlar, to'lov tizimlari, kanallar, dizayn.", main_rows(uid))
    rich_key(s, uid, "partner_text", [[("✅ Hamkor bo'lish", "success")], [("🏠 Menyu", "")]],
             extra=f"\n\n💎 Narxi: {money(num('partner_price'))} so'm (balansdan)\n💰 Balansingiz: {money(u['balance'])}")


@route("✅ Hamkor bo'lish")
def r_bepartner(s, uid, m):
    u, price = U(uid), num("partner_price")
    if not is_main() or g("partner_on") != "1" or u["is_partner"]: return s.menu(uid)
    if u["balance"] < price: return s.send(uid, f"❌ Balans yetarli emas ({money(u['balance'])} / {money(price)}).")
    run("UPDATE users SET balance=balance-?, is_partner=1 WHERE id=?", (price, uid))
    s.send(uid, "🎉 Siz endi hamkorsiz! «🤖 Mening botim» tugmasini bosing.", main_rows(uid))
    log(f"🤝 Yangi hamkor: {uid}")


@route("🤖 Mening botim")
def r_mybot(s, uid, m):
    if not is_main() or not U(uid)["is_partner"]:
        return s.send(uid, "🤖 Avval «🤝 Hamkorlik» bo'limidan hamkor bo'ling.", main_rows(uid))
    cl = q("SELECT token FROM clones WHERE owner=?", (uid,))
    lst = "\n".join("• @" + (BOTS[c["token"]].username if c["token"] in BOTS else "?") for c in cl) or "—"
    STATE[uid] = ("token",)
    s.send(uid, f"🤖 Botlaringiz:\n{lst}\n\n@BotFather dan olgan yangi bot tokenini yuboring.\n"
                f"⚠️ BotFather → Bot Settings → <b>Business Mode</b> ni yoqing.\n"
                f"Botingizda <b>⚙️ Admin panel</b> faqat sizga ko'rinadi.", [[("🏠 Menyu", "")]])
