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
    "pet":   {"name": "抚摸", "emoji": "✋", "affection": +5, "mood": +8, "msg": "被{}摸了一下，舒服地眯起了眼睛"},
    "hug":   {"name": "抱抱", "emoji": "🤗", "affection": +8, "mood": +10, "msg": "被{}抱在怀里，开心地蹭了蹭"},
    "play":  {"name": "玩耍", "emoji": "🎾", "affection": +6, "mood": +12, "energy": -10, "msg": "和{}一起玩耍，跑来跑去好开心！"},
    "talk":  {"name": "聊天", "emoji": "💬", "affection": +3, "mood": +5, "msg": "听{}说了好多话，虽然不太懂但是很认真在听"},
    "train": {"name": "训练", "emoji": "🎯", "affection": +4, "mood": +3, "exp": +10, "msg": "跟{}学习新技能，学得可认真了！"},
}

FOODS = {
    "苹果":   {"emoji": "🍎", "hunger": -15, "mood": +5,  "msg": "吃了一个苹果，脆脆甜甜的"},
    "蛋糕":   {"emoji": "🍰", "hunger": -25, "mood": +10, "msg": "吃了一块蛋糕，好甜好好吃！"},
    "寿司":   {"emoji": "🍣", "hunger": -20, "mood": +8,  "msg": "吃了一份寿司，新鲜美味"},
    "冰淇淋": {"emoji": "🍦", "hunger": -10, "mood": +15, "msg": "吃了一个冰淇淋，凉凉的，好开心！"},
    "肉":     {"emoji": "🥩", "hunger": -30, "mood": +5,  "msg": "吃了一块肉，大满足！"},
    "饼干":   {"emoji": "🍪", "hunger": -12, "mood": +8,  "msg": "吃了一块饼干，酥酥脆脆"},
    "牛奶":   {"emoji": "🥛", "hunger": -8,  "mood": +3,  "msg": "喝了一杯牛奶，暖暖的"},
    "鱼":     {"emoji": "🐟", "hunger": -18, "mood": +7,  "msg": "吃了一条鱼，鲜美可口"},
    "糖果":   {"emoji": "🍬", "hunger": -5,  "mood": +12, "msg": "吃了一颗糖果，甜滋滋的～"},
    "蔬菜":   {"emoji": "🥬", "hunger": -10, "mood": -2,  "msg": "吃了一堆蔬菜...虽然不太喜欢但是健康！"},
}

# ═══════════════════════════════════════════════
# 等级系统
# ═══════════════════════════════════════════════

LEVEL_NAMES = {
    1: "🥚 宠物蛋", 2: "🐣 幼崽", 3: "🐥 成长期",
    4: "🦊 青年期", 5: "🐺 成熟期", 6: "🦁 巅峰期",
    7: "🐉 传说级", 8: "🌟 史诗级", 9: "💫 神话级",
    10: "👑 至尊级",
}

PERSONALITIES = ["活泼", "温柔", "傲娇", "粘人", "贪吃", "慵懒"]
FAVORITE_FOODS = ["🍎苹果", "🍰蛋糕", "🍣寿司", "🍦冰淇淋", "🥩肉", "🍪饼干"]
COLORS = ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD", "#FF9FF3"]


# ═══════════════════════════════════════════════
# 宠物状态模型
# ═══════════════════════════════════════════════

class PetState:
    def __init__(self, owner_id: str, pet_name: str = "小宠物"):
        self.owner_id = owner_id
        self.pet_name = pet_name
        self.hunger = 80
        self.affection = 50
        self.energy = 70
        self.mood = 50
        self.emotion = PetEmotion.NEUTRAL
        self.emotion_locked_until = 0
        self.total_feed = 0
        self.total_pet = 0
        self.total_play = 0
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
            "emotion": self.emotion, "emotion_locked_until": self.emotion_locked_until,
            "total_feed": self.total_feed, "total_pet": self.total_pet,
            "total_play": self.total_play, "last_interact": self.last_interact,
            "created_at": self.created_at, "level": self.level, "exp": self.exp,
            "personality": self.personality, "favorite_food": self.favorite_food,
            "color": self.color,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PetState":
        pet = cls(data["owner_id"], data.get("pet_name", "小宠物"))
        for k in ["hunger","affection","energy","mood","emotion","emotion_locked_until",
                   "total_feed","total_pet","total_play","last_interact","created_at",
                   "level","exp","personality","favorite_food","color"]:
            if k in data:
                setattr(pet, k, data[k])
        return pet


# ═══════════════════════════════════════════════
# 情绪计算
# ═══════════════════════════════════════════════

def calculate_emotion(pet: PetState) -> str:
    if pet.emotion_locked_until > time.time():
        return pet.emotion
    if pet.hunger >= 90:
        return PetEmotion.HUNGRY
    if pet.hunger >= 70:
        return PetEmotion.SAD if pet.mood < 30 else PetEmotion.NEUTRAL
    if pet.energy <= 10:
        return PetEmotion.SLEEPY
    if pet.mood >= 80:
        return PetEmotion.HAPPY
    if pet.mood >= 60:
        return PetEmotion.EXCITED if pet.affection >= 70 else PetEmotion.HAPPY
    if pet.mood <= 20:
        return PetEmotion.SICK if pet.hunger >= 60 else PetEmotion.SAD
    if pet.mood <= 40:
        return PetEmotion.ANGRY if pet.affection <= 30 else PetEmotion.SAD
    if pet.affection >= 80:
        return PetEmotion.SPOILED
    if pet.hunger <= 10:
        return PetEmotion.FULL
    return PetEmotion.NEUTRAL


# ═══════════════════════════════════════════════
# 时间衰减
# ═══════════════════════════════════════════════

def apply_decay(pet: PetState):
    elapsed_hours = (time.time() - pet.last_interact) / 3600
    if elapsed_hours > 0.5:
        pet.hunger = min(100, pet.hunger + int(elapsed_hours * 5))
        pet.mood = max(0, pet.mood - int(elapsed_hours * 3))
        pet.energy = min(100, pet.energy + int(elapsed_hours * 2))
    pet.emotion = calculate_emotion(pet)


# ═══════════════════════════════════════════════
# 经验值
# ═══════════════════════════════════════════════

def add_exp(pet: PetState, amount: int) -> bool:
    pet.exp += amount
    needed = pet.level * 50
    if pet.exp >= needed and pet.level < 10:
        pet.exp -= needed
        pet.level += 1
        return True
    return False