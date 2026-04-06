# Research Session: Compare RAG vs fine-tuning for domain-specific legal AI

**Goal:** Compare RAG vs fine-tuning for domain-specific legal AI
**Session ID:** `bcb82376`
**Status:** completed

## Plan

- ✅ **t1**: Search knowledge base for prior work on legal AI RAG vs fine-tuning — `knowledge_search`
- ✅ **t2**: Web search for conceptual comparisons of RAG vs fine-tuning in legal AI — `ddg_search`
- ✅ **t3**: Read key web articles on RAG vs fine-tuning for domain-specific legal AI — `read_url` *(after t2)*
- ✅ **t4**: Web search for empirical studies and benchmarks of legal RAG and fine-tuned legal models — `ddg_search`
- ✅ **t5**: Synthesize findings into a comparison framework for legal AI RAG vs fine-tuning — `write_file` *(after t1, t3, t4)*

## Execution Log

| Time | Event | Tool | Detail |
|------|-------|------|--------|
| 11:06:59 | plan_created | — | Plan 'Compare RAG vs fine-tuning for domain-specific legal AI' with 5 tasks |
| 11:07:07 | tool_call | knowledge_search | **[Legal RAG Bench: an end-to-end benchmark for legal RAG]** (type: local_file)  |
| 11:07:07 | tool_call | knowledge_search | **[Legal RAG Bench: an end-to-end benchmark for legal RAG]** (type: local_file)  |
| 11:07:08 | tool_call | knowledge_search | **[Legal RAG Bench: an end-to-end benchmark for legal RAG]** (type: local_file)  |
| 11:07:12 | tool_call | ddg_search | **A Reasoning-Focused Legal Retrieval Benchmark - GitHub Pages**   URL: https:// |
| 11:07:14 | tool_call | ddg_search | **RAG vs. Fine-Tuning: Choosing the Right Approach for AI Model**   URL: https:/ |
| 11:07:15 | tool_call | ddg_search | **Retrieval-augmentedgeneration- Wikipedia**   URL: https://en.wikipedia.org/wik |
| 11:07:16 | tool_call | ddg_search | **Large language models in legaltech: Demystifying fine-tuning \| Draftwise \| Leg |
| 11:07:19 | tool_call | ddg_search | **[2408.10343] LegalBench-RAG: A Benchmark for**   URL: https://arxiv.org/abs/24 |
| 11:07:20 | tool_call | ddg_search | **Generative AI 101: When to useRAGvsFineTuning? - YouTube**   URL: https://www. |
| 11:07:21 | tool_call | ddg_search | **Fujitsu/agentic-rag-redteam-bench · Datasets at Hugging Face**   URL: https:// |
| 11:07:23 | tool_call | ddg_search | **Understanding and Implementing Retrieval Augmented Generation RAG**   URL: htt |
| 11:08:04 | tool_call | ddg_search | **Retrieval-augmented generation (RAG): towards a promising LLM ...**   URL: htt |
| 11:08:06 | tool_call | ddg_search | **[2408.10343] LegalBench-RAG: A Benchmark for Retrieval-Augmented ...**   URL:  |
| 11:08:07 | tool_call | ddg_search | **[2505.03970] A Reasoning-Focused Legal Retrieval Benchmark - arXiv.org**   URL |
| 11:08:08 | tool_call | ddg_search | **[PDF] 1 Legal Retrieval-Augmented Generation (RAG)**   URL: https://moritzlaw. |
| 11:09:16 | tool_call | write_file | Written to /Users/amine/.planex/outputs/legal_ai_RAG_vs_finetuning_plan.md |
| 11:09:59 | synthesis | — | Below is a structured, evidence‑based comparison of Retrieval‑Augmented Generati |

## Synthesis

Below is a structured, evidence‑based comparison of Retrieval‑Augmented Generation (RAG) vs. fine‑tuning for domain‑specific legal AI, synthesized from the materials you provided (papers, benchmarks, and practical guides). I highlight key empirical findings, decision criteria, recommended experiments, and an implementation checklist for legal teams.

Executive summary
- RAG is generally the preferred first approach for many legal tasks because it grounds outputs in external documents (reducing many hallucinations), is easier to update, and requires less labeled training data. Several benchmarks and reviews argue RAG’s practicality for legal work (Harvard JOLT Digest, Apr 2, 2025; arXiv work on legal RAG, May 4, 2025).
- Fine‑tuning can outperform RAG on highly constrained tasks when large, high‑quality domain datasets exist and latency/operational simplicity are priorities, but it is more expensive to maintain and more brittle to data drift.
- Empirical work (Legal RAG Bench, Butler et al., Mar 2, 2026) shows retrieval quality is the dominant performance driver: many hallucinations attributed to the LLM actually originate from retrieval failures. A strong embedding/retrieval stack can produce the largest gains in correctness and groundedness.
- Practical recommendation: start with RAG + careful retrieval engineering and strong evaluation; consider fine‑tuning (or hybridizing) only after measuring residual errors and if use‑case constraints demand it.

