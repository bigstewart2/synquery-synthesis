"""The application's small structured-output boundary; credentials stay server-side.

Anthropic retains the existing forced-tool requests. OpenAI uses Responses JSON
Schema output with storage disabled. No provider can bypass the source checks.
"""
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
import time

from jsonschema import Draft202012Validator


MODELS = {
    "anthropic": ("claude-sonnet-5",),
    "openai": ("gpt-5.6-terra", "gpt-5.6-sol"),
}
KEY_NAMES = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}
EFFORTS = ("none", "low", "medium", "high", "xhigh", "max")


def credential_name(provider):
    if provider == "openai" and os.environ.get("INTERVIEW_OPENAI_API_KEY"):
        return "INTERVIEW_OPENAI_API_KEY"
    return KEY_NAMES[provider]


class ProviderConfigurationError(ValueError):
    """Safe configuration message, never an SDK response or credential."""


class StructuredResponseError(ValueError):
    """A response cannot safely enter the evidence workflow."""


@dataclass(frozen=True)
class Usage:
    # Total input includes cache reads/writes on both providers. Output includes
    # reasoning tokens; never add reasoning_tokens to the bill a second time.
    input_tokens: int = 0
    cached_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int | None = None


@dataclass(frozen=True)
class StructuredResult:
    payload: dict
    usage: Usage


def settings(provider=None, model=None):
    provider = provider or os.environ.get("INTERVIEW_PROVIDER", "anthropic")
    if provider not in MODELS:
        raise ProviderConfigurationError("Unsupported INTERVIEW_PROVIDER.")
    model = model or os.environ.get("INTERVIEW_MODEL") or MODELS[provider][0]
    if model not in MODELS[provider]:
        raise ProviderConfigurationError("INTERVIEW_MODEL is not allowed for this provider.")
    return provider, model


def strict_schema(schema):
    """Adapt optional fields to OpenAI's required-but-nullable representation.

    The canonical task schema is never mutated. Legacy optional nulls are removed
    after generation, so the application receives the same missing-field contract.
    """
    out = deepcopy(schema)
    if out.get("type") == "object":
        required = set(out.get("required", []))
        properties = {}
        for key, value in out.get("properties", {}).items():
            value = strict_schema(value)
            if key not in required:
                value = {"anyOf": [value, {"type": "null"}]}
            properties[key] = value
        out.update(properties=properties, required=list(properties), additionalProperties=False)
    elif out.get("type") == "array":
        out["items"] = strict_schema(out["items"])
    for keyword in ("anyOf", "oneOf", "allOf"):
        if keyword in out:
            out[keyword] = [strict_schema(part) for part in out[keyword]]
    return out


def restore_optional_fields(value, schema):
    if isinstance(value, dict) and schema.get("type") == "object":
        required = set(schema.get("required", []))
        props = schema.get("properties", {})
        return {key: restore_optional_fields(item, props.get(key, {}))
                for key, item in value.items() if item is not None or key in required}
    if isinstance(value, list) and schema.get("type") == "array":
        return [restore_optional_fields(item, schema.get("items", {})) for item in value]
    return value


