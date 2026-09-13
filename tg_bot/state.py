from typing import Dict, List
from datetime import datetime
from .config import MAIN_ADMIN_ID   # это правильно, это наш файл config.py

messages_queue: List[dict] = []


pending_approvals: Dict[int, dict] = {}


user_reputation: Dict[int, int] = {}

user_blocks: Dict[int, float] = {}

# Кто сейчас админ
admins_list: List[int] = [MAIN_ADMIN_ID]

admin_access_attempts: Dict[int, int] = {}


published_messages: List[dict] = []


rejected_messages: List[dict] = []
