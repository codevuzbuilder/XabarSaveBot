"""user.py — foydalanuvchi tugmalari (8 tilda): profil, til, obuna, to'lov, promokod, referal, hamkorlik."""
import time
from core import *
from i18n import *
from ui import *
from pay import *
from ops import *
from texts import *


@route("🏠 Menyu")
def r_home(s, uid, m): s.menu(uid)


@route("✅ A'zo bo'ldim")
def r_joined(s, uid, m): s.menu(uid, tr("joined"))


@route("📲 Botni ulash")
def r_connect(s, uid, m):
    s.send_inline(uid, tr("connect", bot=s.username),
                  [[("inline:connect", "tg://settings/edit", "primary")], [("inline:bot", f"https://t.me/{s.username}", "success")]])


@route("💎 Obuna olish")
def r_plans(s, uid, m):
    u = U(uid)
    lst = "\n".join(tr("plan_line", d=d, price=money(num(f"price_{d}"))) for d in (7, 30, 90, 365))
    s.send(uid, tr("plans", list=lst, bal=money(u["balance"])),
           [[("🛒 7 kun", "success"), ("🛒 30 kun", "success")], [("🛒 90 kun", "success"), ("🛒 365 kun", "success")],
            [("💳 Balans to'ldirish", "primary"), ("🏠 Menyu", "")]])


def _buy(days):
    def f(s, uid, m):
        price, u = num(f"price_{days}"), U(uid)
        if u["balance"] < price:
            return s.send(uid, tr("nobal", bal=money(u["balance"]), price=money(price), btn=lab("💳 Balans to'ldirish")))
        until = max(int(time.time()), u["sub_until"]) + days * 86400
        run("UPDATE users SET balance=balance-?, sub_until=? WHERE id=?", (price, until, uid))
        for ref, x in shares(u, price): notify(ref, tr("ref_bonus", ref, x=money(x)))
        s.send(uid, tr("bought", d=days, until=dt(until)), main_rows(uid))
        log(f"🛒 {uid} — {days} kun ({money(price)} so'm)")
    return f


for _d in (7, 30, 90, 365): ROUTES[f"🛒 {_d} kun"] = _buy(_d)


@route("💳 Balans to'ldirish")
def r_topup(s, uid, m):
    rows = []
    if g("co_on") == "1" and g("co_key"): rows.append([("⚡ Checkout orqali", "success")])
    if g("ip_on") == "1" and g("ip_key"): rows.append([("⚡ InPay orqali", "success")])
    if g("click_on") == "1" and g("click_token"): rows.append([("💳 Click orqali", "success")])
    if g("stars_on") == "1": rows.append([("⭐ Stars orqali", "success")])
    if g("manual_pay") == "1": rows.append([("🧾 Chek bilan to'lov", "primary")])
    if not rows: return s.send(uid, tr("no_methods"), main_rows(uid))
    rows.append([("🏠 Menyu", "")])
    s.send(uid, tr("topup_menu", min=money(num("min_topup")), max=money(num("max_topup"))), rows)


def _ask_amount(method):
    def f(s, uid, m):
        STATE[uid] = ("amt", method)
        s.send(uid, tr("ask_amount"), [[("🏠 Menyu", "")]])
    return f


for _lbl, _meth in (("⚡ Checkout orqali", "checkout"), ("⚡ InPay orqali", "inpay"), ("💳 Click orqali", "click"),
                    ("⭐ Stars orqali", "stars"), ("🧾 Chek bilan to'lov", "receipt")):
    ROUTES[_lbl] = _ask_amount(_meth)


@route("✅ To'lovni tekshirish")
def r_check(s, uid, m):
    ps = q("SELECT * FROM payments WHERE user_id=? AND status='pending' AND method IN ('checkout','inpay')", (uid,))
    if not ps: return s.send(uid, tr("no_pending"), main_rows(uid))
    for p in ps:
        try: check_payment(p)
        except Exception: elog()
    left = q("SELECT COUNT(*) c FROM payments WHERE user_id=? AND status='pending' AND method IN ('checkout','inpay')", (uid,), True)["c"]
    if left: s.send(uid, tr("not_yet"))


