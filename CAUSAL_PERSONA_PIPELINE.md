# Causal Persona Generation Pipeline

The persona generator is an executable structural causal model (SCM), not a set of
independent marginal draws. The implementation is in `app/causal.py`; the API adapter
is `app/persona.py`.

## Generation semantics

For a study setup, generation follows this order:

1. Resolve the setup id to a study-family DAG.
2. Validate that requested fields are public, pre-treatment baseline nodes.
3. Sample root variables and latent dispositions.
4. Traverse the DAG in topological order and execute each structural equation.
5. Apply `conditioned_attributes` as explicit interventions (`do(X=x)`). Descendants
   are generated from the intervened value; ancestors are not resampled to fit it.
6. Apply `criteria` as eligibility evidence. A complete draw is retained only if it
   matches the criteria, approximating sampling from `P(persona | eligible)`.
7. Return only public persona attributes. Store the causal diagnostics and latent values in the local database.

This distinction matters. For example, setting `prior_ai_use="frequent"` changes its
descendants such as AI familiarity and AI literacy. Requiring `ai_literacy >= 6` does
not overwrite literacy; it retains naturally generated high-literacy personas and
therefore preserves information about their generated parent variables.

## Study graphs

Each concrete setup id resolves to a graph, while arms of the same experiment share
the same population equations. That keeps the population model invariant across
randomized conditions.

| Model family | Setup ids | Treatment/exposure | Main outcomes |
| --- | --- | --- | --- |
| Truth/source | `truth_source_unlabeled`, `truth_source_labeled` | source-label visibility | truth judgment, confidence, trustworthiness |
| Sycophancy | `sycophancy_neutral`, `sycophancy_sycophantic` | LLM condition | trust, perceived trustworthiness, opinion change |
| Climate partner | neutral, steelman, and Socratic climate setups | partner condition | opinion change, epistemic trust, autonomy |
| Cognitive load | no-, low-, and high-load setups | cognitive load | accuracy, confidence, sharing likelihood |
| AI literacy | text/image intervention setups | literacy intervention | detection accuracy, confidence, difficulty |

The shared population DAG creates dependencies among family socioeconomic background,
parental education, age, education, student/employment status, wealth, digital use,
AI familiarity, AI literacy, skepticism/trust, cognitive capacity, working memory,
attention, reasoning style, topic knowledge, confidence, and initial opinions.

## Confounders and colliders

`confounder` and `collider` are relational graph properties, not permanent labels on
persona attributes.

- A confounder is a common cause of a treatment and an outcome for a particular
  causal question.
- A collider is a node receiving arrows from two variables on a path. Conditioning
  on it can open that path.
- A mediator is downstream of treatment and must not be used to define the baseline
  persona when estimating the total treatment effect.

The current studies assign the experimental arm. In the implemented graphs, the arm
is therefore a root treatment node. Under genuine random assignment, baseline traits
are prognostic covariates, not treatment confounders, and the empty adjustment set
passes the backdoor criterion. If researchers assign arms based on persona traits,
the graph must be changed to include those arrows; otherwise the causal claim would
be false.

The graph engine uses the ancestral-moral-graph criterion for d-separation. Its
backdoor check removes outgoing treatment edges, tests d-separation from each outcome,
and rejects adjustment sets containing treatment descendants. For example, in the
sycophancy graph:

```text
llm_condition -> perceived_agreement -> conversation_engagement <- openness_to_change
```

`llm_condition` and `openness_to_change` are d-separated before conditioning.
Conditioning on `conversation_engagement` opens the path. The persona API blocks that
field because it is a post-treatment collider.

## Internal audit data

SQLite stores causal metadata for generated personas:

- causal model id and family;
- graph node and edge counts;
- topological sampling order;
- criteria and interventions;
- number of rejection-sampling attempts;
- whether each node came from a structural equation or intervention;
- latent generated values;
- identified confounders and graph colliders;
- backdoor d-separation results and adjustment-set validity.

Session and pool traces are stored in `causal_trace_json`. Standalone `/v1/personas`
draws are stored in `generated_personas`. These fields are deliberately omitted from
researcher-facing persona responses, prompts, and session exports.

## Calibration limitation

The DAG makes assumptions explicit and generates coherent dependence, but a DAG alone
cannot establish that personas match real Prolific participants. The current equations
and probabilities are provisional, hand-specified priors. They are not estimates from
Prolific microdata and should not be described as empirically representative.

For research-grade calibration, fit root distributions and conditional mechanisms to
an ethically obtained reference dataset from the intended sampling frame, reserve a
holdout set, and validate:

- marginal prevalence and joint cross-tabs;
- conditional distributions such as AI literacy by education and prior AI use;
- correlations and conditional independences implied by the DAG;
- measurement reliability for latent constructs;
- behavioral outcome distributions by randomized arm;
- sensitivity to alternative graph structures and unmeasured common causes.

The local LLM generates responses from the sampled public persona and task history.
The SCM determines baseline attributes. It does not determine later behavioral outcomes
or establish that model responses resemble those of human participants.
