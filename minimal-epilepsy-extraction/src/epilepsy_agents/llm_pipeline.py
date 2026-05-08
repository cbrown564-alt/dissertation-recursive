from __future__ import annotations

import json
import time
from typing import Any

from .agents import SectionTimelineAgent
from .labels import parse_label
from .providers import (
    ChatMessage,
    LLMProvider,
    anthropic_provider,
    local_lmstudio_provider,
    local_ollama_provider,
    local_vllm_provider,
    openai_provider,
)
from .broader_field_schema import (
    TIER1A_BROADER_ONLY_JSON_SCHEMA,
    TIER1A_JSON_SCHEMA,
    broader_coverage_user_prompt,
    broader_only_context_user_prompt,
    broader_only_user_prompt,
    parse_broader_field_response,
    parse_broader_only_response,
    tier1a_h010_user_prompt,
    tier1a_system_prompt,
    tier1a_user_prompt,
)
from .broader_verification import verify_broader_field_support
from .schema import EvidenceSpan, Prediction
from .structured_schema import EXTRACTION_JSON_SCHEMA, extract_json_object, system_prompt


def _parse_llm_prediction(content: str, default_source: str = "letter") -> Prediction:
    """Parse a raw LLM JSON response into a Prediction."""
    payload = json.loads(extract_json_object(content))
    if not isinstance(payload, dict):
        raise ValueError("prediction_payload_not_object")
    if "seizure_frequency" in payload and isinstance(payload["seizure_frequency"], dict):
        payload = payload["seizure_frequency"]
    label_value = (
        payload.get("label")
        or payload.get("seizure_frequency_label")
        or payload.get("frequency_label")
        or payload.get("prediction")
    )
    if label_value is None:
        raise KeyError("label")
    label = str(label_value).strip()
    parsed = parse_label(label)
    evidence_payload = payload.get("evidence", [])
    if isinstance(evidence_payload, str):
        evidence_payload = [{"text": evidence_payload, "start": None, "end": None, "source": default_source}]
    elif isinstance(evidence_payload, dict):
        evidence_payload = [evidence_payload]
    evidence = [
        EvidenceSpan(
            text=str(item["text"]),
            start=item.get("start"),
            end=item.get("end"),
            source=str(item.get("source", default_source)),
        )
        for item in evidence_payload
        if isinstance(item, dict) and str(item.get("text", "")).strip()
    ]
    warnings = [str(item) for item in payload.get("warnings", [])]
    return Prediction(
        label=label,
        evidence=evidence,
        confidence=float(payload.get("confidence", 0.0)),
        analysis=str(payload.get("analysis", "")),
        parsed_monthly_rate=parsed.monthly_rate,
        pragmatic_class=parsed.pragmatic_class,
        purist_class=parsed.purist_class,
        warnings=warnings,
    )


