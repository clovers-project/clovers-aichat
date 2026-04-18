if not __package__:
    raise RuntimeError("插件路径只能作为模块导入。")
import re
from clovers import Plugin, Result
from clovers_client import Event
from .manager import AIDriver
from .config import Config

# 加载配置
__config = Config.sync_config(__package__)
config_list = __config.config_list
system_prompt = __config.system_prompt
style_prompt = __config.style_prompt
memory = __config.memory
timeout = __config.timeout
AI_DRIVER = AIDriver.from_config(__config.config_list, system_prompt, style_prompt, memory, timeout)
PLUGIN = Plugin[Event](build_result=lambda result: Result("text", result), priority=100)
PLUGIN.protocol = Event
PLUGIN.shutdown(AI_DRIVER.close)

NICKNAME_CLEAN_PATTERN = re.compile(r"[^\u4e00-\u9fa5a-zA-Z\s]")


@PLUGIN.handle(None, ["user_id", "group_id", "nickname", "to_me", "image_list"], rule=lambda e: e.to_me, priority=2, block=False)
async def _(event: Event):
    group_id = event.group_id or f"private:{event.user_id}"
    chat = AI_DRIVER.chat(group_id)
    if chat is None or chat.running:
        return
    text = event.message
    nickname = NICKNAME_CLEAN_PATTERN.sub("", event.nickname) or event.nickname[0]
    chat.running = True
    image_url = event.image_list[0] if event.image_list else None
    result = await chat.chat(nickname, text, image_url)
    chat.running = False
    return result


@PLUGIN.handle(["记忆清除"], ["user_id", "group_id", "to_me", "permission"], rule=lambda e: e.permission > 0, block=True)
async def _(event: Event):
    group_id = event.group_id or f"private:{event.user_id}"
    manager = AI_DRIVER.manager(group_id)
    if manager is not None:
        chat = manager.chat(group_id)
        chat.memory_clear()
        return f"本群【{manager.name} - {chat.name}】记忆已清除！"
