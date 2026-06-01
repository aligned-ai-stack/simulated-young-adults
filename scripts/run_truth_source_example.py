from __future__ import annotations

from api_examples_common import (
    check_health,
    get_json,
    parse_args,
    post_json,
    print_export_summary,
    print_response_checks,
    print_section,
)


STATEMENTS = [
    {
        "statement_id": "TS001",
        "statement_text": "Regular physical activity can reduce the risk of cardiovascular disease.",
        "known_truth": True,
        "actual_source": "human",
    },
    {
        "statement_id": "TS002",
        "statement_text": "Humans can safely breathe on the surface of Mars without equipment.",
        "known_truth": False,
        "actual_source": "ai",
    },
]


PRE_SURVEY_MESSAGE = """
Please answer the following pre-study questions. Return JSON only.

Questions:
1. ai_familiarity_1_to_7: How familiar are you with AI-generated text? 1 = not at all familiar, 7 = extremely familiar.
2. ai_trust_1_to_7: In general, how much do you trust AI systems to provide accurate information? 1 = do not trust at all, 7 = trust completely.
3. online_information_skepticism_1_to_7: How skeptical are you of factual claims you see online? 1 = not skeptical at all, 7 = extremely skeptical.
4. self_rated_fact_checking_frequency_1_to_7: How often do you fact-check information before believing or sharing it? 1 = never, 7 = always.
5. baseline_confidence_in_truth_judgments_1_to_7: How confident are you in your ability to judge whether short factual statements are true or false? 1 = not confident at all, 7 = extremely confident.
""".strip()


POST_SURVEY_MESSAGE = """
Please answer the following post-study questions based on the statement-judgment task you just completed. Return JSON only.

Questions:
1. perceived_task_difficulty_1_to_7: Overall, how difficult was it to judge the statements? 1 = very easy, 7 = very difficult.
2. perceived_accuracy_1_to_7: How accurate do you think your judgments were? 1 = not accurate at all, 7 = extremely accurate.
3. confidence_change_minus3_to_3: Compared with the start of the task, how did your confidence change? -3 = much less confident, 0 = no change, 3 = much more confident.
4. relied_on_source_label_1_to_7: How much did source information, if shown, affect your judgments? 1 = not at all, 7 = a great deal.
5. open_ended_strategy: In one sentence, what was your main strategy for judging the statements?
""".strip()


