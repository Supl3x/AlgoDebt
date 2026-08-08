# Free Tier API Limits

When running evaluations across hundreds of files, it is critical to understand the Free Tier limits of each AI provider so you don't get blocked with `429 Too Many Requests` errors.

Rate limits are generally measured in two ways:
1. **RPM (Requests Per Minute):** The maximum number of API calls you can make in 60 seconds.
2. **TPM (Tokens Per Minute):** The maximum number of words/code pieces you can send and receive in 60 seconds.

Here is the 2026 data for the providers we are testing:

### 1. Groq (`llama-3.3-70b-versatile`)
* **RPM:** 30 Requests Per Minute
* **TPM:** ~6,000 Tokens Per Minute
* **TPD (Tokens Per Day):** 100,000 Tokens Per Day (Resets at Midnight UTC)
* **Optimal Strategy:** Because the TPM limit is incredibly strict, you **cannot batch files**. You must send 1 file per request and wait ~2 seconds between requests. To process 200 files (~250k tokens), you need 3 API keys pooled in your `.env`.

### 2. Google Gemini (`gemini-3.5-flash`)
* **RPM:** 15 Requests Per Minute
* **RPD (Requests Per Day):** 20 Requests Per Day Per Model (Resets at Midnight Pacific Time)
* **Optimal Strategy:** Gemini allows massive input tokens. Thanks to strict JSON Schemas preventing truncation, we safely batch 25 files per request. To process 200 files, you only need exactly 8 requests, meaning 1 single API key can clear the whole dataset without hitting the daily quota.

### 3. Mistral (La Plateforme)
* **RPM:** 30 Requests Per Minute (or 1 Request Per Second)
* **TPM:** 500,000 Tokens Per Minute
* **Optimal Strategy:** Mistral has extremely generous token limits. We comfortably batch 25 files per request with a 2-second delay.

### 4. Cohere
* **RPM:** ~100 Requests Per Minute (Trial Key)
* **TPM:** Generous trial allowance.
* **Optimal Strategy:** Cohere's API rejects strict JSON Schemas, which means it is at risk of truncating output if we send too many files. Therefore, we limit Cohere to batching 15 files at a time to balance speed and data integrity.

---
## Automatic Key Rotation (The Router)
Because we are working under very strict free-tier limits (especially with Groq), the pipeline uses `litellm.Router`. 
You can put as many keys as you want in your `.env` file (`GROQ_API_KEY_1`, `GROQ_API_KEY_2`, etc). The router will automatically swap to a fresh key the millisecond your current key hits a rate limit or daily quota.

---
*Note: The `scripts/llm_detector.py` script automatically configures the optimal batching and delay settings based on the model prefix you provide, so you do not need to memorize these limits!*
