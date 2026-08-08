# ⚠️ Known Limitations & Pipeline Issues

This document tracks all known issues, edge cases, and limitations discovered during the execution of the AlgoDebt research pipeline. Documenting these is critical for the "Threats to Validity" and "Discussion" sections of the research paper.

---

## 1. LLM API & Pipeline Limitations

### 1.1. Cohere Output Truncation (The "Dropped Files" Issue)
- **Issue:** When sending batches of 15 files to Cohere (`command-r-plus-08-2024`), the returned JSON array frequently contains fewer than 15 items (e.g., 12 or 13 files). The terminal log shows progress lagging behind the expected total (e.g., jumping from 15 to 28 instead of 30).
- **Cause:** Cohere's API does not natively support strict JSON Schema enforcement (`response_format`). We have to rely on prompt instructions ("You MUST return valid JSON..."). Without the strict schema forcing the model's output structure, the LLM hits internal output token limits or context fatigue and silently stops generating array items before completing the full batch.
- **Mitigation:** The pipeline handles this automatically using a **Post-Loop Retry Sweep**. After the initial pass, the script identifies any dropped files, halves the batch size (e.g., from 15 to 7), and sweeps the dataset again. It repeats this halving process until 100% of the files are successfully parsed and saved.

### 1.2. Groq's Extreme Rate Limits
- **Issue:** Groq (`llama-3.3-70b-versatile`) cannot process batches larger than 1 file per request.
- **Cause:** Groq has a very strict Tokens Per Minute (TPM) limit on its free tier (~6,000 TPM). An average file with the system prompt and JSON schema costs 1,000–1,500 tokens. A batch of 5 files would exceed 5,000 tokens in a single request, triggering an instant `429 Rate Limit Exceeded` error.
- **Mitigation:** Batch size is locked to 1 with a 2-second delay. We use `litellm.Router` to pool multiple API keys and seamlessly rotate them when daily quotas are hit.

### 1.3. Mistral Hallucination (Zero Precision)
- **Issue:** Mistral (`mistral-large-latest`) completely failed across the board, producing near-zero precision and F1 scores. It flagged almost every file for every anti-pattern.
- **Cause:** The model struggles to differentiate between the *presence* of a pattern and the *mention* of it, or it defaults to `True` when uncertain inside a strict JSON array.
- **Mitigation:** Documented as a negative result in the comparative analysis.

---

## 2. Rule-Based Baseline Limitations (Heuristic Ground Truth)

The AST-based detector (`rule_based_detector.py`) is used as the absolute "ground truth" for grading the LLMs. However, it is a heuristic tool and has its own blind spots.

### 2.1. Train/Test Leakage (Line-Number Ordering)
- **Issue:** The rule-based detector checks if a `fit()` or `fit_transform()` call occurs on a line number *before* `train_test_split()`.
- **Limitation:** This works perfectly for linear Jupyter-style scripts. However, in modular code, a function *definition* containing a `fit()` call might appear at the top of the file, but the function is actually *executed* after the split. The AST detector will falsely flag this as leakage.

### 2.2. Single-File Isolation
- **Issue:** The detector analyzes every Python file completely in isolation.
- **Limitation:** If a repository has a `utils.py` file that calls `np.random.seed(42)`, and `train.py` imports that utility, `train.py` is perfectly reproducible. However, the rule-based detector will flag `train.py` for "No Reproducibility Control" because the seed isn't physically present in that specific file. This causes false positives in the ground truth for well-architected repositories.

### 2.3. Limited Hyperparameter Vocabulary
- **Issue:** Hardcoded hyperparameters are detected by matching variable names against a predefined list (`HYPERPARAM_NAMES`).
- **Limitation:** While it catches standard names (`lr`, `batch_size`, `epochs`), it misses domain-specific or less common names (e.g., `gamma`, `alpha`, `num_heads`, `warmup_steps`). This leads to false negatives in the baseline.

### 2.4. Python Scripts Only
- **Issue:** The pipeline only traverses and parses `.py` files.
- **Limitation:** A massive amount of ML code—and algorithm debt—lives inside Jupyter Notebooks (`.ipynb`). By ignoring notebooks, the research misses a significant portion of real-world ML workflows.

---

## 3. Experimental Design Limitations

### 3.1. File-Role Context Deprivation
- **Issue:** LLMs were observed to heavily over-flag "Missing Data Validation" and "No Reproducibility Control".
- **Limitation:** We ask the LLM to evaluate files in a vacuum. A utility script containing helper functions *should not* have data validation or random seeds. Because the LLM does not know if the file is a training script or a helper file, it flags the absence of these features everywhere. This highlights a flaw in the prompting strategy (lack of file-role context) rather than a flaw in the LLM's reasoning capabilities.

### 3.2. Single Prompting Strategy (Zero-Shot)
- **Issue:** All evaluations were performed using a single, zero-shot system prompt.
- **Limitation:** The study does not explore whether techniques like Few-Shot Prompting (providing 2-3 examples) or Chain-of-Thought (forcing the LLM to explain its reasoning before outputting JSON) would improve performance. The results represent a baseline zero-shot capability, not the maximum potential of the models.
