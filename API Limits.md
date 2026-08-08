# Free Tier API Limits

When running evaluations across hundreds of files, it is critical to understand the Free Tier limits of each AI provider so you don't get blocked with `429 Too Many Requests` errors.

Rate limits are generally measured in two ways:
1. **RPM (Requests Per Minute):** The maximum number of API calls you can make in 60 seconds.
2. **TPM (Tokens Per Minute):** The maximum number of words/code pieces you can send and receive in 60 seconds.

Here is the 2026 data for the providers we are testing:

### 1. Groq
* **RPM:** 30 Requests Per Minute
* **TPM:** ~6,000 to 12,000 Tokens Per Minute (varies slightly by model)
* **Optimal Strategy:** Because the TPM limit is incredibly strict, you **cannot batch files**. You must send 1 file per request and wait ~2 seconds between requests to ensure you never cross 30 RPM.

### 2. Google Gemini (AI Studio)
* **RPM:** 15 Requests Per Minute
* **TPM:** 1,000,000 Tokens Per Minute
* **Optimal Strategy:** Gemini allows a massive amount of tokens but very few individual requests. You **must batch files**. Sending 25 files per request with a 4-second delay is perfect.

### 3. Mistral (La Plateforme)
* **RPM:** 30 Requests Per Minute (or 1 Request Per Second)
* **TPM:** 500,000 Tokens Per Minute
* **Optimal Strategy:** Mistral has generous token limits. You can safely batch 25 files per request and use a small 2-second delay.

### 4. Cohere
* **RPM:** ~100 Requests Per Minute (Trial Key)
* **TPM:** Generous trial allowance.
* **Optimal Strategy:** Similar to Mistral, you can comfortably batch 25 files at a time to speed through the evaluation dataset.

---
*Note: The `scripts/llm_detector.py` script automatically configures the optimal batching and delay settings based on the model prefix you provide, so you do not need to memorize these limits!*
