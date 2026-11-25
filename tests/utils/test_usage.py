import pytest

from llm_gateway.utils.usage import extract_token_usage


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (
            {"usage": {"prompt_tokens": 10, "completion_tokens": 20}},
            (10, 20, "provider"),
        ),
        (
            {"usage": {"input_tokens": 11, "output_tokens": 21}},
            (11, 21, "provider"),
        ),
        (
            {"tokens": {"prompt": 12, "completion": 22}},
            (12, 22, "provider"),
        ),
    ],
)
def test_provider_usage_shapes(result, expected):
    assert extract_token_usage(result, "one two three", "four five") == expected


def test_missing_usage_falls_back_to_explicit_estimate():
    assert extract_token_usage({}, "one two three", "four five") == (
        3,
        2,
        "estimated",
    )


def test_partial_usage_does_not_claim_provider_attribution():
    result = {"usage": {"prompt_tokens": 10}}
    assert extract_token_usage(result, "one two three", "four five") == (
        3,
        2,
        "estimated",
    )
