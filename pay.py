"""pay.py — Checkout.uz, InPay, Click, Telegram Stars, avto-to'lov ustalari va fon vazifalari."""
import os, re, time, json, math, sqlite3
import requests
from core import *
from i18n import *


class GwError(Exception):
    pass


def _pick(d, keys):
    if isinstance(d, dict):
        for k in keys:
            if d.get(k) not in (None, ""): return d[k]


# ----------------------------- Checkout.uz ("co") va InPay ("ip") -----------------------------
NAMES = {"co": "Checkout.uz", "ip": "InPay"}
METHOD = {"co": "checkout", "ip": "inpay"}


def gw_req(p, method, path, payload=None, headers=None):
    """Umumiy so'rov. Xatoda manzil, HTTP kod va javob matni xabarda bo'ladi (admin tekshira oladi)."""
    url, key = g(p + "_base").rstrip("/") + path, g(p + "_key")
    body = json.dumps(payload, separators=(",", ":")) if payload is not None else ""
    h = {"Content-Type": "application/json", "Accept": "application/json", "Authorization": "Bearer " + key}
    if p == "co": h["X-API-KEY"] = key
    h.update(headers or {})
    try: r = requests.request(method, url, data=body or None, headers=h, timeout=30)
    except requests.RequestException as e: raise GwError(f"{method} {url} → ulanish xatosi: {e}")
    try: j = r.json()
    except ValueError: j = None
    if r.status_code >= 400: raise GwError(f"{method} {url} → HTTP {r.status_code}: {(r.text or '')[:160]}")
    if not isinstance(j, dict): return {"value": j}
    for k in ("data", "result"):
        if isinstance(j.get(k), dict): return j[k]
    return j


def gw_create(p, pid, amount):
    if p == "co":
        j = gw_req("co", "POST", g("co_p_create"), {"amount": int(amount), "description": "Balans to'ldirish",
                   "expire_time": int(num("tc_ttl")) * 60}, {"Idempotency-Key": f"{cur().t.split(':')[0]}-topup-{pid}"})
    else:
        mid = g("ip_merchant")
        j = gw_req("ip", "POST", g("ip_p_create"), {"merchant_id": int(mid) if mid.isdigit() else mid,
                   "amount": int(amount), "order_id": str(pid)})
    url = _pick(j, ("pay_url", "payment_url", "url", "link", "checkout_url", "payment_link"))
    if not url or not str(url).startswith("http"): raise GwError("to'lov havolasi kelmadi: " + str(j)[:160])
    return str(_pick(j, ("order_id", "id", "uuid", "payment_id")) or pid), url


def gw_state(p, pay):
    j = gw_req(p, "GET", g(p + "_p_status").format(id=pay["ext_id"]))
    st = str(_pick(j, ("status", "state")) or "").lower()
    if st in ("paid", "success", "succeeded", "completed", "done", "approved") or j.get("paid") is True: return "paid"
    if st in ("expired", "canceled", "cancelled", "failed", "rejected"): return "failed"
    return "pending"


def gw_diag(p):
    """Ulanishni tekshiradi: har bir so'rovning HTTP kodi va javobi ko'rsatiladi."""
    lines, codes = [f"🌐 {g(p + '_base')}"], []
    paths = [g("co_p_balance"), "/me"] if p == "co" else [g("ip_p_status").format(id="0000000000000000")]
    for path in paths:
        try:
            gw_req(p, "GET", path); lines.append(f"✅ {path} — 200"); codes.append(200)
        except GwError as e:
            m = re.search(r"HTTP (\d+)", str(e)); codes.append(int(m.group(1)) if m else 0)
            lines.append(f"❌ {path} — {str(e).split('→')[-1].strip()[:150]}")
    hint = ""
    if codes and all(c == 404 for c in codes): hint = "\n\n💡 404 — manzil yoki yo'l noto'g'ri bo'lishi mumkin (InPay'da mavjud bo'lmagan buyurtma ham 404 beradi). Hujjatdagi yo'llarni «🔗 … yo'li» tugmalari bilan kiriting."
    elif any(c in (401, 403) for c in codes): hint = "\n\n💡 401/403 — API kalit (token) noto'g'ri."
    elif 200 in codes: hint = "\n\n✅ Kalit qabul qilindi."
    return "\n".join(lines) + hint


