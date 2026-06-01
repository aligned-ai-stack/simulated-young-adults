# Researcher API Guide

Base URL:

```text
http://SERVER_IP
```

For local testing:

```text
http://127.0.0.1:8000
```

## 1. List Simulation Setups

```http
GET /v1/experiment-setups
```

Use this to choose `experiment_setup_id`.

Important: `experiment_setup_id` is backend routing metadata. Do not repeat the setup id, condition name, or hypothesis in the `message` shown to the simulated participant. For intervention studies, send only the intervention text or partner response that a real Prolific participant would see.

Current setup ids:

| Setup id | Document | Design |
| --- | --- | --- |
| `truth_source_unlabeled` | `ai-gen-content-true-false.pdf` | Content truth/source detection, source label hidden |
| `truth_source_labeled` | `ai-gen-content-true-false.pdf` | Content truth/source detection, source label shown |
| `image_text_ai_generated_intervention` | `image-text-ai-generated.pdf` | Text/image AI-content detection before and after literacy intervention |
| `cognitive_load_no_load` | `cognitive-load.pdf` | Misinformation veracity task with no secondary load |
| `cognitive_load_low_load` | `cognitive-load.pdf` | Misinformation veracity task with one secondary task |
| `cognitive_load_high_load` | `cognitive-load.pdf` | Misinformation veracity task with three secondary tasks |
| `climate_thinking_partner_neutral` | `ai-thinking-partner.pdf` | Neutral information partner condition |
| `climate_thinking_partner_steelman` | `ai-thinking-partner.pdf` | Steelman thinking partner condition |
| `climate_thinking_partner_socratic` | `ai-thinking-partner.pdf` | Socratic thinking partner condition |
| `sycophancy_neutral` | `sycophancy.pdf` | Neutral LLM condition |
| `sycophancy_sycophantic` | `sycophancy.pdf` | Sycophantic LLM condition |

Each setup has its own internal causal policy and persona-generation rules. Those details are used by the backend but are not returned in public API responses.

## 2. Generate Personas

```http
POST /v1/personas
```

Use this when the researcher wants personas first and will run the study loop on their side. A single bulk request is fine for normal batches such as 20, 72, or 100 personas. The current API limit is 500 personas per request. For larger runs, call the endpoint in batches.

Set `compact: true` when the researcher only needs core demographics and setup-relevant covariates. Set `compact: false` or omit it to receive the full persona profile.

Request:

```json
{
  "experiment_setup_id": "cognitive_load_high_load",
  "count": 100,
  "compact": true,
  "study": {
    "name": "Cognitive load misinformation task",
    "description": "Generate young-adult personas for the high-load condition."
  },
  "criteria": {
    "age": {"min": 18, "max": 25}
  }
}
```

Response:

```json
{
  "synthetic": true,
  "experiment_setup_id": "cognitive_load_high_load",
  "count": 100,
  "personas": [
    {
      "persona_id": "persona_...",
      "age": 22,
      "gender": "woman",
      "education": "undergraduate",
      "ai_literacy": 4,
      "resilience_under_distraction": 5,
      "cognitive_capacity": 4
    }
  ]
}
```

One-by-one assignment is just `count: 1`. Bulk is usually better for 100 personas because it is one HTTP call, no LLM call is involved, and persona generation is lightweight.

## 3. Create a Session

```http
POST /v1/sessions
```

Each session gets one fixed persona. Use the same `session_id` for all turns from that persona.

```json
{
  "experiment_setup_id": "truth_source_unlabeled",
  "study": {
    "name": "AI content truth/source detection",
    "description": "Sequential statement judgment task.",
    "instructions": "Return the requested ratings for each statement."
  },
  "criteria": {
    "age": {"min": 18, "max": 25}
  }
}
```

Optional fields such as `persona_pool_size` and `random_seed` are mainly for debugging or reproducibility. Researchers do not need to send them in normal runs.

Response:

```json
{
  "session_id": "session_...",
  "synthetic": true,
  "experiment_setup_id": "truth_source_unlabeled",
  "persona": {
    "persona_id": "persona_...",
    "age": 22,
    "ai_literacy": 5,
    "ai_trust": 3
  },
  "demographics": {}
}
```

## 4. Send a Trial or Turn

```http
POST /v1/sessions/{session_id}/turns
```

