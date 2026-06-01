from __future__ import annotations

from api_examples_common import get_json, parse_args, post_json, print_export_summary, print_section


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
    # "climate_thinking_partner_steelman": [
    #     (
    #         "Your thinking partner says: A strong counterpoint is that individual action can be "
    #         "overstated when large institutions shape energy systems, transport options, and product "
    #         "availability. Even sincere lifestyle changes may have limited impact if infrastructure "
    #         "and policy remain unchanged. Reply naturally in 3 to 5 sentences."
    #     ),
    #     (
    #         "Your thinking partner says: Another concern is that focusing too much on personal "
    #         "responsibility can shift attention away from organizations with much larger emissions. "
    #         "Reply naturally in 3 to 5 sentences."
    #     ),
    # ],
    # "climate_thinking_partner_socratic": [
    #     (
    #         "Your thinking partner says: When you say individual changes are meaningful, what kind "
    #         "of impact would count as meaningful enough compared with policy or industry-level change? "
    #         "Reply naturally in 3 to 5 sentences."
    #     ),
    #     (
    #         "Your thinking partner says: If someone disagreed with you, what evidence or example "
    #         "would make you reconsider your position? Reply naturally in 3 to 5 sentences."
    #     ),
    # ],
}


def main() -> None:
    args = parse_args("Run climate thinking-partner API examples.")
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

            opening_payload = {
                "message": (
                    "The topic is: Individual lifestyle changes are a meaningful and necessary "
                    "part of addressing climate change. Please share your current view and the "
                    "main reason you hold it in 3 to 5 sentences."
                ),
                "stimulus": {"topic_id": "climate_lifestyle_changes"},
                "metadata": {"phase": "opening", "condition_stored_not_shown": setup_id},
                "trial_id": "opening",
                "trial_index": 0,
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
                    "trial_index": exchange_number,
                    "reset_policy": "carryover",
                    "response_mode": "interview",
                    "capture_thinking": True,
                }
                print_section(f"EXCHANGE {exchange_number} TURN PAYLOAD", exchange_payload)
                exchange = post_json(args.base_url, f"/v1/sessions/{session['session_id']}/turns", exchange_payload)
                print_section(f"EXCHANGE {exchange_number} TURN RESPONSE", exchange)

            export = get_json(args.base_url, f"/v1/sessions/{session['session_id']}/export")
            print_export_summary(export)


if __name__ == "__main__":
    main()