def credit(pid):
    if not run("UPDATE payments SET status='approved' WHERE id=? AND status='pending'", (pid,)): return False
    p = q("SELECT * FROM payments WHERE id=?", (pid,), True)
    add = p["amount"] * (1 + num("topup_bonus") / 100)
    run("UPDATE users SET balance=balance+? WHERE id=?", (add, p["user_id"]))
    notify(p["user_id"], tr("credited", p["user_id"], sum=money(add)))
    log(f"💵 To'lov #{pid}: {p['user_id']} — {money(p['amount'])} so'm ({p['method']})")
    return True


def check_payment(p):
    pre = "co" if p["method"] == "checkout" else "ip"
    st = gw_state(pre, p)
    if st == "paid": credit(p["id"])
    elif st == "failed" or time.time() - p["ts"] > num("tc_ttl") * 60:
        if run("UPDATE payments SET status='expired' WHERE id=? AND status='pending'", (p["id"],)):
            notify(p["user_id"], tr("expired", p["user_id"], pid=p["id"]))


# ----------------------------- Click (BotFather → Payments → Click) va Telegram Stars -----------------------------
def click_invoice(s, uid, amt):
    pid = ins("INSERT INTO payments(user_id,kind,amount,via,method,ts) VALUES(?,?,?,?,?,?)",
              (uid, "topup", amt, s.t, "click", int(time.time())))
    r = s.call("sendInvoice", chat_id=uid, title="Balans to'ldirish", description=f"{money(amt)} so'm",
               payload=f"topup:{pid}", provider_token=g("click_token"), currency="UZS",
               prices=[{"label": "Balans", "amount": int(amt) * 100}])
    if r is None:
        run("UPDATE payments SET status='failed' WHERE id=?", (pid,))
        s.send(s.owner, f"⚠️ Click xatosi: {esc(s.err)}")
        return False
    return True


def stars_for(amt): return max(1, math.ceil(amt / max(num("star_rate"), 1)))


def stars_invoice(s, uid, amt):
    """Telegram Stars (XTR): provider token kerak emas. Stars soni = so'm / kurs (yuqoriga yaxlitlanadi)."""
    n = stars_for(amt)
    pid = ins("INSERT INTO payments(user_id,kind,amount,via,method,ext_id,ts) VALUES(?,?,?,?,?,?,?)",
              (uid, "topup", amt, s.t, "stars", str(n), int(time.time())))
    r = s.call("sendInvoice", chat_id=uid, title="Balans to'ldirish", description=f"{money(amt)} so'm — ⭐ {n} Stars",
               payload=f"topup:{pid}", currency="XTR", prices=[{"label": "Balans", "amount": n}])
    if r is None:
        run("UPDATE payments SET status='failed' WHERE id=?", (pid,))
        s.send(s.owner, f"⚠️ Stars xatosi: {esc(s.err)}")
        return 0
    return n


def _paid_ok(p, currency, total):
    if not p or p["status"] != "pending": return False
    if p["method"] == "click": return currency == "UZS" and total == int(p["amount"]) * 100
    if p["method"] == "stars": return currency == "XTR" and total == int(p["ext_id"] or 0)
    return False


def _payment_of(payload):
    m = re.match(r"topup:(\d+)$", payload or "")
    return q("SELECT * FROM payments WHERE id=?", (int(m.group(1)),), True) if m else None


def pre_checkout(s, pq):
    ok = _paid_ok(_payment_of(pq.get("invoice_payload")), pq.get("currency"), pq.get("total_amount"))
    args = {"pre_checkout_query_id": pq["id"], "ok": ok}
    if not ok: args["error_message"] = "To'lov topilmadi yoki muddati o'tgan. Qaytadan urinib ko'ring."
    s.call("answerPreCheckoutQuery", **args)


def successful_payment(s, m):
    sp = m["successful_payment"]
    p = _payment_of(sp.get("invoice_payload"))
    if _paid_ok(p, sp.get("currency"), sp.get("total_amount")): credit(p["id"])
    elif not (p and p["status"] == "approved"):
        s.send(s.owner, f"⚠️ Mos kelmagan to'lov keldi: {esc(sp)}")