Use `stimulus` for the experimental item and ground-truth metadata. Use `metadata` for design labels such as block, phase, condition, or topic.
The `metadata` object is stored for analysis but should not be written into the participant-facing `message`.

```json
{
  "message": "Statement: Humans need oxygen to survive. Return JSON with predicted_truthfulness, confidence_1_to_7, perceived_source_1_human_to_7_ai, and trustworthiness_1_to_7.",
  "stimulus": {
    "statement_id": "T001",
    "statement_text": "Humans need oxygen to survive.",
    "known_truth": true,
    "actual_source": "human",
    "label_visible": false
  },
  "metadata": {
    "phase": "trial",
    "dataset_version": "v1"
  },
  "trial_id": "T001",
  "trial_index": 1,
  "reset_policy": "carryover",
  "response_mode": "experiment",
  "capture_thinking": true
}
```

Response:

```json
{
  "session_id": "session_...",
  "turn_id": 1,
  "synthetic": true,
  "experiment_setup_id": "truth_source_unlabeled",
  "trial_id": "T001",
  "reset_policy": "carryover",
  "qualitative_thinking": "Concise rationale for qualitative analysis.",
  "response": "{\"predicted_truthfulness\":\"true\",\"confidence_1_to_7\":6}"
}
```

Reset policies:

| Policy | Use when |
| --- | --- |
| `carryover` | Same persona continues and can remember prior turns |
| `trial` | Same persona, but only same `trial_id` history is visible |
| `full` | Fresh persona from the same pool; no prior turn history visible |

## Study-Specific Calls

### Truth/Source Detection, Unlabeled

Create a session:

```json
{
  "experiment_setup_id": "truth_source_unlabeled",
  "study": {
    "name": "Statement judgement task",
    "description": "Participants judge statement truthfulness and trustworthiness.",
    "instructions": "Answer each item using the requested JSON fields."
  },
  "criteria": {"age": {"min": 18, "max": 25}}
}
```

Send pre-survey questions as direct participant-facing items:

```json
{
  "message": "Please answer the following pre-study questions. Return JSON only.\n\nQuestions:\n1. ai_familiarity_1_to_7: How familiar are you with AI-generated text? 1 = not at all familiar, 7 = extremely familiar.\n2. ai_trust_1_to_7: In general, how much do you trust AI systems to provide accurate information? 1 = do not trust at all, 7 = trust completely.\n3. online_information_skepticism_1_to_7: How skeptical are you of factual claims you see online? 1 = not skeptical at all, 7 = extremely skeptical.\n4. self_rated_fact_checking_frequency_1_to_7: How often do you fact-check information before believing or sharing it? 1 = never, 7 = always.\n5. baseline_confidence_in_truth_judgments_1_to_7: How confident are you in your ability to judge whether short factual statements are true or false? 1 = not confident at all, 7 = extremely confident.",
  "stimulus": {"questionnaire_id": "truth_source_pre_survey"},
  "metadata": {"phase": "pre_survey"},
  "trial_id": "pre_survey",
  "trial_index": 0,
  "reset_policy": "carryover",
  "response_mode": "survey",
  "capture_thinking": true
}
```

Send each statement:

```json
{
  "message": "Please evaluate this statement.\n\nStatement: Regular physical activity can reduce the risk of cardiovascular disease.\nNo source label is shown.\n\nReturn JSON only with answers to these exact questions:\n1. predicted_truthfulness: Is the statement true or false? Use true, false, or unsure.\n2. confidence_1_to_7: How confident are you in that judgment? 1 = not at all confident, 7 = extremely confident.\n3. perceived_source_1_human_to_7_ai: Who do you think probably created this statement? 1 = definitely human, 7 = definitely AI.\n4. trustworthiness_1_to_7: How trustworthy does this statement seem? 1 = not trustworthy at all, 7 = extremely trustworthy.\n5. one_sentence_reason: Briefly explain the main reason for your judgment in one sentence.",
  "stimulus": {
    "statement_id": "S001",
    "statement_text": "Regular physical activity can reduce the risk of cardiovascular disease.",
    "known_truth": true,
    "actual_source": "human",
    "label_visible": false
  },
  "metadata": {"dataset_version": "v1"},
  "trial_id": "S001",
  "trial_index": 1,
  "reset_policy": "carryover",
  "response_mode": "experiment",
  "capture_thinking": true
}
```

