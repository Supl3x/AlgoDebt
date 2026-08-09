# 🚀 How to Run — AlgoDebt Detection Pipeline

A complete, step-by-step guide to reproduce the entire AlgoDebt evaluation pipeline from scratch on a **new machine**.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone the Repository](#2-clone-the-repository)
3. [Set Up the Python Environment](#3-set-up-the-python-environment)
4. [Configure API Keys](#4-configure-api-keys)
5. [Stage 1 — Fetch ML Repositories](#stage-1--fetch-ml-repositories-from-github)
6. [Stage 2 — Run the Rule-Based Baseline Detector](#stage-2--run-the-rule-based-baseline-detector)
7. [Stage 3 — Generate the Evaluation Dataset](#stage-3--generate-the-evaluation-dataset)
8. [Stage 4 — Run LLM Detectors](#stage-4--run-llm-detectors)
9. [Stage 4.5 — Classify File Roles (Pre-Filter)](#stage-45--classify-file-roles-pre-filter)
10. [Stage 5 — Compare Results (Grading)](#stage-5--compare-results-grading)
11. [Stage 5.5 — Apply Role Filter & Compare](#stage-55--apply-role-filter--compare)
12. [Stage 6 — Archive a Completed Batch](#stage-6--archive-a-completed-batch)
13. [Understanding the Output](#6-understanding-the-output)
14. [Troubleshooting](#7-troubleshooting)
15. [Project Structure Reference](#8-project-structure-reference)

---

## 1. Prerequisites

Make sure the following are installed on your system before starting:

| Tool | Version | Check Command | Download |
|---|---|---|---|
| **Python** | 3.10+ | `python --version` | [python.org](https://www.python.org/downloads/) |
| **Git** | Any | `git --version` | [git-scm.com](https://git-scm.com/downloads) |
| **pip** | Bundled with Python | `pip --version` | Comes with Python |

> [!NOTE]
> This guide uses **PowerShell** commands (Windows). If you are on macOS/Linux, replace `.\venv\Scripts\activate` with `source venv/bin/activate`.

---

## 2. Clone the Repository

```powershell
git clone https://github.com/Supl3x/AlgoDebt.git
cd AlgoDebt
```

---

## 3. Set Up the Python Environment

### 3.1 Create a Virtual Environment

```powershell
python -m venv venv
```

### 3.2 Activate the Virtual Environment

**Windows (PowerShell):**
```powershell
.\venv\Scripts\activate
```

**macOS / Linux:**
```bash
source venv/bin/activate
```

You should see `(venv)` appear at the beginning of your terminal prompt.

### 3.3 Install Dependencies

```powershell
pip install -r requirements.txt
```

This installs:
- `litellm` — Unified LLM API client with router/load-balancer support.
- `groq` — Groq API client (used as a litellm backend).
- `python-dotenv` — Loads API keys from the `.env` file automatically.

---

## 4. Configure API Keys

Create a file named `.env` in the **root** of the project (same level as `README.md`).

```
AlgoDebt/
├── .env          <-- Create this file here
├── README.md
├── scripts/
└── ...
```

Paste the following template into `.env` and fill in your keys:

```env
# === Groq (Llama 3.3 70B) ===
# Groq has very strict free-tier limits (~100K tokens/day per key).
# Add multiple keys for automatic rotation. The pipeline will seamlessly
# swap to the next key when one is exhausted.
GROQ_API_KEY_1=your_groq_key_here
GROQ_API_KEY_2=your_groq_key_here
GROQ_API_KEY_3=your_groq_key_here

# === Google Gemini ===
# Gemini allows large batches (25 files/request). 1-2 keys is usually enough.
GEMINI_API_KEY_1=your_gemini_key_here
GEMINI_API_KEY_2=your_gemini_key_here

# === Cohere ===
COHERE_API_KEY=your_cohere_key_here

# === Mistral ===
MISTRAL_API_KEY=your_mistral_key_here
```

### Where to get free API keys:

| Provider | Model Used | Free Tier Signup |
|---|---|---|
| **Groq** | `llama-3.3-70b-versatile` | [console.groq.com](https://console.groq.com) |
| **Google AI Studio** | `gemini-3.5-flash` | [aistudio.google.com](https://aistudio.google.com/apikey) |
| **Cohere** | `command-r-plus-08-2024` | [dashboard.cohere.com](https://dashboard.cohere.com/api-keys) |
| **Mistral** | `mistral-large-latest` | [console.mistral.ai](https://console.mistral.ai/api-keys/) |

> [!IMPORTANT]
> **Groq's free tier is very strict** (~100K tokens/day, ~6K tokens/minute). To process 200 files (~250K tokens), you will need **at least 3 Groq API keys** pooled in your `.env`. Create multiple accounts or wait across days. The pipeline handles rotation automatically.

> [!CAUTION]
> **Never commit your `.env` file to Git.** The `.gitignore` already excludes it, but always double-check before pushing.

---

## Stage 1 — Fetch ML Repositories from GitHub

This script searches GitHub for small-to-medium ML training-pipeline repositories and shallow-clones them into the `repos/` directory.

```powershell
python scripts/fetch_repos.py --n 30
```

**What happens:**
- Searches GitHub with 5 curated queries (e.g., `sklearn train_test_split`, `pytorch training loop`).
- Filters for repos with **5–200 stars** (favors individual projects over large frameworks).
- Shallow-clones each repo (`--depth 1`) into `repos/`.
- Saves a manifest to `results/repo_manifest.json`.

**Expected output:**
```
Searching: sklearn train_test_split language:Python stars:5..200
Searching: pytorch training loop language:Python stars:5..200
...
Found 30 candidate repos. Cloning...

Cloning user/repo-name (42 stars)...
...
Done. 28/30 repos cloned successfully.
Manifest saved to results/repo_manifest.json
```

> [!NOTE]
> GitHub's unauthenticated API is rate-limited to **10 requests/minute**. The script automatically waits 6 seconds between queries to stay under this limit. The full fetch takes ~2 minutes.

**⏱ Estimated time:** ~2–3 minutes.

---

## Stage 2 — Run the Rule-Based Baseline Detector

This script runs the AST-based detector across **every Python file** in every cloned repo to establish the **ground truth** baseline.

```powershell
python scripts/run_baseline.py
```

**What happens:**
- Walks through every `.py` file in `repos/`.
- Parses each file's Abstract Syntax Tree (AST) and checks for the 5 anti-patterns.
- Saves detailed per-file findings to `results/algorithms/rule_based_findings.json`.

**Expected output:**
```
Analyzed 28 repos, 1619 total Python files.

Files flagged per anti-pattern (rule-based baseline):
  hardcoded_hyperparameters          85 files  (5.3%)
  missing_data_validation             6 files  (0.4%)
  train_test_leakage                  3 files  (0.2%)
  no_reproducibility_control         29 files  (1.8%)
  silent_exception_handling          20 files  (1.2%)

Saved detailed results to results/algorithms/rule_based_findings.json
```

**⏱ Estimated time:** < 30 seconds (AST parsing is very fast).

---

## Stage 3 — Generate the Evaluation Dataset

This creates a **locked**, stratified sample of files that **all** LLM models will be tested against — ensuring a fair, apples-to-apples comparison.

```powershell
python scripts/llm_detector.py --generate-dataset --sample 200
```

**What happens:**
- Draws a **60/40 stratified sample**: 60% of files are ones the rule-based detector flagged (positive cases), 40% are clean files (negative cases).
- Saves the exact file list to `results/algorithms/evaluation_dataset.json`.
- This file is **locked** — every subsequent LLM run reads from this same list.

**Expected output:**
```
Dataset of 200 files generated and saved to results/algorithms/evaluation_dataset.json
```

> [!WARNING]
> **Run this only ONCE.** If you re-run it, it will overwrite the dataset with a new random sample, invalidating any prior LLM results. Only regenerate if you intentionally want a fresh sample.

**⏱ Estimated time:** < 5 seconds.

---

## Stage 4 — Run LLM Detectors

Now run each LLM against the locked 200-file dataset. Each model can be run independently and in any order.

### 4a. Gemini 3.5 Flash
```powershell
python scripts/llm_detector.py --model gemini/gemini-3.5-flash
```
- **Batch size:** 25 files/request (auto-configured)
- **Delay:** 4 seconds between batches
- **Expected requests:** ~8 total
- **⏱ Estimated time:** ~2–5 minutes

### 4b. Mistral Large
```powershell
python scripts/llm_detector.py --model mistral/mistral-large-latest
```
- **Batch size:** 25 files/request
- **Delay:** 2 seconds between batches
- **⏱ Estimated time:** ~2–5 minutes

### 4c. Cohere Command R+
```powershell
python scripts/llm_detector.py --model cohere/command-r-plus-08-2024
```
- **Batch size:** 15 files/request (reduced to prevent output truncation)
- **Delay:** 2 seconds between batches
- **⏱ Estimated time:** ~5–10 minutes

### 4d. Groq (Llama 3.3 70B)
```powershell
python scripts/llm_detector.py --model groq/llama-3.3-70b-versatile
```
- **Batch size:** 1 file/request (strict TPM limits)
- **Delay:** 2 seconds between batches
- **⏱ Estimated time:** ~10–15 minutes (with 3+ pooled keys)

> [!TIP]
> **Resumable by design.** If the script crashes, gets rate-limited, or you stop it manually — just run the **exact same command** again. It will automatically skip already-processed files and pick up where it left off. You will never lose progress.

**Output files are saved to:**
```
results/llm_findings/llm_findings_<model_name>.json
results/llm_findings/token_usage.log
results/llm_findings/daily_token_tracker.json
```

> [!TIP]
> **Real-Time Token Tracking:** The pipeline automatically tracks your total token usage across all API keys and resets every day at Midnight UTC. The terminal prints a live dashboard updating your session and daily tokens so you never accidentally exceed your quotas!

---

## Stage 5 — Compare Results (Grading)

Once an LLM run is complete, compute its **Precision, Recall, and F1 Score** against the rule-based baseline.

```powershell
# Run whichever model(s) have completed:
python scripts/compare_results.py --model gemini/gemini-3.5-flash
python scripts/compare_results.py --model mistral/mistral-large-latest
python scripts/compare_results.py --model cohere/command-r-plus-08-2024
python scripts/compare_results.py --model groq/llama-3.3-70b-versatile
```

**Expected output (example for Groq):**
```
Compared 199 files.

Anti-pattern                    Precision     Recall       F1    TP    FP    FN    TN
------------------------------------------------------------------------------------------
hardcoded_hyperparameters            0.58       0.77     0.66    58    42    17    82
missing_data_validation              0.03       1.00     0.07     5   143     0    51
train_test_leakage                   0.12       0.33     0.18     1     7     2   189
no_reproducibility_control           0.17       0.92     0.28    24   119     2    54
silent_exception_handling            0.67       0.43     0.52     6     3     8   182

Saved full report + 343 disagreement cases to results/comparison_reports/comparison_report_groq_llama-3.3-70b-versatile.json
```

**Output files are saved to:**
```
results/comparison_reports/comparison_report_<model_name>.json
```

Each report contains:
- **`stats`**: Per-pattern precision, recall, F1, TP, FP, FN, TN.
- **`disagreements`**: Every file+pattern where the LLM and rule-based detector disagreed — invaluable for qualitative analysis.

---

## Stage 4.5 — Classify File Roles (Pre-Filter)

This is the **File-Role Classification Pre-Filter** — a two-pass architecture that dramatically reduces false positives. It classifies each file's role (training script, utility, test, etc.) so that only relevant anti-patterns are checked.

```powershell
# Classify using Gemini (fastest, uses batch_size=25)
python scripts/llm_detector.py --classify --model gemini/gemini-3.5-flash
```

**What happens:**
- Each file in the dataset is sent to the LLM with a classification prompt.
- The LLM assigns one of 6 roles: `training_script`, `data_pipeline`, `model_architecture`, `utility`, `test`, `config`.
- Results are saved to `results/llm_findings/file_roles_gemini_gemini-3.5-flash.json`.
- Supports checkpointing — resumable if interrupted.

**To classify files from an archived batch:**
```powershell
python scripts/llm_detector.py --classify --model gemini/gemini-3.5-flash --dataset-path results/archive/batch_1/evaluation_dataset.json --output-dir results/archive/batch_1/llm_findings
```

**Expected output:**
```
Classifying 200 files using gemini/gemini-3.5-flash...
Configuration: batch_size=25, delay=4.0s

Classifying batch 1 (25 files, 0/200 total)...
...

Classification complete. 200 files classified. Saved to results/llm_findings/file_roles_gemini_gemini-3.5-flash.json

Role distribution:
  training_script              62 files
  utility                      55 files
  model_architecture           38 files
  config                       25 files
  test                         12 files
  data_pipeline                 8 files
```

> [!NOTE]
> You only need to classify **once** per dataset. A single model's classification (e.g., Gemini) can be used to filter all 4 models' findings using the `--roles-model` flag in the next stage.

**⏱ Estimated time:** ~2–3 minutes (Gemini with batch_size=25).

---

## Stage 5.5 — Apply Role Filter & Compare

After classification, apply the role-based filter to each model's existing findings. This retroactively suppresses ineligible anti-pattern flags based on the file's classified role.

```powershell
# Apply Gemini's classification to each model's findings
python scripts/apply_role_filter.py --model gemini/gemini-3.5-flash
python scripts/apply_role_filter.py --model mistral/mistral-large-latest --roles-model gemini/gemini-3.5-flash
python scripts/apply_role_filter.py --model cohere/command-r-plus-08-2024 --roles-model gemini/gemini-3.5-flash
python scripts/apply_role_filter.py --model groq/llama-3.3-70b-versatile --roles-model gemini/gemini-3.5-flash
```

**What happens:**
- For each file, the script looks up its role and checks the eligibility matrix.
- If a pattern is not eligible for that role (e.g., `missing_data_validation` on a `utility` file), the flag is forced to `False`.
- Saves filtered findings as `llm_findings_{model}_role_filtered.json`.

**Then compare the filtered results:**
```powershell
python scripts/compare_results.py --model gemini/gemini-3.5-flash --suffix _role_filtered
python scripts/compare_results.py --model mistral/mistral-large-latest --suffix _role_filtered
python scripts/compare_results.py --model cohere/command-r-plus-08-2024 --suffix _role_filtered
python scripts/compare_results.py --model groq/llama-3.3-70b-versatile --suffix _role_filtered
```

This generates `comparison_report_{model}_role_filtered.json` alongside the original reports, allowing direct before/after comparison.

**For archived batches:**
```powershell
python scripts/apply_role_filter.py --model gemini/gemini-3.5-flash --results-dir results/archive/batch_1
python scripts/compare_results.py --model gemini/gemini-3.5-flash --results-dir results/archive/batch_1 --suffix _role_filtered
```

**⏱ Estimated time:** < 5 seconds per model (no API calls, pure local processing).

---

## Stage 6 — Archive a Completed Batch

After all 4 models finish, you've compared results, and optionally applied the role filter, **archive this batch** before generating a new dataset. The `archive_batch.py` script handles this automatically.

```powershell
# Check if all models are complete and archive
python scripts/archive_batch.py

# Force archive even if some models are incomplete
python scripts/archive_batch.py --force
```

**What the script checks before archiving:**
1. All 4 models have processed all files in the dataset (e.g., 200/200).
2. All 4 comparison reports exist.

If either condition fails, it refuses to archive unless `--force` is used.

**What stays in place (shared across all batches):**
- `results/algorithms/rule_based_findings.json` — the ground truth doesn't change.
- `results/algorithms/repo_manifest.json` — the repo metadata doesn't change.

**What gets archived (batch-specific):**
- `evaluation_dataset.json` — the 200-file sample unique to this batch.
- `llm_findings/` — all model outputs + role classifications for this batch.
- `comparison_reports/` — all comparison reports (including role-filtered ones).

After archiving, generate a **fresh dataset** and repeat from Stage 3:
```powershell
python scripts/llm_detector.py --generate-dataset --sample 200
```

> [!TIP]
> **Running multiple batches** lets you analyze 400, 600, or more files across different random samples, strengthening the statistical power of your results while keeping each batch's data cleanly separated.

---

## 6. Understanding the Output

### Directory Structure After a Full Run

```
results/
├── algorithms/
│   ├── rule_based_findings.json      # Ground truth (shared across batches)
│   ├── evaluation_dataset.json       # Current batch's locked 200-file sample
│   └── repo_manifest.json            # GitHub clone metadata (shared)
├── archive/                          # Completed batch archives
│   └── batch_1/
│       ├── evaluation_dataset.json   # That batch's locked dataset
│       ├── llm_findings/             # That batch's LLM outputs
│       └── comparison_reports/       # That batch's confusion matrices
├── llm_findings/                     # Active batch LLM outputs
│   ├── llm_findings_gemini_gemini-3.5-flash.json
│   ├── llm_findings_mistral_mistral-large-latest.json
│   ├── llm_findings_cohere_command-r-plus-08-2024.json
│   ├── llm_findings_groq_llama-3.3-70b-versatile.json
│   └── token_usage.log               # Timestamped token consumption
└── comparison_reports/               # Active batch confusion matrices
    ├── comparison_report_gemini_gemini-3.5-flash.json
    ├── comparison_report_mistral_mistral-large-latest.json
    ├── comparison_report_cohere_command-r-plus-08-2024.json
    └── comparison_report_groq_llama-3.3-70b-versatile.json
```

### Key Metrics Explained

| Metric | What It Means |
|---|---|
| **Precision** | Of all the files the LLM flagged, how many were actually correct? High precision = few false alarms. |
| **Recall** | Of all the files that actually had the issue, how many did the LLM catch? High recall = few missed cases. |
| **F1 Score** | The harmonic mean of Precision and Recall. A single number that balances both. |
| **TP (True Positive)** | LLM said YES, baseline said YES. ✅ Correct detection. |
| **FP (False Positive)** | LLM said YES, baseline said NO. ❌ False alarm. |
| **FN (False Negative)** | LLM said NO, baseline said YES. ❌ Missed detection. |
| **TN (True Negative)** | LLM said NO, baseline said NO. ✅ Correct rejection. |

---

## 7. Troubleshooting

### "ERROR: evaluation_dataset.json not found"
You need to generate the dataset first. Run:
```powershell
python scripts/llm_detector.py --generate-dataset --sample 200
```

### "ERROR: rule_based_findings.json not found"
The baseline hasn't been generated yet. Run:
```powershell
python scripts/run_baseline.py
```

### Rate limit errors (429 Too Many Requests)
- **Groq:** Add more API keys to `.env` (`GROQ_API_KEY_1`, `GROQ_API_KEY_2`, etc.). The router will auto-rotate.
- **Gemini:** The daily limit is 20 requests/day. With batch size 25, you need only 8 requests for 200 files. Wait until midnight Pacific Time for the limit to reset.
- **All providers:** The script has built-in retry logic with exponential backoff. If all keys are exhausted, stop and resume later — checkpointing ensures no progress is lost.

### "ModuleNotFoundError: No module named 'litellm'"
Make sure you activated the virtual environment and installed dependencies:
```powershell
.\venv\Scripts\activate
pip install -r requirements.txt
```

### Script seems stuck or frozen
Check `results/llm_findings/token_usage.log` — if new lines are appearing, the script is working. Groq processes 1 file every ~3 seconds, so 200 files takes ~10 minutes.

### Git clone errors during fetch_repos.py
Ensure `git` is installed and accessible from your terminal. Some repos may fail to clone due to network issues — the script will continue with the remaining repos and log errors.

---

## 8. Project Structure Reference

```
AlgoDebt/
├── Content/                          # IEEE paper + structured extracts
│   ├── algorithm_debt_paper_IEEE.pdf # The research paper
│   ├── algorithm_debt_paper_IEEE.md  # Grounded markdown version
│   └── tables/                       # Extracted tables (CSV + HTML)
├── scripts/
│   ├── fetch_repos.py                # Stage 1: Clone ML repos from GitHub
│   ├── rule_based_detector.py        # The AST-based anti-pattern detector
│   ├── run_baseline.py               # Stage 2: Run detector across all repos
│   ├── llm_detector.py               # Stage 3+4: Dataset generation + LLM evaluation + classification
│   ├── compare_results.py            # Stage 5: Compute Precision/Recall/F1
│   ├── apply_role_filter.py          # Stage 5.5: Apply role-based filtering to findings
│   └── archive_batch.py              # Stage 6: Archive completed batch
├── repos/                            # Cloned repositories (git-ignored)
├── results/
│   ├── algorithms/                   # Ground truth + active evaluation dataset
│   ├── archive/                      # Completed batch archives (batch_1/, batch_2/, ...)
│   ├── llm_findings/                 # Active batch LLM outputs
│   └── comparison_reports/           # Active batch confusion matrices
├── Analysis.md                       # Human-written analysis of results
├── API Limits.md                     # Free-tier rate limits per provider
├── README.md                         # Project overview + architecture diagram
├── HOW_TO_RUN.md                     # ← You are here
├── commands.md                       # Quick copy-paste command reference
├── requirements.txt                  # Python dependencies
└── .env                              # API keys (git-ignored, create manually)
```

---

## Quick Reference — Full Pipeline in Order

```powershell
# 0. Setup (one-time)
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
# Create .env with your API keys (see Section 4)

# 1. Fetch repos
python scripts/fetch_repos.py --n 30

# 2. Generate ground truth
python scripts/run_baseline.py

# 3. Lock the evaluation dataset
python scripts/llm_detector.py --generate-dataset --sample 200

# 4. Run LLMs (in any order, resumable)
python scripts/llm_detector.py --model gemini/gemini-3.5-flash
python scripts/llm_detector.py --model mistral/mistral-large-latest
python scripts/llm_detector.py --model cohere/command-r-plus-08-2024
python scripts/llm_detector.py --model groq/llama-3.3-70b-versatile

# 5. Grade each model
python scripts/compare_results.py --model gemini/gemini-3.5-flash
python scripts/compare_results.py --model mistral/mistral-large-latest
python scripts/compare_results.py --model cohere/command-r-plus-08-2024
python scripts/compare_results.py --model groq/llama-3.3-70b-versatile

# 5.5. (Optional) Classify file roles and apply role filter
python scripts/llm_detector.py --classify --model gemini/gemini-3.5-flash
python scripts/apply_role_filter.py --model gemini/gemini-3.5-flash
python scripts/apply_role_filter.py --model mistral/mistral-large-latest --roles-model gemini/gemini-3.5-flash
python scripts/apply_role_filter.py --model cohere/command-r-plus-08-2024 --roles-model gemini/gemini-3.5-flash
python scripts/apply_role_filter.py --model groq/llama-3.3-70b-versatile --roles-model gemini/gemini-3.5-flash
python scripts/compare_results.py --model gemini/gemini-3.5-flash --suffix _role_filtered
python scripts/compare_results.py --model mistral/mistral-large-latest --suffix _role_filtered
python scripts/compare_results.py --model cohere/command-r-plus-08-2024 --suffix _role_filtered
python scripts/compare_results.py --model groq/llama-3.3-70b-versatile --suffix _role_filtered

# 6. Archive this batch
python scripts/archive_batch.py
# Then repeat from step 3 for the next batch
```

---

*Built for the AlgoDebt research project — NED University of Engineering and Technology, Karachi.*
