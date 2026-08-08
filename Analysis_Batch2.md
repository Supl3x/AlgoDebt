# 📊 AlgoDebt Analysis: Batch 2 (Gemini vs. Mistral vs. Cohere)

This analysis evaluates the performance of three LLM models against a rule-based baseline on a 200-file dataset. **Groq (Llama 3.3 70B)** has been excluded from this batch as it is currently rate-limited at 107/200 files.

## 🏆 Summary of Findings

1. **Gemini 3.5 Flash is the clear winner.** It demonstrates exceptional precision, acting as a highly conservative but accurate detector. It only flags something when it is absolutely sure.
2. **Mistral Large hallucinates and over-flags.** It suffers from extremely low precision, flagging clean files indiscriminately.
3. **Cohere Command R+ is highly specialized.** It performs decently on `hardcoded_hyperparameters` but completely fails on more abstract patterns like `train_test_leakage`.

---

## 🥇 1. Gemini (gemini-3.5-flash) - The Conservative Expert

Gemini exhibited an incredibly strong preference for **Precision over Recall**. If Gemini flags a file, you can almost guarantee it is a true positive.

| Anti-pattern | Precision | Recall | F1 Score | TP | FP |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **train_test_leakage** | **1.00** | **0.75** | **0.86** | 3 | 0 |
| **silent_exception_handling** | **1.00** | 0.39 | 0.57 | 13 | 0 |
| **hardcoded_hyperparameters** | **0.92** | 0.17 | 0.29 | 12 | 1 |

* **Insight:** Gemini is the perfect tool for a CI/CD pipeline where false positives (annoying developers with fake warnings) must be minimized. It caught 13 silent exceptions and 3 data leakages without a single false alarm! However, its low recall means it misses a large chunk of true algorithmic debt.

---

## 📉 2. Mistral (mistral-large-latest) - The Over-eager Novice

Mistral struggled significantly with the strict definition of these anti-patterns, resulting in massive over-flagging. 

| Anti-pattern | Precision | Recall | F1 Score | FP |
| :--- | :--- | :--- | :--- | :--- |
| hardcoded_hyperparameters | 0.06 | 0.40 | 0.10 | **33** |
| no_reproducibility_control | 0.04 | 1.00 | 0.08 | **49** |
| missing_data_validation | 0.03 | 1.00 | 0.07 | **28** |

* **Insight:** Mistral achieved 100% recall on reproducibility and data validation, but only by flagging dozens of completely clean files. It seems Mistral's internal heuristics for these patterns are far too broad. It cannot be used reliably without human intervention.

---

## 🎯 3. Cohere (command-r-plus-08-2024) - The Hyperparameter Specialist

Cohere was a mixed bag, showing competence in one specific area while completely failing in others.

| Anti-pattern | Precision | Recall | F1 Score | TP | FN |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **hardcoded_hyperparameters** | **0.81** | **0.24** | **0.37** | 17 | 53 |
| silent_exception_handling | 0.00 | 0.00 | 0.00 | 0 | **33** |
| train_test_leakage | 0.00 | 0.00 | 0.00 | 0 | **4** |

* **Insight:** Cohere successfully identified 17 cases of hardcoded hyperparameters with very few false alarms (P=0.81). However, it suffered a complete systemic failure on exception handling and data leakage, scoring absolute zero. It appears the model lacks the semantic understanding required to trace data flow leakage across complex Python scripts.

---

### Conclusion

For immediate deployment, **Gemini 3.5 Flash** is the most viable model due to its perfect precision on critical algorithmic faults. Mistral requires significant prompt engineering to rein in its false positives, while Cohere needs a larger context window or chain-of-thought prompting to understand structural data flow.
