"""
AI宠物 - 图片UI卡片渲染器
==========================
用 Pillow 绘制漂亮的宠物状态卡片（独立 UI，不依赖 t2i / emoji 字体）
"""

import os
import time
import uuid

from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

from .pet_model import (
    PetState, PetEmotion, EMOTION_CN, LEVEL_NAMES,
    EMOTION_CATEGORIES, EMOTION_EMOJIS, current_badge_text, exp_needed,
    sync_derived,
)

# ═══════════════════════════════════════════════
# 字体
# ═══════════════════════════════════════════════

_FONT_CANDIDATES = [
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Medium.ttc",
]

_font_cache = {}


def _font(size: int, bold: bool = True):
    key = (size, bold)
    if key not in _font_cache:
        for fp in _FONT_CANDIDATES:
            try:
                _font_cache[key] = ImageFont.truetype(fp, size)
                break
            except Exception:
                continue
        else:
            _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]

# 主 emoji 字体用 OpenMoji（黑白版，覆盖 1958+ 码点），NotoEmoji 作备份补充
_EMOJI_FONT_PATH = "/usr/share/fonts/openmoji/OpenMoji-black.ttf"
_EMOJI_FONT_PATH_BAK = "/usr/share/fonts/google-noto-emoji-fonts/NotoEmoji-Regular.ttf"
_emoji_font_cache = {}


def _emoji_font(size: int):
    """主 emoji 字体（OpenMoji）"""
    if size not in _emoji_font_cache:
        try:
            _emoji_font_cache[size] = ImageFont.truetype(_EMOJI_FONT_PATH, size)
        except Exception:
            _emoji_font_cache[size] = None
    return _emoji_font_cache[size]


_emoji_font_bak_cache = {}


def _emoji_font_bak(size: int):
    """备份 emoji 字体（NotoEmoji，用于主字体没有的字形）"""
    if size not in _emoji_font_bak_cache:
        try:
            _emoji_font_bak_cache[size] = ImageFont.truetype(_EMOJI_FONT_PATH_BAK, size)
        except Exception:
            _emoji_font_bak_cache[size] = None
    return _emoji_font_bak_cache[size]


_EMOJI_CMAP = None
_EMOJI_CMAP_MAIN = None


def _emoji_cmap():
    """合并主+备份 emoji 字体的 cmap，用于判断字符是否为可用 emoji"""
    global _EMOJI_CMAP
    if _EMOJI_CMAP is None:
        cm = {}
        for fp in (_EMOJI_FONT_PATH, _EMOJI_FONT_PATH_BAK):
            try:
                cm.update(TTFont(fp, fontNumber=0).getBestCmap())
            except Exception:
                pass
        _EMOJI_CMAP = cm
    return _EMOJI_CMAP


def _emoji_cmap_main():
    """只有主 emoji 字体（OpenMoji）的 cmap，用于选具体字体"""
    global _EMOJI_CMAP_MAIN
    if _EMOJI_CMAP_MAIN is None:
        try:
            _EMOJI_CMAP_MAIN = TTFont(_EMOJI_FONT_PATH, fontNumber=0).getBestCmap()
        except Exception:
            _EMOJI_CMAP_MAIN = {}
    return _EMOJI_CMAP_MAIN


def _is_emoji_cp(cp: int) -> bool:
    """只把真正的 emoji 码段交给 emoji 字体；数字/字母/中文/常用符号保持 CJK"""
    return ((0x1F000 <= cp <= 0x1FAFF) or   # emoji 主区（😀🍎🚀等）
            (0x2600 <= cp <= 0x27BF) or      # 杂项符号（✨☀☔等）
            (0x2B00 <= cp <= 0x2BFF))        # 杂项符号箭头（⭐等）


def _has_glyph(font, ch: str) -> bool:
    if not ch:
        return False
    cp = ord(ch)
    if not _is_emoji_cp(cp):
        return False
    return cp in _emoji_cmap()


