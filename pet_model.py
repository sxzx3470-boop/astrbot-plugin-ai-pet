"""
AI宠物 - 数据模型、情绪系统、动作系统、等级系统
"""

import time
import random
from typing import Dict


# ═══════════════════════════════════════════════
# 情绪枚举
# ═══════════════════════════════════════════════

class PetEmotion:
    HAPPY = "happy"
    NEUTRAL = "neutral"
    HUNGRY = "hungry"
    SICK = "sick"
    SLEEPY = "sleepy"
    EXCITED = "excited"
    ANGRY = "angry"
    SAD = "sad"
    FULL = "full"
    SPOILED = "spoiled"


EMOTION_EMOJI = {
    PetEmotion.HAPPY: "😊", PetEmotion.NEUTRAL: "😐",
    PetEmotion.HUNGRY: "😫", PetEmotion.SICK: "🤒",
    PetEmotion.SLEEPY: "😴", PetEmotion.EXCITED: "🤩",
    PetEmotion.ANGRY: "😠", PetEmotion.SAD: "😢",
    PetEmotion.FULL: "🥱", PetEmotion.SPOILED: "😎",
}

EMOTION_CN = {
    PetEmotion.HAPPY: "开心", PetEmotion.NEUTRAL: "平静",
    PetEmotion.HUNGRY: "饥饿", PetEmotion.SICK: "生病",
    PetEmotion.SLEEPY: "困倦", PetEmotion.EXCITED: "兴奋",
    PetEmotion.ANGRY: "生气", PetEmotion.SAD: "伤心",
    PetEmotion.FULL: "饱了", PetEmotion.SPOILED: "被宠坏",
}

# ═══════════════════════════════════════════════
# 动作系统
# ═══════════════════════════════════════════════

INTERACTIONS = {
    "pet":   {"name": "抚摸", "emoji": "✋", "affection": +3, "mood": +4, "msg": "被{}摸了一下，舒服地眯起了眼睛"},
    "hug":   {"name": "抱抱", "emoji": "🤗", "affection": +5, "mood": +5, "msg": "被{}抱在怀里，开心地蹭了蹭"},
    "play":  {"name": "玩耍", "emoji": "🎾", "affection": +4, "mood": +6, "energy": -6, "msg": "和{}一起玩耍，跑来跑去好开心！"},
    "sleep": {"name": "睡觉", "emoji": "🌙", "affection": +2, "mood": +3, "energy": +24, "msg": ""},
    "wake":  {"name": "醒来", "emoji": "⏰", "affection": +2, "mood": +3, "energy": +6, "msg": "被{}叫醒了，伸了个懒腰，精神抖擞地起床啦！"},
    "train": {"name": "训练", "emoji": "🎯", "affection": +3, "mood": +2, "exp": +10, "msg": "跟{}学习新技能，学得可认真了！"},
}

FOODS = {
    "苹果":   {"emoji": "🍎", "hunger": -15, "mood": +3,  "msg": "吃了一个苹果，脆脆甜甜的"},
    "蛋糕":   {"emoji": "🍰", "hunger": -25, "mood": +5,  "msg": "吃了一块蛋糕，好甜好好吃！"},
    "寿司":   {"emoji": "🍣", "hunger": -20, "mood": +4,  "msg": "吃了一份寿司，新鲜美味"},
    "冰淇淋": {"emoji": "🍦", "hunger": -10, "mood": +7,  "msg": "吃了一个冰淇淋，凉凉的，好开心！"},
    "肉":     {"emoji": "🥩", "hunger": -30, "mood": +3,  "msg": "吃了一块肉，大满足！"},
    "饼干":   {"emoji": "🍪", "hunger": -12, "mood": +4,  "msg": "吃了一块饼干，酥酥脆脆"},
    "牛奶":   {"emoji": "🥛", "hunger": -8,  "mood": +2,  "msg": "喝了一杯牛奶，暖暖的"},
    "鱼":     {"emoji": "🐟", "hunger": -18, "mood": +4,  "msg": "吃了一条鱼，鲜美可口"},
    "糖果":   {"emoji": "🍬", "hunger": -5,  "mood": +6,  "msg": "吃了一颗糖果，甜滋滋的～"},
    "奶茶":   {"emoji": "🧋", "hunger": -10, "mood": +6,  "msg": "喝了一杯奶茶，甜甜的，幸福感拉满！"},
    "烤肠":   {"emoji": "🌭", "hunger": -22, "mood": +4,  "msg": "吃了一根烤肠，香喷喷油滋滋的"},
    "薯片":   {"emoji": "🍟", "hunger": -8,  "mood": +5,  "msg": "吃了一包薯片，咔嚓咔嚓，好脆"},
    "可乐":   {"emoji": "🥤", "hunger": -6,  "mood": +7,  "msg": "喝了一口可乐，气泡在嘴里炸开，爽！"},
}