def main() -> None:
    args = parse_args("Run truth/source labeled and unlabeled API examples.")
    check_health(args.base_url)
    for setup_id in ["truth_source_unlabeled", "truth_source_labeled"]:
        for persona_index in range(1, args.personas + 1):
            session_payload = {
                "experiment_setup_id": setup_id,
                "study": {
                    "name": "Statement judgement task",
                    "description": "Participants judge truthfulness and trustworthiness.",
                    "instructions": "Answer each item using only the requested JSON fields.",
                },
                "criteria": {"age": {"min": 18, "max": 25}},
            }
            print_section(f"CREATE SESSION PAYLOAD ({setup_id}, persona {persona_index})", session_payload)
            session = post_json(args.base_url, "/v1/sessions", session_payload)
            print_section("CREATE SESSION RESPONSE", session)

            pre_payload = {
                "message": PRE_SURVEY_MESSAGE,
                "stimulus": {"questionnaire_id": "truth_source_pre_survey"},
                "metadata": {
                    "example_script": "run_truth_source_example.py",
                    "phase": "pre_survey",
                },
                "trial_id": "pre_survey",
                "trial_index": 0,
                "reset_policy": "carryover",
                "response_mode": "survey",
                "capture_thinking": True,
            }
            print_section("PRE-SURVEY PAYLOAD", pre_payload)
            pre = post_json(args.base_url, f"/v1/sessions/{session['session_id']}/turns", pre_payload)
            print_section("PRE-SURVEY RESPONSE", pre)
            pre_fields = [
                "ai_familiarity_1_to_7",
                "ai_trust_1_to_7",
                "online_information_skepticism_1_to_7",
                "self_rated_fact_checking_frequency_1_to_7",
                "baseline_confidence_in_truth_judgments_1_to_7",
            ]
            print_response_checks(pre, required_fields=pre_fields, rating_fields=pre_fields)

            for trial_index, statement in enumerate(STATEMENTS, start=1):
                labeled = setup_id == "truth_source_labeled"
                if labeled:
                    message = (
                        f"Please evaluate this statement.\n\n"
                        f"Statement: {statement['statement_text']}\n"
                        f"Source label shown to you: {statement['actual_source']}-created.\n\n"
                        "Return JSON only with answers to these exact questions:\n"
                        "1. predicted_truthfulness: Is the statement true or false? Use true, false, or unsure.\n"
                        "2. confidence_1_to_7: How confident are you in that judgment? 1 = not at all confident, 7 = extremely confident.\n"
                        "3. trustworthiness_1_to_7: How trustworthy does this statement seem? 1 = not trustworthy at all, 7 = extremely trustworthy.\n"
                        "4. one_sentence_reason: Briefly explain the main reason for your judgment in one sentence."
                    )
                else:
                    message = (
                        f"Please evaluate this statement.\n\n"
                        f"Statement: {statement['statement_text']}\n"
                        "No source label is shown.\n\n"
                        "Return JSON only with answers to these exact questions:\n"
                        "1. predicted_truthfulness: Is the statement true or false? Use true, false, or unsure.\n"
                        "2. confidence_1_to_7: How confident are you in that judgment? 1 = not at all confident, 7 = extremely confident.\n"
                        "3. perceived_source_1_human_to_7_ai: Who do you think probably created this statement? 1 = definitely human, 7 = definitely AI.\n"
                        "4. trustworthiness_1_to_7: How trustworthy does this statement seem? 1 = not trustworthy at all, 7 = extremely trustworthy.\n"
                        "5. one_sentence_reason: Briefly explain the main reason for your judgment in one sentence."
                    )

                stimulus = {
                    **statement,
                    "label_visible": labeled,
                }
                if labeled:
                    stimulus["shown_source_label"] = f"{statement['actual_source']}-created"

                turn_payload = {
                    "message": message,
                    "stimulus": stimulus,
                    "metadata": {
                        "example_script": "run_truth_source_example.py",
                        "phase": "statement_task",
                        "source_label_condition": "labeled" if labeled else "unlabeled",
                    },
                    "trial_id": statement["statement_id"],
                    "trial_index": trial_index,
                    "reset_policy": "carryover",
                    "response_mode": "experiment",
                    "capture_thinking": True,
                }
                print_section("STATEMENT TURN PAYLOAD", turn_payload)
                turn = post_json(args.base_url, f"/v1/sessions/{session['session_id']}/turns", turn_payload)
                print_section("STATEMENT TURN RESPONSE", turn)
                required_fields = [
                    "predicted_truthfulness",
                    "confidence_1_to_7",
                    "trustworthiness_1_to_7",
                    "one_sentence_reason",
                ]
                rating_fields = ["confidence_1_to_7", "trustworthiness_1_to_7"]
                if not labeled:
                    required_fields.append("perceived_source_1_human_to_7_ai")
                    rating_fields.append("perceived_source_1_human_to_7_ai")
                print_response_checks(
                    turn,
                    required_fields=required_fields,
                    rating_fields=rating_fields,
                )

            post_payload = {
                "message": POST_SURVEY_MESSAGE,
                "stimulus": {"questionnaire_id": "truth_source_post_survey"},
                "metadata": {
                    "example_script": "run_truth_source_example.py",
                    "phase": "post_survey",
                },
                "trial_id": "post_survey",
                "trial_index": len(STATEMENTS) + 1,
                "reset_policy": "carryover",
                "response_mode": "survey",
                "capture_thinking": True,
            }
            print_section("POST-SURVEY PAYLOAD", post_payload)
            post = post_json(args.base_url, f"/v1/sessions/{session['session_id']}/turns", post_payload)
            print_section("POST-SURVEY RESPONSE", post)
            post_fields = [
                "perceived_task_difficulty_1_to_7",
                "perceived_accuracy_1_to_7",
                "confidence_change_minus3_to_3",
                "relied_on_source_label_1_to_7",
                "open_ended_strategy",
            ]
            print_response_checks(
                post,
                required_fields=post_fields,
                rating_fields=[
                    "perceived_task_difficulty_1_to_7",
                    "perceived_accuracy_1_to_7",
                    "relied_on_source_label_1_to_7",
                ],
            )

            export = get_json(args.base_url, f"/v1/sessions/{session['session_id']}/export")
            print_export_summary(export)


if __name__ == "__main__":
    main()
