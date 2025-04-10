# Active Context: PDF Data Extractor & Reconciler (Initialization)

## 1. Current Focus

The immediate focus is on finalizing the initial project plan and gathering necessary clarifications before starting implementation. This involves:
*   Completing the initial setup of the Memory Bank documentation.
*   Analyzing the provided `gemini_client.py` and `examples/withgcs.py` to understand the existing Vertex AI interaction patterns.
*   Incorporating user decisions into the plan (OCR for OSS, "extract everything" goal, `.xlsx` format, FastAPI, `gemini-2.0-flash-001` model).
*   Updating Memory Bank documentation to reflect these decisions.
*   Finalizing the plan before requesting the switch to Act Mode.

## 2. Recent Changes

*   Created initial Memory Bank documents:
    *   `projectbrief.md`
    *   `productContext.md`
    *   `systemPatterns.md`
    *   `techContext.md`
*   Received user clarifications on data fields, PDF type, Excel format, framework, and model.
*   Updated `techContext.md` and `systemPatterns.md`.

## 3. Next Steps (Planning Phase)

1.  Update `activeContext.md` (this file).
2.  Update `progress.md`.
3.  Present the final refined plan to the user.
4.  Request the user to switch to Act Mode to begin implementation.

## 4. Active Decisions & Considerations (Updated)

*   **Framework Choice:** FastAPI (Confirmed).
*   **OSS PDF Strategy:** Use Tesseract OCR via `pytesseract` to extract raw text, as PDFs are image-based. The goal is "everything", so structured extraction via OSS is impractical.
*   **Excel Format:** `.xlsx` (Confirmed). `xlwt` is not needed; `openpyxl` will be used with `pandas`.
*   **Specific Data Extraction:** The goal is "extract everything". This simplifies OSS (just OCR text) but puts more emphasis on prompt engineering for both Gemini extraction and reconciliation steps to get comprehensive, structured JSON output.
*   **Reconciliation Strategy:** Refined to use Gemini to compare its initial structured JSON extraction against the raw OCR text, aiming to produce a final, verified JSON structure. Prompt engineering is critical here.
*   **Asynchronous Processing:** Start with synchronous implementation for simplicity, consider refactoring to async later if performance requires it.
*   **AI Model:** Use `gemini-2.0-flash-001` for all Vertex AI calls (Confirmed).

## 5. Key Learnings & Patterns (Updated)

*   The project combines OCR (OSS) for text grounding with multi-stage AI processing (Extraction + Reconciliation) via Vertex AI.
*   Configuration management via `.env` is essential for GCP credentials and settings.
*   The `gemini_client.py` facilitates Vertex AI interactions, supporting GCS URIs and JSON output.
*   The "extract everything" goal requires robust prompt engineering for Gemini to structure the output effectively during both extraction and reconciliation.
*   Tesseract OCR external dependency needs to be managed.
