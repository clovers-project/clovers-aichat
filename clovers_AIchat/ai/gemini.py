from pydantic import BaseModel
import base64
import asyncio
from ..core import ChatInterface, ChatInfo, ChatContext, ImageSegment


class Config(ChatInfo, BaseModel):
    api_key: str
    google_search: bool = False
    url_context: bool = False
    code_execution: bool = False


class Chat(ChatInterface):
    """Gemini"""

    def _parse_config(self, config: dict):
        _config = Config.model_validate(config)
        self.model = _config.model
        self.system_prompt = _config.system_prompt
        self.style_prompt = _config.style_prompt
        self.memory = _config.memory
        self.timeout = _config.timeout
        self.url = f"{_config.url.rstrip("/")}/{_config.model}:generateContent?key={_config.api_key}"
        self.tools = []
        if _config.google_search:
            self.tools.append({"google_search": {}})
        if _config.url_context:
            self.tools.append({"url_context": {}})
        if _config.code_execution:
            self.tools.append({"code_execution": {}})

    async def build_payload(self, system_prompt, context):

        async def download_image(data: dict, seg: ImageSegment, image_url: str):
            resp = await self.async_client.get(image_url)
            if resp.status_code == 200:
                data["inline_data"]["data"] = seg["image_data"] = base64.b64encode(resp.content).decode("utf-8")
            else:
                data.clear()
                data["type"] = "text"
                data["text"] = "[image]"

        def build_content(context: ChatContext, tasks: list) -> dict:
            content = []
            for seg in context["messages"]:
                if seg["type"] == "text":
                    content.append({"text": seg["text"]})
                elif seg["type"] == "image":
                    data = {"inline_data": {"mime_type": "image/jpeg"}}
                    if image_data := seg.get("image_data"):
                        data["inline_data"]["data"] = image_data
                    elif image_url := seg.get("image_url"):
                        tasks.append(asyncio.create_task(download_image(data, seg, image_url)))
                    else:
                        raise ValueError("Image segment must have either image_data or image_url.")
                    content.append(data)

            if context["role"] == "user":
                return {"role": "user", "parts": content}
            else:
                return {"role": "model", "parts": content}

        tasks = []
        data: dict = {"contents": [build_content(message, tasks) for message in context]}
        if self.tools:
            data["tools"] = self.tools
        if system_prompt:
            data["system_instruction"] = {"parts": [{"text": system_prompt}]}
        await asyncio.gather(*tasks)
        return data

    async def call_api(self, payload):
        resp = await self.async_client.post(self.url, json=payload, headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
