# Simulated participants for study development

A FastAPI service for testing surveys and conversational studies with synthetic young-adult personas. It generates baseline attributes from study-specific causal graphs, keeps session and trial history, and records model responses in SQLite.

Built with Python, FastAPI, Pydantic, and SQLite. Model responses come from self-hosted Ollama or vLLM; a deterministic mock provider supports development. Part of [Aligned AI Stack](https://github.com/aligned-ai-stack).

## What it implements

- **Persona generation:** hand-specified directed acyclic graphs and structural equations for baseline attributes, with seeded sampling.
- **Eligibility and interventions:** `criteria` filter complete draws; `conditioned_attributes` set baseline values before generating their descendants. Treatments, mediators, outcomes, and designated selection nodes are rejected as persona inputs.
- **Study sessions:** reusable persona pools and three history policies: carryover, isolated trial, and full persona reset.
- **Response traces:** request payloads, prompts, visible history, model metadata, and optional self-report rationales stored for inspection and export.

Registered studies cover source labeling, AI-content detection, cognitive load, climate discussion, and sycophancy. The researcher supplies stimuli and runs the study procedure.

## Run locally

Requires Python 3.10 or newer. From the repository root, in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:SIM_PROVIDER="mock"
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open [API documentation](http://127.0.0.1:8000/docs). The health endpoint is `GET /health`. Mock responses exercise the application flow; they do not simulate human behavior.

The code defaults to Ollama when `SIM_PROVIDER` is unset. To generate model responses, start Ollama separately, pull a model, and configure the API before launching it:

```powershell
ollama pull llama3.1
$env:SIM_PROVIDER="ollama"
$env:OLLAMA_BASE_URL="http://127.0.0.1:11434"
$env:OLLAMA_MODEL="llama3.1"
```

For vLLM, set `SIM_PROVIDER=vllm`, `VLLM_BASE_URL`, `VLLM_MODEL`, and `VLLM_API_KEY` to match your server. `SIM_DB_PATH` changes the SQLite location. Configuration is read from environment variables; the application does not load a `.env` file.

## Try one response

With the API running, in a second PowerShell terminal:

```powershell
$payload = @{
    study = @{ name = "Campus transport"; instructions = "Give a short survey answer." }
    message = "How did you get to campus this week?"
    criteria = @{ age = @{ min = 18; max = 25 } }
    random_seed = 42
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/v1/respond -ContentType application/json -Body $payload
```

Responses include `synthetic: true`, a session id, and response text. Session creation exposes the persona; turn responses omit persona and internal pool identifiers. A seed controls baseline sampling, not the reproducibility of generated model responses.

For multi-turn studies, create a session with `POST /v1/sessions`, then send prompts to `POST /v1/sessions/{session_id}/turns`.

| `reset_policy` | Persona | Visible history |
| --- | --- | --- |
| `carryover` | Same persona | All earlier session turns |
| `trial` | Same persona | Turns sharing the current `trial_id` |
| `full` | Newly sampled persona | No previous turns |

See [RESEARCHER_API.md](RESEARCHER_API.md) for endpoint contracts, study ids, and examples. [CAUSAL_PERSONA_PIPELINE.md](CAUSAL_PERSONA_PIPELINE.md) explains the graphs, interventions, and audit fields.

## Verify

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
```

Two end-to-end tests start a real local API with a temporary SQLite database and the mock provider. They exercise persona generation, invalid-input rejection, a single response, and a multi-turn study through reset, demographics, and export. They verify application flows, not fidelity to human participants.

## Code map

| Path | Responsibility |
| --- | --- |
| `app/causal.py`, `app/persona.py` | Graph operations, structural equations, and sampling |
| `app/experiments.py` | Study setup definitions |
| `app/service.py` | Sessions, pools, trial state, and response orchestration |
| `app/llm.py`, `app/prompting.py` | Providers and prompt construction |
| `app/storage.py` | SQLite persistence and traces |
| `app/main.py`, `app/schemas.py` | HTTP routes and request/response schemas |
| `scripts/` | Example study clients and a database maintenance script |

## Scope and deployment

The graphs and distributions are hand-specified assumptions, not estimates from a representative participant dataset. Model responses are synthetic outputs, not observations of people. The service is useful for developing study workflows; using it to estimate human treatment effects requires separate empirical validation. The optional `qualitative_thinking` field is a generated self-report rationale, not access to hidden model reasoning.

The API has no authentication layer, and stored traces contain study prompts and responses. The quick start binds to localhost. Add authentication and appropriate data controls before making a deployment accessible to others.

`docker-compose.yml` runs Ollama, the API, and Nginx together and requests NVIDIA GPUs. It requires the NVIDIA container runtime; pull the model with `docker compose exec ollama ollama pull llama3.1`. The supplied Nginx configuration exposes the API on port 80. `nginx/default.conf` also provides a host-side proxy example.
