# Progress: PDF Data Extractor & Reconciler (Initialization)

## 1. Current Status

*   **Phase:** Planning & Setup
*   **Overall Progress:** 0% implemented. Initial project documentation (Memory Bank) is being established.

## 2. What Works

*   N/A (No implementation yet)

## 3. What's Left to Build (High-Level)

*   Project structure setup (directories, virtual environment).
*   Backend API skeleton (using FastAPI/Flask).
*   `.env` configuration setup and loading logic.
*   Frontend HTML/JS for file upload.
*   Backend endpoint for handling file uploads to GCS.
*   OSS PDF extraction module implementation.
*   Integration with `gemini_client.py` for Vertex AI extraction (based on `examples/withgcs.py`).
*   Integration with `gemini_client.py` for Vertex AI reconciliation (requires prompt design).
*   Workflow management logic to orchestrate the steps.
*   Excel (`.xls` or `.xlsx`) generation module.
*   Backend endpoint to serve the generated Excel file.
*   Error handling and user feedback mechanisms.
*   Dependency management (`requirements.txt`).
*   Testing (Unit/Integration).

## 4. Known Issues & Blockers (Updated)

*   **External Dependency:** The use of `pytesseract` requires the Tesseract OCR engine to be installed on the host system where the backend runs. This needs to be ensured during setup/deployment.
*   **Prompt Engineering:** The "extract everything" goal requires careful prompt engineering for both the initial Gemini extraction and the reconciliation step to ensure comprehensive and accurately structured JSON output. This will likely require iteration during development.

## 5. Decisions Log (Updated)

*   **(Confirmed)** Backend Framework: FastAPI.
*   **(Confirmed)** OSS PDF Strategy: Tesseract OCR (via `pytesseract` and `Pillow`) for raw text extraction from image-based PDFs.
*   **(Confirmed)** Excel Output Format: `.xlsx` (using `pandas` and `openpyxl`).
*   **(Confirmed)** AI Model: `gemini-2.0-flash-001` for all Vertex AI interactions.
*   **(Decision)** Asynchronous Processing: Start synchronously, consider async refactor later if needed.
