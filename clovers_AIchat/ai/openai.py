from pydantic import BaseModel
from ..core import ChatInterface, ChatInfo, ChatContext


class Config(ChatInfo, BaseModel):
    api_key: str


class Chat(ChatInterface):
    """OpenAI"""

    def _parse_config(self, config: dict) -> None:
        _config = Config.model_validate(config)
        self.model = _config.model
        self.system_prompt = _config.system_prompt
        self.style_prompt = _config.style_prompt
        self.memory = _config.memory
        self.timeout = _config.timeout
        self.url = f"{_config.url.rstrip("/")}/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {_config.api_key}",
            "Content-Type": "application/json",
        }

    async def build_payload(self, system_prompt, context):
        def build_content(context: ChatContext):
            content = []
            for seg in context["messages"]:
                if seg["type"] == "text":
                    content.append({"type": "text", "text": seg["text"]})
                elif seg["type"] == "image":
                    if "image_data" in seg:
                        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{seg['image_data']}"}})
                    elif "image_url" in seg:
                        content.append({"type": "image_url", "image_url": {"url": seg["image_url"]}})
            return {"role": context["role"], "content": content}

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(map(build_content, context))
        return {"model": self.model, "messages": messages}

    async def call_api(self, payload) -> str:
        resp = await self.async_client.post(self.url, headers=self.headers, json=payload)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    # async def Responses(self) -> str | None:
    #     def build_content(message: ChatContext):
    #         role = message["role"]
    #         text = message["text"]
    #         image_url = message["image_url"]
    #         if image_url is None:
    #             context = text
    #         elif role == "assistant":
    #             context = [{"type": "output_text", "text": text}, {"type": "output_image", "image_url": image_url}]
    #         else:
    #             context = [{"type": "input_text", "text": text}, {"type": "input_image", "image_url": image_url}]
    #         return {"role": role, "content": context}