Definitions (short)
- RAG: At inference, the model retrieves relevant documents from an external corpus (via embedding/vector search or symbolic indices) and conditions generation on those retrieved passages.
- Fine‑tuning: Update model weights on domain‑specific labeled examples (supervised or instruction‑tuning) so the model internalizes domain knowledge.

Key empirical findings (from provided sources)
- Legal RAG Bench (Butler et al., Mar 2, 2026): used 4,876 passages (Victorian Criminal Charge Book) and 100 complex questions; evaluated 3 embedding methods (Kanon 2 Embedder, Gemini Embedding 001, Text Embedding 3 Large) and 2 LLMs (Gemini 3.1 Pro, GPT‑5.2). Kanon 2 produced the largest improvements: average correctness +17.5 points, groundedness +4.5 points, retrieval accuracy +34 points. The work concluded retrieval quality was the main driver and many hallucinations were retrieval failures. Code/data released for reproducibility. (Butler et al., 2026)
- Benchmarks focusing on reasoning‑heavy legal retrieval tasks (Bar Exam QA, Housing Statute QA — arXiv:2505.03970 / ACM paper Mar 25, 2025) show the importance of retrieval design and evaluation that separates retrieval vs. reasoning errors.
- Multiple reviews and practitioner guides (e.g., DeepChecks, Intersog, App Academy and others, 2024–2025) summarize tradeoffs: costs, compliance, maintainability, and operational complexity.

Comparison by dimension

1) Accuracy, groundedness, and hallucinations
- RAG: Tends to produce more grounded outputs when retrieval returns correct, on‑topic passages. However, “confident wrong” answers occur when retrieval returns irrelevant or misleading chunks (silent degradation). Legal RAG Bench quantifies large gains from better embeddings/retrieval—implying retrieval is the weak link for grounding (Butler et al., 2026).
- Fine‑tuning: Can produce high task accuracy on distributional data it was trained on and may hallucinate less for those tasks, but can still hallucinate when asked beyond training distribution or when statutes/cases change.

2) Data requirements & sample efficiency
- RAG: Low upfront labeled data needs; main requirement is a clean, searchable corpus and a reasonable retrieval index. Good for corpora of statutes, briefs, contract libraries, precedents.
- Fine‑tuning: Requires sizable labeled data (or high‑quality instruction pairs) to reach parity on complex tasks. For many legal tasks, obtaining enough curated labels is costly.

3) Updatability & handling legal change
- RAG: Easily updated—swap or append documents to the vector store when law changes. Good for time‑sensitive legal corpora.
- Fine‑tuning: Requires retraining or continual fine‑tuning to incorporate new law; slower and more costly to update.

4) Compliance, provenance & explainability
- RAG: Stronger provenance—can cite source documents; easier to produce extractable citations and audit trails (important for legal/regulatory compliance).
- Fine‑tuning: Less natural provenance—model answers are internalized and harder to attribute to specific documents unless combined with retrieval/evidence pipelines.

5) Cost & operational complexity
- RAG: Costs stem from embedding/recall (vector DB, embedding model calls) and LLM inference. Ongoing operational costs for index maintenance and re‑embedding when changing embedding models.
- Fine‑tuning: High one‑time compute and data‑labeling costs for training; lower per‑query complexity (no retrieval step) and often lower inference cost if using a smaller fine‑tuned model.

6) Latency & scale
- RAG: Typically higher latency (embedding search + LLM). Engineering (caching, approximate nearest neighbor tuning, pre‑retrieval filters) can mitigate.
- Fine‑tuning: Lower latency if models are small and hosted efficiently, but larger fine‑tuned LLMs may still be costly.

7) Robustness and domain specificity
- RAG: Robust to domain drift in the corpus (you update docs) but sensitive to retrieval quality and chunking strategy (how documents are split).
- Fine‑tuning: May overfit to training artifacts and degrade when legal language or user queries vary.

8) Evaluation and error analysis
- RAG: Requires separate evaluation of retrieval accuracy, groundedness (are citations correct), and final reasoning correctness. Legal RAG Bench used hierarchical error decomposition to separate retrieval vs. reasoning errors—this is essential.
- Fine‑tuning: Evaluate on held‑out labeled data; use adversarial/legal‑review tests for hallucinations and citation fidelity if you try to force provenance.

When to prefer RAG (practical rules of thumb)
- Corpus is large, frequently changing, or proprietary (statutes, regulatory updates, internal precedents).
- You need strong provenance and audit trails for compliance or to support human lawyers with citations.
- You lack large labeled training datasets.
- You want rapid iteration and the ability to update knowledge without retraining.
- You want to test feasibility quickly and explore what tasks actually require model adaptation vs. retrieval improvements.

When to prefer fine‑tuning
- You have a large, high‑quality labeled dataset that matches target tasks (e.g., standardized forms, classification, templated drafting).
- Low latency and minimal runtime infrastructure complexity are top priorities.
- Task behavior must be highly consistent/deterministic (e.g., strict classification).
- You need best possible performance on a narrowly defined task and are prepared to maintain retraining pipelines.

