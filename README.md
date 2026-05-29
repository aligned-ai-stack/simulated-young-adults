# AI Simulation Backend

Backend for synthetic young-adult research participants. Researchers call the API with a study task and optional inclusion criteria; the service samples a persona, maintains multi-turn state when needed, and returns clearly marked synthetic responses.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

By default the service uses `SIM_PROVIDER=mock`, which is deterministic and useful for development tests only.

For real runs, use a self-hosted local LLM backend: Ollama or vLLM. The model can run on a remote Linux server; this backend just points to that server's private URL or SSH-forwarded URL. No third-party model API is required.

```powershell
$env:SIM_PROVIDER="ollama"
$env:OLLAMA_BASE_URL="http://YOUR_LINUX_SERVER:11434"
$env:OLLAMA_MODEL="llama3.1"
uvicorn app.main:app --reload
```

Or with a vLLM OpenAI-compatible server:

```powershell
$env:SIM_PROVIDER="vllm"
$env:VLLM_BASE_URL="http://YOUR_LINUX_SERVER:8001"
$env:VLLM_MODEL="meta-llama/Llama-3.1-8B-Instruct"
$env:VLLM_API_KEY="EMPTY"
uvicorn app.main:app --reload
```

If the Linux server is reachable only through SSH, forward it locally and keep the backend URL on `127.0.0.1`:

```powershell
ssh -L 11434:127.0.0.1:11434 user@YOUR_LINUX_SERVER
$env:SIM_PROVIDER="ollama"
$env:OLLAMA_BASE_URL="http://127.0.0.1:11434"
```

Provider traces are stored on every turn. A real Ollama run stores `provider_trace.provider = "ollama"`; a real vLLM run stores `provider_trace.provider = "vllm"`.

## API shape

List registered experiment setups:

```http
GET /v1/experiment-setups
```

The first imported experiment setup from `Experiment setup.pdf` is registered as two setup ids:

| Setup id | Source label | Questions per statement |
| --- | --- | --- |
| `truth_source_unlabeled` | Source is not shown | truthfulness, confidence, perceived source, trustworthiness |
| `truth_source_labeled` | Source is shown as AI/human | truthfulness, confidence, trustworthiness |
| `ai_agent_literacy_intervention` | Not applicable | judgement, confidence, difficulty, short reasoning |
| `climate_thinking_partner_neutral` | Not applicable | pre-survey, opening position, 5 exchanges, post-survey |
| `climate_thinking_partner_steelman` | Not applicable | pre-survey, opening position, 5 exchanges, post-survey |
| `climate_thinking_partner_socratic` | Not applicable | pre-survey, opening position, 5 exchanges, post-survey |

The second imported experiment setup from `Experimental Setup.pdf` is registered as:

```text
ai_agent_literacy_intervention
```

It is a within-subject repeated-measures design. Each persona completes:

- 10 pre-intervention text-detection stimuli
- text-detection literacy intervention
- 10 post-intervention text-detection stimuli
- 10 pre-intervention image-detection stimuli
- image-detection literacy intervention
- 10 post-intervention image-detection stimuli

Use the same session and `reset_policy: "carryover"` across these phases when you want the same persona to retain the intervention. Store phase details in `stimulus` or `metadata`, for example `modality: "text"` and `stage: "pre_intervention"`.

The third imported experiment setup from `Experimental Set-up 2.pdf` is registered as three thinking-partner condition ids:

```text
climate_thinking_partner_neutral
climate_thinking_partner_steelman
climate_thinking_partner_socratic
```

The discussion topic is:

```text
Individual lifestyle changes are a meaningful and necessary part of addressing climate change.
```

Each condition has its own persona pool. The intended procedure is pre-study survey, participant opening position, 5 conversation exchanges with the assigned thinking partner, full transcript storage, and post-study survey. The sampled persona fields include age, AI literacy, AI trust, education, openness to new information, general confidence, reasoning style, initial climate-lifestyle view, gender, and nationality.

Each setup gets its own persona pool. The pool key is:

```text
experiment_setup_id + criteria + conditioned_attributes
```

That means `truth_source_unlabeled` and `truth_source_labeled` never share the same persona roster, and a narrower eligibility run creates/reuses a separate matched pool.

Optionally pre-create a persona pool:

```http
POST /v1/experiment-setups/truth_source_unlabeled/persona-pools
```

```json
{
  "pool_size": 500,
  "random_seed": 42,
  "criteria": {
    "age": {"min": 18, "max": 25}
  }
}
```

