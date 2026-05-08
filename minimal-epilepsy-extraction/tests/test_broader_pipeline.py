import unittest
from unittest.mock import MagicMock

from epilepsy_agents.broader_field_schema import (
    broader_coverage_user_prompt,
    parse_broader_field_response,
    parse_broader_only_response,
    tier1a_h010_user_prompt,
    tier1a_user_prompt,
)
from epilepsy_agents.broader_verification import verify_broader_field_support
from epilepsy_agents.llm_pipeline import (
    BroaderFieldContextInjectedPipeline,
    BroaderFieldMediumPipeline,
    BroaderFieldMultiAgentPipeline,
    BroaderFieldSinglePromptPipeline,
)
from epilepsy_agents.providers import LLMResult


def _make_provider(content: str) -> MagicMock:
    provider = MagicMock()
    provider.provider_name = "mock"
    provider.model = "mock-model"
    provider.chat_json.return_value = LLMResult(
        content=content, model="mock-model", provider="mock", raw={}
    )
    return provider


_VALID_RESPONSE = """{
  "seizure_frequency": {"label": "2 per week", "evidence": "2 seizures per week", "confidence": 0.9},
  "current_medications": [
    {"drug_name": "levetiracetam", "dose_text": "500mg bd", "status": "current",
     "evidence": "prescribed levetiracetam 500mg bd", "confidence": 0.95}
  ],
  "seizure_types": [
    {"description": "focal aware seizures", "onset": "focal",
     "evidence": "focal aware seizures", "confidence": 0.9}
  ],
  "investigations": [
    {"investigation_type": "MRI", "result": "normal",
     "status": "historical", "evidence": "MRI brain was normal", "confidence": 0.95}
  ]
}"""

_EMPTY_ARRAYS_RESPONSE = """{
  "seizure_frequency": {"label": "unknown", "evidence": "", "confidence": 0.0},
  "current_medications": [],
  "seizure_types": [],
  "investigations": []
}"""


