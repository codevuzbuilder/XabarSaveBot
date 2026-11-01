"""bot.py — Telegram bot (ishga tushirish: python bot.py). Barcha .py fayllar bir papkada turishi kerak."""
import os, re, sys, time, threading
import requests
from core import *
from ui import *
from pay import *
from ops import *
import user, buttons
from biz import BizMixin
from design import design_handle
from history import history_handle

UPDATES = ["message", "business_connection", "business_message", "edited_business_message",
           "deleted_business_messages", "pre_checkout_query"]
DZ_STATES = ("dzarea", "dz", "dzname", "dzemoji")


class Bot(BizMixin):
    """Bitta bot = bitta tenant: o'z bazasi, sozlamalari, foydalanuvchilari va admin paneli bor."""

    def __init__(s, token, partner=None):
        s.setup(token, partner)
        me = s.call("getMe") or {}
        s.username, s.biz = me.get("username", "bot"), bool(me.get("can_connect_to_business"))
        if s.code != 401: s.open()

    def setup(s, token, partner=None):
        s.t, s.partner, s.alive, s.err, s.code = token, partner, True, "", None
        s.owner = ADMIN_ID if token == TOKEN else partner
        s.api = f"https://api.telegram.org/bot{token}/"
        s.db_path = DB_FILE if token == TOKEN else os.path.join(os.path.dirname(DB_FILE) or ".", f"clone_{token.split(':')[0]}.db")
        s.lock, s.emap, s.noicons = threading.RLock(), {}, False

    def open(s): s.con = open_db(s.db_path)

    def call(s, method, **p):
        s.code = None
        try:
            r = requests.post(s.api + method, json=p, timeout=60).json()
            if r.get("ok"): return r["result"]
            s.err, s.code = str(r.get("description")), r.get("error_code")
            print(method, r)
        except Exception as e:
            s.err = str(e)
            print(method, e)

    def upload(s, method, field, name, data, **p):
        try:
            r = requests.post(s.api + method, data=p, files={field: (name, data)}, timeout=120).json()
            if r.get("ok"): return r["result"]
            s.err = str(r.get("description"))
            print(method, r)
        except Exception: elog()

    def fetch_file(s, fid):
        f = s.call("getFile", file_id=fid)
        if f: return requests.get(f"https://api.telegram.org/file/bot{s.t}/{f['file_path']}", timeout=60).content

    def _icon_err(s): return any(w in s.err.lower() for w in ("icon", "emoji", "button"))

    def send(s, chat, text, rows=None):
        p = dict(chat_id=chat, text=text[:4000], parse_mode="HTML")
        with using(s):
            if rows: p["reply_markup"] = kb(rows)
            r = s.call("sendMessage", **p)
            if r is None and "parse entities" in s.err:
                p.pop("parse_mode"); r = s.call("sendMessage", **p)
            if r is None and rows and not s.noicons and s._icon_err():
                s.noicons = True; p["reply_markup"] = kb(rows); r = s.call("sendMessage", **p)
        return r

    def send_inline(s, chat, text, rows):
        """Inline (havolali) tugmalar. tg:// havola qabul qilinmasa, faqat https havolalar bilan qayta urinadi."""
        p = dict(chat_id=chat, text=text[:4000], parse_mode="HTML")
        with using(s):
            p["reply_markup"] = ikb(rows)
            r = s.call("sendMessage", **p)
            if r is None and not s.noicons and s._icon_err():
                s.noicons = True; p["reply_markup"] = ikb(rows); r = s.call("sendMessage", **p)
            if r is None:
                web = [[b for b in row if b[1].startswith("http")] for row in rows]
                web = [x for x in web if x]
                if web: p["reply_markup"] = ikb(web)
                else: p.pop("reply_markup")
                r = s.call("sendMessage", **p)
        return r

    def run(s):
        off = 0
        while s.alive:
            ups = s.call("getUpdates", offset=off, timeout=30, allowed_updates=UPDATES)
            if ups is None:
                if s.code == 401: return s.dead()
                time.sleep(3); continue
            for u in ups:
                off = u["update_id"] + 1
                try: s.handle(u)
                except Exception: elog()

    def dead(s):
        """Token yaroqsiz (401) bo'lsa botni to'xtatadi va klonni asosiy bazadan o'chiradi."""
        s.alive = False
        BOTS.pop(s.t, None)
        print("Bot to'xtatildi (token yaroqsiz):", s.t.split(":")[0])
        if s.t != TOKEN:
            with using(main_bot()):
                run("DELETE FROM clones WHERE token=?", (s.t,))
                if s.partner: main_bot().send(s.partner, "⚠️ Botingiz tokeni yaroqsiz (bekor qilingan), bot to'xtatildi. Yangi token bilan qayta qo'shing.")
                main_bot().send(ADMIN_ID, f"⚠️ Klon bot (hamkor {s.partner}) tokeni yaroqsiz — o'chirildi.")

    def handle(s, u):
        with using(s):
            if "business_connection" in u: return s.conn(u["business_connection"])
            if "business_message" in u: return s.bmsg(u["business_message"])
            if "edited_business_message" in u: return s.bedit(u["edited_business_message"])
            if "deleted_business_messages" in u: return s.bdel(u["deleted_business_messages"])
            if "pre_checkout_query" in u: return pre_checkout(s, u["pre_checkout_query"])
            if "message" in u: return s.msg(u["message"])

    # ---------- Suhbat ----------
    def menu(s, uid, text="🏠 Bosh menyu"):
        STATE.pop(uid, None)
        s.send(uid, text, main_rows(uid))

    def gate_msg(s, uid, chans):
        rows = [[(f"📢 {c['title'][:28]}", channel_link(c), "primary")] for c in chans if channel_link(c)]
        text = "📢 Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:\n" + "\n".join(f"• {esc(c['title'])}" for c in chans)
        if rows: s.send_inline(uid, text, rows)
        else: s.send(uid, text)
        s.send(uid, "A'zo bo'lgach pastdagi tugmani bosing 👇", [[("✅ A'zo bo'ldim", "success")]])

    def msg(s, m):
        if m["chat"]["type"] != "private": return
        if "successful_payment" in m: return successful_payment(s, m)
        uid, t0 = m["from"]["id"], (m.get("text") or "").strip()
        if not is_admin(uid) and g("bot_on") != "1":
            return s.send(uid, "🔧 Bot vaqtincha o'chirilgan. Keyinroq urinib ko'ring.")
        ref = int(t0[11:]) if t0.startswith("/start ref_") and t0[11:].isdigit() else None
        new = reg(uid, ref)
        if new is None: return s.send(uid, "🔒 Hozircha ro'yxatdan o'tish yopiq.")
        if U(uid)["banned"]: return s.send(uid, "🚫 Siz bloklangansiz.")
        if new and g("notify_admin_new") == "1" and uid != s.owner:
            s.send(s.owner, f"🆕 Yangi foydalanuvchi: <code>{uid}</code> ({esc(m['from'].get('first_name'))})")
        chans = unsub(s, uid)
        if chans: return s.gate_msg(uid, chans)
        if t0.startswith("/start"):
            if new and g("trial_on") == "1" and num("trial_days") > 0:
                s.send(uid, f"🎁 Sizga <b>{int(num('trial_days'))} kun bepul</b> foydalanish berildi!")
            return s.menu(uid, g("welcome_text"))
        st = STATE.get(uid)
        if st and st[0] in DZ_STATES and is_admin(uid) and design_handle(s, uid, t0, m, st): return
        if st and st[0] == "hist" and history_handle(s, uid, t0, st): return
        mt = re.match(r"/(ok|no)_(\d+)$", t0)
        if mt and is_admin(uid): return s.receipt_decision(uid, mt.group(1), int(mt.group(2)))
        t = resolve(t0)
        if t in ROUTES:
            STATE.pop(uid, None)
            return ROUTES[t](s, uid, m)
        if st: return s.state(uid, st, m)
        s.menu(uid)

    def receipt_decision(s, uid, act, pid):
        p = q("SELECT * FROM payments WHERE id=? AND method='receipt'", (pid,), True)
        if not p or p["status"] != "pending": return s.send(uid, "ℹ️ Bu to'lov allaqachon ko'rib chiqilgan.")
        if act == "ok":
            credit(pid); s.send(uid, f"✅ #{pid} tasdiqlandi.")
        else:
            run("UPDATE payments SET status='rejected' WHERE id=?", (pid,))
            notify(p["user_id"], f"❌ To'lov #{pid} rad etildi.")
            s.send(uid, f"❌ #{pid} rad etildi.")

    def state(s, uid, st, m):
        t, k = (m.get("text") or "").strip(), st[0]
        back = [[("🏠 Menyu", "")]]
        if k == "amt":
            digits = re.sub(r"\D", "", t)
            if not digits: return s.send(uid, "❌ Summani raqam bilan yuboring.", back)
            amt = int(digits)
            if amt < num("min_topup") or amt > num("max_topup"):
                return s.send(uid, f"❌ Summa {money(num('min_topup'))} dan {money(num('max_topup'))} gacha bo'lsin.", back)
            if st[1] == "receipt":
                STATE[uid] = ("receipt", amt)
                return s.send(uid, f"{esc(g('pay_info'))}\n\n💵 {money(amt)} so'm o'tkazing va <b>chek rasmini</b> yuboring.", back)
            if st[1] == "click":
                STATE.pop(uid, None)
                if click_invoice(s, uid, amt): s.send(uid, "💳 Hisob-fakturani to'lang. To'lovdan so'ng balans avtomatik to'ldiriladi.", main_rows(uid))
                else: s.send(uid, "⚠️ Click vaqtincha ishlamayapti. Boshqa usulni tanlang.", main_rows(uid))
                return
            pid = ins("INSERT INTO payments(user_id,kind,amount,via,method,ts) VALUES(?,?,?,?,?,?)",
                      (uid, "topup", amt, s.t, "tc", int(time.time())))
            try:
                ext, url = tc_create(pid, amt)
                run("UPDATE payments SET ext_id=?, url=? WHERE id=?", (ext, url, pid))
                STATE.pop(uid, None)
                s.send(uid, f"⚡ <b>To'lov #{pid}</b>\n💵 {money(amt)} so'm\n⏱ {int(num('tc_ttl'))} daqiqa ichida to'lang:\n{url}\n\n"
                            f"To'lovdan so'ng hisob avtomatik to'ldiriladi.", [[("✅ To'lovni tekshirish", "success")], [("🏠 Menyu", "")]])
            except Exception as e:
                elog(); run("UPDATE payments SET status='failed' WHERE id=?", (pid,))
                s.send(uid, "⚠️ To'lov tizimi vaqtincha ishlamayapti. Keyinroq urinib ko'ring.", main_rows(uid))
                s.send(s.owner, f"⚠️ Tezcheck xatosi: {esc(e)}")
        elif k == "receipt":
            if not m.get("photo"): return s.send(uid, "🧾 Chek rasmini yuboring.", back)
            amt = st[1]
            pid = ins("INSERT INTO payments(user_id,kind,amount,via,method,ts) VALUES(?,?,?,?,?,?)",
                      (uid, "topup", amt, s.t, "receipt", int(time.time())))
            s.call("sendPhoto", chat_id=s.owner, photo=m["photo"][-1]["file_id"],
                   caption=f"🧾 To'lov #{pid}\n👤 {uid}\n💵 {money(amt)} so'm\n\n✅ /ok_{pid}\n❌ /no_{pid}")
            STATE.pop(uid, None)
            s.send(uid, "✅ Chek adminga yuborildi. Tasdiqlangach xabar keladi.", main_rows(uid))
        elif k == "promo":
            STATE.pop(uid, None)
            s.send(uid, redeem(uid, t.upper()), main_rows(uid))
        elif k == "token" and is_main():
            s.call("deleteMessage", chat_id=uid, message_id=m["message_id"])
            try: me = requests.get(f"https://api.telegram.org/bot{t}/getMe", timeout=20).json()
            except Exception: me = {}
            if not me.get("ok"): return s.send(uid, "❌ Token noto'g'ri. Qayta yuboring.", back)
            if q("SELECT 1 FROM clones WHERE token=?", (t,), True) or t == TOKEN:
                return s.send(uid, "❌ Bu token allaqachon ishlatilgan.", back)
            run("INSERT INTO clones VALUES(?,?)", (t, uid))
            nb = start(t, uid)
            STATE.pop(uid, None)
            warn = "" if nb.biz else "\n\n⚠️ Bu botda <b>Business Mode</b> yoqilmagan: @BotFather → Bot Settings → Business Mode."
            s.send(uid, f"✅ @{nb.username} ishga tushdi! U yerga kirib /start bosing — <b>⚙️ Admin panel</b> faqat sizga ko'rinadi.{warn}", main_rows(uid))
        elif k == "set" and is_admin(uid):
            key = st[1]
            if key in NUM:
                t = t.replace(" ", "")
                try: float(t)
                except ValueError: return s.send(uid, "❌ Faqat raqam yuboring.")
            setv(key, t)
            if key in ("tc_key", "tc_kassa", "click_token"): s.call("deleteMessage", chat_id=uid, message_id=m["message_id"])
            STATE.pop(uid, None)
            s.send(uid, f"✅ {esc(st[2])} yangilandi.")
        elif k == "op" and is_admin(uid):
            try: out = OPS[st[1]](s, t.split(), t)
            except (ValueError, IndexError): return s.send(uid, f"❌ Format noto'g'ri.\n{st[3]}")
            STATE.pop(uid, None)
            s.send(uid, out)
        elif k == "bc" and is_admin(uid):
            STATE.pop(uid, None)
            broadcast(s, uid, st[1], t)
        elif k == "wiz" and is_admin(uid):
            wizard_step(s, uid, st, m)
        else:
            s.menu(uid)


