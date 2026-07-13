"""Small OpenAI-compatible chat client using only Python stdlib."""

import json
from urllib import request


class LlmClient:
    def __init__(self, base_url, api_key, model, timeout=30.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def answer(self, text, context=None):
        if not self.base_url or not self.api_key or not self.model:
            raise RuntimeError("LLM is not configured")
        system = (
            "?????????????????????????"
            "????????????"
        )
        if context:
            system += "\n???????" + json.dumps(context, ensure_ascii=False)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
            "temperature": 0.2,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            self.base_url + "/chat/completions",
            data=body,
            headers={
                "Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=self.timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
        try:
            return result["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("LLM response does not contain answer text") from exc