class BroaderFieldSchemaParsingTests(unittest.TestCase):
    def test_parse_valid_response(self) -> None:
        result = parse_broader_field_response(_VALID_RESPONSE)

        self.assertFalse(result["invalid_output"])
        self.assertEqual(result["seizure_frequency"]["label"], "2 per week")
        self.assertEqual(len(result["current_medications"]), 1)
        self.assertEqual(result["current_medications"][0]["drug_name"], "levetiracetam")
        self.assertEqual(len(result["seizure_types"]), 1)
        self.assertEqual(result["seizure_types"][0]["onset"], "focal")
        self.assertEqual(len(result["investigations"]), 1)
        self.assertEqual(result["investigations"][0]["investigation_type"], "MRI")

    def test_parse_empty_arrays(self) -> None:
        result = parse_broader_field_response(_EMPTY_ARRAYS_RESPONSE)

        self.assertFalse(result["invalid_output"])
        self.assertEqual(result["seizure_frequency"]["label"], "unknown")
        self.assertEqual(result["current_medications"], [])
        self.assertEqual(result["seizure_types"], [])
        self.assertEqual(result["investigations"], [])

    def test_parse_invalid_json_returns_fallback(self) -> None:
        result = parse_broader_field_response("not valid json at all")

        self.assertTrue(result["invalid_output"])
        self.assertEqual(result["seizure_frequency"]["label"], "unknown")
        self.assertEqual(result["current_medications"], [])

    def test_parse_coerces_non_list_fields(self) -> None:
        response = """{
          "seizure_frequency": {"label": "unknown", "evidence": "", "confidence": 0.0},
          "current_medications": null,
          "seizure_types": "not a list",
          "investigations": []
        }"""
        result = parse_broader_field_response(response)

        self.assertFalse(result["invalid_output"])
        self.assertEqual(result["current_medications"], [])
        self.assertEqual(result["seizure_types"], [])

    def test_parse_normalizes_investigation_variants_from_evidence(self) -> None:
        response = """{
          "seizure_frequency": {"label": "unknown", "evidence": "", "confidence": 0.0},
          "current_medications": [],
          "seizure_types": [],
          "investigations": [
            {"investigation_type": "video_EEG", "result": "pending", "status": "planned",
             "evidence": "Ambulatory home EEG has been requested", "confidence": 0.8},
            {"investigation_type": "blood_test", "result": "normal", "status": "completed",
             "evidence": "Routine bloods were normal including FBC and LFTs", "confidence": 0.8},
            {"investigation_type": "MRI", "result": "not_stated", "status": "not_stated",
             "evidence": "historical neuroimaging is not accessible in our system", "confidence": 0.7}
          ]
        }"""
        result = parse_broader_field_response(response)

        self.assertEqual(result["investigations"][0]["investigation_type"], "EEG")
        self.assertEqual(result["investigations"][1]["investigation_type"], "other")
        self.assertEqual(result["investigations"][2]["investigation_type"], "other")
        self.assertEqual(result["investigations"][2]["status"], "uncertain")

    def test_parse_does_not_infer_ct_from_blood_metabolic_or_ecg_evidence(self) -> None:
        response = """{
          "seizure_frequency": {"label": "unknown", "evidence": "", "confidence": 0.0},
          "current_medications": [],
          "seizure_types": [],
          "investigations": [
            {"investigation_type": "CT", "result": "pending", "status": "planned",
             "evidence": "Please arrange basic metabolic panel and ECG locally before uptitration to screen for any conduction concerns", "confidence": 0.8},
            {"investigation_type": "CT", "result": "pending", "status": "planned",
             "evidence": "requested thyroid function and metabolic profile", "confidence": 0.8},
            {"investigation_type": "CT", "result": "pending", "status": "planned",
             "evidence": "will request updated serum drug levels and routine bloods", "confidence": 0.8}
          ]
        }"""
        result = parse_broader_field_response(response)

        self.assertEqual(
            [item["investigation_type"] for item in result["investigations"]],
            ["other", "other", "other"],
        )

    def test_parse_preserves_explicit_ct_evidence(self) -> None:
        response = """{
          "seizure_frequency": {"label": "unknown", "evidence": "", "confidence": 0.0},
          "current_medications": [],
          "seizure_types": [],
          "investigations": [
            {"investigation_type": "other", "result": "normal", "status": "completed",
             "evidence": "CT head was normal", "confidence": 0.8}
          ]
        }"""
        result = parse_broader_field_response(response)

        self.assertEqual(result["investigations"][0]["investigation_type"], "CT")

    def test_parse_normalizes_conditional_and_pending_investigation_statuses(self) -> None:
        response = """{
          "seizure_frequency": {"label": "unknown", "evidence": "", "confidence": 0.0},
          "current_medications": [],
          "seizure_types": [],
          "investigations": [
            {"investigation_type": "EEG", "result": "pending", "status": "considered",
             "evidence": "Consider ambulatory EEG if frequency worsens", "confidence": 0.8},
            {"investigation_type": "MRI", "result": "pending", "status": "requested",
             "evidence": "MRI report has been requested and is awaited", "confidence": 0.8}
          ]
        }"""
        result = parse_broader_field_response(response)

        self.assertEqual(result["investigations"][0]["status"], "conditional")
        self.assertEqual(result["investigations"][1]["status"], "pending")

    def test_parse_filters_non_asm_medications(self) -> None:
        response = """{
          "seizure_frequency": {"label": "unknown", "evidence": "", "confidence": 0.0},
          "current_medications": [
            {"drug_name": "Lamotrigine", "dose_text": "100 mg twice daily", "status": "current",
             "evidence": "Lamotrigine 100 mg twice daily", "confidence": 0.9},
            {"drug_name": "Vitamin D3", "dose_text": "1000 IU once daily", "status": "current",
             "evidence": "Vitamin D3 1000 IU once daily", "confidence": 0.8},
            {"drug_name": "Ramipril", "dose_text": "5 mg once daily", "status": "current",
             "evidence": "Ramipril 5 mg once daily", "confidence": 0.8}
          ],
          "seizure_types": [],
          "investigations": []
        }"""
        result = parse_broader_field_response(response)

        self.assertEqual(len(result["current_medications"]), 1)
        self.assertEqual(result["current_medications"][0]["drug_name"], "Lamotrigine")

    def test_user_prompt_contains_all_key_names(self) -> None:
        prompt = tier1a_user_prompt("some letter text")

        for key in ("seizure_frequency", "current_medications", "seizure_types", "investigations",
                    "drug_name", "dose_text", "investigation_type"):
            self.assertIn(key, prompt)
        self.assertIn("anti-seizure medications only", prompt)
        self.assertIn("explicitly names or clearly describes a test", prompt)
        self.assertIn("do not infer EEG", prompt)
        self.assertIn("conditional", prompt)
        self.assertIn("absence-only", prompt)

    def test_h010_prompt_has_anti_abstention_guidance(self) -> None:
        prompt = tier1a_h010_user_prompt("some letter text")

        self.assertIn("do not use unknown for seizure-free patients", prompt)
        self.assertIn("use unknown only when", prompt)
        self.assertIn("empty array only if", prompt)

    def test_h010_pipeline_uses_anchored_prompt(self) -> None:
        provider = _make_provider(_VALID_RESPONSE)
        pipeline = BroaderFieldSinglePromptPipeline(
            provider=provider,
            user_prompt_fn=tier1a_h010_user_prompt,
        )

        pipeline.predict("test letter")

        call_args = provider.chat_json.call_args
        user_msg = call_args[0][0][1].content
        self.assertIn("do not use unknown for seizure-free patients", user_msg)


