"""rich.py — matnlar + media (rasm/video/dumaloq video): tahrirlash, yuborish, bir nechta qo'llanma."""
import html
from core import *
from ui import *

REMOVE = ("media-o'chirish", "media o'chirish", "media-ochirish", "media ochirish")
_TAGS = {"bold": ("<b>", "</b>"), "italic": ("<i>", "</i>"), "underline": ("<u>", "</u>"),
         "strikethrough": ("<s>", "</s>"), "spoiler": ("<tg-spoiler>", "</tg-spoiler>"),
         "code": ("<code>", "</code>"), "pre": ("<pre>", "</pre>"), "blockquote": ("<blockquote>", "</blockquote>")}


def to_html(text, entities):
    """Telegram formatlash (qalin, kursiv, havola...) ni HTML ga o'tkazadi. Offsetlar UTF-16 birliklarida."""
    if not entities: return html.escape(text, quote=False)
    opens, closes = {}, {}
    for e in entities:
        t = e.get("type")
        if t in _TAGS: o, c = _TAGS[t]
        elif t == "text_link" and e.get("url"): o, c = f'<a href="{html.escape(e["url"], quote=True)}">', "</a>"
        else: continue
        a, b = e["offset"], e["offset"] + e["length"]
        opens.setdefault(a, []).append((b, o)); closes.setdefault(b, []).append((a, c))
    out, pos = [], 0

    def flush(p):
        for _, c in sorted(closes.get(p, []), key=lambda x: -x[0]): out.append(c)
        for _, o in sorted(opens.get(p, []), key=lambda x: -x[0]): out.append(o)
    for ch in text:
        flush(pos); out.append(html.escape(ch, quote=False)); pos += 2 if ord(ch) > 0xFFFF else 1
    flush(pos)
    return "".join(out)


def parse_msg(m):
    """Xabardan (HTML matn, media turi, file_id) ni ajratadi."""
    mt = fid = None
    if m.get("photo"): mt, fid = "photo", m["photo"][-1]["file_id"]
    elif m.get("video"): mt, fid = "video", m["video"]["file_id"]
    elif m.get("video_note"): mt, fid = "video_note", m["video_note"]["file_id"]
    elif m.get("animation"): mt, fid = "animation", m["animation"]["file_id"]
    elif m.get("voice"): mt, fid = "voice", m["voice"]["file_id"]
    raw = m.get("text") or m.get("caption") or ""
    return (to_html(raw, m.get("entities") or m.get("caption_entities") or []) if raw else ""), mt, fid


def send_rich(s, uid, text, mtype=None, fid=None, rows=None):
    """Matnni (ixtiyoriy media bilan) yuboradi. Klaviatura oxirgi xabarga biriktiriladi; media yuborilmasa matn yuboriladi."""
    text = text or ""
    if mtype and fid:
        if mtype == "video_note" or not text or len(text) > 1000:
            if s.send_media(uid, mtype, fid, None, None if text else rows) is not None:
                if text: s.send(uid, text, rows)
                return
        elif s.send_media(uid, mtype, fid, text, rows) is not None: return
    s.send(uid, text or "—", rows)


def rich_key(s, uid, key, rows=None, extra=""):
    m = q("SELECT mtype, fid FROM rich_media WHERE k=?", (key,), True)
    send_rich(s, uid, g(key) + extra, m["mtype"] if m else None, m["fid"] if m else None, rows)


def rich_start(s, uid, kind, key="", label=""):
    if kind == "rt":
        STATE[uid] = ("rt", key, label)
        s.send(uid, f"✏️ <b>{esc(label)}</b>\n\n• Yangi <b>matn</b> yuboring (qalin, kursiv, havola formatlari saqlanadi).\n"
                    f"• <b>Rasm / video / dumaloq video / ovozli xabar</b> qo'shish: shu turdagi xabarni yuboring (matn — izoh sifatida).\n"
                    f"• Mediani olib tashlash: <code>media-o'chirish</code>\n\nHozirgi matn:\n{g(key)}")
    else:
        STATE[uid] = ("gnew1",)
        s.send(uid, "➕ <b>Yangi qo'llanma</b>\n1/2 — qo'llanma <b>sarlavhasini</b> yozing (tugma nomi bo'ladi):")