# ═══════════════════════════════════════════════
# 等级系统
# ═══════════════════════════════════════════════

LEVEL_NAMES = {
    1: "等级", 2: "幼崽", 3: "成长期",
    4: "青年期", 5: "成熟期", 6: "巅峰期",
    7: "传说级", 8: "史诗级", 9: "神话级",
    10: "至尊级", 11: "无双级", 12: "主宰级",
    13: "天启级", 14: "不朽级", 15: "创世级",
    16: "超神级", 17: "神王级", 18: "神帝级",
    19: "寰宇级", 20: "万古级",
}

# ═══════════════════════════════════════════════
# 情绪 / 心情 双维度系统
# ═══════════════════════════════════════════════

# 基础情绪（6大类），每类含子情绪
EMOTION_CATEGORIES = {
    "快乐": ["喜悦", "满足", "欣喜"],
    "悲伤": ["忧郁", "失落", "哀痛"],
    "愤怒": ["生气", "暴躁", "恼火"],
    "恐惧": ["害怕", "惊慌", "忧虑"],
    "厌恶": ["反感", "讨厌", "恶心"],
    "惊讶": ["吃惊", "诧异"],
}

EMOTION_EMOJIS = {
    "快乐": "😊", "悲伤": "😢", "愤怒": "😠",
    "恐惧": "😨", "厌恶": "🤢", "惊讶": "😲",
}

# 心情极性（唤醒 x 效价），只统计积极/消极两类
MOOD_POLARITY = {
    "积极": ["兴奋", "充满活力", "神清气爽", "平静", "安详", "慵懒", "满足"],
    "消极": ["紧张", "焦虑", "烦躁", "坐立不安", "沮丧", "消沉", "倦怠", "忧郁", "空虚"],
}

MOOD_EMOJIS = {"积极": "✨", "消极": "🌧️"}

DEFAULT_EMOTION_SCORES = {c: 0 for c in EMOTION_CATEGORIES}
DEFAULT_MOOD_SCORES = {p: 0 for p in MOOD_POLARITY}


def record_emotion(pet: "PetState", categories=(), polarity=None):
    """记录一次情绪事件：命中某情绪大类就 +1，命中积极/消极心情极性也 +1"""
    for c in categories:
        if c in pet.emotion_scores:
            pet.emotion_scores[c] = min(50, pet.emotion_scores[c] + 1)
    if polarity and polarity in pet.mood_scores:
        pet.mood_scores[polarity] = min(50, pet.mood_scores[polarity] + 1)


def emotion_label_to_category(label: str):
    """把实时情绪标签映射到 6 大基础情绪之一，不属于大类的返回 None"""
    mapping = {
        PetEmotion.HAPPY: "快乐", PetEmotion.EXCITED: "快乐",
        PetEmotion.SPOILED: "快乐", PetEmotion.FULL: "快乐",
        PetEmotion.SAD: "悲伤", PetEmotion.SICK: "悲伤",
        PetEmotion.HUNGRY: "悲伤",
        PetEmotion.ANGRY: "愤怒",
    }
    return mapping.get(label)


def current_mood_polarity(pet: "PetState") -> str:
    """当前心情极性：快乐/惊讶 → 积极；悲伤/愤怒/恐惧/厌恶 → 消极；
    平静/困倦等中性状态按心情值高低判断"""
    cat = emotion_label_to_category(pet.emotion)
    if cat in ("快乐", "惊讶"):
        return "积极"
    if cat in ("悲伤", "愤怒", "恐惧", "厌恶"):
        return "消极"
    # 中性状态按 积极/消极 分数比较（0基准，谁多算谁）
    pos = pet.mood_scores.get("积极", 0)
    neg = pet.mood_scores.get("消极", 0)
    return "积极" if pos > neg else "消极"


def current_badge_text(pet: "PetState") -> str:
    """右上角徽章文本：情绪大类 · 心情极性"""
    cat = emotion_label_to_category(pet.emotion)
    pol = current_mood_polarity(pet)
    if cat:
        return f"{cat} · {pol}"
    cn = EMOTION_CN.get(pet.emotion, "平静")
    return f"{cn} · {pol}"


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def current_emotion_value(pet: "PetState") -> int:
    """情绪值（0-100）：由情绪区六大类调和——
    快乐/惊讶(积极情绪)加分，悲伤/愤怒/恐惧/厌恶(消极情绪)减分，基准0"""
    es = pet.emotion_scores
    pos = es.get("快乐", 0) + es.get("惊讶", 0)
    neg = es.get("悲伤", 0) + es.get("愤怒", 0) + es.get("恐惧", 0) + es.get("厌恶", 0)
    return int(round(_clamp(pos - neg, 0, 100)))