class BroaderFieldPipelineTests(unittest.TestCase):
    def test_pipeline_returns_structured_result(self) -> None:
        provider = _make_provider(_VALID_RESPONSE)
        pipeline = BroaderFieldSinglePromptPipeline(provider=provider)

        result = pipeline.predict(
            "The patient is prescribed levetiracetam 500mg bd. MRI brain was normal. "
            "She reports focal aware seizures and 2 seizures per week."
        )

        self.assertFalse(result["invalid_output"])
        self.assertEqual(result["seizure_frequency"]["label"], "2 per week")
        self.assertEqual(len(result["current_medications"]), 1)
        self.assertTrue(result["current_medications"][0]["support"]["supported"])
        self.assertTrue(result["investigations"][0]["support"]["supported"])
        self.assertIn("metadata", result)
        self.assertEqual(result["metadata"]["provider"], "mock")

    def test_pipeline_returns_fallback_on_provider_failure(self) -> None:
        provider = MagicMock()
        provider.provider_name = "mock"
        provider.model = "mock-model"
        provider.chat_json.side_effect = ConnectionError("refused")
        pipeline = BroaderFieldSinglePromptPipeline(provider=provider, max_retries=0)

        result = pipeline.predict("letter")

        self.assertTrue(result["invalid_output"])
        self.assertIn("pipeline_failure", result["warnings"])

    def test_pipeline_retries_malformed_model_json(self) -> None:
        provider = MagicMock()
        provider.provider_name = "mock"
        provider.model = "mock-model"
        provider.chat_json.side_effect = [
            LLMResult(content="not json", model="mock-model", provider="mock", raw={}),
            LLMResult(content=_VALID_RESPONSE, model="mock-model", provider="mock", raw={}),
        ]
        pipeline = BroaderFieldSinglePromptPipeline(provider=provider, max_retries=1)

        result = pipeline.predict(
            "The patient is prescribed levetiracetam 500mg bd. MRI brain was normal. "
            "She reports focal aware seizures and 2 seizures per week."
        )

        self.assertFalse(result["invalid_output"])
        self.assertEqual(result["seizure_frequency"]["label"], "2 per week")
        self.assertEqual(provider.chat_json.call_count, 2)
        self.assertIn("attempt_1_valueerror", result["warnings"])

    def test_pipeline_calls_provider_with_both_messages(self) -> None:
        provider = _make_provider(_VALID_RESPONSE)
        pipeline = BroaderFieldSinglePromptPipeline(provider=provider)

        pipeline.predict("test letter")

        call_args = provider.chat_json.call_args
        messages = call_args[0][0]
        self.assertEqual(messages[0].role, "system")
        self.assertEqual(messages[1].role, "user")
        self.assertIn("test letter", messages[1].content)


_BROADER_ONLY_RESPONSE = """{
  "current_medications": [
    {"drug_name": "levetiracetam", "dose_text": "500mg bd", "status": "current",
     "evidence": "prescribed levetiracetam 500mg bd", "confidence": 0.95}
  ],
  "seizure_types": [
    {"description": "focal aware seizures", "onset": "focal",
     "evidence": "focal aware seizures", "confidence": 0.9}
  ],
  "investigations": []
}"""

_SF_PREDICTION_RESPONSE = """{
  "label": "2 per week",
  "evidence": [{"text": "2 seizures per week", "start": null, "end": null, "source": "candidate"}],
  "confidence": 0.9,
  "analysis": "Extracted from candidate span.",
  "warnings": []
}"""


