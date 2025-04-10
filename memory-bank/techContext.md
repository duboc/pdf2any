# Tech Context: PDF Data Extractor & Reconciler

## 1. Core Technologies

*   **Backend Language:** Python (Version 3.8+)
*   **Backend Framework:** FastAPI (Confirmed), Uvicorn (ASGI server)
*   **Frontend:** Standard HTML, CSS, JavaScript (No complex framework initially planned)
*   **Cloud Platform:** Google Cloud Platform (GCP)
    *   **Storage:** Google Cloud Storage (GCS) for PDF uploads and potentially storing results.
    *   **AI Services:** Google Cloud Vertex AI (Gemini API - `gemini-2.0-flash-001` model confirmed) for data extraction and reconciliation.
*   **Configuration:** `python-dotenv` for loading environment variables from a `.env` file.
*   **Dependency Management:** `pip` with a `requirements.txt` file.

## 2. Key Python Libraries

*   **Web Framework:** `fastapi`, `uvicorn`
*   **GCP Interaction:**
    *   `google-cloud-storage`: For interacting with GCS buckets.
*   **Vertex AI Client:**
    *   The provided `gemini_client.py`.
    *   Dependencies identified: `google-generativeai`, `tenacity`.
*   **OSS PDF Extraction (OCR):**
    *   `pytesseract`: Python wrapper for Google's Tesseract-OCR engine (Required due to image-based PDFs).
    *   `Pillow`: Required by `pytesseract` for image handling.
    *   **External Dependency:** Tesseract OCR engine must be installed on the host system.
*   **Excel Generation:**
    *   `pandas`: For data manipulation and exporting to Excel.
    *   `openpyxl`: Required by pandas for `.xlsx` format (Confirmed).
*   **Environment Variables:** `python-dotenv`

## 3. Development Setup

*   **Environment:** Virtual environment (`venv`) recommended for managing Python dependencies.
    ```bash
    python -m venv venv
    source venv/bin/activate # or venv\Scripts\activate on Windows
    pip install -r requirements.txt
    ```
*   **`.env` File:** A `.env` file at the project root containing:
    ```dotenv
    GCP_PROJECT_ID=your-gcp-project-id
    GCS_BUCKET_NAME=your-pdf-upload-bucket-name
    GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json # Or rely on application default credentials
    # Potentially other Vertex AI specific configs if needed by gemini_client.py
    VERTEX_AI_LOCATION=your-gcp-region # e.g., us-central1
    ```
*   **`gemini_client.py`:** Ensure this file is correctly placed within the project structure (e.g., in a `lib` or `utils` directory) and is importable by the backend application.
*   **`examples/withgcs.py`:** Use as a reference for understanding how `gemini_client.py` interacts with GCS URIs.

## 4. Technical Constraints & Considerations

*   **Vertex AI Quotas/Limits:** Be mindful of Vertex AI API call limits and costs.
*   **OSS Library Limitations:** Different OSS PDF libraries have varying capabilities regarding layout preservation, handling of scanned documents (requiring OCR), and extracting data from complex tables or forms. The choice depends heavily on the expected input PDF format.
*   **Reconciliation Prompt Engineering:** The effectiveness of the reconciliation step heavily depends on the quality of the prompt provided to Gemini. This will likely require iteration.
*   **Excel Format (`.xlsx`):** Confirmed `.xlsx` format. `xlwt` is not needed.
*   **Security:** Ensure the service account credentials used have the principle of least privilege applied (only access to necessary GCS buckets and Vertex AI services). Avoid exposing the `.env` file or credentials in version control.
*   **AI Model:** Use `gemini-2.0-flash-001` as specified by the user for all Gemini interactions via `gemini_client.py`.