@route("👤 Profilim")
def r_profile(s, uid, m):
    u, now = U(uid), time.time()
    act = u["sub_until"] > now
    until = f"{dt(u['sub_until'])} ({tr('days_left', d=int((u['sub_until'] - now) // 86400))})" if act else "—"
    paid = q("SELECT 1 FROM payments WHERE user_id=? AND status='approved' LIMIT 1", (uid,), True)
    cnt = lambda sql: q(sql, (uid,), True)[0]
    ctx.lang = ulang(uid)
    s.send(uid, tr("profile", id=uid, name=esc((u["name"] or "").strip() or "—"), lang_name=dict(LANGS).get(u["lang"], "—"), bal=money(u["balance"]),
                   sub=tr("sub_active" if act else "sub_inactive"), until=until, kind=tr("kind_paid" if paid else "kind_free"),
                   conns=cnt("SELECT COUNT(*) FROM conns WHERE user_id=?"), msgs=cnt("SELECT COUNT(*) FROM msgs WHERE owner=?"),
                   refs=cnt("SELECT COUNT(*) FROM users WHERE referrer=?"),
                   joined=time.strftime("%d.%m.%Y", time.localtime(u["joined"])) if u["joined"] else "—"),
           [[("🌐 Tilni almashtirish", "primary")], [("💳 Balans to'ldirish", "success"), ("🏠 Menyu", "")]])


@route("🌐 Tilni almashtirish")
def r_lang(s, uid, m):
    STATE[uid] = ("lang",)
    ks = [n for _, n in LANGS]
    s.send(uid, tr("lang_pick"), [ks[i:i + 2] for i in range(0, len(ks), 2)] + [[("🏠 Menyu", "")]])


def lang_handle(s, uid, t, st):
    """Til tanlash bosqichi. True — xabar shu yerda ishlatildi."""
    names = {n: c for c, n in LANGS}
    lb = match_label(t, list(names))
    if not lb: return resolve(t) not in ROUTES and (s.send(uid, tr("lang_pick")) or True)
    run("UPDATE users SET lang=? WHERE id=?", (names[lb], uid))
    STATE.pop(uid, None)
    ctx.lang = names[lb]
    s.menu(uid, tr("lang_set"))
    return True


@route("📅 Obunam")
def r_sub(s, uid, m):
    u = U(uid)
    n = q("SELECT COUNT(*) c FROM conns WHERE user_id=?", (uid,), True)["c"]
    st = tr("sub_on", until=dt(u["sub_until"])) if u["sub_until"] > time.time() else tr("sub_off")
    s.send(uid, tr("sub_info", st=st, n=n), main_rows(uid))


@route("🧾 To'lovlarim")
def r_pay_history(s, uid, m):
    ps = q("SELECT * FROM payments WHERE user_id=? ORDER BY id DESC LIMIT 10", (uid,))
    ic = {"approved": "✅", "pending": "⏳", "rejected": "❌", "expired": "⌛", "failed": "⚠️"}
    lst = "\n".join(f"{ic.get(p['status'], '•')} #{p['id']} — {money(p['amount'])} ({time.strftime('%d.%m %H:%M', time.localtime(p['ts']))})" for p in ps) or "—"
    s.send(uid, tr("pay_hist", list=lst), main_rows(uid))


@route("🎁 Promokod")
def r_promo(s, uid, m):
    if g("promo_on") != "1": return s.send(uid, tr("promo_off"), main_rows(uid))
    STATE[uid] = ("promo",)
    s.send(uid, tr("promo_ask"), [[("🏠 Menyu", "")]])


@route("🔗 Referal")
def r_ref(s, uid, m):
    if g("ref_on") != "1": return s.send(uid, "🔗 —", main_rows(uid))
    n = q("SELECT COUNT(*) c FROM users WHERE referrer=?", (uid,), True)["c"]
    rich_key(s, uid, "ref_text", main_rows(uid),
             extra=tr("ref_extra", link=f"https://t.me/{s.username}?start=ref_{uid}", n=n, pct=g("ref_percent")))


@route("🤝 Hamkorlik")
def r_partner(s, uid, m):
    if not is_main() or g("partner_on") != "1": return s.send(uid, "🤝 —", main_rows(uid))
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
    if u["balance"] < price: return s.send(uid, f"❌ {money(u['balance'])} / {money(price)}")
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
