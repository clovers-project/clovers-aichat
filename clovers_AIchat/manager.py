import httpx
from pathlib import Path
from pydantic import BaseModel
from clovers.logger import logger
from .core import AIChat, ChatInterface
from .ai.mix import Chat as MixChat
from .ai.openai import Chat as OpenAIChat
from .ai.hunyuan import Chat as HunYuanChat
from .ai.gemini import Chat as GeminiChat


def matchChat(key: str) -> tuple[type[ChatInterface], str]:
    match key:
        case "chatgpt":
            return OpenAIChat, "ChatGPT"
        case "qwen":
            return OpenAIChat, "通义千问"
        case "deepseek":
            return OpenAIChat, "DeepSeek"
        case "hunyuan":
            return HunYuanChat, "腾讯混元"
        case "gemini":
            return GeminiChat, "Gemini"
        case _:
            from importlib import import_module

            Chat = getattr(import_module(".".join(Path(key.rstrip(".py")).relative_to(Path()).parts)), "Chat", None)
            if Chat and issubclass(Chat, ChatInterface):
                return Chat, key
            raise ValueError(f"不支持的模型:{key}")


class ManagerInfo:
    """实例设置"""

    whitelist: set[str] = set()
    """白名单"""
    blacklist: set[str] = set()
    """黑名单"""
    proxy: str | None = None
    """代理地址"""


class ManagerConfig(ManagerInfo, BaseModel):
    pass


class MixManagerConfig(ManagerInfo, BaseModel):
    text: dict
    image: dict


class Manager(ManagerInfo):
    """实例运行管理类"""

    name: str
    """实例名称"""

    def __init__(self, config: dict) -> None:
        self.chats: dict[str, AIChat] = {}
        self.config = config
        if config["key"] == "mix":
            _config = MixManagerConfig.model_validate(config)
            self.async_client = httpx.AsyncClient(proxy=_config.proxy, timeout=60.0)
            ChatText, ChatTextName = matchChat(_config.text["key"])
            chat_text = ChatText(config | _config.text, self.async_client)
            ChatImage, ChatImageName = matchChat(_config.image["key"])
            chat_image = ChatImage(config | _config.image, self.async_client)
            self.name = f"Mix({ChatTextName},{ChatImageName})"
            self.newChat = lambda: MixChat(_config.whitelist, _config.blacklist, chat_text, chat_image)
        else:
            _config = ManagerConfig.model_validate(config)
            self.async_client = httpx.AsyncClient(proxy=_config.proxy, timeout=60.0)
            newChat, self.name = matchChat(config["key"])
            self.newChat = lambda: newChat(self.config, self.async_client)
        self.whitelist = _config.whitelist
        self.blacklist = _config.blacklist

    def chat(self, group_id: str):
        if group_id not in self.chats:
            self.chats[group_id] = self.newChat()
        return self.chats[group_id]

    def check(self, group_id: str) -> bool:
        raise NotImplementedError("check 方法未注入，请在创建实例时设置 check 方法")

    def none_check(self, group_id: str) -> bool:
        return True

    def whitelist_check(self, group_id: str) -> bool:
        return group_id in self.whitelist

    def blacklist_check(self, group_id: str) -> bool:
        return group_id not in self.blacklist


class AIDriver:
    def __init__(self, system_prompt: str, style_prompt: str, memory: int, timeout: int):
        self.managers: list[Manager] = []
        self.system_prompt = system_prompt
        self.style_prompt = style_prompt
        self.memory = memory
        self.timeout = timeout

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

    @classmethod
    def from_config(cls, config_list: list[dict], system_prompt: str, style_prompt: str, memory: int, timeout: int) -> "AIDriver":
        self = cls(system_prompt, style_prompt, memory, timeout)
        for config_unit in config_list:
            manager_config = {
                "system_prompt": self.system_prompt,
                "style_prompt": self.style_prompt,
                "memory": self.memory,
                "timeout": self.timeout,
            }
            manager_config.update(config_unit)
            try:
                self.add_manager(Manager(manager_config))
            except Exception as e:
                logger.exception(e)
                logger.debug(config_unit)
        return self