Hybrid and staged approaches (recommended)
- Start with RAG + strong retrieval engineering and evaluation. Measure residual failure modes (retrieval vs reasoning).
- If residual errors are mostly reasoning errors that cannot be fixed by retrieval improvements, consider fine‑tuning a model on curated instruction pairs or chain‑of‑thought exemplars.
- A common hybrid: fine‑tune a smaller legal‑specialized LLM for core tasks, then use RAG for supporting evidence and up‑to‑date citations.
- Use retrieval to surface evidence and a fine‑tuned model to synthesize/format. This can combine provenance with improved reasoning on domain patterns.

Recommended experimental setup (practical, replicable)
- Baseline: RAG with several embedding models + vector DB + off‑the‑shelf LLM (zero‑shot). Evaluate on held‑out QA/bench set.
- Ablations: vary embedding model, chunk size, retrieval k (top‑k), re‑ranking strategy.
- Compare to: a fine‑tuned model trained on the same task data (use identical evaluation set).
- Metrics to capture: correctness (accuracy), groundedness (fraction of answers supported by cited passages), retrieval accuracy (is the gold passage among top‑k), and calibration/overconfidence measures.
- Use full factorial or hierarchical error decomposition (as Legal RAG Bench did) to attribute errors to retrieval vs. reasoning. Example resource: Legal RAG Bench (Butler et al., Mar 2, 2026) used 4,876 passages and 100 complex questions—good template for small‑scale reproducible experiments.

Operational checklist (before production rollout)
- Data curation: canonicalize statutes/cases; decide chunking and metadata (jurisdiction, date).
- Embeddings: benchmark multiple embedders for retrieval accuracy (Legal RAG Bench found large differences; Kanon 2 gave big gains in that study).
- Instrumentation: logs, provenance capture, retrieval diagnostics (what was retrieved, distances), and human review workflows.
- Evaluation suite: include reasoning benchmarks (Bar Exam QA, Housing Statute QA), domain‑specific holdouts, adversarial/legal red‑team tests.
- Governance: legal review, compliance checks, retention & PII policies, and clear user disclaimers for non‑binding outputs.
- Update policy: how often to re‑embed corpus, when to retrain/fine‑tune, and monitoring for drift.

Risks and mitigations
- Risk: “Confident wrong” from bad retrieval. Mitigation: retrieval fallbacks (lower temperature, ask for “I don’t know” when retrieval confidence low), multi‑retrieval consensus, and human‑in‑the‑loop verification.
- Risk: Data leakage/PII exposure during fine‑tuning. Mitigation: scrub training data, legal review, and follow data handling policies.
- Risk: Model brittleness after fine‑tuning. Mitigation: continuous evaluation, holdout tests with new statutes, and staged rollouts.

Concrete conclusions and action plan (short)
1. Start with RAG for most legal knowledge tasks—it buys rapid iteration, provenance, and easier updating. Instrument retrieval quality as a first‑order metric. (Supported by Legal RAG Bench findings: retrieval drives performance; Butler et al., Mar 2, 2026.)
2. Run a structured evaluation: compare 2–3 embedders, 2 LLMs, and vary retrieval hyperparameters using a held‑out legal QA set (use Legal RAG Bench or Bar Exam/Housing Statute QA tasks as templates).
3. If errors remain that are primarily reasoning / formatting (not retrieval), pilot fine‑tuning a small model on curated exemplars; consider hybridizing with RAG for evidence.
4. For production, require provenance, configurable conservatism (decline on low confidence), and legal‑team signoff.

Selected references (from your supplied material)
- Butler et al., “Legal RAG Bench: an end‑to‑end benchmark for legal RAG,” March 2, 2026. (4,876 passages; 100 complex questions; found Kanon 2 Embedder provided largest gains; retrieval quality is main performance driver.)
- “A Reasoning‑Focused Legal Retrieval Benchmark,” arXiv:2505.03970 / ACM paper (May 6, 2025 / Mar 25, 2025) — Bar Exam QA and Housing Statute QA benchmarks.
- Harvard JOLT Digest, “RAG: towards a promising LLM architecture for legal work,” Apr 2, 2025.
- arXiv “Incorporating Legal Structure in Retrieval‑Augmented Generation,” v1, May 4, 2025.
- LegalBench‑RAG (arXiv:2408.10343, Aug 17, 2024) and related GitHub repos (ZeroEntropy-AI/legalbenchrag, Legal RAG Bench code released).

If you want, I can:
- Draft an experiment plan you can run (exact datasets, evaluation scripts, metric definitions) based on Legal RAG Bench and Bar Exam QA templates.
- Produce a one‑page decision flowchart (when to use RAG / fine‑tune / hybrid) customized to a specific legal product (e.g., contract analysis vs. statutory QA).
- Help benchmark candidate embedding models on your corpus (I’ll need sample documents and target queries).

Which of those would you like next?