# ----------------------------- avto to'lov ulash ustalari -----------------------------
WIZ_BACK = [[("⬅️ Admin panel", "primary")]]


def wizard_start(s, uid, kind):
    if kind == "co":
        STATE[uid] = ("wiz", "co")
        s.send(uid, "⚡ <b>Checkout.uz ulash</b>\ncheckout.uz kabinetidagi <b>API kalit</b>ni kiriting:", WIZ_BACK)
    elif kind == "ip":
        STATE[uid] = ("wiz", "ip1")
        s.send(uid, "⚡ <b>InPay ulash</b>\n1/2 — <b>Merchant ID</b> ni kiriting:", WIZ_BACK)
    else:
        STATE[uid] = ("wiz", "click")
        s.send(uid, "💳 <b>Click ulash</b>\n@BotFather → /mybots → botingiz → <b>Payments</b> → <b>Click</b> ni ulang "
                    "va berilgan <b>provider token</b>ni shu yerga yuboring:", WIZ_BACK)


def wizard_step(s, uid, st, m):
    t = (m.get("text") or "").strip()
    s.call("deleteMessage", chat_id=uid, message_id=m["message_id"])     # maxfiy kalit chatda qolmasin
    if st[1] == "co":
        setv("co_key", t); setv("co_on", "1"); STATE.pop(uid, None)
        return s.send(uid, "✅ <b>Checkout.uz yoqildi!</b>\n\n" + gw_diag("co"))
    if st[1] == "ip1":
        setv("ip_merchant", t); STATE[uid] = ("wiz", "ip2")
        return s.send(uid, "✅ Merchant ID saqlandi.\n2/2 — <b>API token</b> (Bearer) ni kiriting:", WIZ_BACK)
    if st[1] == "ip2":
        setv("ip_key", t); setv("ip_on", "1"); STATE.pop(uid, None)
        return s.send(uid, "✅ <b>InPay yoqildi!</b>\n\n" + gw_diag("ip"))
    if st[1] == "click":
        r = s.call("createInvoiceLink", title="Test", description="Test", payload="test", provider_token=t,
                   currency="UZS", prices=[{"label": "Test", "amount": 100000}])
        STATE.pop(uid, None)
        if r is None: return s.send(uid, f"❌ Token qabul qilinmadi: {esc(s.err)}")
        setv("click_token", t); setv("click_on", "1")
        return s.send(uid, "✅ <b>Click ulandi va yoqildi!</b> Endi foydalanuvchilar «💳 Click orqali» tugmasini ko'radi.")


# ----------------------------- fon vazifalari -----------------------------
def poller():
    while True:
        time.sleep(15)
        for b in list(BOTS.values()):
            try:
                with using(b):
                    for p in q("SELECT * FROM payments WHERE status='pending' AND method IN ('checkout','inpay')"):
                        try:
                            if g(("co" if p["method"] == "checkout" else "ip") + "_key"): check_payment(p)
                        except Exception: elog()
            except Exception: elog()


def backup_to_admin(b, chat=None):
    """Shu bot bazasining zaxira nusxasini uning egasiga yuboradi."""
    dst = sqlite3.connect("backup_tmp.db")
    with b.lock: b.con.backup(dst)
    dst.close()
    with open("backup_tmp.db", "rb") as f: data = f.read()
    os.remove("backup_tmp.db")
    b.upload("sendDocument", "document", "bot_backup.db", data, chat_id=chat or b.owner,
             caption=time.strftime("💾 Zaxira %d.%m.%Y %H:%M"), disable_notification="true")


def cleaner():
    hours = 0
    while True:
        for b in list(BOTS.values()):
            try:
                with using(b):
                    run("DELETE FROM msgs WHERE ts<?", (int(time.time() - num("cache_days") * 86400),))
                    n = int(os.getenv("BACKUP_HOURS", "0") or 0)     # 0 = o'chiq
                    if n and hours and hours % n == 0: backup_to_admin(b)
            except Exception: elog()
        hours += 1
        time.sleep(3600)
