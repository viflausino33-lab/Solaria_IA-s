# Arquitetura proposta

## Objetivo funcional

Receber uma tarefa e escolher a execução de menor custo/recursos que satisfaça os critérios de qualidade definidos. “Equipe de IAs” significa **papéis lógicos com delegação condicionada**, não todas as IAs ativas simultaneamente.

## Camadas

```text
HTTP/CLI
  ↓
Validation & Limits
  ↓
Task Classifier ─── no LLM call on baseline
  ↓
Policy Engine ───── risk × complexity × privacy × budget × resource availability
  ↓
Workflow Planner ── single | sequential-review | bounded-parallel (future, opt-in)
  ↓
Context Builder ─── task brief + only relevant artifacts
  ↓
Provider Registry ─ local Ollama / future cloud via a common interface
  ↓
Result Validator / Critic (conditional)
  ↓
Answer + run trace + metrics
```

## Policy variables

Each request should be classified across distinct dimensions rather than a single vague “complexity” score:

- `task_type`: general, research, coding, analysis, planning, extraction.
- `complexity`: low / medium / high, estimated by deterministic baseline and calibrated over tests.
- `consequence`: low / medium / high (cost of a wrong answer or action).
- `privacy`: local_only / standard / external_allowed.
- `confidence`: confidence in routing, not confidence in truth.
- `budget_remaining`: hard ceiling per request/run/day.
- `resource_state`: local model available, RAM/VRAM budget, queue size.
- `verification_required`: explicit policy, high consequence or low answer-confidence.

## Initial execution policy

| Situation | Path |
|---|---|
| Simple, low-risk question | One local generation |
| Private input | Local-only; refuse/escalate to user if local model unavailable |
| Medium task | One specialist answer; critic only when requested or a verification trigger fires |
| High complexity but low consequence | One answer first; request critique only if uncertainty signals justify extra cost |
| High consequence | Draft → reviewer → final revision if material issues; do not silently substitute a weak model for an authority model |
| Cloud disabled or price unknown | Do not call cloud; return local fallback or explicit “cannot escalate under current policy” |
| Local memory pressure | Do not fan out; queue one local inference, shorten context, or reject with a resource diagnostic |

## Resource and context controls

### Model memory

- One local model in use by default; `SOLARIA_LOCAL_PARALLELISM=1`.
- Set Ollama keep-alive explicitly. Short keep-alive frees memory sooner; longer keep-alive avoids reload latency. Expose this as a setting.
- Do not download multiple large models as a first step. Start with one model whose quantization/context fit the machine.
- Record load and generation latency; hardware-specific memory estimates must be measured, not assumed.

### Context memory

- The main conversation stores references to artifacts, not every full prompt/output.
- Each subtask receives `{goal, constraints, relevant_evidence, expected_output_schema}`.
- A reviewer receives the task and draft, not the entire history.
- Use bounded output tokens and per-run call budgets.
- Summarization/RAG is conditional: do not call a second model simply to summarize every short input.
- Preserve exact source snippets/code when summarizing; summaries are not authoritative evidence.

### Cost accounting

The first version only executes mock/local inference. Before adding any paid adapter, implement:

1. dated model price catalogue sourced from provider pricing pages;
2. conservative pre-call estimate of input + maximum output cost;
3. atomic budget reservation before sending the request;
4. reconciliation using actual provider usage/cost;
5. strict failure when price/usage is unknown (unless the user explicitly disables the hard-cap guarantee);
6. explicit opt-in for external processing and no fallback from local to paid without permission;
7. limits per request, run, day, and model-call count.

A gateway's budget feature is helpful, but it must be configured and tested (including database and fallback paths) before claimed as a financial hard ceiling.

## Model registry (future)

Every model entry should have:

- provider and model ID;
- capabilities (`coding`, `research`, `vision`, etc.);
- local/cloud flag and privacy policy;
- max context and tested hardware envelope;
- input/output price with currency, effective date and source URL;
- quality score by task from our own test suite;
- supported structured outputs/tools;
- known limits and fallback target.

Do not treat a model as “best” globally. The policy should select the cheapest candidate that meets the task constraints, then escalate if the answer fails verification.

## State model

For each run persist only (initially in SQLite):

- run ID, timestamp, status;
- task hash + optional opt-in local task text;
- classification/routing explanation;
- steps and model IDs;
- token estimates/actual usage and latency;
- cost estimate/actual cost when known;
- validation result and errors.

Do not persist all prompts/responses by default. Keep local logs configurable and redact secrets.

## What we deliberately do not build yet

- Web UI or dashboard.
- Vector database or long-term semantic memory.
- Dynamic LLM-based router.
- Autonomous shell/code execution.
- Multi-model parallel debate as default.
- Multi-user hosted service.
- Cloud provider adapters before budgets are tested.
