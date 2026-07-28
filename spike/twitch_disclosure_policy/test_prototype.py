"""Executable claims for the disposable Twitch disclosure prototype."""

from __future__ import annotations

from minnarone.human import HumanLikeness
from spike.twitch_disclosure_policy.prototype import (
    APPROVED_COPY,
    REPOSITORY_URL,
    DeterministicStrategy,
    HybridStrategy,
    PromptOnlyStrategy,
    classify_interaction,
    comparison_corpus,
    run_strategy,
)


def _by_id(strategy_name: str):
    _, observations = run_strategy(strategy_name)
    return {item.scenario_id: item for item in observations}


def test_classifier_matches_the_approved_tabletop_corpus():
    for event in comparison_corpus():
        assert classify_interaction(event) is event.expected_kind


def test_prompt_only_exposes_the_expected_policy_failures():
    metrics, observations = run_strategy(PromptOnlyStrategy.name)

    assert metrics.false_positive_promotions == 3
    assert metrics.false_negative_disclosures == 1
    assert metrics.repeated_session_links == 6
    assert metrics.repeated_conversation_links == 2
    assert metrics.proactive_cadence_violations == 1
    assert metrics.natural_answers == metrics.natural_answer_opportunities == 1
    assert metrics.network_sends == 0
    assert all(item.action in {"shadow", "drop"} for item in observations)


def test_deterministic_policy_enforces_safety_but_loses_answer_naturalness():
    metrics, observations = run_strategy(DeterministicStrategy.name)

    assert metrics.false_positive_promotions == 0
    assert metrics.false_negative_disclosures == 0
    assert metrics.repeated_session_links == 0
    assert metrics.repeated_conversation_links == 0
    assert metrics.proactive_cadence_violations == 0
    assert metrics.natural_answers == 0
    assert metrics.natural_answer_opportunities == 1
    assert metrics.network_sends == 0
    assert all(item.action in {"shadow", "drop"} for item in observations)


def test_hybrid_enforces_policy_and_keeps_the_contextual_answer():
    metrics, observations = run_strategy(HybridStrategy.name)

    assert metrics.false_positive_promotions == 0
    assert metrics.false_negative_disclosures == 0
    assert metrics.repeated_session_links == 0
    assert metrics.repeated_conversation_links == 0
    assert metrics.proactive_cadence_violations == 0
    assert metrics.natural_answers == metrics.natural_answer_opportunities == 1
    assert metrics.network_sends == 0
    assert all(item.action in {"shadow", "drop"} for item in observations)


def test_hybrid_commits_caps_only_after_the_shadow_budget_accepts():
    observations = _by_id(HybridStrategy.name)

    dropped = observations["qualifying_budget_drop"]
    retried = observations["qualifying_retry_after_budget"]
    assert dropped.action == "drop"
    assert dropped.reason == "budget_minute"
    assert APPROVED_COPY in dropped.message
    assert retried.action == "shadow"
    assert APPROVED_COPY in retried.message


def test_hybrid_resets_the_link_cap_for_a_new_session():
    observations = _by_id(HybridStrategy.name)

    first_session = observations["identity_and_how"]
    new_session = observations["new_session_false_negative"]
    assert first_session.session_id != new_session.session_id
    assert REPOSITORY_URL in first_session.message
    assert REPOSITORY_URL in new_session.message


def test_deterministic_boundaries_reject_an_unexpected_model_url():
    for strategy_name in (DeterministicStrategy.name, HybridStrategy.name):
        observation = _by_id(strategy_name)["unexpected_model_url"]
        assert observation.action == "drop"
        assert observation.reason == "unexpected_repository_url"
        assert REPOSITORY_URL not in observation.message


def test_existing_text_dedup_is_not_a_repository_link_cap():
    human = HumanLikeness(dedup_threshold=0.9)
    paraphrase = f"Yes — the public source is here: {REPOSITORY_URL}"

    decision = human.process(paraphrase, [APPROVED_COPY])

    assert decision.drop is False
