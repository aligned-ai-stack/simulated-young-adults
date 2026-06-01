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


PRE_SURVEY_MESSAGE = """
Please answer the following pre-study questions about the topic below. Return JSON only.

Topic: Individual lifestyle changes are a meaningful and necessary part of addressing climate change.

Questions:
1. pre_opinion_1_to_7: How much do you agree with the topic statement? 1 = strongly disagree, 7 = strongly agree.
2. pre_opinion_confidence_1_to_7: How confident are you in that view? 1 = not confident at all, 7 = extremely confident.
3. climate_topic_familiarity_1_to_7: How familiar are you with debates about individual versus systemic climate action? 1 = not familiar at all, 7 = extremely familiar.
4. openness_to_reconsider_1_to_7: How open are you to reconsidering your view during a discussion? 1 = not open at all, 7 = extremely open.
5. trust_in_ai_thinking_partner_1_to_7: How much would you trust an AI thinking partner to help you reason about this topic? 1 = not at all, 7 = a great deal.
""".strip()


OPENING_MESSAGE = """
The topic is: Individual lifestyle changes are a meaningful and necessary part of addressing climate change.

Please share your current view and the main reason you hold it in 3 to 5 sentences.
""".strip()


POST_SURVEY_MESSAGE = """
Please answer the following post-discussion questions based on the climate discussion you just completed. Return JSON only.

Questions:
1. post_opinion_1_to_7: How much do you agree with the topic statement now? 1 = strongly disagree, 7 = strongly agree.
2. post_opinion_confidence_1_to_7: How confident are you in your current view? 1 = not confident at all, 7 = extremely confident.
3. reconsideration_1_to_7: How much did the discussion make you reconsider your initial view? 1 = not at all, 7 = a great deal.
4. perceived_partner_helpfulness_1_to_7: How helpful was the thinking partner? 1 = not helpful at all, 7 = extremely helpful.
5. perceived_autonomy_1_to_7: During the discussion, how much did you feel you were making up your own mind? 1 = not at all, 7 = completely.
6. open_ended_reflection: In one sentence, describe what most influenced your final view.
""".strip()


CONDITION_TO_PARTNER_TEXTS = {
    "climate_thinking_partner_neutral": [
        (
            "Your thinking partner says: There are arguments that individual actions matter "
            "because they reduce demand and normalize sustainable habits. There are also arguments "
            "that systemic policies and corporate practices are necessary because individual choices "
            "alone cannot match the scale of emissions. Reply naturally in 3 to 5 sentences."
        ),
        (
            "Your thinking partner says: That makes sense. Some people treat personal behavior "
            "and policy as connected, because public habits can influence what leaders and companies "
            "see as acceptable. Reply naturally in 3 to 5 sentences."
        ),
    ],
    "climate_thinking_partner_steelman": [
        (
            "Your thinking partner says: A strong counterpoint is that individual action can be "
            "overstated when large institutions shape energy systems, transport options, and product "
            "availability. Even sincere lifestyle changes may have limited impact if infrastructure "
            "and policy remain unchanged. Reply naturally in 3 to 5 sentences."
        ),
        (
            "Your thinking partner says: Another concern is that focusing too much on personal "
            "responsibility can shift attention away from organizations with much larger emissions. "
            "Reply naturally in 3 to 5 sentences."
        ),
    ],
    "climate_thinking_partner_socratic": [
        (
            "Your thinking partner says: When you say individual changes are meaningful, what kind "
            "of impact would count as meaningful enough compared with policy or industry-level change? "
            "Reply naturally in 3 to 5 sentences."
        ),
        (
            "Your thinking partner says: If someone disagreed with you, what evidence or example "
            "would make you reconsider your position? Reply naturally in 3 to 5 sentences."
        ),
    ],
}