class BroaderOnlyParsingTests(unittest.TestCase):
    def test_parse_broader_only_response(self) -> None:
        result = parse_broader_only_response(_BROADER_ONLY_RESPONSE)

        self.assertFalse(result["invalid_output"])
        self.assertEqual(len(result["current_medications"]), 1)
        self.assertEqual(result["seizure_types"][0]["onset"], "focal")
        self.assertEqual(result["investigations"], [])

    def test_parse_broader_only_invalid_returns_fallback(self) -> None:
        result = parse_broader_only_response("not json")

        self.assertTrue(result["invalid_output"])
        self.assertEqual(result["current_medications"], [])

    def test_broader_coverage_prompt_is_coverage_oriented(self) -> None:
        prompt = broader_coverage_user_prompt("some letter text")

        self.assertIn("Seizure frequency is extracted in a separate call", prompt)
        self.assertIn("coverage-oriented and evidence-bound", prompt)
        self.assertIn("use empty arrays only when", prompt)
        self.assertIn("current_medications", prompt)
        self.assertIn("investigations", prompt)


class BroaderFieldVerificationTests(unittest.TestCase):
    def test_verifier_marks_exact_span_supported(self) -> None:
        result = parse_broader_field_response(_VALID_RESPONSE)
        verified = verify_broader_field_support(
            "She is prescribed levetiracetam 500mg bd. MRI brain was normal.",
            result,
        )

        self.assertEqual(
            verified["current_medications"][0]["support"]["evidence_grade"], "exact_span"
        )
        self.assertTrue(verified["current_medications"][0]["support"]["supported"])
        self.assertTrue(verified["investigations"][0]["support"]["supported"])

    def test_verifier_accepts_normalized_investigation_label(self) -> None:
        result = parse_broader_field_response("""{
          "seizure_frequency": {"label": "unknown", "evidence": "", "confidence": 0.0},
          "current_medications": [],
          "seizure_types": [],
          "investigations": [
            {"investigation_type": "blood_test", "result": "normal", "status": "completed",
             "evidence": "Blood tests were normal", "confidence": 0.8}
          ]
        }""")
        verified = verify_broader_field_support("Blood tests were normal.", result)
        support = verified["investigations"][0]["support"]

        self.assertTrue(support["supported"])
        self.assertEqual(verified["investigations"][0]["investigation_type"], "other")
        self.assertEqual(support["warnings"], [])

    def test_verifier_rejects_eeg_inferred_from_video_follow_up(self) -> None:
        result = parse_broader_field_response("""{
          "seizure_frequency": {"label": "unknown", "evidence": "", "confidence": 0.0},
          "current_medications": [],
          "seizure_types": [],
          "investigations": [
            {"investigation_type": "EEG", "result": "not_stated", "status": "completed",
             "evidence": "I conducted a video follow-up today", "confidence": 0.7}
          ]
        }""")
        verified = verify_broader_field_support("I conducted a video follow-up today.", result)
        support = verified["investigations"][0]["support"]

        self.assertFalse(support["supported"])
        self.assertIn("investigation_type_not_in_evidence", support["warnings"])

    def test_verifier_flags_conditional_plan_marked_as_planned(self) -> None:
        result = parse_broader_field_response("""{
          "seizure_frequency": {"label": "unknown", "evidence": "", "confidence": 0.0},
          "current_medications": [],
          "seizure_types": [],
          "investigations": [
            {"investigation_type": "EEG", "result": "pending", "status": "planned",
             "evidence": "Consider ambulatory EEG if frequency worsens", "confidence": 0.8}
          ]
        }""")
        verified = verify_broader_field_support(
            "Consider ambulatory EEG if frequency worsens.", result
        )
        support = verified["investigations"][0]["support"]

        self.assertFalse(support["supported"])
        self.assertFalse(support["status_supported"])
        self.assertIn("conditional_plan_marked_planned", support["warnings"])

    def test_verifier_accepts_conditional_status_for_conditional_plan(self) -> None:
        result = parse_broader_field_response("""{
          "seizure_frequency": {"label": "unknown", "evidence": "", "confidence": 0.0},
          "current_medications": [],
          "seizure_types": [],
          "investigations": [
            {"investigation_type": "EEG", "result": "pending", "status": "conditional",
             "evidence": "Consider ambulatory EEG if frequency worsens", "confidence": 0.8}
          ]
        }""")
        verified = verify_broader_field_support(
            "Consider ambulatory EEG if frequency worsens.", result
        )
        support = verified["investigations"][0]["support"]

        self.assertTrue(support["supported"])
        self.assertTrue(support["status_supported"])

    def test_verifier_rejects_non_asm_medication(self) -> None:
        verified = verify_broader_field_support(
            "Vitamin D3 1000 IU once daily.",
            {
                "current_medications": [
                    {
                        "drug_name": "Vitamin D3",
                        "dose_text": "1000 IU once daily",
                        "status": "current",
                        "evidence": "Vitamin D3 1000 IU once daily",
                        "confidence": 0.8,
                    }
                ],
                "investigations": [],
            },
        )
        support = verified["current_medications"][0]["support"]

        self.assertFalse(support["supported"])
        self.assertIn("non_asm_medication", support["warnings"])

    def test_verifier_rejects_absence_only_pending_investigation(self) -> None:
        result = parse_broader_field_response("""{
          "seizure_frequency": {"label": "unknown", "evidence": "", "confidence": 0.0},
          "current_medications": [],
          "seizure_types": [],
          "investigations": [
            {"investigation_type": "EEG", "result": "pending", "status": "pending",
             "evidence": "No prior EEGs available in our system", "confidence": 0.8}
          ]
        }""")
        verified = verify_broader_field_support(
            "No prior EEGs available in our system.", result
        )
        support = verified["investigations"][0]["support"]

        self.assertFalse(support["supported"])
        self.assertFalse(support["status_supported"])
        self.assertIn("absence_only_investigation", support["warnings"])


