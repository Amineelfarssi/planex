<!-- 
  Generated with:
    planex run "Research the latest advances in prompt optimization techniques and compare approaches" -y --transcript > examples/transcript_research.md
  
  Or reproduce any session:
    planex run "your goal" -y --transcript > transcript.md
-->


# Research Session: Research plan on prompt optimization techniques and compare approaches

**Goal:** Research the latest advances in prompt optimization techniques and compare approaches
**Session ID:** `1779645b`
**Status:** completed

## Plan

- ✅ **t1**: Use web search to identify recent prompt optimization techniques and compare approaches — `web_search`
- ✅ **t2**: Read key survey or overview articles on prompt optimization techniques and compare approaches — `read_url` *(after t1)*
- ✅ **t3**: Read representative primary papers on distinct prompt optimization techniques and compare approaches — `read_url` *(after t1)*
- ✅ **t4**: Draft structured comparison of prompt optimization techniques and compare approaches — `write_file` *(after t2, t3)*
- ✅ **t5**: Write final synthesis report on prompt optimization techniques and compare approaches — `write_file` *(after t4)*

## Execution Log

| Time | Event | Tool | Detail |
|------|-------|------|--------|
| 21:59:11 | plan_created |  | Plan 'Research plan on prompt optimization techniques and compare approaches' wi |
| 21:59:26 | tool_call | web_search | Do you want me to:  - Search arXiv for 2023 surveys specifically about "prompt o |
| 22:00:04 | tool_call | web_search | Got it — here’s the paper and PDF links.  - Official EMNLP paper (PDF) — availab |
| 22:00:34 | tool_call | web_search | Here’s a compact, curated list of surveys, tutorials and high‑level reviews (202 |
| 22:01:25 | tool_call | write_file | Written to /Users/amine/.planex/outputs/prompt_optimization_techniques_and_compa |
| 22:01:35 | tool_call | knowledge_search | **[Optimize Anything with LLMs]** (type: web_page) # Optimize Anything with LLMs |
| 22:02:20 | synthesis |  | Below is a concise synthesis of recent advances in prompt optimization (2020–202 |

## Synthesis

Below is a concise synthesis of recent advances in prompt optimization (2020–2024), a structured comparison of major approaches, practical recommendations, and open research directions. I cite the surveys and representative papers found in your search results; I can export BibTeX or a one‑page reading summary on request.

1) High‑level taxonomy (what “prompt optimization” covers)
- Manual / human prompt engineering: hand‑crafted natural language instructions and examples (few‑shot, zero‑shot).
- Example/exemplar selection & ordering: choosing few‑shot exemplars (k‑shot selection, clustering, diversity).
- Chain‑of‑Thought (CoT) and reasoning prompts: prompting styles that elicit stepwise reasoning (self‑consistency, voting).
- Automated discrete prompt search: algorithmic search over literal textual prompts (e.g., AutoPrompt).
- Continuous / soft prompting and prefix tuning: learnable embedding prompts that require model weight access (P‑tuning, prompt tuning, prefix tuning).
- Black‑box optimization: treat model as oracle and optimize prompts via black‑box optimizers (evolutionary algs, Bayesian optimization, RL).
- Data‑free / zero‑data optimization: methods that need few or no labeled examples and optimize prompts by model interrogation (e.g., GEPA-style claims).
- Meta‑prompting and ensemble/meta‑learning: learn higher‑level strategies that output prompts or prompt templates.
- Multimodal & vision‑language prompting: prompting strategies for models that accept images + text.

Key sources and surveys (2023–2024)
- Systematic surveys and tutorials assembled in 2023–2024 (examples you collected): Liu (Nov 2023) “Pre‑train, Prompt, and Predict” style survey; Qiao (ACL 2023) prompting overview; Amatriain (Jan 2024), Sahoo et al. (Feb 2024), Schulhoff et al. (Jun 2024), Ye (2024). A vision‑language prompting survey (Jul 2023) covers multimodal prompts. These provide overviews, datasets, and comparisons across the methods above.
- Representative primary papers: AutoPrompt (Shin et al., EMNLP 2020; arXiv:2010.15980) for discrete automated prompts; Tree of Thoughts (Yao et al., 2023, rev. Dec 2023) for structured reasoning prompting.

Also notable recent product/technique claim:
- GEPA / “Optimize Anything with LLMs” (product page): a zero‑training‑data, black‑box prompt optimization system that claims strong cost/time improvements vs RL and shows concrete improvement on AIME 2025 with GPT‑4.1 Mini (46.6%→56.6%). It emphasizes human‑readable traces, works with as few as 3 examples, and is intended as a rapid complement to RL/fine‑tuning. (Source: Optimize Anything with LLMs page.)

2) Comparison of approaches (concise, by criteria)

