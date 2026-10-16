# Measured synthetic findings

Source: evaluation-results.json, recorded 2026-10-16T05:11:37.947927+00:00. Dataset: benchmarks/synthetic-v1.json. These are deliberately small sanity cases and must not be generalized to actual students.

| Measure | Actual observation |
|---|---|
| Skill mention extraction | 18 true positives, 0 false positives, 0 false negatives across 10 synthetic resumes; precision 1.000, recall 1.000 |
| Taxonomy normalization | 9/9 exact expected outputs |
| Keyword retrieval | Precision@1 1.000, recall@1 1.000 over 3 positive queries; 1/1 expected abstentions |
| Source citation accuracy | 1.000; exact source identity/quote check |
| Extractive groundedness | 1.000; unsupported excerpt frequency 0.000 |
| Objective grading | 6/6 expected exact-set outcomes |
| Persisted LangGraph tasks | 3/3 completed; mean 782.50 ms using deterministic fallback |
| Generic vs drive-specific plan | Unfinished-task required-skill overlap 0.000 versus 0.667 in one .NET scenario |
| Adaptation preservation/budget | 1/1 completed tasks preserved; 3 new hours within 3 available hours |
| CSV reliability | 1000 records asserted in a passing API flow; complete case 45.24 seconds, including other acceptance steps |
| Named tenant-isolation cases | 4/4 passed; see test names in the JSON |

Mention extraction counts explicit skill mentions, including ambiguous/negative statements that are labelled for clarification. It does not count verified proficiency. The extraction dataset uses the controlled taxonomy's aliases; use a separate held-out, independently annotated dataset before reporting research accuracy.

Groundedness here measures copied evidence excerpts, not the truth of the document or the semantic quality of a generative model. Roadmap overlap is exact topic coverage, not observed learning improvement. Latency is machine/run dependent and is not an inference-performance claim. CSV case time is not isolated import throughput.

Keyword-versus-real-LLM and real-vector-versus-hybrid comparisons were **not run** because weights/services were not enabled. No LLM hallucination rate, real-world placement probability, production scalability or official compliance result is fabricated. See AI_AND_EVALUATION.md for the evaluation protocol and next experiments.
