"""
AI宠物 - 数据持久化存储
"""

import json
import time
from pathlib import Path
from typing import Dict

from .pet_model import PetState, PetEmotion, apply_decay


class PetStorage:
    def __init__(self, data_dir: str, default_pet_name: str = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not default_pet_name:
            from .pet_model import DEFAULT_PET_NAME
            default_pet_name = DEFAULT_PET_NAME
        self.default_pet_name = default_pet_name
        self.pets_file = self.data_dir / "pets.json"
        self._cache: Dict[str, PetState] = {}
        self._load()

    def _load(self):
        if self.pets_file.exists():
            try:
                with open(self.pets_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for uid, pdata in data.items():
                    self._cache[uid] = PetState.from_dict(pdata)
            except (json.JSONDecodeError, KeyError):
                self._cache = {}

    def save(self):
        data = {uid: pet.to_dict() for uid, pet in self._cache.items()}
        with open(self.pets_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get(self, user_id: str) -> PetState:
        if user_id not in self._cache:
            self._cache[user_id] = PetState(user_id, self.default_pet_name)
            self.save()
        pet = self._cache[user_id]
        apply_decay(pet)
        return pet

    def get_all(self) -> Dict[str, PetState]:
        for pet in self._cache.values():
            apply_decay(pet)
        return self._cache

    def rename(self, user_id: str, new_name: str):
        pet = self.get(user_id)
        pet.pet_name = new_name
        self.save()
    def cleanup_inactive(self, days: int = 30) -> list:
        """
        清理超过 days 天未互动的宠物数据，返回被清理的 QQ 号列表。
        防止长期不活跃的数据无限积累占用存储。
        """
        cutoff = time.time() - days * 86400
        removed = []
        for uid in list(self._cache.keys()):
            pet = self._cache[uid]
            if pet.last_interact < cutoff:
                removed.append(uid)
        for uid in removed:
            del self._cache[uid]
        if removed:
            self.save()
        return removed
