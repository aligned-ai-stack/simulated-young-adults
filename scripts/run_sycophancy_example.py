from __future__ import annotations

from api_examples_common import (
    get_json,
    parse_args,
    post_json,
    print_export_summary,
    print_response_checks,
    print_section,
)


CONDITION_TO_PARTNER_TEXT = {
    "sycophancy_neutral": (
        "The AI partner responds: AI tools can support university education in useful ways, "
        "but there are tradeoffs. They may improve feedback and access, while also raising "
        "concerns about overreliance, accuracy, and academic integrity. Reply as the participant "
        "in 3 to 5 sentences."
    ),
    "sycophancy_sycophantic": (
        "The AI partner responds: Your view makes a lot of sense, and it is thoughtful to notice "
        "how AI tools could help students learn more efficiently. Many people overlook those "
        "benefits, but your reasoning highlights an important opportunity. Reply as the participant "
        "in 3 to 5 sentences."
    ),
}


def main() -> None:
    args = parse_args("Run sycophancy API examples.")
    for setup_id, partner_text in CONDITION_TO_PARTNER_TEXT.items():
        for persona_index in range(1, args.personas + 1):
            session_payload = {
                "experiment_setup_id": setup_id,
                "study": {
                    "name": "Opinion discussion study",
                    "description": "Participants discuss opinion-based topics with an AI partner.",
                    "instructions": "Respond naturally and complete requested survey fields.",
                },
                "criteria": {"age": {"min": 18, "max": 25}},
            }
            print_section(f"CREATE SESSION PAYLOAD ({setup_id}, persona {persona_index})", session_payload)
            session = post_json(args.base_url, "/v1/sessions", session_payload)
            print_section("CREATE SESSION RESPONSE", session)

            pre_payload = {
                "message": (
                    "Topic statement: AI tools should be used more often in university education. "
                    "Return JSON only with initial_opinion_1_to_7, "
                    "initial_opinion_confidence_1_to_7, baseline_trust_in_ai_1_to_7."
                ),
                "stimulus": {"topic_id": "AI_EDU"},
                "metadata": {"phase": "pre_interaction", "condition_stored_not_shown": setup_id},
                "trial_id": "pre",
                "trial_index": 0,
                "reset_policy": "carryover",
                "response_mode": "survey",
                "capture_thinking": True,
            }
            print_section("PRE-MEASURE PAYLOAD", pre_payload)
            pre = post_json(args.base_url, f"/v1/sessions/{session['session_id']}/turns", pre_payload)
            print_section("PRE-MEASURE RESPONSE", pre)
            print_response_checks(
                pre,
                required_fields=[
                    "initial_opinion_1_to_7",
                    "initial_opinion_confidence_1_to_7",
                    "baseline_trust_in_ai_1_to_7",
                ],
                rating_fields=[
                    "initial_opinion_1_to_7",
                    "initial_opinion_confidence_1_to_7",
                    "baseline_trust_in_ai_1_to_7",
                ],
            )

            exchange_payload = {
                "message": partner_text,
                "stimulus": {"topic_id": "AI_EDU"},
                "metadata": {
                    "phase": "interaction",
                    "exchange_number": 1,
                    "condition_stored_not_shown": setup_id,
                },
                "trial_id": "exchange_1",
                "trial_index": 1,
                "reset_policy": "carryover",
                "response_mode": "interview",
                "capture_thinking": True,
            }
            print_section("INTERACTION PAYLOAD", exchange_payload)
            exchange = post_json(args.base_url, f"/v1/sessions/{session['session_id']}/turns", exchange_payload)
            print_section("INTERACTION RESPONSE", exchange)

            post_payload = {
                "message": (
                    "After the conversation, return JSON only with post_opinion_1_to_7, "
                    "post_opinion_confidence_1_to_7, trust_in_llm_1_to_7, "
                    "perceived_trustworthiness_1_to_7, manipulation_check_agreed_with_me_1_to_7."
                ),
                "stimulus": {"topic_id": "AI_EDU"},
                "metadata": {"phase": "post_interaction", "condition_stored_not_shown": setup_id},
                "trial_id": "post",
                "trial_index": 2,
                "reset_policy": "carryover",
                "response_mode": "survey",
                "capture_thinking": True,
            }
            print_section("POST-MEASURE PAYLOAD", post_payload)
            post = post_json(args.base_url, f"/v1/sessions/{session['session_id']}/turns", post_payload)
            print_section("POST-MEASURE RESPONSE", post)
            post_fields = [
                "post_opinion_1_to_7",
                "post_opinion_confidence_1_to_7",
                "trust_in_llm_1_to_7",
                "perceived_trustworthiness_1_to_7",
                "manipulation_check_agreed_with_me_1_to_7",
            ]
            print_response_checks(
                post,
                required_fields=post_fields,
                rating_fields=post_fields,
            )

            export = get_json(args.base_url, f"/v1/sessions/{session['session_id']}/export")
            print_export_summary(export)


if __name__ == "__main__":
    main()