def _dtext(draw, xy, text, font, fill=None, **kw):
    """带 emoji 回退的文本绘制：emoji 字符优先 OpenMoji、缺字形补 NotoEmoji，其余走 CJK 字体"""
    if not text:
        return
    if "anchor" in kw:
        # 居中锚定场景（如徽章）逐字符会错位，直接整段画
        draw.text(xy, text, font=font, fill=fill, **kw)
        return
    efont = _emoji_font(font.size)
    ebak = _emoji_font_bak(font.size)
    cmap_main = _emoji_cmap_main()
    x, y = xy
    for ch in text:
        if _has_glyph(efont, ch):
            if ord(ch) in cmap_main:
                draw.text((x, y), ch, font=efont, fill=fill)
                x += efont.getlength(ch)
            elif ebak is not None:
                draw.text((x, y), ch, font=ebak, fill=fill)
                x += ebak.getlength(ch)
            else:
                draw.text((x, y), ch, font=font, fill=fill)
                x += font.getlength(ch)
        else:
            draw.text((x, y), ch, font=font, fill=fill)
            x += font.getlength(ch)



# ═══════════════════════════════════════════════
# 主题色（按性格）
# ═══════════════════════════════════════════════

PERSONALITY_COLORS = {
    "活泼": "#FF6B6B", "温柔": "#DDA0DD", "傲娇": "#45B7D1",
    "粘人": "#FF9FF3", "贪吃": "#FFA726", "慵懒": "#96CEB4",
}

DEFAULT_THEME = "#4ECDC4"


def _hex2rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _lighten(rgb, f: float = 0.55):
    return tuple(int(c + (255 - c) * f) for c in rgb)


def _darken(rgb, f: float = 0.25):
    return tuple(int(c * (1 - f)) for c in rgb)


# ═══════════════════════════════════════════════
# 进度条
# ═══════════════════════════════════════════════

def _rounded_progress(draw, x, y, w, h, pct, color, bg=None):
    # 进度条：浅磨砂槽(无描边) + 纯色圆角填充条(不提亮)
    if bg is None:
        bg = (250, 252, 255)
    r = h // 2
    draw.rounded_rectangle([x, y, x + w, y + h], radius=r, fill=bg)  # 磨砂槽
    fw = max(int(w * max(0, min(100, pct)) / 100), r * 2)
    if fw > 0:
        base = _hex2rgb(color) if isinstance(color, str) else color
        draw.rounded_rectangle([x, y, x + fw, y + h], radius=r, fill=base)


# ═══════════════════════════════════════════════
# Q版宠物脸（按情绪画表情）
# ═══════════════════════════════════════════════

def _draw_pet_face(draw, cx, cy, r, emotion, fur):
    """画一只圆滚滚的 Q 版宠物（猫系），根据情绪切换表情"""
    fur_rgb = _hex2rgb(fur)

    # 耳朵（猫耳）
    ear = _hex2rgb(fur)
    eo = int(r * 0.28)  # 耳朵偏移
    draw.polygon([(cx - eo, cy - r + 8), (cx - eo - int(r * 0.42), cy - r - int(r * 0.42)),
                  (cx - eo + int(r * 0.12), cy - r + 4)], fill=ear)
    draw.polygon([(cx + eo, cy - r + 8), (cx + eo + int(r * 0.42), cy - r - int(r * 0.42)),
                  (cx + eo - int(r * 0.12), cy - r + 4)], fill=ear)
    # 耳内
    inner = _lighten(ear, 0.4)
    draw.polygon([(cx - eo + 4, cy - r + 12), (cx - eo - int(r * 0.26), cy - r - int(r * 0.22)),
                  (cx - eo + int(r * 0.1), cy - r + 8)], fill=inner)
    draw.polygon([(cx + eo - 4, cy - r + 12), (cx + eo + int(r * 0.26), cy - r - int(r * 0.22)),
                  (cx + eo - int(r * 0.1), cy - r + 8)], fill=inner)

    # 脸
    face = _lighten(fur_rgb, 0.72)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=face)

    # 额头花纹（小爱心/斑纹）
    draw.polygon([(cx, cy - int(r * 0.55)), (cx - 12, cy - int(r * 0.28)),
                  (cx + 12, cy - int(r * 0.28))], fill=fur_rgb)

    # 眼睛与嘴
    _draw_eyes_mouth(draw, cx, cy, r, emotion)

    # 腮红
    blush = (255, 160, 160)
    bx = int(r * 0.55)
    draw.ellipse([cx - bx - 14, cy + int(r * 0.28), cx - bx + 6, cy + int(r * 0.28) + 22], fill=blush)
    draw.ellipse([cx + bx - 6, cy + int(r * 0.28), cx + bx + 14, cy + int(r * 0.28) + 22], fill=blush)

    # 胡须
    line = (150, 150, 150)
    hx = int(r * 0.62); hy = cy + int(r * 0.12)
    for dx in (-14, -6, 6, 14):
        draw.line([(cx - hx, hy + dx), (cx - hx - 26, hy + dx + 8)], fill=line, width=2)
        draw.line([(cx + hx, hy + dx), (cx + hx + 26, hy + dx + 8)], fill=line, width=2)