def plain(value):
    """Serialize SDK responses, plus small fake responses used by offline checks."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if hasattr(value, "__dict__"):
        return plain(vars(value))
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def normalized_usage(provider, response):
    usage = plain(getattr(response, "usage", None)) or {}
    if any(type(usage.get(k)) is not int or usage[k] < 0 for k in ("input_tokens", "output_tokens")):
        raise StructuredResponseError("The model response contained invalid usage information. Please retry.")
    if provider == "anthropic":
        cached = usage.get("cache_read_input_tokens", 0) or 0
        created = usage.get("cache_creation_input_tokens", 0) or 0
        return Usage((usage.get("input_tokens", 0) or 0) + cached + created,
                     cached, created, usage.get("output_tokens", 0) or 0)
    return Usage(usage.get("input_tokens", 0) or 0,
                 (usage.get("input_tokens_details") or {}).get("cached_tokens", 0) or 0,
                 0, usage.get("output_tokens", 0) or 0,
                 (usage.get("output_tokens_details") or {}).get("reasoning_tokens"))


class StructuredProvider:
    def __init__(self, provider, model, client, *, reasoning_effort=None,
                 capture=False, before_call=None, after_call=None):
        self.provider, self.model = settings(provider, model)
        if reasoning_effort is not None and reasoning_effort not in EFFORTS:
            raise ProviderConfigurationError("Unsupported OpenAI reasoning effort.")
        self.client = client
        self.reasoning_effort = reasoning_effort
        self.capture = capture
        self.before_call, self.after_call = before_call, after_call
        self.records = []

    def generate_structured(self, *, instructions, input, tool, max_output_tokens, thinking=None):
        schema = tool["input_schema"]
        Draft202012Validator.check_schema(schema)
        # Preserve the workload's existing thinking role. Medium is an explicit
        # pilot approximation for Claude adaptive thinking, not a claim of parity.
        effort = self.reasoning_effort or ("medium" if thinking else "none")
        if self.provider == "anthropic":
            request = dict(model=self.model, max_tokens=max_output_tokens,
                           system=instructions, tools=[tool],
                           tool_choice={"type": "tool", "name": tool["name"]},
                           messages=[{"role": "user", "content": input}])
            if thinking:
                request["thinking"] = thinking
        else:
            request = dict(model=self.model, instructions=instructions, input=input,
                           max_output_tokens=max_output_tokens, store=False,
                           reasoning={"effort": effort},
                           text={"format": {"type": "json_schema", "name": tool["name"],
                                            "description": tool["description"],
                                            "schema": strict_schema(schema), "strict": True}})
        record = dict(provider=self.provider, model=self.model, stage=tool["name"],
                      started_at=datetime.now(timezone.utc).isoformat(),
                      reasoning=thinking if self.provider == "anthropic" else {"effort": effort},
                      max_output_tokens=max_output_tokens, request_sha256=digest(request),
                      instructions_sha256=digest(instructions), input_sha256=digest(input),
                      schema_sha256=digest(schema), status="pending", usage=None)
        if self.capture:
            record["request"] = request
        if self.before_call:
            self.before_call(record, request)
        start = time.perf_counter()
        response = None
        try:
            if self.provider == "anthropic":
                response = self.client.messages.create(**request)
            else:
                response = self.client.responses.create(**request)
            record.update(response_id=getattr(response, "id", None),
                          returned_model=getattr(response, "model", None))
            if self.capture:
                record["response"] = plain(response)
            if getattr(response, "usage", None) is None:
                raise StructuredResponseError("The model response did not include usage information. Please retry.")
            usage = normalized_usage(self.provider, response)
            record["usage"] = asdict(usage)
            if self.provider == "anthropic":
                if getattr(response, "stop_reason", None) == "max_tokens":
                    raise StructuredResponseError("The model response was cut off. Please retry.")
                blocks = [b for b in response.content if b.type == "tool_use"]
                if len(blocks) != 1 or blocks[0].name != tool["name"]:
                    raise StructuredResponseError("The model did not return one complete structured response. Please retry.")
                payload = blocks[0].input
            else:
                if getattr(response, "status", None) != "completed":
                    raise StructuredResponseError("The model response was incomplete. Please retry.")
                texts = []
                for block in response.output:
                    if block.type == "message":
                        for part in block.content:
                            if part.type == "refusal":
                                raise StructuredResponseError("The model declined this request. Please review the input.")
                            if part.type == "output_text":
                                texts.append(part.text)
                if len(texts) != 1:
                    raise StructuredResponseError("The model did not return one complete structured response. Please retry.")
                try:
                    payload = json.loads(texts[0])
                except (TypeError, json.JSONDecodeError):
                    raise StructuredResponseError("The model returned invalid structured data. Please retry.") from None
                payload = restore_optional_fields(payload, schema)
            if not isinstance(payload, dict) or not Draft202012Validator(schema).is_valid(payload):
                raise StructuredResponseError("The model response did not match the required schema. Please retry.")
            record["status"] = "completed"
            return StructuredResult(payload, usage)
        except Exception as exc:
            # Keep provider exceptions out of reports; their body may include input.
            record.update(status="failed", error_type=type(exc).__name__,
                          http_status=getattr(exc, "status_code", None))
            raise
        finally:
            record["elapsed_s"] = round(time.perf_counter() - start, 6)
            self.records.append(record)
            if self.after_call:
                self.after_call(record)


def create_provider(provider=None, model=None, *, client=None, reasoning_effort=None,
                    capture=False, max_retries=None, timeout=None,
                    before_call=None, after_call=None):
    provider, model = settings(provider, model)
    if client is None:
        key_name = credential_name(provider)
        if not os.environ.get(key_name):
            raise ProviderConfigurationError(f"Server is missing {key_name}.")
        kwargs = {}
        if max_retries is not None:
            kwargs["max_retries"] = max_retries
        if timeout is not None:
            kwargs["timeout"] = timeout
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(**kwargs)
        else:
            from openai import OpenAI
            client = OpenAI(api_key=os.environ[key_name],
                            base_url="https://api.openai.com/v1", **kwargs)
    reasoning_effort = reasoning_effort or os.environ.get("INTERVIEW_OPENAI_REASONING_EFFORT")
    return StructuredProvider(provider, model, client, reasoning_effort=reasoning_effort,
                              capture=capture, before_call=before_call, after_call=after_call)


def generate_structured(client, *, model, **kwargs):
    """Keep existing local Anthropic callers usable while migrating the boundary."""
    if not isinstance(client, StructuredProvider):
        client = StructuredProvider("anthropic", model, client)
    return client.generate_structured(**kwargs)
