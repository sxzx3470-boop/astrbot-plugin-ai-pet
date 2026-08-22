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
  /宠物状态           查看宠物状态
  /pet                查看宠物状态（别名）
  /喂食 <食物>         喂宠物
  /抚摸               抚摸宠物
  /抱抱               抱抱宠物
  /玩耍               和宠物玩耍
  /聊天               和宠物聊天
  /训练               训练宠物
  /宠物状态 help       帮助信息
"""

import asyncio
import random
import logging
import re
import time
import os

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, StarTools

logger = logging.getLogger("AiPet")

from .pet_model import (
    PetState, PetEmotion, EMOTION_EMOJI, EMOTION_CN,
    INTERACTIONS, FOODS, LEVEL_NAMES, add_exp, apply_decay, calculate_emotion, interaction_multiplier,
    check_negative, NEGATIVE_WORDS, record_emotion, sync_derived
)

# 负面词正则（记仇功能用）
_NEG_REGEX = "|".join(re.escape(w) for w in NEGATIVE_WORDS)
from .pet_card import (
    render_pet_card, render_mini_card, render_other_card,
    render_feed_result, render_interact_result, render_level_up, render_help
)
from .pet_card_image import render_pet_card_image, render_relation_image
from .pet_storage import PetStorage


class AiPetPlugin(Star):
    def __init__(self, context: Context, config=None):
        super().__init__(context)
        config = config or {}
        data_dir = StarTools.get_data_dir("astrbot_plugin_ai_pet")
        self.storage = PetStorage(
            str(data_dir),
            default_pet_name=config.get("default_pet_name"),
        )
        self._img_dir = str(data_dir) + "/cards"
        self._avatar_path = str(data_dir) + "/avatar.png"
        # 是否允许用户给宠物改名（部署者可在配置里关掉）
        self._allow_rename = bool(config.get("allow_rename", True))
        # 自动清理：超过 N 天未互动的数据会在每日清理任务中被删除
        self._cleanup_days = int(config.get("cleanup_days", 30))
        self._cleanup_task = None

    async def initialize(self) -> None:
        """插件加载后启动每日数据清理任务"""
        old = getattr(self, "_cleanup_task", None)
        if old and not old.done():
            old.cancel()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def terminate(self) -> None:
        if getattr(self, "_cleanup_task", None):
            self._cleanup_task.cancel()

    async def _cleanup_loop(self):
        """每日定时清理不活跃的宠物存档"""
        while True:
            try:
                removed = self.storage.cleanup_inactive(days=self._cleanup_days)
                if removed:
                    logger.info("[AiPet] 自动清理了 %d 个超过 %d 天未互动的存档",
                                len(removed), self._cleanup_days)
            except Exception as e:
                logger.warning("[AiPet] 自动清理异常: %s", e)
            try:
                await asyncio.sleep(86400)  # 每 24 小时执行一次
            except asyncio.CancelledError:
                break

    # ── 查看宠物状态 ──

    @filter.regex(r"^(?:/)?\s*(?:宠物状态|状态)(?:\s|$)")
    async def pet_status(self, event: AstrMessageEvent):
        """查看自己或他人的宠物状态"""
        msg = event.get_message_str()
        args = self._parse_args(msg)

        if "help" in args:
            pet = self.storage.get(event.get_sender_id())
            yield event.plain_result(render_help(pet.pet_name))
            return

        pet = self.storage.get(event.get_sender_id())
        img_path = render_pet_card_image(pet, "我的宠物", self._img_dir, self._avatar_path)
        yield event.image_result(img_path)

    # ── pet：显示所有指令 ──

    @filter.regex(r"^(?:/)?\s*pet(?:\s|$)")
    async def pet_help(self, event: AstrMessageEvent):
        """输入 pet 显示所有指令"""
        pet = self.storage.get(event.get_sender_id())
        yield event.plain_result(render_help(pet.pet_name))

    # ── 给宠物改名字 ──

    @filter.regex(r"^(?:/)?\s*(?:改名|宠物改名)(?:\s|$)")
    async def rename_pet(self, event: AstrMessageEvent):
        """每个用户都可以给自己的宠物改名字"""
        if not self._allow_rename:
            yield event.plain_result("管理员关闭了改名功能哦")
            return
        msg = event.get_message_str()
        new_name = re.sub(r"^(?:/)?\s*(?:改名|宠物改名)", "", msg).strip()
        if not new_name:
            yield event.plain_result("用法: /改名 <新名字>\n比如: /改名 汤圆")
            return
        if len(new_name) > 12:
            yield event.plain_result("名字太长啦，12 个字以内吧～")
            return
        uid = event.get_sender_id()
        pet = self.storage.get(uid)
        old = pet.pet_name
        self.storage.rename(uid, new_name)
        yield event.plain_result(f"好呀，以后就叫你{new_name}啦（{old} → {new_name}）")

    # ── 查看对某人的好感 ──

    @filter.regex(r"^(?:/)?\s*(?:好感|好感度|亲密度)(?:\s|$)")
    async def relation(self, event: AstrMessageEvent):
        """查看宠物对某人的好感度、情绪值和相处统计"""
        target_uid, target_name = self._resolve_target(event)
        pet = self.storage.get(target_uid)
        avatar = self._fetch_avatar(target_uid)
        img_path = render_relation_image(pet, target_name, self._img_dir, avatar)
        yield event.image_result(img_path)

    # ── 喂食 ──

    @filter.regex(r"^(?:/)?\s*喂食(?:\s|$)")
    async def feed(self, event: AstrMessageEvent):
        """喂宠物吃东西"""
        msg = event.get_message_str()
        # 提取食物名（兼容带/不带斜杠）
        food_name = re.sub(r"^(?:/)?\s*喂食", "", msg).strip()

        if not food_name:
            # 没有指定食物，列出可选食物
            food_list = "\n".join(
                f"  {k} (饱食 {abs(v['hunger'])} | 心情 {v['mood']:+d})"
                for k, v in FOODS.items()
            )
            yield event.plain_result(
                f"🍽️ 请选择要喂的食物:\n{food_list}\n\n用法: /喂食 <食物名>"
            )
            return

        # 模糊匹配食物
        matched = self._match_food(food_name)
        if not matched:
            yield event.plain_result(
                f"❌ 没有找到「{food_name}」这种食物\n"
                f"可选: {'、'.join(FOODS.keys())}"
            )
            return

        food_key, food_info = matched
        pet = self.storage.get(event.get_sender_id())

        # 应用喂食效果（同一食物短时间反复喂会腻，心情收益递减）
        _mult = interaction_multiplier(pet, f"food_{food_key}")
        _mood_gain = int(food_info["mood"] * _mult)
        pet.hunger = max(0, pet.hunger + food_info["hunger"])
        pet.mood_scores["积极"] = min(50, pet.mood_scores.get("积极", 0) + _mood_gain)
        pet.action_log[f"food_{food_key}"] = time.time()
        pet.total_feed += 1
        pet.last_interact = __import__("time").time()

        # 吃最爱食物额外加成
        bonus_msg = ""
        # 情绪记录：吃东西 → 快乐/积极；吃到最爱 → 惊喜
        record_emotion(pet, ["快乐"], "积极")
        if food_key in pet.favorite_food:
            pet.affection = min(100, pet.affection + 5)
            record_emotion(pet, ["惊讶"])
            bonus_msg = f"\n💕 这是{pet.pet_name}最爱的食物！好感度 +5"

        # 升级
        level_up = add_exp(pet, 5)
        sync_derived(pet)
        pet.emotion = calculate_emotion(pet)
        self.storage.save()

        reply = food_info["msg"].format("主人")
        if bonus_msg:
            reply += "\n" + bonus_msg
        reply += "\n饱食度 {:d}%  |  心情值 {:d}%".format(
            food_info["hunger"], _mood_gain)
        if level_up:
            reply += "\n" + render_level_up(pet)
        yield event.plain_result(reply)

    # ── 互动动作 ──

    @filter.regex(r"^(?:/)?\s*抚摸(?:\s|$)")
    async def pet_action(self, event: AstrMessageEvent):
        yield await self._do_interact(event, "pet")

    @filter.regex(r"^(?:/)?\s*抱抱(?:\s|$)")
    async def hug_action(self, event: AstrMessageEvent):
        yield await self._do_interact(event, "hug")

    @filter.regex(r"^(?:/)?\s*玩耍(?:\s|$)")
    async def play_action(self, event: AstrMessageEvent):
        yield await self._do_interact(event, "play")

    @filter.regex(r"^(?:/)?\s*睡觉(?:\s|$)")
    async def sleep_action(self, event: AstrMessageEvent):
        yield await self._do_interact(event, "sleep")

    @filter.regex(r"^(?:/)?\s*训练(?:\s|$)")
    async def train_action(self, event: AstrMessageEvent):
        yield await self._do_interact(event, "train")

    @filter.regex(r"^(?:/)?\s*醒来(?:\s|$)")
    async def wake_action(self, event: AstrMessageEvent):
        yield await self._do_interact(event, "wake")

    async def _do_interact(self, event: AstrMessageEvent, action_key: str):
        """执行互动动作"""
        action = INTERACTIONS[action_key]
        pet = self.storage.get(event.get_sender_id())

        # 应用互动效果（同一动作反复做会腻，心情收益递减；好感靠真心累积不受影响）
        _mult = interaction_multiplier(pet, action_key)
        _mood_gain = int(action.get("mood", 0) * _mult)
        pet.affection = min(100, pet.affection + action.get("affection", 0))
        pet.mood_scores["积极"] = min(50, pet.mood_scores.get("积极", 0) + _mood_gain)
        pet.action_log[action_key] = time.time()
        if "energy" in action:
            pet.energy = max(0, min(100, pet.energy + action["energy"]))

        # 情绪记录：互动带来快乐/积极心情
        _emo_map = {
            "pet": (["快乐"], "积极"),
            "hug": (["快乐"], "积极"),
            "play": (["快乐"], "积极"),
            "sleep": ([], "积极"),
            "wake": (["快乐"], "积极"),
            "train": (["快乐"], "积极"),
        }
        _cats, _pol = _emo_map.get(action_key, ([], None))
        record_emotion(pet, _cats, _pol)
        if action_key == "play" and random.random() < 0.15:
            record_emotion(pet, ["惊讶"])

        # 统计
        pet.total_interact += 1
        if action_key == "pet":
            pet.total_pet += 1
        elif action_key in ("play", "train"):
            pet.total_play += 1

        # 时间戳
        pet.last_interact = __import__("time").time()

        # 经验
        exp_gain = action.get("exp", 3)
        level_up = add_exp(pet, exp_gain)
        sync_derived(pet)
        pet.emotion = calculate_emotion(pet)
        self.storage.save()

        if action_key == "sleep":
            # 按时间说午安/晚安
            _hour = int(__import__("time").strftime("%H"))
            _greet = "午安" if 6 <= _hour < 18 else "晚安"
            reply = f"和主人说{_greet}，钻进被窝呼呼大睡，美美休息了一觉～"
        else:
            reply = action["msg"].format("主人")
        reply += "\n好感度 {:+d}  |  心情值 {:+d}".format(
            action.get("affection", 0), _mood_gain
        )
        if "energy" in action:
            reply += "  |  精力 {:+d}".format(action["energy"])
        if level_up:
            reply += "\n" + render_level_up(pet)
        return event.plain_result(reply)

    # ── 记仇：检测到负面词自动掉好感/心情 ──

    @filter.regex(_NEG_REGEX)
    async def on_negative_message(self, event: AstrMessageEvent):
        try:
            uid = event.get_sender_id()
            pet = self.storage.get(uid)
            # 每个人10秒内只记一次，避免刷屏连扣
            now = time.time()
            last = getattr(pet, "_last_negative", 0)
            if now - last < 10:
                return
            pet._last_negative = now
            pet.affection = max(0, pet.affection - 2)
            pet.mood_scores["消极"] = min(50, pet.mood_scores.get("消极", 0) + 3)
            sync_derived(pet)
            # 情绪记录：被骂 → 愤怒/悲伤/恐惧 + 消极心情；连骂会厌恶
            if pet.mood >= 35:
                record_emotion(pet, ["愤怒"], "消极")
            elif pet.mood <= 8:
                record_emotion(pet, ["恐惧"], "消极")
            else:
                record_emotion(pet, ["悲伤"], "消极")
            if now - last < 30:
                record_emotion(pet, ["厌恶"])
            pet.emotion = calculate_emotion(pet)
            self.storage.save()
            yield event.plain_result(
                f"……听到有人这么说，心情一下就down了。好感度-2，心情-3"
            )
        except Exception:
            logger.exception("记仇逻辑异常")

    # ── 辅助方法 ──

    def _match_food(self, name: str):
        """模糊匹配食物名"""
        name_lower = name.lower()
        for k, v in FOODS.items():
            if k == name or k in name or name in k:
                return k, v
        return None

    def _fetch_avatar(self, uid: str):
        """实时获取目标用户的QQ头像，本地缓存10分钟；失败回退到默认头像"""
        import urllib.request
        if not uid:
            return self._avatar_path
        cache_dir = os.path.join(self._img_dir, "avatars")
        os.makedirs(cache_dir, exist_ok=True)
        cache = os.path.join(cache_dir, f"{uid}.jpg")
        if os.path.exists(cache) and os.path.getsize(cache) > 512 \
                and time.time() - os.path.getmtime(cache) < 600:
            return cache
        url = f"https://q1.qlogo.cn/g?b=qq&nk={uid}&s=640"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = r.read()
            if data and len(data) > 512:
                with open(cache, "wb") as f:
                    f.write(data)
                return cache
        except Exception:
            pass
        return self._avatar_path

    def _resolve_target(self, event: AstrMessageEvent):
        """解析命令@的目标；没@或@的是机器人自己 → 返回自己"""
        try:
            from astrbot.core.message.components import At, AtAll
        except ImportError:
            return event.get_sender_id(), event.get_sender_name()
        self_uid = str(event.get_self_id() or "")
        for comp in event.get_messages():
            if isinstance(comp, At) and not isinstance(comp, AtAll):
                uid = str(comp.qq)
                if uid == "all" or (self_uid and uid == self_uid):
                    continue
                name = comp.name or "ta"
                return uid, name
        return event.get_sender_id(), event.get_sender_name()

    def _parse_args(self, msg: str) -> list:
        """解析命令参数"""
        parts = msg.strip().split()
        return parts[1:] if len(parts) > 1 else []