class SinglePromptLLMPipeline:
    """Single-prompt LLM baseline used for the first Phase A smoke runs."""

    def __init__(self, provider: LLMProvider, max_retries: int = 1) -> None:
        self.provider = provider
        self.max_retries = max_retries

    def predict(self, letter: str) -> Prediction:
        warnings: list[str] = []
        last_error: str | None = None

        for attempt in range(1, self.max_retries + 2):
            started = time.perf_counter()
            try:
                result = self.provider.chat_json(self._messages(letter), EXTRACTION_JSON_SCHEMA)
                latency_ms = round((time.perf_counter() - started) * 1000, 1)
                prediction = self._prediction_from_result(result.content)
                metadata = {
                    "provider": result.provider,
                    "model": result.model,
                    "latency_ms": latency_ms,
                    "attempt": attempt,
                    "invalid_output": False,
                    **_usage_metadata(result.raw),
                }
                return Prediction(
                    label=prediction.label,
                    evidence=prediction.evidence,
                    confidence=prediction.confidence,
                    analysis=prediction.analysis,
                    parsed_monthly_rate=prediction.parsed_monthly_rate,
                    pragmatic_class=prediction.pragmatic_class,
                    purist_class=prediction.purist_class,
                    warnings=warnings + prediction.warnings,
                    metadata=metadata,
                )
            except Exception as exc:
                last_error = type(exc).__name__
                warnings.append(f"attempt_{attempt}_{type(exc).__name__.lower()}")

        parsed = parse_label("unknown")
        return Prediction(
            label="unknown",
            evidence=[],
            confidence=0.0,
            analysis="The LLM pipeline failed to return a valid schema-conformant response.",
            parsed_monthly_rate=parsed.monthly_rate,
            pragmatic_class=parsed.pragmatic_class,
            purist_class=parsed.purist_class,
            warnings=warnings + ["invalid_output"],
            metadata={
                "provider": getattr(self.provider, "provider_name", "unknown"),
                "model": getattr(self.provider, "model", "unknown"),
                "latency_ms": None,
                "attempt": self.max_retries + 1,
                "invalid_output": True,
                "error_type": last_error,
            },
        )

    def _messages(self, letter: str) -> list[ChatMessage]:
        return [
            ChatMessage(role="system", content=system_prompt()),
            ChatMessage(
                role="user",
                content=(
                    "Extract the current seizure-frequency label from this synthetic epilepsy clinic letter. "
                    "Prefer an explicit frequency label when the letter gives a count and time window; "
                    "if the letter states the patient is seizure-free or has had no seizures, use a label "
                    "starting with 'seizure free', for example 'seizure free for 6 months' or "
                    "'seizure free for multiple months' — do not use unknown for seizure-free patients; "
                    "use unknown only when the current seizure frequency is genuinely absent, ambiguous, "
                    "or impossible to normalize. "
                    "Return a JSON object with exactly these top-level keys: "
                    "label (string), evidence (array of objects each with keys text, start, end, source), "
                    "confidence (number 0 to 1), analysis (string), warnings (array of strings).\n\n"
                    f"Letter:\n{letter}"
                ),
            ),
        ]

    def _prediction_from_result(self, content: str) -> Prediction:
        return _parse_llm_prediction(content, default_source="letter")


class MultiAgentLLMPipeline:
    """Role-separated pipeline: deterministic candidate selection + LLM extraction (h004)."""

    _MAX_CANDIDATES = 12

    def __init__(self, provider: LLMProvider, max_retries: int = 1) -> None:
        self.provider = provider
        self.max_retries = max_retries
        self._timeline_agent = SectionTimelineAgent()

    def predict(self, letter: str) -> Prediction:
        timeline = self._timeline_agent.run(letter)
        candidates = timeline.candidates[: self._MAX_CANDIDATES]
        warnings: list[str] = []
        last_error: str | None = None

        for attempt in range(1, self.max_retries + 2):
            started = time.perf_counter()
            try:
                result = self.provider.chat_json(self._messages(candidates), EXTRACTION_JSON_SCHEMA)
                latency_ms = round((time.perf_counter() - started) * 1000, 1)
                prediction = _parse_llm_prediction(result.content, default_source="candidate")
                metadata = {
                    "provider": result.provider,
                    "model": result.model,
                    "latency_ms": latency_ms,
                    "attempt": attempt,
                    "invalid_output": False,
                    "candidate_count": len(candidates),
                    **_usage_metadata(result.raw),
                }
                return Prediction(
                    label=prediction.label,
                    evidence=prediction.evidence,
                    confidence=prediction.confidence,
                    analysis=prediction.analysis,
                    parsed_monthly_rate=prediction.parsed_monthly_rate,
                    pragmatic_class=prediction.pragmatic_class,
                    purist_class=prediction.purist_class,
                    warnings=warnings + prediction.warnings,
                    metadata=metadata,
                )
            except Exception as exc:
                last_error = type(exc).__name__
                warnings.append(f"attempt_{attempt}_{type(exc).__name__.lower()}")

        parsed = parse_label("unknown")
        return Prediction(
            label="unknown",
            evidence=[],
            confidence=0.0,
            analysis="The LLM pipeline failed to return a valid schema-conformant response.",
            parsed_monthly_rate=parsed.monthly_rate,
            pragmatic_class=parsed.pragmatic_class,
            purist_class=parsed.purist_class,
            warnings=warnings + ["invalid_output"],
            metadata={
                "provider": getattr(self.provider, "provider_name", "unknown"),
                "model": getattr(self.provider, "model", "unknown"),
                "latency_ms": None,
                "attempt": self.max_retries + 1,
                "invalid_output": True,
                "error_type": last_error,
            },
        )

    def _messages(self, candidates: list[EvidenceSpan]) -> list[ChatMessage]:
        candidate_text = "\n".join(f"[{i + 1}] {span.text}" for i, span in enumerate(candidates))
        return [
            ChatMessage(role="system", content=system_prompt()),
            ChatMessage(
                role="user",
                content=(
                    "Extract the current seizure-frequency label from the evidence candidates below. "
                    "These candidates have been pre-selected as the most relevant spans from a synthetic "
                    "epilepsy clinic letter. "
                    "Prefer an explicit frequency label when a candidate gives a count and time window; "
                    "if a candidate states the patient is seizure-free or has had no seizures, use a label "
                    "starting with 'seizure free', for example 'seizure free for 6 months' or "
                    "'seizure free for multiple months' — do not use unknown for seizure-free patients; "
                    "use unknown only when the current seizure frequency is genuinely absent, ambiguous, "
                    "or impossible to normalize across all candidates. "
                    "Return a JSON object with exactly these top-level keys: "
                    "label (string), evidence (array of objects each with keys text, start, end, source), "
                    "confidence (number 0 to 1), analysis (string), warnings (array of strings).\n\n"
                    f"Evidence candidates:\n{candidate_text}"
                ),
            ),
        ]


