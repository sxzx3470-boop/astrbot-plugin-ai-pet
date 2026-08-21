"""
AI宠物 - 状态卡片渲染器
将宠物状态渲染为文本卡片（适配 QQ 消息）
"""

from pet_model import (
    PetState, EMOTION_EMOJI, EMOTION_CN, LEVEL_NAMES,
    get_level_info, add_exp
)


def bar(value: int, total: int = 100, width: int = 10) -> str:
    """进度条"""
    filled = int(value / total * width)
    return "█" * filled + "░" * (width - filled)


def _progress_bar(value: int, label: str, color: str = "▇") -> str:
    """彩色进度条"""
    pct = value
    b = bar(value, 100, 10)
    return f"  {label}: {b} {pct}%"


def render_pet_card(pet: PetState, title: str = "🐾 宠物状态") -> str:
    """渲染宠物状态卡片"""
    emoji = EMOTION_EMOJI.get(pet.emotion, "😐")
    emotion_cn = EMOTION_CN.get(pet.emotion, "平静")
    level_name = LEVEL_NAMES.get(pet.level, f"⭐ Lv.{pet.level}")
    exp_needed = pet.level * 50

    lines = [
        f"╔══════════════════════════╗",
        f"║     {title}     ║",
        f"╠══════════════════════════╣",
        f"║  {pet.pet_name}  {emoji} {emotion_cn}",
        f"║  {level_name}  Lv.{pet.level}",
        f"║  性格: {pet.personality}",
        f"║  最爱: {pet.favorite_food}",
        f"╠══════════════════════════╣",
        f"║ {_progress_bar(100 - pet.hunger, '饱食度')}",
        f"║ {_progress_bar(pet.affection, '好感度')}",
        f"║ {_progress_bar(pet.mood, '心情值')}",
        f"║ {_progress_bar(pet.energy, '精力值')}",
        f"╠══════════════════════════╣",
        f"║  EXP: {pet.exp}/{exp_needed}",
        f"║  喂食: {pet.total_feed}次 | 互动: {pet.total_pet + pet.total_play}次",
        f"╚══════════════════════════╝",
    ]
    return "\n".join(lines)


def render_mini_card(pet: PetState) -> str:
    """迷你状态卡片"""
    emoji = EMOTION_EMOJI.get(pet.emotion, "😐")
    emotion_cn = EMOTION_CN.get(pet.emotion, "平静")
    return (
        f"🐾 {pet.pet_name} {emoji} {emotion_cn} | "
        f"饱食 {100 - pet.hunger}% | "
        f"好感 {pet.affection}% | "
        f"心情 {pet.mood}% | "
        f"Lv.{pet.level}"
    )


def render_other_card(pet: PetState, owner_name: str) -> str:
    """查看他人宠物卡片"""
    emoji = EMOTION_EMOJI.get(pet.emotion, "😐")
    emotion_cn = EMOTION_CN.get(pet.emotion, "平静")
    level_name = LEVEL_NAMES.get(pet.level, f"⭐ Lv.{pet.level}")

    lines = [
        f"╔══════════════════════════╗",
        f"║   🐾 {owner_name}的宠物   ║",
        f"╠══════════════════════════╣",
        f"║  {pet.pet_name}  {emoji} {emotion_cn}",
        f"║  {level_name}  Lv.{pet.level}",
        f"║  性格: {pet.personality}",
        f"║  最爱: {pet.favorite_food}",
        f"╠══════════════════════════╣",
        f"║ {_progress_bar(100 - pet.hunger, '饱食度')}",
        f"║ {_progress_bar(pet.affection, '好感度')}",
        f"║ {_progress_bar(pet.mood, '心情值')}",
        f"║ {_progress_bar(pet.energy, '精力值')}",
        f"╚══════════════════════════╝",
    ]
    return "\n".join(lines)


def render_feed_result(pet: PetState, food_name: str, food_emoji: str,
                       hunger_change: int, mood_change: int, msg: str) -> str:
    """喂食结果卡片"""
    emoji = EMOTION_EMOJI.get(pet.emotion, "😐")
    emotion_cn = EMOTION_CN.get(pet.emotion, "平静")
    lines = [
        f"{food_emoji} 喂食: {food_name}",
        f"",
        f"🐾 {pet.pet_name} {emoji}",
        f"   {msg}",
        f"",
        f"📊 变化:",
        f"  饱食度 {'+' if hunger_change < 0 else ''}{-hunger_change}%",
        f"  心情值 {'+' if mood_change > 0 else ''}{mood_change}%",
        f"",
        f"当前: 饱食 {100 - pet.hunger}% | 好感 {pet.affection}% | 心情 {pet.mood}%",
    ]
    return "\n".join(lines)


def render_interact_result(pet: PetState, action_name: str, action_emoji: str,
                           msg: str, affection_change: int = 0,
                           mood_change: int = 0) -> str:
    """互动结果卡片"""
    emoji = EMOTION_EMOJI.get(pet.emotion, "😐")
    emotion_cn = EMOTION_CN.get(pet.emotion, "平静")
    parts = [f"{msg}"]
    if affection_change:
        parts.append(f"好感度 {'+' if affection_change > 0 else ''}{affection_change}")
    if mood_change:
        parts.append(f"心情值 {'+' if mood_change > 0 else ''}{mood_change}")
    changes = " | ".join(parts)
    lines = [
        f"{action_emoji} 互动: {action_name}",
        f"",
        f"🐾 {pet.pet_name} {emoji} {emotion_cn}",
        f"   {changes}",
        f"",
        f"当前: 饱食 {100 - pet.hunger}% | 好感 {pet.affection}% | 心情 {pet.mood}%",
    ]
    return "\n".join(lines)


def render_level_up(pet: PetState) -> str:
    """升级卡片"""
    level_name = LEVEL_NAMES.get(pet.level, f"⭐ Lv.{pet.level}")
    return (
        f"🎉 {pet.pet_name} 升级了！\n"
        f"   现在等级: {level_name} Lv.{pet.level}\n"
        f"   继续加油哦～"
    )


def render_help() -> str:
    """帮助信息"""
    return """🐾 AI宠物养成 - 帮助

📋 基础命令:
  /pet 或 /宠物状态     查看你的宠物状态
  /pet help             显示此帮助

🍽️ 喂食:
  /喂食 <食物>          喂宠物吃东西
  可选食物: 苹果、蛋糕、寿司、冰淇淋、肉、饼干、牛奶、鱼、糖果、蔬菜

✋ 互动:
  /抚摸                  抚摸宠物
  /抱抱                  抱抱宠物
  /玩耍                  和宠物玩耍
  /聊天                  和宠物聊天
  /训练                  训练宠物

🔍 查看他人:
  /宠物状态 @某人        查看某人的宠物

💡 提示:
  - 宠物会随时间变饿、心情变差
  - 喂食增加饱食度，互动增加好感度
  - 好感度高了宠物会更粘人
  - 积累经验可以升级，解锁新称号"""