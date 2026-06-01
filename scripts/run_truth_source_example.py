from __future__ import annotations

from api_examples_common import (
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


def main() -> None:
    args = parse_args("Run truth/source labeled and unlabeled API examples.")
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

            for trial_index, statement in enumerate(STATEMENTS, start=1):
                labeled = setup_id == "truth_source_labeled"
                if labeled:
                    message = (
                        f"Statement: {statement['statement_text']} "
                        f"Source label: {statement['actual_source']}-created. "
                        "Return JSON only with predicted_truthfulness, confidence_1_to_7, "
                        "trustworthiness_1_to_7."
                    )
                else:
                    message = (
                        f"Statement: {statement['statement_text']} Source label is hidden. "
                        "Return JSON only with predicted_truthfulness, confidence_1_to_7, "
                        "perceived_source_1_human_to_7_ai, trustworthiness_1_to_7."
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
                        "condition_hidden_from_message": not labeled,
                    },
                    "trial_id": statement["statement_id"],
                    "trial_index": trial_index,
                    "reset_policy": "carryover",
                    "response_mode": "experiment",
                    "capture_thinking": True,
                }
                print_section("TURN PAYLOAD", turn_payload)
                turn = post_json(args.base_url, f"/v1/sessions/{session['session_id']}/turns", turn_payload)
                print_section("TURN RESPONSE", turn)
                required_fields = [
                    "predicted_truthfulness",
                    "confidence_1_to_7",
                    "trustworthiness_1_to_7",
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

            export = get_json(args.base_url, f"/v1/sessions/{session['session_id']}/export")
            print_export_summary(export)


if __name__ == "__main__":
    main()
