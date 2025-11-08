import httpx
from datetime import datetime
from abc import ABC, abstractmethod
from typing import TypedDict, Literal, Iterable, NotRequired
from logging import getLogger
from collections import deque

logger = getLogger("AICHAT")


class AIChat(ABC):
    """对话模型"""

    def __init__(self) -> None:
        self.running: bool = False
        self.style_prompt: str

    @abstractmethod
    async def chat(self, nickname: str, text: str, image_url: str | None) -> str | None: ...

    @abstractmethod
    async def call(self, system_prompt: str, text: str, image_url: str | None) -> str | None: ...

    @abstractmethod
    def memory_clear(self) -> None: ...
    @property
    @abstractmethod
    def name(self) -> str: ...


class ChatInfo:
    """对话设置"""

    url: str
    """接入点url"""
    model: str
    """模型版本名"""
    memory: int
    """对话记录长度"""
    timeout: int | float
    """对话超时时间"""
    system_prompt: str
    """系统提示词"""
    style_prompt: str
    """风格提示词"""


class TextSegment(TypedDict):
    """文本消息"""

    type: Literal["text"]
    text: str


class ImageSegment(TypedDict):
    """图片消息"""

    type: Literal["image"]
    image_url: NotRequired[str]
    image_data: NotRequired[str]


class ChatContext(TypedDict):
    """对话上下文"""

    time: float
    role: Literal["user", "assistant"]
    messages: list[TextSegment | ImageSegment]


class ChatInterface(ChatInfo, AIChat):
    """模型对话接口"""

    messages: deque[ChatContext]
    """对话记录"""
    memory: int
    """对话记录长度"""
    timeout: int | float
    """对话超时时间"""

    def __init__(self, config: dict, async_client: httpx.AsyncClient) -> None:
        super().__init__()
        self.async_client = async_client
        self._parse_config(config)
        self.messages = deque(maxlen=self.memory + 1)

    @abstractmethod
    def _parse_config(self, config: dict) -> dict: ...

    @abstractmethod
    async def build_payload(self, system_prompt: str, context: Iterable[ChatContext]):
        """构建请求参数

        Args:
            system_prompt (str): 总系统提示词
            context (Iterable[ChatContext]): 对话上下文
        """

    @abstractmethod
    async def call_api(self, payload) -> str:
        """调用API

        Args:
            payload (Any): 请求参数

        Returns:
            str: 响应内容
        """

    def memory_filter(self, timestamp: int | float):
        """过滤记忆"""
        timeout = timestamp - self.timeout
        while self.messages and self.messages[0]["time"] <= timeout:
            self.messages.popleft()
        if self.messages[0]["role"] == "assistant":
            self.messages.popleft()
        assert self.messages[0]["role"] == "user"

    @property
    def system_prompt(self) -> str:
        """系统提示词"""
        return f"{self._system_prompt}\n{self.style_prompt}"

    @system_prompt.setter
    def system_prompt(self, system_prompt: str) -> None:
        self._system_prompt = system_prompt

    async def chat(self, nickname: str, text: str, image_url: str | None):
        now = datetime.now()
        timestamp = now.timestamp()
        content = []
        content.append({"type": "text", "text": f'{nickname} [{now.strftime("%H:%M")}] {text}'})
        if image_url:
            content.append({"type": "image", "image_url": image_url})
        chat_context: ChatContext = {
            "time": timestamp,
            "role": "user",
            "messages": content,
        }
        self.messages.append(chat_context)
        self.memory_filter(timestamp)
        try:
            payload = await self.build_payload(
                f"{self._system_prompt}\n{self.style_prompt}\ndate:{now.strftime("%Y-%m-%d")}",
                self.messages,
            )
            resp_content = await self.call_api(payload)
        except Exception as err:
            self.messages.pop()
            logger.exception(err)
            return
        self.messages.append({"time": timestamp, "role": "assistant", "messages": [{"type": "text", "text": resp_content}]})
        return resp_content

    async def call(self, system_prompt: str, text: str, image_url: str | None):
        timestamp = datetime.now().timestamp()
        messages = []
        messages.append({"type": "text", "text": text})
        if image_url:
            messages.append({"type": "image", "image_url": image_url})
        try:
            payload = await self.build_payload(system_prompt, [{"role": "user", "time": timestamp, "messages": messages}])
            resp_content = await self.call_api(payload)
        except Exception as err:
            logger.exception(err)
            return
        self.messages.append({"time": timestamp, "role": "assistant", "messages": [{"type": "text", "text": resp_content}]})

    def memory_clear(self) -> None:
        self.messages.clear()

    @property
    def name(self) -> str:
        return self.model