class BroaderFieldMultiAgentPipelineTests(unittest.TestCase):
    def _make_h009_provider(self) -> MagicMock:
        provider = MagicMock()
        provider.provider_name = "mock"
        provider.model = "mock-model"
        # First call returns SF prediction; subsequent calls return broader-only response
        provider.chat_json.side_effect = [
            LLMResult(content=_SF_PREDICTION_RESPONSE, model="mock-model", provider="mock", raw={}),
            LLMResult(content=_BROADER_ONLY_RESPONSE, model="mock-model", provider="mock", raw={}),
        ]
        return provider

    def test_h009_returns_combined_result(self) -> None:
        provider = self._make_h009_provider()
        pipeline = BroaderFieldMultiAgentPipeline(provider=provider)

        result = pipeline.predict("letter text about seizures and medications")

        self.assertFalse(result["invalid_output"])
        self.assertEqual(result["seizure_frequency"]["label"], "2 per week")
        self.assertEqual(len(result["current_medications"]), 1)
        self.assertEqual(len(result["seizure_types"]), 1)
        self.assertEqual(result["investigations"], [])

    def test_h009_metadata_has_two_call_keys(self) -> None:
        provider = self._make_h009_provider()
        pipeline = BroaderFieldMultiAgentPipeline(provider=provider)

        result = pipeline.predict("letter")

        self.assertIn("sf_call", result["metadata"])
        self.assertIn("broader_call", result["metadata"])

    def test_h009_broader_failure_sets_invalid_output(self) -> None:
        provider = MagicMock()
        provider.provider_name = "mock"
        provider.model = "mock-model"
        provider.chat_json.side_effect = [
            LLMResult(content=_SF_PREDICTION_RESPONSE, model="mock-model", provider="mock", raw={}),
            ConnectionError("refused"),
        ]
        pipeline = BroaderFieldMultiAgentPipeline(provider=provider, max_retries=0)

        result = pipeline.predict("letter")

        self.assertTrue(result["invalid_output"])
        self.assertEqual(result["current_medications"], [])
        # SF should still have valid label from stage 1
        self.assertEqual(result["seizure_frequency"]["label"], "2 per week")

    def test_h009_retries_malformed_broader_json(self) -> None:
        provider = MagicMock()
        provider.provider_name = "mock"
        provider.model = "mock-model"
        provider.chat_json.side_effect = [
            LLMResult(content=_SF_PREDICTION_RESPONSE, model="mock-model", provider="mock", raw={}),
            LLMResult(content="not json", model="mock-model", provider="mock", raw={}),
            LLMResult(content=_BROADER_ONLY_RESPONSE, model="mock-model", provider="mock", raw={}),
        ]
        pipeline = BroaderFieldMultiAgentPipeline(provider=provider, max_retries=1)

        result = pipeline.predict("letter text about seizures and medications")

        self.assertFalse(result["invalid_output"])
        self.assertEqual(len(result["current_medications"]), 1)
        self.assertEqual(provider.chat_json.call_count, 3)
        self.assertIn("broader_attempt_1_valueerror", result["warnings"])

    def test_h009_makes_exactly_two_llm_calls(self) -> None:
        provider = self._make_h009_provider()
        pipeline = BroaderFieldMultiAgentPipeline(provider=provider)

        pipeline.predict("letter text")

        self.assertEqual(provider.chat_json.call_count, 2)