Send post-survey questions after all statements:

```json
{
  "message": "Please answer the following post-study questions based on the statement-judgment task you just completed. Return JSON only.\n\nQuestions:\n1. perceived_task_difficulty_1_to_7: Overall, how difficult was it to judge the statements? 1 = very easy, 7 = very difficult.\n2. perceived_accuracy_1_to_7: How accurate do you think your judgments were? 1 = not accurate at all, 7 = extremely accurate.\n3. confidence_change_minus3_to_3: Compared with the start of the task, how did your confidence change? -3 = much less confident, 0 = no change, 3 = much more confident.\n4. relied_on_source_label_1_to_7: How much did source information, if shown, affect your judgments? 1 = not at all, 7 = a great deal.\n5. open_ended_strategy: In one sentence, what was your main strategy for judging the statements?",
  "stimulus": {"questionnaire_id": "truth_source_post_survey"},
  "metadata": {"phase": "post_survey"},
  "trial_id": "post_survey",
  "trial_index": 999,
  "reset_policy": "carryover",
  "response_mode": "survey",
  "capture_thinking": true
}
```

### Truth/Source Detection, Labeled

Create a session with:

```json
{
  "experiment_setup_id": "truth_source_labeled",
  "study": {
    "name": "Statement judgement task",
    "description": "Participants judge statement truthfulness and trustworthiness.",
    "instructions": "Answer each item using the requested JSON fields."
  },
  "criteria": {"age": {"min": 18, "max": 25}}
}
```

Send each statement with the source label in the participant-facing message:

```json
{
  "message": "Please evaluate this statement.\n\nStatement: Regular physical activity can reduce the risk of cardiovascular disease.\nSource label shown to you: human-created.\n\nReturn JSON only with answers to these exact questions:\n1. predicted_truthfulness: Is the statement true or false? Use true, false, or unsure.\n2. confidence_1_to_7: How confident are you in that judgment? 1 = not at all confident, 7 = extremely confident.\n3. trustworthiness_1_to_7: How trustworthy does this statement seem? 1 = not trustworthy at all, 7 = extremely trustworthy.\n4. one_sentence_reason: Briefly explain the main reason for your judgment in one sentence.",
  "stimulus": {
    "statement_id": "S001",
    "statement_text": "Regular physical activity can reduce the risk of cardiovascular disease.",
    "known_truth": true,
    "actual_source": "human",
    "shown_source_label": "human-created",
    "label_visible": true
  },
  "metadata": {"dataset_version": "v1"},
  "trial_id": "S001",
  "trial_index": 1,
  "reset_policy": "carryover",
  "response_mode": "experiment",
  "capture_thinking": true
}

```

### Climate Thinking Partner

Use one of:

```text
climate_thinking_partner_neutral
climate_thinking_partner_steelman
climate_thinking_partner_socratic
```

The researcher chooses the setup id for routing, but does not reveal the condition name to the participant. The partner response/intervention itself is sent as ordinary conversation text.

Create a session:

```json
{
  "experiment_setup_id": "climate_thinking_partner_steelman",
  "study": {
    "name": "Climate discussion study",
    "description": "Participants discuss a climate-change opinion statement.",
    "instructions": "Stay in character and respond conversationally."
  },
  "criteria": {"age": {"min": 18, "max": 25}}
}
```

Opening prompt:

```json
{
  "message": "The topic is: Individual lifestyle changes are a meaningful and necessary part of addressing climate change. Please share your current view and the main reason you hold it in 3 to 5 sentences.",
  "metadata": {"phase": "opening"},
  "trial_id": "climate_opening",
  "trial_index": 0,
  "reset_policy": "carryover",
  "response_mode": "interview",
  "capture_thinking": true
}
```

For each partner exchange, send only what the participant would see:

```json
{
  "message": "Your thinking partner says: [paste the intervention or partner response here]. Reply naturally in 3 to 5 sentences.",
  "metadata": {"phase": "exchange", "exchange_number": 1},
  "trial_id": "climate_exchange_1",
  "trial_index": 1,
  "reset_policy": "carryover",
  "response_mode": "interview",
  "capture_thinking": true
}
```

### Sycophancy Study

Use one of:

```text
sycophancy_neutral
sycophancy_sycophantic
```

Again, the setup id is routing metadata only. The participant-facing message should not say "sycophantic" or "neutral".