class SelfConsistencyLLMPipeline:
    """h006/h007: MultiAgentLLMPipeline sampled k times; aggregates by majority pragmatic class (h006 k=3)."""

    def __init__(self, provider: LLMProvider, k: int = 3, max_retries: int = 1) -> None:
        self._pipeline = MultiAgentLLMPipeline(provider=provider, max_retries=max_retries)
        self.k = k

    def predict(self, letter: str) -> Prediction:
        samples: list[Prediction] = [self._pipeline.predict(letter) for _ in range(self.k)]
        return _aggregate_by_majority(samples, self.k)


def _aggregate_by_majority(samples: list[Prediction], k: int) -> Prediction:
    """Return the majority-pragmatic-class prediction; break ties by specificity then confidence."""
    from collections import Counter

    class_counts: Counter[str | None] = Counter(s.pragmatic_class for s in samples)
    majority_class, majority_count = class_counts.most_common(1)[0]

    candidates = [s for s in samples if s.pragmatic_class == majority_class]
    best = max(candidates, key=lambda s: (s.confidence, len(s.evidence)))

    agreement_rate = majority_count / k
    metadata = {
        **(best.metadata or {}),
        "sc_k": k,
        "sc_majority_count": majority_count,
        "sc_agreement_rate": agreement_rate,
        "sc_class_votes": dict(class_counts),
    }
    warnings = list(best.warnings)
    if majority_count == 1:
        warnings.append("sc_no_majority")

    return Prediction(
        label=best.label,
        evidence=best.evidence,
        confidence=best.confidence * agreement_rate,
        analysis=best.analysis,
        parsed_monthly_rate=best.parsed_monthly_rate,
        pragmatic_class=best.pragmatic_class,
        purist_class=best.purist_class,
        warnings=warnings,
        metadata=metadata,
    )


class EvidenceRequiringVerifier:
    """Downgrades LLM predictions that lack any evidence span to unknown (h005 post-step)."""

    _ABSTENTION_LABELS = {"unknown", "no seizure frequency reference"}

    def verify(self, prediction: Prediction) -> Prediction:
        if prediction.label.lower() in self._ABSTENTION_LABELS:
            return prediction
        has_evidence = any(span.text.strip() for span in prediction.evidence if isinstance(span, EvidenceSpan))
        if has_evidence:
            return prediction
        parsed = parse_label("unknown")
        return Prediction(
            label="unknown",
            evidence=[],
            confidence=0.0,
            analysis="Verifier: prediction lacked evidence support and was downgraded to unknown.",
            parsed_monthly_rate=parsed.monthly_rate,
            pragmatic_class=parsed.pragmatic_class,
            purist_class=parsed.purist_class,
            warnings=list(prediction.warnings) + ["no_evidence_support"],
            metadata={**(prediction.metadata or {}), "verified": True, "downgraded": True},
        )


class MultiAgentEvidenceRequiredLLMPipeline:
    """h005: MultiAgentLLMPipeline with evidence-requiring verification."""

    def __init__(self, provider: LLMProvider, max_retries: int = 1) -> None:
        self._pipeline = MultiAgentLLMPipeline(provider=provider, max_retries=max_retries)
        self._verifier = EvidenceRequiringVerifier()

    def predict(self, letter: str) -> Prediction:
        prediction = self._pipeline.predict(letter)
        return self._verifier.verify(prediction)