def _draw_eyes_mouth(draw, cx, cy, r, emotion):
    """根据情绪绘制眼睛和嘴巴"""
    eye_y = cy - int(r * 0.08)
    eye_l = cx - int(r * 0.34)
    eye_r = cx + int(r * 0.34)
    dark = (70, 60, 60)

    sad_eyes = emotion in (PetEmotion.SAD, PetEmotion.SICK, PetEmotion.HUNGRY)
    happy_eyes = emotion in (PetEmotion.HAPPY, PetEmotion.EXCITED, PetEmotion.FULL, PetEmotion.SPOILED)
    sleepy = emotion == PetEmotion.SLEEPY
    angry = emotion == PetEmotion.ANGRY

    # ── 眼睛 ──
    if happy_eyes:
        # 弯弯的月牙笑眼
        for ex in (eye_l, eye_r):
            draw.arc([ex - 16, eye_y - 10, ex + 16, eye_y + 14], start=20, end=160, fill=dark, width=4)
    elif sleepy:
        # 半闭眼
        for ex in (eye_l, eye_r):
            draw.line([(ex - 12, eye_y), (ex + 12, eye_y)], fill=dark, width=4)
    else:
        # 圆眼
        for ex in (eye_l, eye_r):
            draw.ellipse([ex - 13, eye_y - 13, ex + 13, eye_y + 13], fill=dark)
            draw.ellipse([ex - 4, eye_y - 5, ex + 5, eye_y + 4], fill=(255, 255, 255))
        if sad_eyes:
            # 眼泪
            draw.ellipse([eye_l - 4, eye_y + 18, eye_l + 8, eye_y + 34], fill=(140, 190, 255))
            draw.ellipse([eye_r - 4, eye_y + 18, eye_r + 8, eye_y + 34], fill=(140, 190, 255))

    # ── 眉毛（生气）──
    if angry:
        draw.line([(eye_l - 18, eye_y - 22), (eye_l + 14, eye_y - 12)], fill=dark, width=5)
        draw.line([(eye_r + 18, eye_y - 22), (eye_r - 14, eye_y - 12)], fill=dark, width=5)

    # ── 嘴巴 ──
    my = cy + int(r * 0.38)
    if happy_eyes:
        # 张大的笑脸
        draw.arc([cx - 22, my - 16, cx + 22, my + 26], start=0, end=180, fill=dark, width=4)
    elif angry:
        draw.arc([cx - 16, my - 6, cx + 16, my + 22], start=200, end=340, fill=dark, width=4)
    elif sleepy or sad_eyes:
        draw.arc([cx - 14, my - 6, cx + 14, my + 14], start=0, end=180, fill=dark, width=3)
    else:
        draw.line([(cx - 12, my), (cx + 12, my)], fill=dark, width=3)


# ═══════════════════════════════════════════════
# 圆形头像粘贴（替换默认Q版宠物脸）
# ═══════════════════════════════════════════════

def _paste_avatar(img, cx, cy, r, avatar_path, border="#FFFFFF"):
    """把外部头像图裁剪成圆形并粘贴到卡片中央"""
    try:
        av = Image.open(avatar_path).convert("RGBA")
    except Exception:
        return False
    w, h = av.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    av = av.crop((left, top, left + side, top + side))
    av = av.resize((r * 2, r * 2), Image.LANCZOS)
    mask = Image.new("L", (r * 2, r * 2), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, r * 2, r * 2], fill=255)
    img.paste(av, (cx - r, cy - r), mask)
    return True


# ═══════════════════════════════════════════════
# 主卡片
# ═══════════════════════════════════════════════

def _glass(img, x, y, w, h, radius=18, color=(255, 255, 255), alpha=110):
    """在 RGBA 卡片上叠加一条半透明圆角面板（槽位），返回合成后的图"""
    ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=color + (alpha,))
    return Image.alpha_composite(img, ov)