Create a session:

```json
{
  "experiment_setup_id": "sycophancy_sycophantic",
  "study": {
    "name": "Opinion discussion study",
    "description": "Participants discuss opinion-based topics with an AI partner.",
    "instructions": "Respond naturally and complete the requested survey fields."
  },
  "criteria": {"age": {"min": 18, "max": 25}}
}
```

Send a pre-measure:

```json
{
  "message": "Topic statement: AI tools should be used more often in university education. Return JSON with initial_opinion_1_to_7, initial_opinion_confidence_1_to_7, baseline_trust_in_ai_1_to_7.",
  "metadata": {"phase": "pre_interaction", "topic_id": "AI_EDU"},
  "trial_id": "AI_EDU_pre",
  "trial_index": 0,
  "reset_policy": "carryover",
  "response_mode": "survey",
  "capture_thinking": true
}
```

Send each partner turn without naming the condition:

```json
{
  "message": "The AI partner responds: [paste the partner response here]. Reply as the participant in 3 to 5 sentences.",
  "metadata": {"phase": "interaction", "topic_id": "AI_EDU", "exchange_number": 1},
  "trial_id": "AI_EDU_exchange_1",
  "trial_index": 1,
  "reset_policy": "carryover",
  "response_mode": "interview",
  "capture_thinking": true
}
```

Send post-measures:

```json
{
  "message": "After the conversation, return JSON with post_opinion_1_to_7, post_opinion_confidence_1_to_7, trust_in_llm_items_1_to_7, perceived_trustworthiness_items_1_to_7, manipulation_check_items_1_to_7.",
  "metadata": {"phase": "post_interaction", "topic_id": "AI_EDU"},
  "trial_id": "AI_EDU_post",
  "trial_index": 99,
  "reset_policy": "carryover",
  "response_mode": "survey",
  "capture_thinking": true
}
```

### Cognitive Load

Use one of:

```text
cognitive_load_no_load
cognitive_load_low_load
cognitive_load_high_load
```

Generate personas:

```json
{
  "experiment_setup_id": "cognitive_load_low_load",
  "count": 100,
  "compact": true,
  "study": {
    "name": "Cognitive load misinformation task",
    "description": "Generate personas for the low-load condition."
  },
  "criteria": {"age": {"min": 18, "max": 25}}
}
```

Relevant pre-treatment covariates include AI literacy, education, general confidence, domain knowledge, AI trust/skepticism, resilience under distraction, cognitive capacity, and working memory. Do not condition on veracity judgement, accuracy, confidence, sharing likelihood, or secondary-task performance.

### Image/Text AI-Generated Detection

Use:

```text
image_text_ai_generated_intervention
```

Generate personas:

```json
{
  "experiment_setup_id": "image_text_ai_generated_intervention",
  "count": 20,
  "compact": true,
  "study": {
    "name": "Image/text AI-generated content detection",
    "description": "Generate personas for text and image detection before and after literacy guidance."
  },
  "criteria": {"age": {"min": 18, "max": 25}}
}
```

Relevant pre-treatment covariates include AI literacy level, prior AI use, online content skepticism, attention to detail, and prior exposure to misinformation. Do not condition on post-intervention judgement, detection accuracy, confidence, difficulty, or improvement scores.

## 5. Store End-of-Session Demographics

```http
POST /v1/sessions/{session_id}/demographics
```

```json
{
  "demographics": {
    "age": 22,
    "gender": "woman",
    "country": "US",
    "education": "undergraduate"
  }
}
```

## 6. Fetch Data and Trace

Turns only:

```http
GET /v1/sessions/{session_id}/turns
```

Trace events only:

```http
GET /v1/sessions/{session_id}/traces
```

Full export:

```http
GET /v1/sessions/{session_id}/export
```

The full export returns:

```json
{
  "session": {},
  "experiment_setup": {},
  "persona": {},
  "demographics": {},
  "turns": [],
  "traces": []
}
```

Each stored turn includes the original request payload, stimulus, metadata, exact system prompt, visible history, qualitative thinking, final response, provider trace, persona snapshot, and trial context.

## Causal Sampling Rule

The backend uses internal causal policies to sample study-appropriate pre-treatment persona attributes and avoid conditioning persona generation on outcomes, mediators, or colliders. These internal policies are not exposed in public API responses.