class BroaderFieldSinglePromptPipeline:
    """h008/h010: Single LLM call for Tier 1a broader-field extraction on the full letter.

    Pass user_prompt_fn=tier1a_h010_user_prompt for the h010 anchored variant.
    """

    def __init__(
        self,
        provider: LLMProvider,
        max_retries: int = 1,
        user_prompt_fn=None,
    ) -> None:
        self.provider = provider
        self.max_retries = max_retries
        self._user_prompt_fn = user_prompt_fn if user_prompt_fn is not None else tier1a_user_prompt

    def predict(self, letter: str) -> dict[str, Any]:
        """Return a broader-field result dict; always includes an invalid_output flag."""
        warnings: list[str] = []
        last_error: str | None = None

        for attempt in range(1, self.max_retries + 2):
            started = time.perf_counter()
            try:
                messages = [
                    ChatMessage(role="system", content=tier1a_system_prompt()),
                    ChatMessage(role="user", content=self._user_prompt_fn(letter)),
                ]
                result = self.provider.chat_json(messages, TIER1A_JSON_SCHEMA)
                latency_ms = round((time.perf_counter() - started) * 1000, 1)
                parsed = verify_broader_field_support(
                    letter, parse_broader_field_response(result.content)
                )
                if parsed.get("invalid_output"):
                    raise ValueError("invalid_broader_field_output")
                return {
                    **parsed,
                    "warnings": warnings,
                    "metadata": {
                        "provider": result.provider,
                        "model": result.model,
                        "latency_ms": latency_ms,
                        "attempt": attempt,
                        **_usage_metadata(result.raw),
                    },
                }
            except Exception as exc:
                last_error = type(exc).__name__
                warnings.append(f"attempt_{attempt}_{type(exc).__name__.lower()}")

        return {
            "seizure_frequency": {"label": "unknown", "evidence": "", "confidence": 0.0},
            "current_medications": [],
            "seizure_types": [],
            "investigations": [],
            "invalid_output": True,
            "warnings": warnings + ["pipeline_failure"],
            "metadata": {
                "provider": getattr(self.provider, "provider_name", "unknown"),
                "model": getattr(self.provider, "model", "unknown"),
                "latency_ms": None,
                "attempt": self.max_retries + 1,
                "error_type": last_error,
            },
        }


class BroaderFieldMultiAgentPipeline:
    """h009: Two-stage broader-field pipeline.

    Stage 1: MultiAgentLLMPipeline (h004 architecture) for seizure frequency.
    Stage 2: Dedicated LLM call for the three broader Tier 1a fields only.
    """

    def __init__(self, provider: LLMProvider, max_retries: int = 1) -> None:
        self.provider = provider
        self.max_retries = max_retries
        self._sf_pipeline = MultiAgentLLMPipeline(provider=provider, max_retries=max_retries)

    def predict(self, letter: str) -> dict[str, Any]:
        sf_pred = self._sf_pipeline.predict(letter)
        sf_evidence = sf_pred.evidence[0].text if sf_pred.evidence else ""

        broader_warnings: list[str] = []
        last_error: str | None = None
        broader_result: dict[str, Any] | None = None

        for attempt in range(1, self.max_retries + 2):
            started = time.perf_counter()
            try:
                messages = [
                    ChatMessage(role="system", content=tier1a_system_prompt()),
                    ChatMessage(role="user", content=broader_only_user_prompt(letter)),
                ]
                result = self.provider.chat_json(messages, TIER1A_BROADER_ONLY_JSON_SCHEMA)
                latency_ms = round((time.perf_counter() - started) * 1000, 1)
                parsed = verify_broader_field_support(
                    letter, parse_broader_only_response(result.content)
                )
                if parsed.get("invalid_output"):
                    raise ValueError("invalid_broader_only_output")
                broader_result = {
                    **parsed,
                    "broader_metadata": {
                        "provider": result.provider,
                        "model": result.model,
                        "latency_ms": latency_ms,
                        "attempt": attempt,
                        **_usage_metadata(result.raw),
                    },
                }
                break
            except Exception as exc:
                last_error = type(exc).__name__
                broader_warnings.append(f"broader_attempt_{attempt}_{type(exc).__name__.lower()}")

        if broader_result is None:
            broader_result = {
                "current_medications": [],
                "seizure_types": [],
                "investigations": [],
                "invalid_output": True,
                "broader_metadata": {
                    "provider": getattr(self.provider, "provider_name", "unknown"),
                    "model": getattr(self.provider, "model", "unknown"),
                    "latency_ms": None,
                    "error_type": last_error,
                },
            }

        sf_invalid = bool((sf_pred.metadata or {}).get("invalid_output"))
        broader_invalid = broader_result.get("invalid_output", False)

        return {
            "seizure_frequency": {
                "label": sf_pred.label,
                "evidence": sf_evidence,
                "confidence": sf_pred.confidence,
            },
            "current_medications": broader_result.get("current_medications", []),
            "seizure_types": broader_result.get("seizure_types", []),
            "investigations": broader_result.get("investigations", []),
            "invalid_output": sf_invalid or broader_invalid,
            "warnings": list(sf_pred.warnings) + broader_warnings,
            "metadata": {
                "sf_call": sf_pred.metadata or {},
                "broader_call": broader_result.get("broader_metadata", {}),
            },
        }