Create a reusable multi-turn session:

```http
POST /v1/sessions
```

```json
{
  "experiment_setup_id": "truth_source_unlabeled",
  "persona_pool_size": 500,
  "study": {
    "name": "Truth and source detection: unlabeled",
    "description": "Sequential statement judgment task.",
    "instructions": "Return the requested ratings for each statement."
  },
  "criteria": {
    "age": {"min": 18, "max": 25},
    "country": "US",
    "student_status": ["undergraduate", "not_student"]
  },
  "conditioned_attributes": {
    "country": "US"
  },
  "random_seed": 1234
}
```

Send a turn:

```http
POST /v1/sessions/{session_id}/turns
```

```json
{
  "message": "How often did you order food delivery last month?",
  "stimulus": {
    "statement_id": "s17",
    "source": "ai",
    "known_truth": false
  },
  "metadata": {
    "dataset_version": "v1"
  },
  "trial_id": "trial_001",
  "trial_index": 1,
  "reset_policy": "carryover",
  "response_mode": "survey",
  "capture_thinking": true
}
```

Single-turn convenience endpoint:

```http
POST /v1/respond
```

```json
{
  "study": {
    "name": "Campus transport",
    "description": "Assess commuting habits.",
    "instructions": "Give a concise open-ended survey answer."
  },
  "message": "How did you get to campus this week?",
  "criteria": {"age": {"min": 18, "max": 29}}
}
```

Every response includes `synthetic: true`, the sampled persona, the seed, and the session id for auditability.
When `experiment_setup_id` is provided, responses also include `persona_pool_id` and `persona_pool_member_id`.

## Trace and qualitative thinking storage

Each trial stores a full analysis/debug trace in SQLite. The default is `capture_thinking: true`.

The stored turn row includes:

- researcher request payload
- stimulus and metadata
- sampled persona at that turn
- reset policy and trial context
- exact system prompt
- visible history passed to the model
- qualitative thinking trace
- final participant response
- provider metadata and raw provider trace

Trace retrieval endpoints:

```http
GET /v1/sessions/{session_id}/turns
GET /v1/sessions/{session_id}/traces
```

The `qualitative_thinking` field is an explicit self-report rationale for coding, debugging, and later qualitative analysis. It is not hidden model chain-of-thought.

## Multi-turn and trial resets

Sequential studies can represent Prolific-style behavior with `reset_policy` on each turn:

| Policy | Meaning | Persona | Visible history |
| --- | --- | --- | --- |
| `carryover` | Same participant continues through the study. Use this for normal within-subject trials. | Same persona | All prior session turns |
| `trial` | Same participant starts or continues an isolated trial. Use this when trial content should not leak across trials. | Same persona | Prior turns with the same `trial_id` only |
| `full` | Fresh synthetic participant reset inside the same study stream. Use this for between-subject replacement or explicit full reset. | New sampled persona using the original criteria | No prior turns |

The prompt also receives lightweight crowdsourcing context: prior session turn count, completed trial count, visible prior turns, and estimated fatigue. This lets the model express realistic learning, attention drift, or satisficing only when the reset policy makes that plausible.

## Research-validity defaults

- Inclusion criteria restrict eligible sampled values.
- `conditioned_attributes` are the only forced persona fields.
- All other persona attributes are sampled independently from marginal distributions to avoid accidental dependency structure.
- The model prompt tells the agent not to claim to be a real human participant.
- Conversation history is stored per session for multi-turn consistency.
- Trial reset rules determine whether cross-trial memory and fatigue can affect a response.

## Persona fields

Personas include lightweight Prolific/survey-panel-style profile fields for screening, balancing, and downstream analysis. Examples include:

```text
first_name, last_name, age, sex, gender, ethnicity, race, detailed_race,
hispanic_origin, city, state, political_views, party_identification,
residence_at_16, family_structure_at_16, family_income_at_16,
parents' education, marital_status, work_status, military_service_duration,
religion, religion_at_16, born_in_us, us_citizenship_status,
highest_degree_received, speak_other_language, total_wealth
```

Addresses are generated only as synthetic placeholders and include `(synthetic)` in the string. They are not intended to represent real people or real panel records.

Researchers can condition or screen on these fields through `criteria` or `conditioned_attributes`, for example:

```json
{
  "criteria": {
    "age": {"min": 18, "max": 25},
    "state": ["AR", "TX"],
    "race": ["White", "Asian"]
  },
  "conditioned_attributes": {
    "sex": "Male",
    "highest_degree_received": "High school"
  }
}
```