- Human prompt engineering
  - Data / labels: none (manual).
  - Model access: none.
  - Compute: minimal.
  - Pros: fast, interpretable, cheap.
  - Cons: brittle, suboptimal, labor‑intensive; scaling to many tasks is inefficient.
  - Use when: prototyping, small tasks, interpretability required.

- Exemplar selection / few‑shot design
  - Data: requires a small labeled set to choose exemplars.
  - Model access: none.
  - Pros: large effect on performance; simple to apply to closed‑API LLMs.
  - Cons: exemplar selection is combinatorial; sensitivity to order.
  - Use when: few labeled examples exist and model is accessed via API.

- Chain‑of‑Thought (CoT) and structured reasoning (including Tree of Thoughts)
  - Data: may need few exemplars or engineered prompt templates.
  - Model access: none.
  - Pros: substantial gains on reasoning tasks; can be combined with self‑consistency for robustness.
  - Cons: longer outputs, more compute per query; not always effective for smaller models.
  - Use when: complex reasoning or multi‑step problems.

- Discrete automated search (AutoPrompt, greedy/search)
  - Data: can be data‑free or need validation set.
  - Model access: usually requires gradient access for some variants (AutoPrompt used gradient signals on BERT), but discrete search variants can be black‑box.
  - Pros: finds non‑intuitive trigger phrases; effective for knowledge elicitation.
  - Cons: discovered prompts can be brittle, uninterpretable, or exploit model artifacts.
  - Use when: extracting latent knowledge or optimizing small discrete prompt tokens.

- Continuous / soft prompting and prefix tuning (P‑tuning, prompt tuning)
  - Data: needs labeled data to train the prompt embeddings.
  - Model access: white‑box (access to model weights or fine‑tuning hooks).
  - Compute: lower than full fine‑tuning, but requires training.
  - Pros: parameter‑efficient; good for transfer to downstream tasks; often robust.
  - Cons: not applicable to closed‑API models (unless provider enables soft prompts); less interpretable.
  - Use when: you have model weights or provider supports tuning; want parameter‑efficient adaptation.

- Black‑box optimization (Bayesian opt, evolutionary, RL on prompts)
  - Data: validation set + evaluation budget.
  - Model access: only API (black‑box).
  - Compute: can be expensive (many evals), though some methods reduce cost.
  - Pros: works with closed APIs; can optimize arbitrary prompt components (instruction, examples, system messages).
  - Cons: sample‑inefficient; quality depends on optimization algorithm and noise in eval.
  - Use when: closed‑API LLMs and labeled eval metric available.

- Zero‑/few‑example black‑box optimizers with interpretability (GEPA‑style)
  - Data: claims to work with as few as 3 examples or zero training data.
  - Model access: black‑box API only.
  - Pros: fast prototyping; human‑readable traces; low infrastructural cost per claims.
  - Cons: claims need independent academic validation; may not match fine‑tuning/RL in final performance for large production deployments.
  - Use when: rapid iteration, scarce labeled data, or costly rollouts — then escalate to RL/fine‑tuning.

