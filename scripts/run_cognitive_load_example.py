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
        "statement_id": "CL001",
        "domain": "health",
        "statement_text": "A diet rich in fruits, vegetables, and whole grains can help reduce the risk of heart disease.",
        "known_truth": True,
    },
    {
        "statement_id": "CL002",
        "domain": "space",
        "statement_text": "The Moon produces its own light in the same way that the Sun does.",
        "known_truth": False,
    },
]


LOAD_TASKS = {
    "cognitive_load_no_load": "",
    "cognitive_load_low_load": """
Before evaluating the statement, complete this secondary task:
T1. Remove the bracketed tags from this sentence: The [blue] campus [quietly] opened [small] gardens.
Include your cleaned sentence in secondary_task_answer.
""".strip(),
    "cognitive_load_high_load": """
Before evaluating the statement, complete these secondary tasks:
T1. Remove the bracketed tags from this sentence: The [blue] campus [quietly] opened [small] gardens.
T2. Reverse the word order of your cleaned sentence.
T3. Write the numbers from negative five to positive five in words.
Include all secondary-task answers in secondary_task_answer.
""".strip(),
}


PRE_SURVEY_MESSAGE = """
Please answer the following pre-study questions. Return JSON only.

Questions:
1. ai_literacy_1_to_7: How familiar are you with AI-generated or AI-assisted online content? 1 = not familiar at all, 7 = extremely familiar.
2. general_confidence_1_to_7: How confident are you generally when making factual judgments? 1 = not confident at all, 7 = extremely confident.
3. online_information_skepticism_1_to_7: How skeptical are you of factual claims online? 1 = not skeptical at all, 7 = extremely skeptical.
4. resilience_under_distraction_1_to_7: How well do you usually maintain focus when distracted? 1 = not well at all, 7 = extremely well.
5. perceived_working_memory_1_to_7: How good is your ability to keep multiple pieces of information in mind? 1 = very poor, 7 = excellent.
""".strip()


POST_SURVEY_MESSAGE = """
Please answer the following post-study questions based on the cognitive-load statement task you just completed. Return JSON only.

Questions:
1. perceived_task_difficulty_1_to_7: Overall, how difficult was the task? 1 = very easy, 7 = very difficult.
2. perceived_accuracy_1_to_7: How accurate do you think your true/false judgments were? 1 = not accurate at all, 7 = extremely accurate.
3. cognitive_load_felt_1_to_7: How mentally demanding did the task feel? 1 = not demanding at all, 7 = extremely demanding.
4. distraction_effect_1_to_7: How much did the secondary task affect your statement judgments? 1 = not at all, 7 = a great deal.
5. open_ended_strategy: In one sentence, describe your main strategy for doing the task.
""".strip()


def main() -> None:
    args = parse_args("Run cognitive-load API examples.")
    check_health(args.base_url)
    for setup_id, load_text in LOAD_TASKS.items():
        for persona_index in range(1, args.personas + 1):
            session_payload = {
                "experiment_setup_id": setup_id,
                "study": {
                    "name": "Cognitive load misinformation task",
                    "description": "Participants complete secondary tasks and judge factual statements.",
                    "instructions": "Answer the exact questionnaire and task questions as the participant.",
                },
                "criteria": {"age": {"min": 18, "max": 25}},
            }
            print_section(f"CREATE SESSION PAYLOAD ({setup_id}, persona {persona_index})", session_payload)
            session = post_json(args.base_url, "/v1/sessions", session_payload)
            print_section("CREATE SESSION RESPONSE", session)

            pre_payload = {
                "message": PRE_SURVEY_MESSAGE,
                "stimulus": {"questionnaire_id": "cognitive_load_pre_survey"},
                "metadata": {"phase": "pre_survey"},
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
                "ai_literacy_1_to_7",
                "general_confidence_1_to_7",
                "online_information_skepticism_1_to_7",
                "resilience_under_distraction_1_to_7",
                "perceived_working_memory_1_to_7",
            ]
            print_response_checks(pre, required_fields=pre_fields, rating_fields=pre_fields)

            for trial_index, statement in enumerate(STATEMENTS, start=1):
                task_prefix = f"{load_text}\n\n" if load_text else ""
                message = (
                    f"{task_prefix}"
                    "Now evaluate the target statement.\n\n"
                    f"Statement: {statement['statement_text']}\n"
                    "Return JSON only with answers to these exact questions:\n"
                    "1. veracity: Do you think the statement is true or false? Use true, false, or unsure.\n"
                    "2. confidence_1_to_7: How confident are you in your true/false judgment? 1 = not at all confident, 7 = extremely confident.\n"
                    "3. sharing_likelihood_1_to_7: If you saw this statement on social media, how likely would you be to share it? 1 = extremely unlikely, 7 = extremely likely.\n"
                    "4. one_sentence_reason: Briefly explain the main reason for your judgment in one sentence.\n"
                    "5. secondary_task_answer: If there was a secondary task, provide your answer; otherwise use null."
                )
                turn_payload = {
                    "message": message,
                    "stimulus": statement,
                    "metadata": {
                        "phase": "statement_task",
                        "load_setup_id": setup_id,
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
                print_response_checks(
                    turn,
                    required_fields=[
                        "veracity",
                        "confidence_1_to_7",
                        "sharing_likelihood_1_to_7",
                        "one_sentence_reason",
                        "secondary_task_answer",
                    ],
                    rating_fields=["confidence_1_to_7", "sharing_likelihood_1_to_7"],
                )

            post_payload = {
                "message": POST_SURVEY_MESSAGE,
                "stimulus": {"questionnaire_id": "cognitive_load_post_survey"},
                "metadata": {"phase": "post_survey"},
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
                "cognitive_load_felt_1_to_7",
                "distraction_effect_1_to_7",
                "open_ended_strategy",
            ]
            print_response_checks(
                post,
                required_fields=post_fields,
                rating_fields=[
                    "perceived_task_difficulty_1_to_7",
                    "perceived_accuracy_1_to_7",
                    "cognitive_load_felt_1_to_7",
                    "distraction_effect_1_to_7",
                ],
            )

            export = get_json(args.base_url, f"/v1/sessions/{session['session_id']}/export")
            print_export_summary(export)


if __name__ == "__main__":
    main()