def start(token, partner):
    b = Bot(token, partner)
    if b.code == 401:
        with using(main_bot()): run("DELETE FROM clones WHERE token=?", (token,))
        print("Yaroqsiz klon token o'chirildi:", token.split(":")[0])
        return b
    BOTS[token] = b
    load_emoji(b)
    threading.Thread(target=b.run, daemon=True).start()
    return b


BIZ_WARN = ("⚠️ Bu botda <b>Business Mode</b> yoqilmagan — akkauntga ulashda «yaroqsiz» deydi.\n"
            "@BotFather → /mybots → bot → Bot Settings → Business Mode → Turn on.")

if __name__ == "__main__":
    BOTS[TOKEN] = main = Bot(TOKEN)
    if main.code == 401: sys.exit("❌ Asosiy bot tokeni yaroqsiz. BOT_TOKEN ni tekshiring.")
    n = load_emoji(main)
    print("Bot: @" + main.username, "| Business Mode:", "YOQILGAN" if main.biz else "O'CHIQ!", "| premium emoji:", n)
    if not main.biz:
        print(BIZ_WARN.replace("<b>", "").replace("</b>", ""))
        main.send(ADMIN_ID, BIZ_WARN)
    with using(main): clones = q("SELECT * FROM clones")
    for r in clones: start(r["token"], r["owner"])
    threading.Thread(target=poller, daemon=True).start()
    threading.Thread(target=cleaner, daemon=True).start()
    main.run()