def current_mood_value(pet: "PetState") -> int:
    """心情值（0-100）：由心情区积极/消极调和——积极加分、消极减分，基准0"""
    ms = pet.mood_scores
    return int(round(_clamp(ms.get("积极", 0) - ms.get("消极", 0), 0, 100)))


def sync_derived(pet: "PetState"):
    """把情绪区/心情区的分数调和成 心情值 + 情绪值，回写到 pet.mood / pet.emotion_value"""
    pet.mood = current_mood_value(pet)
    pet.emotion_value = current_emotion_value(pet)


# 新宠物的默认名字（部署者可通过 _conf_schema.json 的 default_pet_name 覆盖）
DEFAULT_PET_NAME = "小宠物"

PERSONALITIES = ["活泼", "温柔", "傲娇", "粘人", "贪吃", "慵懒"]
FAVORITE_FOODS = ["苹果", "蛋糕", "寿司", "冰淇淋", "肉", "饼干", "奶茶", "烤肠", "薯片", "可乐"]
COLORS = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD", "#FF9FF3"]


# ═══════════════════════════════════════════════
# 宠物状态模型
# ═══════════════════════════════════════════════

class PetState:
    def __init__(self, owner_id: str, pet_name: str = DEFAULT_PET_NAME):
        self.owner_id = owner_id
        self.pet_name = pet_name
        self.hunger = 80
        self.affection = 0
        self.energy = 70
        self.mood = 0
        self.emotion_value = 0
        self.emotion = PetEmotion.NEUTRAL
        self.emotion_locked_until = 0
        self.total_feed = 0
        self.total_pet = 0
        self.total_play = 0
        self.total_interact = 0
        self.impression = ""
        self.action_log = {}
        self.emotion_scores = dict(DEFAULT_EMOTION_SCORES)
        self.mood_scores = dict(DEFAULT_MOOD_SCORES)
        self.last_interact = time.time()
        self.created_at = time.time()
        self.level = 1
        self.exp = 0
        self.personality = random.choice(PERSONALITIES)
        self.favorite_food = random.choice(FAVORITE_FOODS)
        self.color = random.choice(COLORS)

    def to_dict(self) -> dict:
        return {
            "owner_id": self.owner_id, "pet_name": self.pet_name,
            "hunger": self.hunger, "affection": self.affection,
            "energy": self.energy, "mood": self.mood,
            "emotion_value": self.emotion_value,
            "emotion": self.emotion, "emotion_locked_until": self.emotion_locked_until,
            "total_feed": self.total_feed, "total_pet": self.total_pet,
            "total_play": self.total_play, "total_interact": self.total_interact,
            "impression": self.impression,
            "emotion_scores": self.emotion_scores,
            "mood_scores": self.mood_scores,
            "last_interact": self.last_interact,
            "created_at": self.created_at, "level": self.level, "exp": self.exp,
            "personality": self.personality, "favorite_food": self.favorite_food,
            "color": self.color,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PetState":
        pet = cls(data["owner_id"], data.get("pet_name", DEFAULT_PET_NAME))
        for k in ["hunger","affection","energy","mood","emotion","emotion_locked_until",
                   "total_feed","total_pet","total_play","total_interact","impression","emotion_value","last_interact","created_at",
                   "level","exp","personality","favorite_food","color"]:
            if k in data:
                setattr(pet, k, data[k])
        # 情绪/心情分数：合并存档值，缺的用默认 0（旧存档兼容），并强制钳制到各区上限50
        pet.emotion_scores = {c: min(50, v) for c, v in
                              {**DEFAULT_EMOTION_SCORES, **data.get("emotion_scores", {})}.items()}
        pet.mood_scores = {p: min(50, v) for p, v in
                           {**DEFAULT_MOOD_SCORES, **data.get("mood_scores", {})}.items()}
        return pet


# ═══════════════════════════════════════════════
# 负面词检测（记仇）
# ═══════════════════════════════════════════════

NEGATIVE_WORDS = [
    "傻逼", "煞笔", "傻b", "shabi", "sb", "废物", "垃圾", "蠢货", "蠢",
    "白痴", "低能", "憨批", "笨蛋", "猪", "滚", "滚蛋", "去死", "死开",
    "讨厌你", "烦死", "有病", "神经病", "妈的", "尼玛",
    "操", "草泥马", "骂你", "打你", "踢你", "掐死", "弄死你",
]

def check_negative(text: str):
    """返回消息里命中的负面词列表，没命中返回空列表"""
    if not text:
        return []
    low = text.lower()
    hit = [w for w in NEGATIVE_WORDS if w in low]
    return hit


# ═══════════════════════════════════════════════
# 情绪计算
# ═══════════════════════════════════════════════

def calculate_emotion(pet: PetState) -> str:
    """四维情绪判断：精力 / 饥饿 / 心情 / 好感"""
    if pet.emotion_locked_until > time.time():
        return pet.emotion
    # 精力见底 → 困倦（人困到不行是藏不住的）
    if pet.energy <= 12:
        return PetEmotion.SLEEPY
    # 饿得不行
    if pet.hunger >= 85:
        return PetEmotion.HUNGRY
    # 又饿又蔫 → 生病感
    if pet.hunger >= 70 and pet.mood < 20:
        return PetEmotion.SICK
    # 心情很低（消极偏多才判定，避免初始0就摆脸）
    if pet.mood <= 5 and pet.mood_scores.get("消极", 0) >= 15:
        return PetEmotion.ANGRY if pet.affection < 40 else PetEmotion.SAD
    if pet.mood <= 15 and pet.mood_scores.get("消极", 0) >= 6:
        return PetEmotion.SAD
    # 吃饱喝足 → 满足（优先于开心，人是先满足再高兴）
    if pet.hunger <= 8:
        return PetEmotion.FULL
    # 心情很高（0基准，实际上限50）
    if pet.mood >= 40:
        if pet.energy >= 60:
            return PetEmotion.EXCITED if pet.affection >= 60 else PetEmotion.HAPPY
        return PetEmotion.HAPPY
    if pet.mood >= 30:
        return PetEmotion.HAPPY
    # 被宠到有恃无恐
    if pet.affection >= 85 and pet.mood >= 28:
        return PetEmotion.SPOILED
    return PetEmotion.NEUTRAL


# ═══════════════════════════════════════════════
# 时间衰减
# ═══════════════════════════════════════════════

def apply_decay(pet: PetState):
    """真实衰减：饿得慢、醒着会累、心情缓慢自我调节、长期冷落会生疏"""
    elapsed_hours = (time.time() - pet.last_interact) / 3600
    if elapsed_hours <= 0.5:
        return
    # 饥饿随时间上升（不会饿太猛）
    pet.hunger = min(100, pet.hunger + int(elapsed_hours * 2))
    # 精力：清醒时自然消耗（人会累），每小时 -1.5
    pet.energy = max(0, pet.energy - int(elapsed_hours * 1.5))
    # 心情：有惯性，作用于心情区，让心情值慢慢向中性(50)回归
    if pet.mood_scores.get("积极", 0) > 35:
        pet.mood_scores["积极"] = max(0, pet.mood_scores["积极"] - int(elapsed_hours * 0.5))
    if pet.mood_scores.get("消极", 0) > 12:
        pet.mood_scores["消极"] = max(0, pet.mood_scores["消极"] - int(elapsed_hours * 0.4))
    # 情绪也会随时间慢慢淡（像人的记忆一样）
    for _c in pet.emotion_scores:
        if pet.emotion_scores[_c] > 0:
            pet.emotion_scores[_c] = max(0, pet.emotion_scores[_c] - int(elapsed_hours * 0.2))
    # 好感：超过3天不互动开始生疏，之后每24小时 -1
    if elapsed_hours > 72:
        pet.affection = max(0, pet.affection - int((elapsed_hours - 72) / 24))
    sync_derived(pet)
    pet.emotion = calculate_emotion(pet)


def interaction_multiplier(pet: PetState, key: str, cooldown: int = 1800,
                           factor: float = 0.7) -> float:
    """边际效应：同一动作在冷却期内重复，心情收益递减（像人一样会腻）"""
    now = time.time()
    last = getattr(pet, "action_log", {}).get(key, 0)
    if now - last < cooldown:
        return factor
    return 1.0


# ═══════════════════════════════════════════════
# 经验值
# ═══════════════════════════════════════════════

def exp_needed(level: int) -> int:
    """升级所需经验，随等级递增（前期轻松、后期越来越难）"""
    n = level - 1
    return 60 + 40 * n + 15 * n * n


def add_exp(pet: PetState, amount: int) -> bool:
    pet.exp += amount
    leveled = False
    while pet.exp >= exp_needed(pet.level) and pet.level < 10:
        pet.exp -= exp_needed(pet.level)
        pet.level += 1
        leveled = True
    return leveled