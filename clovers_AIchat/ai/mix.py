from ..core import AIChat, ChatInterface


class Chat(AIChat):
    def __init__(
        self,
        whitelist: set[str],
        blacklist: set[str],
        chat_text: ChatInterface,
        chat_image: ChatInterface,
    ) -> None:
        super().__init__()
        self.whitelist = whitelist
        self.blacklist = blacklist
        self.chat_text = chat_text
        self.chat_image = chat_image

    async def chat(self, nickname: str, text: str, image_url: str | None) -> str | None:
        if image_url:
            self.chat_image.memory_clear()
            resp_content = await self.chat_image.chat(nickname, text, image_url)
            self.chat_text.messages.extend(self.chat_image.messages)
        else:
            resp_content = await self.chat_text.chat(nickname, text, image_url)
        return resp_content

    async def call(self, system_prompt: str, text: str, image_url: str | None) -> str | None:
        if image_url:
            resp_content = await self.chat_image.call(system_prompt, text, image_url)
        else:
            resp_content = await self.chat_text.call(system_prompt, text, image_url)
        return resp_content

    def memory_clear(self) -> None:
        self.chat_text.messages.clear()

    @property
    def name(self) -> str:
        return f"text:{self.chat_text.name} - image:{self.chat_image.name}"

    @property
    def style_prompt(self) -> str:
        return self.chat_text.style_prompt

    @style_prompt.setter
    def system_prompt(self, style_prompt: str) -> None:
        self.chat_text.style_prompt = style_prompt
        self.chat_image.style_prompt = style_prompt
