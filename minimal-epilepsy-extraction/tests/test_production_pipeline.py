import unittest

from epilepsy_agents.production_pipeline import ProductionMultiAgentPipeline
from epilepsy_agents.production_schema import (
    classification_user_prompt,
    parse_classification_response,
)
from epilepsy_agents.providers import LLMResult


_SF_RESPONSE = """{
  "label": "2 per week",
  "evidence": [{"text": "She reports 2 seizures per week", "start": null, "end": null, "source": "letter"}],
  "confidence": 0.9,
  "analysis": "Explicit current frequency.",
  "warnings": []
}"""

_BROADER_RESPONSE = """{
  "current_medications": [
    {"drug_name": "lamotrigine", "dose_text": "100 mg twice daily", "status": "current",
     "evidence": "Lamotrigine 100 mg twice daily", "confidence": 0.95}
  ],
  "seizure_types": [
    {"description": "focal impaired awareness seizures", "onset": "focal",
     "evidence": "focal impaired awareness seizures", "confidence": 0.86}
  ],
  "investigations": [
    {"investigation_type": "EEG", "result": "abnormal", "status": "historical",
     "evidence": "Previous EEG showed left temporal sharp waves", "confidence": 0.9}
  ]
}"""

_CLASSIFICATION_RESPONSE = """{
  "epilepsy_type": {
    "value": "focal epilepsy",
    "evidence": "diagnosis remains focal epilepsy",
    "confidence": 0.88
  },
  "epilepsy_syndrome": {
    "value": "unknown",
    "evidence": "",
    "confidence": 0.0
  }
}"""

_LETTER = (
    "Diagnosis: diagnosis remains focal epilepsy.\n"
    "Current medication: Lamotrigine 100 mg twice daily.\n"
    "Seizures: She reports 2 seizures per week with focal impaired awareness seizures.\n"
    "Investigations: Previous EEG showed left temporal sharp waves."
)


class ProductionSchemaTests(unittest.TestCase):
    def test_parse_classification_response(self) -> None:
        parsed = parse_classification_response(_CLASSIFICATION_RESPONSE)

        self.assertFalse(parsed["invalid_output"])
        self.assertEqual(parsed["epilepsy_type"]["value"], "focal epilepsy")
        self.assertEqual(parsed["epilepsy_syndrome"]["value"], "unknown")

    def test_classification_prompt_discourages_inference(self) -> None:
        prompt = classification_user_prompt("letter")

        self.assertIn("Do not infer type", prompt)
        self.assertIn("Do not invent a syndrome", prompt)


class ProductionPipelineTests(unittest.TestCase):
    def test_pipeline_exposes_role_artifacts_and_final_json(self) -> None:
        provider = _FakeProvider([_SF_RESPONSE, _BROADER_RESPONSE, _CLASSIFICATION_RESPONSE])
        pipeline = ProductionMultiAgentPipeline(provider=provider)

        result = pipeline.predict(_LETTER)

        self.assertEqual(result["pipeline_id"], "production_multi_agent_v1")
        self.assertFalse(result["invalid_output"])
        self.assertEqual(result["metadata"]["call_budget"]["llm_calls"], 3)
        self.assertIn("section_timeline", result["artifacts"])
        self.assertIn("field_extractions", result["artifacts"])
        self.assertIn("verification", result["artifacts"])
        self.assertIn("aggregation", result["artifacts"])
        self.assertEqual(result["final"]["seizure_frequency"]["label"], "2 per week")
        self.assertEqual(result["final"]["current_medications"][0]["drug_name"], "lamotrigine")
        self.assertTrue(result["final"]["current_medications"][0]["support"]["supported"])
        self.assertEqual(result["final"]["epilepsy_type"]["value"], "focal epilepsy")
        self.assertGreaterEqual(len(result["final"]["citations"]), 4)
        self.assertEqual(len(provider.calls), 3)

    def test_pipeline_downgrades_unsupported_classification_evidence(self) -> None:
        bad_classification = """{
          "epilepsy_type": {"value": "generalized epilepsy", "evidence": "not in source text", "confidence": 0.9},
          "epilepsy_syndrome": {"value": "unknown", "evidence": "", "confidence": 0.0}
        }"""
        provider = _FakeProvider([_SF_RESPONSE, _BROADER_RESPONSE, bad_classification])
        pipeline = ProductionMultiAgentPipeline(provider=provider)

        result = pipeline.predict(_LETTER)

        self.assertFalse(result["final"]["epilepsy_type"]["support"]["supported"])
        self.assertIn("unsupported_evidence", result["warnings"])
        self.assertLess(result["final"]["epilepsy_type"]["confidence"], 0.9)

    def test_classification_failure_invalidates_full_contract_not_core_broader(self) -> None:
        provider = _FakeProvider([_SF_RESPONSE, _BROADER_RESPONSE, "not json"])
        pipeline = ProductionMultiAgentPipeline(provider=provider, max_retries=0)

        result = pipeline.predict(_LETTER)

        self.assertTrue(result["invalid_output"])
        self.assertFalse(result["metadata"]["calls"]["core_invalid_output"])
        self.assertTrue(result["metadata"]["calls"]["classification_invalid_output"])
        self.assertTrue(result["metadata"]["calls"]["full_contract_invalid_output"])
        self.assertTrue(result["metadata"]["calls"]["optional_invalid_output"])
        self.assertEqual(result["final"]["epilepsy_type"]["value"], "unknown")
        self.assertIn("classification_pipeline_failure", result["warnings"])

    def test_seizure_frequency_json_failure_uses_core_fallback(self) -> None:
        provider = _FakeProvider(["not json", _BROADER_RESPONSE, _CLASSIFICATION_RESPONSE])
        pipeline = ProductionMultiAgentPipeline(provider=provider, max_retries=0)

        result = pipeline.predict(_LETTER)

        self.assertFalse(result["invalid_output"])
        self.assertFalse(result["metadata"]["calls"]["core_invalid_output"])
        self.assertTrue(result["metadata"]["calls"]["sf_call"]["fallback_used"])
        self.assertEqual(result["final"]["seizure_frequency"]["label"], "2 per week")
        self.assertIn("sf_deterministic_fallback", result["warnings"])

    def test_broader_json_failure_uses_valid_core_fallback(self) -> None:
        provider = _FakeProvider([_SF_RESPONSE, "not json", _CLASSIFICATION_RESPONSE])
        pipeline = ProductionMultiAgentPipeline(provider=provider, max_retries=0)

        result = pipeline.predict(_LETTER)

        self.assertFalse(result["invalid_output"])
        self.assertFalse(result["metadata"]["calls"]["core_invalid_output"])
        self.assertTrue(result["metadata"]["calls"]["broader_call"]["fallback_used"])
        self.assertEqual(result["final"]["current_medications"][0]["drug_name"], "lamotrigine")
        self.assertIn("broader_deterministic_fallback", result["warnings"])


class _FakeProvider:
    provider_name = "fake-provider"
    model = "fake-model"

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls = []

    def chat_json(self, messages, schema):
        self.calls.append({"messages": messages, "schema": schema})
        response = self.responses[len(self.calls) - 1]
        return LLMResult(
            content=response,
            model="fake-model",
            provider="fake-provider",
            raw={"usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
        )


if __name__ == "__main__":
    unittest.main()
