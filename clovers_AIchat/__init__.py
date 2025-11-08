import re
from clovers import Plugin, Result
from clovers.logger import logger
from .manager import Manager
from .clovers import Event
from clovers.config import Config as CloversConfig
from .config import Config

config_data = CloversConfig.environ().setdefault(__package__, {})
__config__ = Config.model_validate(config_data)
config_data.update(__config__.model_dump())


class AIDriver:
    def __init__(self):
        self.managers: list[Manager] = []

    def add_manager(self, manager: Manager):
        if manager.whitelist:
            logger.info(f"{manager.name} 检查规则设置为白名单模式：{manager.whitelist}")
            manager.check = manager.whitelist_check
        elif manager.blacklist:
            logger.info(f"{manager.name} 检查规则设置为黑名单模式：{manager.blacklist}")
            manager.check = manager.blacklist_check
        else:
            logger.info(f"{manager.name} 未设置黑白名单，已在全部群组启用")
            manager.check = manager.none_check
        self.managers.append(manager)

    def chat(self, group_id: str):
        manager = self.manager(group_id)
        if manager:
            return manager.chat(group_id)

    def manager(self, group_id: str):
        for manager in self.managers:
            if manager.check(group_id):
                return manager

    async def close(self):
        for manager in self.managers:
            await manager.async_client.aclose()
        self.managers.clear()


AI_driver = AIDriver()


for _config in __config__.config_list:

    manager_config = {
        "system_prompt": __config__.system_prompt,
        "style_prompt": __config__.style_prompt,
        "memory": __config__.memory,
        "timeout": __config__.timeout,
    }
    manager_config.update(_config)
    try:
        AI_driver.add_manager(Manager(manager_config))
    except Exception as e:
        logger.exception(e)
        logger.debug(_config)

pattern = re.compile(r"[^\u4e00-\u9fa5a-zA-Z\s]")

plugin = Plugin(build_result=lambda result: Result("text", result), priority=100)
plugin.set_protocol("properties", Event)
plugin.shutdown(AI_driver.close)

type Rule = Plugin.Rule.Checker[Event]

permission_check: Rule = lambda e: e.permission > 0
to_me: Rule = lambda e: e.to_me


@plugin.handle(["记忆清除"], ["user_id", "group_id", "to_me", "permission"], rule=permission_check, block=True)
async def _(event: Event):
    group_id = event.group_id or f"private:{event.user_id}"
    manager = AI_driver.manager(group_id)
    if manager is not None:
        chat = manager.chat(group_id)
        chat.memory_clear()
        return f"本群【{manager.name} - {chat.name}】记忆已清除！"


@plugin.handle(["修改设定"], ["user_id", "group_id", "to_me", "permission"], rule=permission_check, block=True)
async def _(event: Event):
    group_id = event.group_id or f"private:{event.user_id}"
    manager = AI_driver.manager(group_id)
    if manager is None:
        return
    style_prompt = event.message[4:]
    chat = manager.chat(group_id)
    if style_prompt:
        chat.memory_clear()
        chat.style_prompt = style_prompt
        return f"本群【{manager.name} - {chat.name}】设定已修改！"
    else:
        del manager.chats[group_id]
        return f"本群【{manager.name} - {chat.name}】设定已重置！"


@plugin.handle(None, ["user_id", "group_id", "nickname", "to_me", "image_list"], rule=to_me, priority=2, block=False)
async def _(event: Event):
    group_id = event.group_id or f"private:{event.user_id}"
    chat = AI_driver.chat(group_id)
    if chat is None or chat.running:
        return
    text = event.message
    nickname = pattern.sub("", event.nickname) or event.nickname[0]
    chat.running = True
    image_url = event.image_list[0] if event.image_list else None
    result = await chat.chat(nickname, text, image_url)
    chat.running = False
    return result


__plugin__ = plugin
