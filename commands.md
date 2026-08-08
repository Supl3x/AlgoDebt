# Copy-Paste Commands for Evaluation Pipeline

*Make sure your virtual environment is activated before running these.*
```powershell
.\venv\Scripts\activate
```

---

### 1. Generate the 200-File Dataset (Run Once)
```powershell
python scripts/llm_detector.py --generate-dataset --sample 200
```

### 2. Run Gemini 3.5 Flash
```powershell
python scripts/llm_detector.py --model gemini/gemini-3.5-flash
```

### 3. Run Mistral Large
```powershell
python scripts/llm_detector.py --model mistral/mistral-large-latest
```

### 4. Run Cohere Command R+
```powershell
python scripts/llm_detector.py --model cohere/command-r-plus-08-2024
```

### 5. Run Groq (Llama 3.3)
```powershell
python scripts/llm_detector.py --model groq/llama-3.3-70b-versatile
```

---

### 🌟 All-in-One Sequential Run (Run all 4 one by one in the same terminal)
```powershell
python scripts/llm_detector.py --model gemini/gemini-3.5-flash ; python scripts/llm_detector.py --model mistral/mistral-large-latest ; python scripts/llm_detector.py --model cohere/command-r-plus-08-2024 ; python scripts/llm_detector.py --model groq/llama-3.3-70b-versatile
```

---

### 6. Compare Results (Grading)
*Run this for each model once they finish to get their Precision/Recall/F1 scores.*

```powershell
python scripts/compare_results.py --model gemini/gemini-3.5-flash
```

```powershell
python scripts/compare_results.py --model mistral/mistral-large-latest
```

```powershell
python scripts/compare_results.py --model cohere/command-r-plus-08-2024
```

```powershell
python scripts/compare_results.py --model groq/llama-3.3-70b-versatile
```
