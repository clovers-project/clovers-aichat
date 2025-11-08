from clovers_aichat.core import ChatContext
from clovers_aichat.ai.openai import Chat as OpenAIChat
import re


pattern = re.compile(r"<think>(.*)</think>(.*)", re.DOTALL)


class Chat(OpenAIChat):
    """Ollama DeepSeek"""

    async def build_payload(self, system_prompt, context):
        def build_content(context: ChatContext):
            return {"role": context["role"], "content": "".join([seg["text"] for seg in context["messages"] if seg["type"] == "text"])}

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(map(build_content, context))
        return {"model": self.model, "messages": messages}

    async def call_api(self, payload):
        resp = await self.async_client.post(self.url, headers=self.headers, json=payload)
        resp.raise_for_status()
        resp_content: str = resp.json()["choices"][0]["message"]["content"].strip()
        matcher = pattern.match(resp_content)
        if matcher is None:
            return resp_content
        else:
            return matcher.group(2).strip()
