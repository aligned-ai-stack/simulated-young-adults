from __future__ import annotations

from api_examples_common import (
    get_json,
    parse_args,
    post_json,
    print_export_summary,
    print_response_checks,
    print_section,
)



def main() -> None:
    args = parse_args("image_text_ai_generated_intervention")
    
    session_payload = {
            "experiment_setup_id": "image_text_ai_generated_intervention",
            "count": 1,
            "compact": True,
            "study": {
                "name": "Cognitive load misinformation task",
                "description": "Generate young-adult personas for the high-load condition."
            },
            "criteria": {
                "age": {"min": 18, "max": 25}
            },
            "conditioned_attributes": {}
        }
    print_section(f"CREATE PERSONA PAYLOAD", session_payload)
    session = post_json(args.base_url, "/v1/personas", session_payload)
    print_section("CREATE SESSION RESPONSE", session)




if __name__ == "__main__":
    main()
