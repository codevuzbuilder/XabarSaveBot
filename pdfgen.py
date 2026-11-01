"""pdfgen.py — kutubxonasiz oddiy PDF yozuvchi: matn (Helvetica) va JPEG rasm. Kirill harflari lotinga o'giriladi."""
import zlib, struct

_C = dict(zip("абвгдезийклмнопрстуфхъыьэ", ["a", "b", "v", "g", "d", "e", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s",
                                          "t", "u", "f", "x", "'", "i", "", "e"]))
_C.update({"ё": "yo", "ж": "j", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ю": "yu", "я": "ya", "ў": "o'", "қ": "q",
           "ғ": "g'", "ҳ": "h"})
_PUNCT = {"ʻ": "'", "ʼ": "'", "‘": "'", "’": "'", "`": "'", "´": "'", "“": '"', "”": '"', "«": '"', "»": '"',
          "–": "-", "—": "-", "…": "...", "\u00a0": " ", "\t": " "}


def clean(s):
    """PDF (Helvetica/WinAnsi) uchun matnni tozalaydi: kirill→lotin, emoji va noma'lum belgilar olib tashlanadi."""
    out = []
    for ch in str(s or ""):
        low = ch.lower()
        if ch in _PUNCT: out.append(_PUNCT[ch])
        elif low in _C: out.append(_C[low].capitalize() if ch != low else _C[low])
        elif ch == "\n": out.append("\n")
        else:
            try: ch.encode("cp1252"); out.append(ch)
            except UnicodeEncodeError: pass
    return "".join(out)


def _cw(ch):
    if ch == " ": return .278
    if ch in "il.,;:'!|jI[]()ft": return .28
    if ch in "mwMW@%": return .85
    if ch.isupper(): return .68
    return .556 if ch.isdigit() else .52


def tw(s, size, bold=False): return sum(_cw(c) for c in s) * size * (1.07 if bold else 1)


def wrap(text, size, width, bold=False):
    lines = []
    for para in clean(text).split("\n"):
        cur = ""
        for word in para.split(" "):
            while tw(word, size, bold) > width:                       # juda uzun so'z: bo'lib tashlaymiz
                k = max(1, int(len(word) * width / tw(word, size, bold)) - 1)
                if cur: lines.append(cur); cur = ""
                lines.append(word[:k]); word = word[k:]
            t = (cur + " " + word).strip() if cur else word
            if tw(t, size, bold) <= width: cur = t
            else: lines.append(cur); cur = word
        lines.append(cur)
    return lines


def jpeg_info(d):
    if d[:2] != b"\xff\xd8": raise ValueError("JPEG emas")
    i = 2
    while i + 4 < len(d):
        if d[i] != 0xFF: i += 1; continue
        m = d[i + 1]; i += 2
        if m in (0xD8, 0x01, 0xFF) or 0xD0 <= m <= 0xD7: continue
        ln = struct.unpack(">H", d[i:i + 2])[0]
        if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            _, h, w, n = struct.unpack(">BHHB", d[i + 2:i + 8]); return w, h, n
        i += ln
    raise ValueError("JPEG o'lchami topilmadi")


def _esc(s): return clean(s).encode("cp1252", "ignore").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


class Doc:
    W, H, M = 595, 842, 40

    def __init__(s):
        s.pages, s.imgs = [], []
        s.new_page()

    def new_page(s): s.cur = []; s.pages.append(s.cur); s.y = s.H - s.M

    def need(s, h):
        if s.y - h < s.M: s.new_page()

    def space(s, h): s.y -= h

    def line(s, text, size=10, font="F1", color=(0, 0, 0), x=0):
        s.need(size * 1.35); s.y -= size * 1.35
        s.cur.append(b"BT /%s %g Tf %g %g %g rg %g %.1f Td (%s) Tj ET" % (font.encode(), size, *color, s.M + x, s.y, _esc(text)))

    def para(s, text, size=10, font="F1", color=(0, 0, 0), x=0):
        for ln in wrap(text, size, s.W - 2 * s.M - x, font == "F2"): s.line(ln, size, font, color, x)

    def image(s, data, maxw=230, maxh=260, x=0):
        w, h, n = jpeg_info(data)
        if n not in (1, 3): raise ValueError("rang fazosi qo'llanmaydi")
        k = min(maxw / w, maxh / h, 1.0); dw, dh = w * k, h * k
        s.need(dh + 6); s.y -= dh + 3
        s.imgs.append((w, h, "DeviceGray" if n == 1 else "DeviceRGB", data))
        s.cur.append(b"q %.1f 0 0 %.1f %g %.1f cm /Im%d Do Q" % (dw, dh, s.M + x, s.y, len(s.imgs) - 1))
        s.y -= 3

    def save(s, title="Tarix"):
        objs = [None, None, None]

        def add(b): objs.append(b); return len(objs)
        fonts = [add(b"<< /Type /Font /Subtype /Type1 /BaseFont /%s /Encoding /WinAnsiEncoding >>" % f)
                 for f in (b"Helvetica", b"Helvetica-Bold", b"Helvetica-Oblique")]
        imgs = [add(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /%s /BitsPerComponent 8 "
                    b"/Filter /DCTDecode /Length %d >>\nstream\n" % (w, h, cs.encode(), len(d)) + d + b"\nendstream")
                for w, h, cs, d in s.imgs]
        objs[2] = (b"<< /Font << " + b" ".join(b"/F%d %d 0 R" % (i + 1, o) for i, o in enumerate(fonts)) + b" >> /XObject << "
                   + b" ".join(b"/Im%d %d 0 R" % (i, o) for i, o in enumerate(imgs)) + b" >> >>")
        kids = []
        for page in s.pages:
            z = zlib.compress(b"\n".join(page))
            c = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(z) + z + b"\nendstream")
            kids.append(add(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Resources 3 0 R /Contents %d 0 R >>"
                            % (s.W, s.H, c)))
        objs[1] = b"<< /Type /Pages /Count %d /Kids [%s] >>" % (len(kids), b" ".join(b"%d 0 R" % k for k in kids))
        objs[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
        info = add(b"<< /Title (%s) /Producer (xabar-bot) >>" % _esc(title))
        out, offs = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"), []
        for i, o in enumerate(objs):
            offs.append(len(out)); out += b"%d 0 obj\n" % (i + 1) + o + b"\nendobj\n"
        x = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
        out += b"trailer\n<< /Size %d /Root 1 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, info, x)
        return bytes(out)
