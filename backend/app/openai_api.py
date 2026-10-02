"""Pure, shared helpers for strict OpenAI Responses requests and responses."""

from __future__ import annotations

from copy import deepcopy
import re


OPENAI_HOST = "https://api.openai.com"
MODEL = re.compile(r"gpt-[a-zA-Z0-9][a-zA-Z0-9._-]{0,99}")
_ERROR_CODES = frozenset({
    "invalid_model", "invalid_request", "invalid_response", "incomplete_response",
    "refusal", "unsupported_output",
})


class OpenAIResponseError(ValueError):
    def __init__(self, code: str = "invalid_response") -> None:
        self.code = code if code in _ERROR_CODES else "invalid_response"
        super().__init__(self.code)


def validate_model(model: str) -> bool:
    return isinstance(model, str) and MODEL.fullmatch(model) is not None


def _strict_schema(schema: dict) -> dict:
    if not isinstance(schema, dict):
        raise OpenAIResponseError("invalid_request")
    result = deepcopy(schema)
    value_type = result.get("type")
    if isinstance(value_type, str):
        result["type"] = value_type.lower()
    elif isinstance(value_type, list):
        result["type"] = [value.lower() if isinstance(value, str) else value for value in value_type]
    properties = result.get("properties")
    if isinstance(properties, dict):
        if not all(isinstance(value, dict) for value in properties.values()):
            raise OpenAIResponseError("invalid_request")
        result["properties"] = {key: _strict_schema(value) for key, value in properties.items()}
        result["required"] = list(properties)
        result["additionalProperties"] = False
    elif result.get("type") == "object":
        raise OpenAIResponseError("invalid_request")
    if isinstance(result.get("items"), dict):
        result["items"] = _strict_schema(result["items"])
    for key in ("anyOf", "oneOf", "allOf"):
        if isinstance(result.get(key), list):
            if not all(isinstance(value, dict) for value in result[key]):
                raise OpenAIResponseError("invalid_request")
            result[key] = [_strict_schema(value) for value in result[key]]
    if isinstance(result.get("$defs"), dict):
        result["$defs"] = {key: _strict_schema(value) for key, value in result["$defs"].items()}
    return result


def build_request(model: str, instructions: str, content: list[dict], schema: dict,
                  name: str, max_output_tokens: int) -> dict:
    if not validate_model(model):
        raise OpenAIResponseError("invalid_model")
    if (not isinstance(instructions, str) or not instructions.strip()
            or not isinstance(content, list) or not content or not all(isinstance(part, dict) for part in content)
            or not isinstance(schema, dict) or not isinstance(name, str)
            or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", name)
            or type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 32768):
        raise OpenAIResponseError("invalid_request")
    strict_schema = _strict_schema(schema)
    if strict_schema.get("type") != "object":
        raise OpenAIResponseError("invalid_request")
    return {
        "model": model,
        "instructions": instructions,
        "input": [{"role": "user", "content": deepcopy(content)}],
        "store": False,
        "reasoning": {"effort": "none"},
        "max_output_tokens": max_output_tokens,
        "text": {"format": {"type": "json_schema", "name": name, "strict": True, "schema": strict_schema}},
    }


def parse_response(payload: object) -> tuple[str, dict[str, int]]:
    if not isinstance(payload, dict):
        raise OpenAIResponseError()
    if payload.get("status") != "completed" or payload.get("incomplete_details") is not None:
        raise OpenAIResponseError("incomplete_response")
    if payload.get("error") is not None:
        raise OpenAIResponseError()
    output = payload.get("output")
    if not isinstance(output, list) or not output:
        raise OpenAIResponseError()
    if any(not isinstance(message, dict) or message.get("type") != "message" for message in output):
        raise OpenAIResponseError("unsupported_output")
    if len(output) != 1:
        raise OpenAIResponseError()
    message = output[0]
    if message.get("role") != "assistant" or message.get("status") != "completed":
        raise OpenAIResponseError()
    content = message.get("content")
    if not isinstance(content, list) or not content:
        raise OpenAIResponseError()
    parts = []
    for part in content:
        if not isinstance(part, dict):
            raise OpenAIResponseError()
        if part.get("type") == "refusal" or part.get("refusal") is not None:
            raise OpenAIResponseError("refusal")
        if part.get("type") != "output_text":
            raise OpenAIResponseError("unsupported_output")
        text = part.get("text")
        if not isinstance(text, str) or not text.strip():
            raise OpenAIResponseError()
        parts.append(text)
    metadata = payload.get("usage")
    usage = {
        key: value for key, value in metadata.items()
        if key in ("input_tokens", "output_tokens", "total_tokens") and type(value) is int and value >= 0
    } if isinstance(metadata, dict) else {}
    return "".join(parts), usage
