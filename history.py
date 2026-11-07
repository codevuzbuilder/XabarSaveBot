"""history.py — «🕘 Tarixim»: shaxsiy chatni tanlab, shu chatdagi yozishmalarni PDF qilib olish."""
import re, time
from core import *
from ui import *
from i18n import *
import pdfgen

KINDS = {"photo": "rasm", "video": "video", "voice": "ovozli xabar", "video_note": "video xabar",
         "document": "fayl", "audio": "audio", "animation": "GIF", "sticker": "stiker"}


@route("🕘 Tarixim")
def r_hist(s, uid, m):
    rows = q("SELECT chat, MAX(chat_name) AS name, COUNT(*) AS n, MAX(ts) AS last FROM msgs WHERE owner=? "
             "GROUP BY chat ORDER BY last DESC LIMIT 12", (uid,))
    if not rows:
        return s.send(uid, tr("hist_empty"), main_rows(uid))
    labels = {}
    for i, r in enumerate(rows, 1):
        lab = f"👤 {(r['name'] or str(r['chat']))[:22]} ({r['n']})"
        labels[lab if lab not in labels else f"{lab} #{i}"] = r["chat"]
    ks = list(labels)
    STATE[uid] = ("hist", labels)
    s.send(uid, tr("hist_pick"),
           [ks[i:i + 2] for i in range(0, len(ks), 2)] + [[("🏠 Menyu", "")]])


def build_pdf(s, owner, chat):
    rows = list(reversed(q("SELECT * FROM msgs WHERE owner=? AND chat=? ORDER BY ts DESC, mid DESC LIMIT 500", (owner, chat))))
    name = (rows[0]["chat_name"] if rows else None) or str(chat)
    d = pdfgen.Doc()
    d.line(f"Chat tarixi: {name}", 16, "F2")
    d.line(f"Yaratilgan: {time.strftime('%d.%m.%Y %H:%M')}   Xabarlar: {len(rows)}", 9, "F1", (0.4, 0.4, 0.4))
    d.space(8)
    imgs = 0
    for r in rows:
        who = "Siz" if r["mine"] else (r["who"] or "Suhbatdosh")
        head, color = f"{time.strftime('%d.%m.%Y %H:%M', time.localtime(r['ts'] or 0))}   {who}", \
            (0.1, 0.3, 0.7) if r["mine"] else (0.1, 0.1, 0.1)
        if r["deleted"]: head, color = head + "   [O'CHIRILGAN]", (0.8, 0.0, 0.0)
        d.space(3); d.line(head, 9, "F2", color)
        if r["text"]: d.para(r["text"], 10, x=8)
        if r["old_text"]: d.para("(tahrirlangan, avval: " + r["old_text"] + ")", 8, "F3", (0.4, 0.4, 0.4), x=8)
        if r["kind"]:
            note = f"[{KINDS.get(r['kind'], r['kind'])}]"
            if r["kind"] == "photo" and r["fid"] and imgs < 15:
                try: d.image(s.fetch_file(r["fid"]), x=8); imgs += 1; note = None
                except Exception: note += " (rasmni yuklab bo'lmadi)"
            if note: d.line(note, 9, "F3", (0.4, 0.4, 0.4), x=8)
    return d.save(f"Tarix {name}"), name, len(rows)


def history_handle(s, uid, t, st):
    """True — xabar shu yerda ishlatildi; False — oddiy tugma sifatida davom ettiriladi."""
    lab = match_label(t, list(st[1]))
    if not lab:
        return resolve(t) not in ROUTES and (s.send(uid, tr("hist_hint")) or True)
    chat = st[1][lab]
    STATE.pop(uid, None)
    s.send(uid, tr("hist_wait"))
    data, name, n = build_pdf(s, uid, chat)
    fname = "tarix_" + re.sub(r"[^A-Za-z0-9_-]+", "_", pdfgen.clean(name)).strip("_") + ".pdf"
    s.upload("sendDocument", "document", fname, data, chat_id=uid, caption=f"🕘 {pdfgen.clean(name)} — {n} ta xabar")
    s.send(uid, tr("hist_done"), main_rows(uid))
    return True
