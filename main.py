"""
AI宠物养成插件 - AstrBot 插件入口
===============================

功能:
  - 喂食、抚摸、抱抱、玩耍、聊天、训练
  - 好感度、情绪、饥饿度、饱食度系统
  - 状态卡片展示（自己 / 他人）
  - 多用户独立宠物，数据持久化
  - 时间衰减：宠物会随时间变饿、心情变差
  - 等级系统：互动积累经验，解锁新称号

用法:
  /pet             查看宠物状态
  /宠物状态         查看宠物状态（别名）
  /喂食 <食物>      喂宠物
  /抚摸             抚摸宠物
  /抱抱             抱抱宠物
  /玩耍             和宠物玩耍
  /聊天             和宠物聊天
  /训练             训练宠物
  /宠物状态 @某人   查看某人的宠物
  /pet help        帮助信息
"""

from astrbot.api import AstrBotPlugin, Command, MessageEvent, CommandResult
from astrbot.api.message import MessageChain, Plain

from pet_model import (
    PetState, PetEmotion, EMOTION_EMOJI, EMOTION_CN,
    INTERACTIONS, FOODS, LEVEL_NAMES, add_exp, apply_decay, calculate_emotion
)
from pet_card import (
    render_pet_card, render_mini_card, render_other_card,
    render_feed_result, render_interact_result, render_level_up, render_help
)
from pet_storage import PetStorage


class AiPetPlugin(AstrBotPlugin):
    def __init__(self, context):
        super().__init__(context)
        self.storage = PetStorage("data/ai_pet")

    # ── 查看宠物状态 ──

    @Command("pet", "宠物状态")
    async def pet_status(self, event: MessageEvent) -> CommandResult:
        """查看自己或他人的宠物状态"""
        msg = event.get_message_str()
        args = self._parse_args(msg)

        if "help" in args:
            return CommandResult().message(render_help())

        pet = self.storage.get(event.user_id)
        return CommandResult().message(render_pet_card(pet, "🐾 宠物状态"))

    # ── 喂食 ──

    @Command("喂食")
    async def feed(self, event: MessageEvent) -> CommandResult:
        """喂宠物吃东西"""
        msg = event.get_message_str()
        # 提取食物名
        food_name = msg.replace("/喂食", "").strip()

        if not food_name:
            # 没有指定食物，列出可选食物
            food_list = "\n".join(
                f"  {v['emoji']} {k} (饱食 {abs(v['hunger'])} | 心情 {v['mood']:+d})"
                for k, v in FOODS.items()
            )
            return CommandResult().message(
                f"🍽️ 请选择要喂的食物:\n{food_list}\n\n用法: /喂食 <食物名>"
            )

        # 模糊匹配食物
        matched = self._match_food(food_name)
        if not matched:
            return CommandResult().message(
                f"❌ 没有找到「{food_name}」这种食物\n"
                f"可选: {'、'.join(FOODS.keys())}"
            )

        food_key, food_info = matched
        pet = self.storage.get(event.user_id)

        # 应用喂食效果
        pet.hunger = max(0, pet.hunger + food_info["hunger"])
        pet.mood = min(100, pet.mood + food_info["mood"])
        pet.total_feed += 1
        pet.last_interact = __import__("time").time()

        # 吃最爱食物额外加成
        bonus_msg = ""
        if food_key in pet.favorite_food:
            pet.affection = min(100, pet.affection + 5)
            bonus_msg = f"\n💕 这是{pet.pet_name}最爱的食物！好感度 +5"

        # 升级
        level_up = add_exp(pet, 5)
        pet.emotion = calculate_emotion(pet)
        self.storage.save()

        result = render_feed_result(
            pet, food_key, food_info["emoji"],
            food_info["hunger"], food_info["mood"],
            food_info["msg"].format("主人")
        )
        if bonus_msg:
            result += bonus_msg
        if level_up:
            result += "\n\n" + render_level_up(pet)

        return CommandResult().message(result)

    # ── 互动动作 ──

    @Command("抚摸")
    async def pet_action(self, event: MessageEvent) -> CommandResult:
        return await self._do_interact(event, "pet")

    @Command("抱抱")
    async def hug_action(self, event: MessageEvent) -> CommandResult:
        return await self._do_interact(event, "hug")

    @Command("玩耍")
    async def play_action(self, event: MessageEvent) -> CommandResult:
        return await self._do_interact(event, "play")

    @Command("聊天")
    async def talk_action(self, event: MessageEvent) -> CommandResult:
        return await self._do_interact(event, "talk")

    @Command("训练")
    async def train_action(self, event: MessageEvent) -> CommandResult:
        return await self._do_interact(event, "train")

    async def _do_interact(self, event: MessageEvent, action_key: str) -> CommandResult:
        """执行互动动作"""
        action = INTERACTIONS[action_key]
        pet = self.storage.get(event.user_id)

        # 应用互动效果
        pet.affection = min(100, pet.affection + action.get("affection", 0))
        pet.mood = min(100, pet.mood + action.get("mood", 0))
        if "energy" in action:
            pet.energy = max(0, pet.energy + action["energy"])

        # 统计
        if action_key == "pet":
            pet.total_pet += 1
        elif action_key in ("play", "train"):
            pet.total_play += 1

        # 时间戳
        pet.last_interact = __import__("time").time()

        # 经验
        exp_gain = action.get("exp", 3)
        level_up = add_exp(pet, exp_gain)
        pet.emotion = calculate_emotion(pet)
        self.storage.save()

        result = render_interact_result(
            pet, action["name"], action["emoji"],
            action["msg"].format("主人"),
            affection_change=action.get("affection", 0),
            mood_change=action.get("mood", 0),
        )
        if level_up:
            result += "\n\n" + render_level_up(pet)

        return CommandResult().message(result)

    # ── 辅助方法 ──

    def _match_food(self, name: str):
        """模糊匹配食物名"""
        name_lower = name.lower()
        for k, v in FOODS.items():
            if k == name or k in name or name in k:
                return k, v
        return None

    def _parse_args(self, msg: str) -> list:
        """解析命令参数"""
        parts = msg.strip().split()
        return parts[1:] if len(parts) > 1 else []


# ═══════════════════════════════════════════════
# 插件入口
# ═══════════════════════════════════════════════

def create_plugin(context):
    """AstrBot 插件工厂函数"""
    return AiPetPlugin(context)