def _new_card_canvas(W: int, H: int, bg_path: str = None, bg_scale: float = 0.42):
    """创建卡片画布：AI 背景板按 bg_scale 缩放居中粘贴(装饰框完整露出)，四周浅色填充；无底图回退深蓝渐变"""
    if bg_path and os.path.exists(bg_path):
        try:
            bg = Image.open(bg_path).convert("RGB")
            bw = max(1, int(bg.width * bg_scale))
            bh = max(1, int(bg.height * bg_scale))
            bg = bg.resize((bw, bh), Image.LANCZOS)
            canvas = Image.new("RGB", (W, H), (250, 250, 252))
            canvas.paste(bg, ((W - bw) // 2, (H - bh) // 2))
            return canvas
        except Exception:
            pass
    # 回退：浅色竖向渐变
    img = Image.new("RGB", (W, H), (243, 246, 253))
    draw = ImageDraw.Draw(img)
    steps = 90
    for i in range(steps):
        y0 = int(H * i / steps)
        y1 = int(H * (i + 1) / steps)
        f = i / steps
        color = tuple(int(a + (b - a) * f) for a, b in zip((243, 246, 253), (225, 232, 248)))
        draw.rectangle([0, y0, W, y1], fill=color)
    return img


def render_pet_card_image(pet: PetState, title: str = "我的宠物", out_dir: str = None,
                          avatar_path: str = None) -> str:
    """
    渲染宠物状态图片卡片，返回保存的图片路径
    avatar_path: 可选，用外部头像图（圆形裁剪）替换默认Q版宠物脸
    """
    # 先把情绪区/心情区的分数调和成 心情值+情绪值，保证卡片显示联动
    sync_derived(pet)
    # 高度自适应：状态4行 + 情绪6条 + 心情2条 + EXP + 底部统计
    H = 448 + 4 * 52 + (16 + 46 + 6 * 48) + (16 + 46 + 2 * 48) + (16 + 52) + (40 + 40) + 52
    W = 540
    theme = PERSONALITY_COLORS.get(pet.personality, DEFAULT_THEME)
    theme_rgb = _hex2rgb(theme)
    bg_top = (31, 46, 106)
    bg_bottom = (10, 17, 48)

    bg_img = _new_card_canvas(W, H, os.path.join(os.path.dirname(__file__), "assets", "card_bg_state.png"))
    # 内容画在透明层，最后整体缩小居中放进背景板的装饰框内
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    emotion = pet.emotion or PetEmotion.NEUTRAL
    _lv_raw = LEVEL_NAMES.get(pet.level)
    level_name = _lv_raw if _lv_raw and not str(_lv_raw).startswith("Lv.") else f"Lv.{pet.level}"
    badge_text = current_badge_text(pet)

    # ── 顶栏：宠物名 + 情绪徽章（情绪大类 · 心情极性）──
    f_name = _font(40)
    f_badge = _font(22)

    _dtext(draw, (48, 48), f"{pet.pet_name}", font=f_name, fill=(43, 56, 96))
    name_w = draw.textlength(pet.pet_name, font=f_name)
    # 情绪徽章
    badge_w = int(draw.textlength(badge_text, font=f_badge)) + 40
    bx0 = W - 50 - badge_w
    draw.rounded_rectangle([bx0, 54, bx0 + badge_w, 96], radius=21, fill=theme_rgb)
    _dtext(draw, (bx0 + badge_w / 2, 75), badge_text, font=f_badge,
              fill=(43, 56, 96), anchor="mm")

    # 等级称号（顶栏下方小字；称号缺失回退为 Lv.x 时不重复拼接）
    level_text = f"{level_name}   Lv.{pet.level}" if not level_name.startswith("Lv.") else f"Lv.{pet.level}"
    _dtext(draw, (50, 106), level_text, font=_font(22),
              fill=(88, 103, 148))

    # ── 宠物头像区（优先用外部头像，否则画Q版脸）──
    draw_face = ImageDraw.Draw(img)
    avatar_used = False
    _avatar = avatar_path or os.path.join(os.path.dirname(__file__), "assets", "avatar_handsome.png")
    if _avatar:
        avatar_used = _paste_avatar(img, W // 2, 256, 100, _avatar,
                                    border=(150, 175, 255))
    if not avatar_used:
        _draw_pet_face(draw_face, W // 2, 256, 108, emotion, theme)

    # 性格 & 最爱（♥ 精确居中于 最爱 和 食物 之间）
    fav_show = pet.favorite_food if pet.favorite_food else "未知"
    f_info = _font(24)
    infoA = f"性格 {pet.personality}    最爱"
    x0 = 52
    _dtext(draw, (x0, 398), infoA, font=f_info, fill=(70, 86, 132))
    wa = f_info.getlength(infoA)
    e_heart = _emoji_font(24)
    if e_heart is not None and _has_glyph(e_heart, "♥"):
        bb = e_heart.getbbox("♥")
        ew = bb[2] - bb[0]
        eh = bb[3] - bb[1]
        g = 16
        hx = x0 + wa + g + ew / 2.0
        cy = 398 + 26 / 2.0
        draw.text((hx - bb[0] - ew / 2.0, cy - eh / 2.0), "♥", font=e_heart, fill=(70, 86, 132))
        fx = x0 + wa + g * 2 + ew
    else:
        fh = f_info.getlength("♥")
        g = 14
        hx = x0 + wa + g + fh / 2.0
        _dtext(draw, (hx, 398), "♥", font=f_info, fill=(70, 86, 132), anchor="mm")
        fx = x0 + wa + g * 2 + fh
    _dtext(draw, (fx, 398), fav_show, font=f_info, fill=(70, 86, 132))

    # ── 状态区（饱食 / 心情 / 情绪 / 精力，emoji 图标）──
    stats = [
        ("饱食度", 100 - pet.hunger, "#FF9F43", "🍖"),
        ("心情值", pet.mood, "#F6C343", "😊"),
        ("情绪值", pet.emotion_value, "#FF6B6B", "💗"),
        ("精力值", pet.energy, "#54A0FF", "⚡"),
    ]
    y = 448
    for (label, val, color, icon) in stats:
        img = _glass(img, 48, y - 8, 444, 44)
        draw = ImageDraw.Draw(img)
        _dtext(draw, (56, y - 2), icon, font=_font(24), fill=color)
        _dtext(draw, (94, y - 2), label, font=_font(24), fill=(88, 103, 148))
        _rounded_progress(draw, 188, y, 205, 22, val, color)
        _dtext(draw, (432, y - 2), f"{val}%", font=_font(22), fill=(88, 103, 148))
        y += 52

    # ── 情绪区（6 大基础情绪，一条一条竖排）──
    y += 16
    _dtext(draw, (52, y), "情绪", font=_font(24), fill=(43, 56, 96))
    y += 46
    _EMO_COLORS = {
        "快乐": "#FF6B6B", "悲伤": "#54A0FF", "愤怒": "#FF5E57",
        "恐惧": "#9B59B6", "厌恶": "#95A5A6", "惊讶": "#F6C343",
    }
    _EMO_ICONS = {
        "快乐": "😁", "悲伤": "😢", "愤怒": "😡",
        "恐惧": "😨", "厌恶": "🤢", "惊讶": "😲",
    }
    scores = pet.emotion_scores
    for cat in EMOTION_CATEGORIES.keys():
        img = _glass(img, 48, y - 7, 444, 40)
        draw = ImageDraw.Draw(img)
        val = scores.get(cat, 0)
        pct = min(100, int(val / 50 * 100))
        _dtext(draw, (56, y - 2), _EMO_ICONS.get(cat, "😐"), font=_font(25),
                  fill=_EMO_COLORS.get(cat, "#FFFFFF"))
        _dtext(draw, (96, y - 2), cat, font=_font(22), fill=(70, 86, 132))
        _rounded_progress(draw, 140, y, 205, 20, pct, _EMO_COLORS.get(cat, "#FFFFFF"))
        _dtext(draw, (418, y - 2), str(val), font=_font(22),
                  fill=_EMO_COLORS.get(cat, "#FFFFFF"))
        y += 48

    # ── 心情区（积极 / 消极，与情绪区对齐）──
    y += 16
    _dtext(draw, (52, y), "心情", font=_font(24), fill=(43, 56, 96))
    y += 46
    ms = pet.mood_scores
    for val, color, icon in [
        (ms.get("积极", 0), "#4CD97B", "😄"),
        (ms.get("消极", 0), "#8D99AE", "😞"),
    ]:
        img = _glass(img, 48, y - 7, 444, 40)
        draw = ImageDraw.Draw(img)
        pct = min(100, int(val / 50 * 100))
        _dtext(draw, (56, y - 2), icon, font=_font(25), fill=color)
        _rounded_progress(draw, 92, y, 205, 20, pct, color)
        _dtext(draw, (368, y - 2), str(val), font=_font(22), fill=(88, 103, 148))
        y += 48

    # ── EXP（与心情区对齐，难度随等级递增）──
    y += 16
    _need = exp_needed(pet.level)
    exp_pct = min(100, int(pet.exp / _need * 100)) if _need else 0
    img = _glass(img, 48, y - 8, 444, 46)
    draw = ImageDraw.Draw(img)
    _dtext(draw, (56, y - 2), "⭐", font=_font(25), fill=(88, 103, 148))
    _rounded_progress(draw, 92, y + 4, 205, 20, exp_pct, _lighten(theme_rgb, 0.1))
    _dtext(draw, (368, y), f"{pet.exp}/{_need}", font=_font(20), fill=(88, 103, 148))
    y += 52

    # ── 底部统计 ──
    total_inter = pet.total_pet + pet.total_play
    line = f"喂食 {pet.total_feed} 次     互动 {total_inter} 次     时长 {pet.pet_name}养成中"
    _dtext(draw, (52, y), line, font=_font(22), fill=(105, 120, 164))
    y += 40
    _dtext(draw, (52, y), f"—— {title} ——", font=_font(20), fill=(105, 120, 164))

    # 内容层整体缩小，居中放进背景板的装饰框内
    content_scale = 0.80
    cw, ch = max(1, int(W * content_scale)), max(1, int(H * content_scale))
    content = img.resize((cw, ch), Image.LANCZOS)
    px, py = (W - cw) // 2, (H - ch) // 2
    bg_img.paste(content, (px, py), content)
    # 只保留背景板自带的装饰框区域，裁掉四周白色留白
    # 装饰框在渲染图上的外缘(基于 v3 背景 + bg_scale=0.42 + 内容0.8): 左25 上105 右513 下1233
    bg_img = bg_img.crop((25, 105, 513, 1233))
    img = bg_img

    # 保存
    if not out_dir:
        out_dir = os.path.join(os.getcwd(), "cards")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"pet_{pet.owner_id}_{int(time.time())}.png")
    img.save(path, "PNG")
    return path
# ═══════════════════════════════════════════════
# 好感关系卡（宠物对某人的好感度 / 情绪 / 相处统计）
# ═══════════════════════════════════════════════

def _wrap_text(draw, text, font, max_w):
    """按像素宽度把文本折行，返回行列表"""
    lines, cur = [], ""
    for ch in text:
        if cur and draw.textlength(cur + ch, font=font) > max_w:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def _impression_of(pet) -> str:
    """宠物对某个人的当前印象，随好感/相处时长/互动动态变化"""
    days = max(1, int((time.time() - pet.created_at) / 86400) + 1)
    feed = getattr(pet, "total_feed", 0) or 0
    inter = getattr(pet, "total_interact", 0) or         (getattr(pet, "total_pet", 0) or 0) + (getattr(pet, "total_play", 0) or 0)
    a = pet.affection or 0

    if a >= 90:
        base = "是可以交心的人，想把最好的都给你"
    elif a >= 75:
        base = "很信得过的人，跟你待着特别安心"
    elif a >= 60:
        base = "聊得来的老朋友，见面就想多待一会儿"
    elif a >= 40:
        base = "越来越熟的朋友，好感正在路上"
    elif a >= 20:
        base = "见过几面的熟面孔，印象不赖"
    else:
        base = "初次见面，还在偷偷观察你"

    marks = []
    if days >= 7:
        marks.append(f"已相伴{days}天")
    if inter >= 10:
        marks.append(f"互动过{inter}次")
    if feed >= 5:
        marks.append(f"喂过我{feed}次")
    if marks:
        base += "，" + "、".join(marks)
    return base


def _short_num(n) -> str:
    """数字太长缩写，保证框内放得下"""
    n = int(n or 0)
    if n >= 100000000:
        v = n / 100000000
        return f"{int(v)}亿" if v >= 10 else f"{v:.1f}亿"
    if n >= 10000:
        v = n / 10000
        return f"{int(v)}万" if v >= 10 else f"{v:.1f}万"
    if n >= 1000:
        v = n / 1000
        return f"{int(v)}k" if v >= 10 else f"{v:.1f}k"
    return str(n)


def _relation_level(affection: int) -> str:
    """好感度对应的关系等级"""
    if affection >= 90:
        return "挚友"
    if affection >= 75:
        return "亲密"
    if affection >= 60:
        return "熟悉"
    if affection >= 40:
        return "相识"
    if affection >= 20:
        return "眼熟"
    return "陌生人"


def render_relation_image(pet: PetState, target_name: str = "ta",
                          out_dir: str = None, avatar_path: str = None) -> str:
    """
    渲染"宠物对某人的好感"关系卡片，返回图片路径
    包含：好感度+关系等级、情绪值+情绪、喂食次数、互动次数、相处时长、印象
    """
    # 先把情绪区/心情区调和回写，保证情绪值显示的是正确联动值
    sync_derived(pet)
    W = 540
    # 优先用持久化印象（基于最近聊天维护），没有就用好感度生成的短印象兜底
    f_imp = _font(24)
    imp_text = getattr(pet, "impression", "") or _impression_of(pet)
    _imp_lines, _cur = [], ""
    for _ch in imp_text:
        if _cur and f_imp.getlength(_cur + _ch) > W - 110:
            _imp_lines.append(_cur)
            _cur = _ch
        else:
            _cur += _ch
    if _cur:
        _imp_lines.append(_cur)
    # 印象框宽高随文本自适应（左右各32 padding，行高36，上下16）
    imp_max_w = max([f_imp.getlength(ln) for ln in _imp_lines] or [0])
    imp_box_w = min(W - 80, int(imp_max_w) + 64)
    imp_box_h = max(72, len(_imp_lines) * 36 + 32)
    # 卡片总高按内容算：印象框底部 + 日记行 + 底部边距
    H = 796 + imp_box_h
    theme = PERSONALITY_COLORS.get(pet.personality, DEFAULT_THEME)
    theme_rgb = _hex2rgb(theme)
    bg_top = (31, 46, 106)
    bg_bottom = (10, 17, 48)

    # 背景：豆包生成的纯净渐变背景板，直接缩放铺满整张画布(渐变拉伸无视觉损失)
    bg_path = os.path.join(os.path.dirname(__file__), "assets", "card_bg_relation.png")
    if os.path.exists(bg_path):
        _bg = Image.open(bg_path).convert("RGB")
        img = _bg.resize((W, H), Image.LANCZOS).convert("RGBA")
    else:
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        _g = ImageDraw.Draw(img)
        for i in range(90):
            yy0 = int(H * i / 90)
            yy1 = int(H * (i + 1) / 90)
            f = i / 90
            color = tuple(int(a + (b - a) * f) for a, b in zip((250, 246, 250), (240, 247, 253)))
            _g.rectangle([0, yy0, W, yy1], fill=color)
    draw = ImageDraw.Draw(img)

    # 整卡玻璃框：圆角磨砂描边 + 半透明填充 + 顶部高光，背景渐变透出
    img = _glass(img, 12, 16, W - 24, H - 32, radius=22, color=(255, 255, 255), alpha=95)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([12, 16, W - 12, H - 16], radius=22,
                           outline=(255, 255, 255, 220), width=3)
    # 顶部内侧高光条，模拟玻璃反光
    draw.rounded_rectangle([20, 21, W - 20, 27], radius=3,
                           outline=None, fill=(255, 255, 255, 95))

    emotion = pet.emotion or PetEmotion.NEUTRAL
    badge_text = current_badge_text(pet).replace(" ", "")

    # ── 顶栏：标题 + 情绪徽章（情绪大类·心情极性，紧凑）──
    f_title = _font(40)
    f_badge = _font(22)
    title = f"{pet.pet_name}对 {target_name} 的好感"
    # 标题若与徽章冲突：先自动缩小字号，缩到底还放不下才截断兜底
    badge_w = int(draw.textlength(badge_text, font=f_badge)) + 36
    bx0 = W - 16 - badge_w
    max_title_w = bx0 - 36
    tsize = 40
    while tsize > 22 and int(draw.textlength(title, font=_font(tsize))) > max_title_w:
        tsize -= 2
    if int(draw.textlength(title, font=_font(tsize))) > max_title_w:
        tsize = 22
        t_name = target_name
        title = f"对 {t_name} 的好感"
        while t_name and int(draw.textlength(title, font=_font(tsize))) > max_title_w:
            t_name = t_name[:-1]
            title = f"对 {t_name}… 的好感"
    _dtext(draw, (20, 36), title, font=_font(tsize), fill=(43, 56, 96))
    draw.rounded_rectangle([bx0, 42, bx0 + badge_w, 84], radius=21, fill=theme_rgb)
    _dtext(draw, (bx0 + badge_w / 2, 63), badge_text, font=f_badge,
              fill=(255, 255, 255), anchor="mm")

    # ── 头像区（帅哥头像）──
    avatar_used = _paste_avatar(img, W // 2, 215, 85, avatar_path,
                                border=(190, 208, 245))
    if not avatar_used:
        _draw_pet_face(draw, W // 2, 215, 85, emotion, theme)

    # 关系等级横幅（头像下方）
    rel = _relation_level(pet.affection)
    rel_badge = f"好感等级 · {rel}"
    rw = int(draw.textlength(rel_badge, font=_font(26))) + 48
    rx0 = (W - rw) // 2
    ry0 = 318
    img = _glass(img, rx0, ry0, rw, 42, radius=21, color=(255, 255, 255), alpha=120)
    draw = ImageDraw.Draw(img)
    _dtext(draw, (rx0 + rw / 2, ry0 + 42 / 2), rel_badge, font=_font(26),
              fill=theme_rgb, anchor="mm")

    # ── 好感度进度条 ──
    y = 388
    _dtext(draw, (40, y - 2), "好感度", font=_font(26), fill=(88, 103, 148))
    _dtext(draw, (450, y - 2), f"{pet.affection}%", font=_font(24), fill=(70, 86, 132))
    _rounded_progress(draw, 190, y, 250, 24, pet.affection, "#FF6B9D")
    y += 44

    # ── 情绪值进度条 ──
    _dtext(draw, (40, y - 2), "情绪值", font=_font(26), fill=(88, 103, 148))
    _dtext(draw, (450, y - 2), f"{pet.emotion_value}%", font=_font(24), fill=(70, 86, 132))
    _rounded_progress(draw, 190, y, 250, 24, pet.emotion_value, "#FF6B6B")
    y += 50

    # ── 喂食 / 互动 统计框（深蓝，无图标）──
    total_inter = getattr(pet, "total_interact", 0) or (pet.total_pet + pet.total_play)
    box_w = 214
    box_h = 110
    box_gap = 16
    box_x0, box_x1 = 40, 40 + box_w + box_gap
    box_y = y
    for bx, val, label in [
        (box_x0, pet.total_feed, "喂食次数"),
        (box_x1, total_inter, "互动次数"),
    ]:
        img = _glass(img, bx, box_y, box_w, box_h, radius=18, color=(255, 255, 255), alpha=120)
        draw = ImageDraw.Draw(img)
        f_lab, f_num = _font(24), _font(30)
        num_text = _short_num(val)
        lw = draw.textlength(label, font=f_lab)
        nw = draw.textlength(num_text, font=f_num)
        # 标签靠上居中，数字在框中间（水平+垂直都居中）
        _dtext(draw, (bx + (box_w - lw) / 2, box_y + 10), label, font=f_lab,
                  fill=(88, 103, 148))
        _dtext(draw, (bx + (box_w - nw) / 2, box_y + 46), num_text, font=f_num,
                  fill=(43, 56, 96))
    y = box_y + box_h + 24

    # ── 相处信息 ──
    days = max(1, int((time.time() - pet.created_at) / 86400) + 1)
    _dtext(draw, (40, y), f"已相伴 {days} 天   ·   最爱 {pet.favorite_food}",
              font=_font(26), fill=(88, 103, 148))
    y += 48

    # ── 宠物对TA的印象模块（框宽高随文本自适应）──
    _dtext(draw, (40, y), f"{pet.pet_name}对你的印象", font=_font(26), fill=(88, 103, 148))
    y += 40
    img = _glass(img, 40, y, imp_box_w, imp_box_h, radius=16, color=(255, 255, 255), alpha=120)
    draw = ImageDraw.Draw(img)
    ty = y + 18
    for ln in _imp_lines:
        _dtext(draw, (72, ty), ln, font=_font(24), fill=(70, 86, 132))
        ty += 36
    y += imp_box_h + 28

    _dtext(draw, (40, y), f"—— {pet.pet_name}养成日记 ——", font=_font(22),
              fill=(120, 140, 190))

    # 保存
    if not out_dir:
        out_dir = os.path.join(os.getcwd(), "cards")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"rel_{pet.owner_id}_{int(time.time())}.png")
    img.save(path, "PNG")
    return path