class BroaderFieldContextInjectedPipelineTests(unittest.TestCase):
    def _make_h011_provider(self) -> MagicMock:
        provider = MagicMock()
        provider.provider_name = "mock"
        provider.model = "mock-model"
        provider.chat_json.side_effect = [
            LLMResult(content=_SF_PREDICTION_RESPONSE, model="mock-model", provider="mock", raw={}),
            LLMResult(content=_BROADER_ONLY_RESPONSE, model="mock-model", provider="mock", raw={}),
        ]
        return provider

    def test_h011_injects_sf_label_into_broader_prompt(self) -> None:
        provider = self._make_h011_provider()
        pipeline = BroaderFieldContextInjectedPipeline(provider=provider)

        pipeline.predict("letter about seizures and medications")

        broader_call_args = provider.chat_json.call_args_list[1]
        broader_user_msg = broader_call_args[0][0][1].content
        self.assertIn("2 per week", broader_user_msg)

    def test_h011_returns_combined_result(self) -> None:
        provider = self._make_h011_provider()
        pipeline = BroaderFieldContextInjectedPipeline(provider=provider)

        result = pipeline.predict("letter")

        self.assertFalse(result["invalid_output"])
        self.assertEqual(result["seizure_frequency"]["label"], "2 per week")
        self.assertEqual(len(result["current_medications"]), 1)

    def test_h011_sf_call_uses_dedicated_prompt_not_tier1a(self) -> None:
        """Stage 1 should use the h004 architecture, not the broader-field system prompt."""
        provider = self._make_h011_provider()
        pipeline = BroaderFieldContextInjectedPipeline(provider=provider)

        pipeline.predict("letter")

        sf_call_args = provider.chat_json.call_args_list[0]
        sf_system_msg = sf_call_args[0][0][0].content
        # h004 system prompt mentions seizure-frequency extraction specifically
        self.assertIn("seizure", sf_system_msg.lower())


class BroaderFieldMediumPipelineTests(unittest.TestCase):
    def _make_h012_provider(self) -> MagicMock:
        provider = MagicMock()
        provider.provider_name = "mock"
        provider.model = "mock-model"
        provider.chat_json.side_effect = [
            LLMResult(content=_SF_PREDICTION_RESPONSE, model="mock-model", provider="mock", raw={}),
            LLMResult(content=_BROADER_ONLY_RESPONSE, model="mock-model", provider="mock", raw={}),
        ]
        return provider

    def test_h012_uses_h003_style_full_letter_sf_call(self) -> None:
        provider = self._make_h012_provider()
        pipeline = BroaderFieldMediumPipeline(provider=provider)

        pipeline.predict("full letter text")

        sf_call_args = provider.chat_json.call_args_list[0]
        sf_user_msg = sf_call_args[0][0][1].content
        self.assertIn("full letter text", sf_user_msg)
        self.assertIn("Extract the current seizure-frequency label", sf_user_msg)

    def test_h012_uses_coverage_broader_prompt(self) -> None:
        provider = self._make_h012_provider()
        pipeline = BroaderFieldMediumPipeline(provider=provider)

        result = pipeline.predict("letter about seizures and medications")

        broader_call_args = provider.chat_json.call_args_list[1]
        broader_user_msg = broader_call_args[0][0][1].content
        self.assertIn("coverage-oriented and evidence-bound", broader_user_msg)
        self.assertEqual(result["seizure_frequency"]["label"], "2 per week")
        self.assertEqual(len(result["current_medications"]), 1)
        self.assertIn("sf_call", result["metadata"])
        self.assertIn("broader_call", result["metadata"])


if __name__ == "__main__":
    unittest.main()