class BroaderFieldContextInjectedPipeline:
    """h011: Two-stage pipeline where Stage 2 receives the Stage 1 SF label as plain-text context.

    Stage 1: MultiAgentLLMPipeline (h004 architecture) for seizure frequency.
    Stage 2: Broader-only schema with SF label injected into the prompt as context.
    Hypothesis: the model needs SF as a clinical anchor but not as a schema field.
    """

    def __init__(self, provider: LLMProvider, max_retries: int = 1) -> None:
        self.provider = provider
        self.max_retries = max_retries
        self._sf_pipeline = MultiAgentLLMPipeline(provider=provider, max_retries=max_retries)

    def predict(self, letter: str) -> dict[str, Any]:
        sf_pred = self._sf_pipeline.predict(letter)
        sf_evidence = sf_pred.evidence[0].text if sf_pred.evidence else ""

        broader_warnings: list[str] = []
        last_error: str | None = None
        broader_result: dict[str, Any] | None = None

        for attempt in range(1, self.max_retries + 2):
            started = time.perf_counter()
            try:
                messages = [
                    ChatMessage(role="system", content=tier1a_system_prompt()),
                    ChatMessage(
                        role="user",
                        content=broader_only_context_user_prompt(letter, sf_pred.label),
                    ),
                ]
                result = self.provider.chat_json(messages, TIER1A_BROADER_ONLY_JSON_SCHEMA)
                latency_ms = round((time.perf_counter() - started) * 1000, 1)
                parsed = verify_broader_field_support(
                    letter, parse_broader_only_response(result.content)
                )
                if parsed.get("invalid_output"):
                    raise ValueError("invalid_broader_only_output")
                broader_result = {
                    **parsed,
                    "broader_metadata": {
                        "provider": result.provider,
                        "model": result.model,
                        "latency_ms": latency_ms,
                        "attempt": attempt,
                        **_usage_metadata(result.raw),
                    },
                }
                break
            except Exception as exc:
                last_error = type(exc).__name__
                broader_warnings.append(f"broader_attempt_{attempt}_{type(exc).__name__.lower()}")

        if broader_result is None:
            broader_result = {
                "current_medications": [],
                "seizure_types": [],
                "investigations": [],
                "invalid_output": True,
                "broader_metadata": {
                    "provider": getattr(self.provider, "provider_name", "unknown"),
                    "model": getattr(self.provider, "model", "unknown"),
                    "latency_ms": None,
                    "error_type": last_error,
                },
            }

        sf_invalid = bool((sf_pred.metadata or {}).get("invalid_output"))
        broader_invalid = broader_result.get("invalid_output", False)

        return {
            "seizure_frequency": {
                "label": sf_pred.label,
                "evidence": sf_evidence,
                "confidence": sf_pred.confidence,
            },
            "current_medications": broader_result.get("current_medications", []),
            "seizure_types": broader_result.get("seizure_types", []),
            "investigations": broader_result.get("investigations", []),
            "invalid_output": sf_invalid or broader_invalid,
            "warnings": list(sf_pred.warnings) + broader_warnings,
            "metadata": {
                "sf_call": sf_pred.metadata or {},
                "broader_call": broader_result.get("broader_metadata", {}),
            },
        }