def rich_state(s, uid, st, m):
    k, raw = st[0], (m.get("text") or "").strip().lower()
    text, mt, fid = parse_msg(m)
    if k == "gnew1":
        title = (m.get("text") or "").strip()
        if not title or len(title) > 40: return s.send(uid, "❌ Sarlavha 1–40 belgi bo'lsin. Qayta yozing:")
        STATE[uid] = ("gnew2", title)
        return s.send(uid, f"✅ Sarlavha: <b>{esc(title)}</b>\n2/2 — qo'llanma <b>matnini</b> yuboring. Rasm/video/dumaloq video/ovozli xabar ham "
                           f"qo'shsangiz bo'ladi (matn — izoh sifatida).")
    if k in ("rt", "ge") and raw in REMOVE:
        if k == "rt": run("DELETE FROM rich_media WHERE k=?", (st[1],))
        else: run("UPDATE guides SET mtype=NULL, fid=NULL WHERE id=?", (st[1],))
        STATE.pop(uid, None)
        return s.send(uid, "✅ Media olib tashlandi.")
    if not text and not mt: return s.send(uid, "❌ Matn yoki rasm/video yuboring.")
    if k == "gnew2":
        gid = ins("INSERT INTO guides(title,text,mtype,fid) VALUES(?,?,?,?)", (st[1], text, mt, fid))
        STATE.pop(uid, None)
        s.send(uid, f"✅ Qo'llanma #{gid} qo'shildi. Foydalanuvchiga shunday ko'rinadi:")
        return send_rich(s, uid, text, mt, fid)
    if k == "ge":
        gid = st[1]
        if text: run("UPDATE guides SET text=? WHERE id=?", (text, gid))
        if mt: run("UPDATE guides SET mtype=?, fid=? WHERE id=?", (mt, fid, gid))
        r = q("SELECT * FROM guides WHERE id=?", (gid,), True)
        STATE.pop(uid, None)
        s.send(uid, "✅ Qo'llanma yangilandi. Ko'rinishi:")
        return send_rich(s, uid, r["text"], r["mtype"], r["fid"])
    if k == "rt":
        key = st[1]
        if text: setv(key, text)
        if mt: run("INSERT OR REPLACE INTO rich_media VALUES(?,?,?)", (key, mt, fid))
        STATE.pop(uid, None)
        s.send(uid, "✅ Saqlandi. Foydalanuvchiga shunday ko'rinadi:")
        return rich_key(s, uid, key)


# ----------------------------- qo'llanmalar (bir nechta) -----------------------------
def f_guides(s, uid):
    return "📋 Qo'llanmalar (asosiy qo'llanmadan tashqari):\n" + ("\n".join(
        f"• #{r['id']} {esc(r['title'])}" + (f" [{r['mtype']}]" if r["mtype"] else "") for r in q("SELECT * FROM guides ORDER BY id")) or "—")


def op_gedit(s, a, raw):
    r = q("SELECT * FROM guides WHERE id=?", (int(a[0]),), True)
    if not r: raise ValueError
    return ("state", ("ge", r["id"]), f"✏️ Qo'llanma #{r['id']} «{esc(r['title'])}»\nYangi matn yoki rasm/video yuboring "
                                      f"(mediani olib tashlash: <code>media-o'chirish</code>).\n\nHozirgi matn:\n{r['text']}")


def op_gdel(s, a, raw):
    if not run("DELETE FROM guides WHERE id=?", (int(a[0]),)): raise ValueError
    return "🗑 Qo'llanma o'chirildi."


@route("📖 Qo'llanma")
def r_guide(s, uid, m):
    gs = q("SELECT id, title FROM guides ORDER BY id")
    if not gs: return rich_key(s, uid, "guide_text", main_rows(uid))
    labels = {}
    for r in gs:
        lab = f"📘 {r['title'][:28]}"
        labels[lab if lab not in labels else f"{lab} #{r['id']}"] = r["id"]
    ks = list(labels)
    STATE[uid] = ("guides", labels)
    rich_key(s, uid, "guide_text", [ks[i:i + 2] for i in range(0, len(ks), 2)] + [[("🏠 Menyu", "")]])


def guides_handle(s, uid, t, st):
    """True — xabar shu yerda ishlatildi (tanlangan qo'llanma yuborildi)."""
    lab = match_label(t, list(st[1]))
    if not lab: return False
    r = q("SELECT * FROM guides WHERE id=?", (st[1][lab],), True)
    if not r: return False
    ks = list(st[1])
    send_rich(s, uid, r["text"], r["mtype"], r["fid"], [ks[i:i + 2] for i in range(0, len(ks), 2)] + [[("🏠 Menyu", "")]])
    return True