3) Practical workflows & recommended hybrids
- Rapid prototyping on closed APIs:
  1. Manual prompt + exemplar selection + CoT (if reasoning).
  2. Run a black‑box optimizer (e.g., GEPA or Bayesian/evolutionary) to refine prompts quickly.
  3. Use human‑readable traces to assess safety/failure modes.
  4. If performance still insufficient, collect labeled examples for exemplar selection or fine‑tuning.

- White‑box / production deployment:
  1. Start with instruction tuning or soft prompt tuning (P‑tuning/prefix tuning) for parameter efficiency.
  2. Use RL (policy optimization / RLHF) if behavior needs to be optimized under complex reward signals.
  3. Combine with automated discrete search for instruction phrasing and with exemplar selection for few‑shot tasks.

- Reasoning tasks:
  - Use CoT prompts + self‑consistency (sample multiple reasoning chains and majority vote).
  - For hard combinatorial tasks, use Tree of Thoughts or structured prompting to explore reasoning trajectories.

4) Evaluation best practices
- Use held‑out validation/test sets that reflect deployment distribution.
- Report cost and latency (important for black‑box iterative methods).
- Report robustness: paraphrase prompts, adversarial prompts, distribution shift.
- Human evaluation for open‑ended tasks and safety metrics for harmful outputs.
- Compare against strong baselines: human engineered prompts, few‑shot exemplars, prompt tuning when possible.

5) Strengths, limitations, and open research directions
- Strengths of recent advances:
  - Large gains from prompting strategies (CoT, self‑consistency).
  - Parameter‑efficient adaptation via soft prompts and prefix tuning.
  - Black‑box optimizers (including commercial tools like GEPA) make optimization accessible for closed APIs.
- Limitations and open problems:
  - Reproducibility: many commercial claims (speed/cost gains) need independent peer review.
  - Robustness and generalization: prompts can be brittle under distribution shift.
  - Interpretability: soft prompts are effective but hard to interpret.
  - Evaluation: lack of standardized benchmarks for prompt optimization methods across tasks and modalities.
  - Multimodal prompting: emerging area — how to jointly optimize textual and visual prompt components.
  - Scaling laws: how optimization behavior changes as models scale (and cost tradeoffs).

6) Concrete references (from your findings; ask me to export full BibTeX)
- AutoPrompt: Shin et al., EMNLP 2020 — “AutoPrompt: Eliciting Knowledge from Language Models with Automatically Generated Prompts” (arXiv:2010.15980).
- Tree of Thoughts: Yao et al., 2023 — “Tree of Thoughts: Deliberate Problem Solving with Large Language Models” (submitted May 17 2023, revised Dec 3 2023).
- Surveys & tutorials (2023–2024): Liu (Nov 2023) systematic survey; Qiao (ACL 2023) prompting methods; Amatriain (Jan 2024), Sahoo et al. (Feb 2024), Schulhoff et al. (Jun 2024), Ye (2024), vision‑language prompting survey (Jul 2023).
- GEPA / Optimize Anything with LLMs: product page describing zero‑data black‑box optimization and reported empirical claims (AIME 2025 result, users such as Shopify/Databricks/Dropbox).

7) Suggested next steps I can perform for you
- Export a one‑page reading summary or a BibTeX file for the surveys and key papers.
- Retrieve and summarize full PDFs (AutoPrompt, Tree of Thoughts, specific surveys).
- Generate a runnable checklist/workflow (code snippets) for applying a GEPA‑style black‑box optimizer vs soft prompting vs RL.
- Produce a comparison table (CSV/Markdown) tailored to your target tasks (NLP classification, reasoning, multimodal).

If you want, tell me which of the next steps above to do (e.g., “summarize AutoPrompt and P‑tuning papers” or “export BibTeX for the 2023–2024 surveys”) and I’ll fetch and synthesize those details.