class BroaderFieldMediumPipeline:
    """h012: h003-style SF call plus a coverage-oriented broader M-C3 call.

    Stage 1 keeps seizure-frequency extraction isolated on the full letter.
    Stage 2 asks for the three broader fields with coverage-oriented, evidence-bound guidance.
    """

    def __init__(self, provider: LLMProvider, max_retries: int = 1) -> None:
        self.provider = provider
        self.max_retries = max_retries
        self._sf_pipeline = SinglePromptLLMPipeline(provider=provider, max_retries=max_retries)

    def predict(self, letter: str) -> dict[str, Any]:
        sf_pred = self._sf_pipeline.predict(letter)
        sf_evidence = sf_pred.evidence[0].text if sf_pred.evidence else ""

        broader_warnings: list[str] = []
        last_error: str | None = None
        broader_result: dict[str, Any] | None = None

        for attempt in range(1, self.max_retries + 2):
            started = time.perf_counter()
            try:
                messages = [
                    ChatMessage(role="system", content=tier1a_system_prompt()),
                    ChatMessage(role="user", content=broader_coverage_user_prompt(letter)),
                ]
                result = self.provider.chat_json(messages, TIER1A_BROADER_ONLY_JSON_SCHEMA)
                latency_ms = round((time.perf_counter() - started) * 1000, 1)
                parsed = verify_broader_field_support(
                    letter, parse_broader_only_response(result.content)
                )
                if parsed.get("invalid_output"):
                    raise ValueError("invalid_broader_coverage_output")
                broader_result = {
                    **parsed,
                    "broader_metadata": {
                        "provider": result.provider,
                        "model": result.model,
                        "latency_ms": latency_ms,
                        "attempt": attempt,
                        **_usage_metadata(result.raw),
                    },
                }
                break
            except Exception as exc:
                last_error = type(exc).__name__
                broader_warnings.append(f"broader_attempt_{attempt}_{type(exc).__name__.lower()}")

        if broader_result is None:
            broader_result = {
                "current_medications": [],
                "seizure_types": [],
                "investigations": [],
                "invalid_output": True,
                "broader_metadata": {
                    "provider": getattr(self.provider, "provider_name", "unknown"),
                    "model": getattr(self.provider, "model", "unknown"),
                    "latency_ms": None,
                    "error_type": last_error,
                },
            }

        sf_invalid = bool((sf_pred.metadata or {}).get("invalid_output"))
        broader_invalid = broader_result.get("invalid_output", False)

        return {
            "seizure_frequency": {
                "label": sf_pred.label,
                "evidence": sf_evidence,
                "confidence": sf_pred.confidence,
            },
            "current_medications": broader_result.get("current_medications", []),
            "seizure_types": broader_result.get("seizure_types", []),
            "investigations": broader_result.get("investigations", []),
            "invalid_output": sf_invalid or broader_invalid,
            "warnings": list(sf_pred.warnings) + broader_warnings,
            "metadata": {
                "sf_call": sf_pred.metadata or {},
                "broader_call": broader_result.get("broader_metadata", {}),
            },
        }


def create_provider(
    name: str,
    model: str,
    base_url: str | None = None,
    timeout_seconds: int = 120,
    temperature: float = 0.0,
    num_predict: int = 512,
) -> LLMProvider:
    if name == "lmstudio":
        return local_lmstudio_provider(
            model=model,
            base_url=base_url or "http://localhost:1234/v1",
            timeout_seconds=timeout_seconds,
            temperature=temperature,
        )
    if name == "vllm":
        return local_vllm_provider(
            model=model,
            base_url=base_url or "http://localhost:8000/v1",
            timeout_seconds=timeout_seconds,
            temperature=temperature,
        )
    if name == "ollama":
        return local_ollama_provider(
            model=model,
            base_url=base_url or "http://localhost:11434/api",
            timeout_seconds=timeout_seconds,
            temperature=temperature,
            num_predict=num_predict,
        )
    if name == "openai":
        return openai_provider(model=model, temperature=temperature, timeout_seconds=timeout_seconds)
    if name == "anthropic":
        return anthropic_provider(model=model, temperature=temperature, timeout_seconds=timeout_seconds)
    raise ValueError(f"Unsupported provider: {name}")


def _usage_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    usage = raw.get("usage", {})
    prompt_tokens = (
        raw.get("prompt_eval_count")
        or usage.get("prompt_tokens")
        or usage.get("input_tokens")
    )
    completion_tokens = (
        raw.get("eval_count")
        or usage.get("completion_tokens")
        or usage.get("output_tokens")
    )
    total_tokens = raw.get("usage", {}).get("total_tokens")
    if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
        total_tokens = prompt_tokens + completion_tokens

    metadata: dict[str, Any] = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
    for key in ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration"):
        if key in raw:
            metadata[key] = raw[key]
    return metadata