def main() -> None:
    args = parse_args("Run climate thinking-partner API examples.")
    check_health(args.base_url)
    for setup_id, partner_texts in CONDITION_TO_PARTNER_TEXTS.items():
        for persona_index in range(1, args.personas + 1):
            session_payload = {
                "experiment_setup_id": setup_id,
                "study": {
                    "name": "Climate discussion study",
                    "description": "Participants discuss a climate-change opinion statement.",
                    "instructions": "Respond conversationally as a young adult participant.",
                },
                "criteria": {"age": {"min": 18, "max": 25}},
            }
            print_section(f"CREATE SESSION PAYLOAD ({setup_id}, persona {persona_index})", session_payload)
            session = post_json(args.base_url, "/v1/sessions", session_payload)
            print_section("CREATE SESSION RESPONSE", session)

            pre_payload = {
                "message": PRE_SURVEY_MESSAGE,
                "stimulus": {"questionnaire_id": "climate_pre_survey"},
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
                "pre_opinion_1_to_7",
                "pre_opinion_confidence_1_to_7",
                "climate_topic_familiarity_1_to_7",
                "openness_to_reconsider_1_to_7",
                "trust_in_ai_thinking_partner_1_to_7",
            ]
            print_response_checks(pre, required_fields=pre_fields, rating_fields=pre_fields)

            opening_payload = {
                "message": OPENING_MESSAGE,
                "stimulus": {"topic_id": "climate_lifestyle_changes"},
                "metadata": {"phase": "opening", "condition_stored_not_shown": setup_id},
                "trial_id": "opening_position",
                "trial_index": 1,
                "reset_policy": "carryover",
                "response_mode": "interview",
                "capture_thinking": True,
            }
            print_section("OPENING TURN PAYLOAD", opening_payload)
            opening = post_json(args.base_url, f"/v1/sessions/{session['session_id']}/turns", opening_payload)
            print_section("OPENING TURN RESPONSE", opening)

            for exchange_number, partner_text in enumerate(partner_texts, start=1):
                exchange_payload = {
                    "message": partner_text,
                    "stimulus": {"topic_id": "climate_lifestyle_changes"},
                    "metadata": {
                        "phase": "exchange",
                        "exchange_number": exchange_number,
                        "condition_stored_not_shown": setup_id,
                    },
                    "trial_id": f"exchange_{exchange_number}",
                    "trial_index": exchange_number + 1,
                    "reset_policy": "carryover",
                    "response_mode": "interview",
                    "capture_thinking": True,
                }
                print_section(f"EXCHANGE {exchange_number} TURN PAYLOAD", exchange_payload)
                exchange = post_json(args.base_url, f"/v1/sessions/{session['session_id']}/turns", exchange_payload)
                print_section(f"EXCHANGE {exchange_number} TURN RESPONSE", exchange)

            post_payload = {
                "message": POST_SURVEY_MESSAGE,
                "stimulus": {"questionnaire_id": "climate_post_survey"},
                "metadata": {"phase": "post_survey"},
                "trial_id": "post_survey",
                "trial_index": len(partner_texts) + 2,
                "reset_policy": "carryover",
                "response_mode": "survey",
                "capture_thinking": True,
            }
            print_section("POST-SURVEY PAYLOAD", post_payload)
            post = post_json(args.base_url, f"/v1/sessions/{session['session_id']}/turns", post_payload)
            print_section("POST-SURVEY RESPONSE", post)
            post_fields = [
                "post_opinion_1_to_7",
                "post_opinion_confidence_1_to_7",
                "reconsideration_1_to_7",
                "perceived_partner_helpfulness_1_to_7",
                "perceived_autonomy_1_to_7",
                "open_ended_reflection",
            ]
            print_response_checks(
                post,
                required_fields=post_fields,
                rating_fields=[
                    "post_opinion_1_to_7",
                    "post_opinion_confidence_1_to_7",
                    "reconsideration_1_to_7",
                    "perceived_partner_helpfulness_1_to_7",
                    "perceived_autonomy_1_to_7",
                ],
            )

            export = get_json(args.base_url, f"/v1/sessions/{session['session_id']}/export")
            print_export_summary(export)


if __name__ == "__main__":
    main()
