# Project Brief: PDF Data Extractor & Reconciler

## 1. Project Goal

Build a Python web application that enables users to upload PDF files to a Google Cloud Storage (GCS) bucket. The application will orchestrate the extraction of specific information from these PDFs using two methods:
1.  Open-source Python libraries.
2.  Google Cloud Vertex AI (specifically, the Gemini model).

After extraction, the application will use another Vertex AI call to reconcile the data obtained from both sources. Finally, it will generate an Excel (.xls) file containing the reconciled data.

## 2. Core Components

*   **Frontend:** A web interface allowing users to select and upload PDF files.
*   **Backend API (Python):**
    *   Handles PDF file uploads and saves them to a designated GCS bucket.
    *   Manages the workflow: triggers OSS extraction, triggers Vertex AI extraction, triggers Vertex AI reconciliation.
    *   Generates the final Excel report.
    *   Likely built using a web framework like Flask or FastAPI.
*   **OSS PDF Extraction Module:** A Python module responsible for extracting data using libraries like PyPDF2, pdfminer.six, or others suitable for the PDF structure. May require OCR capabilities (e.g., integrating Tesseract) if PDFs are image-based.
*   **Vertex AI Gemini Integration (`gemini_client.py`):** Utilizes the provided `gemini_client.py` library and leverages patterns from `examples/withgcs.py` to interact with Vertex AI:
    *   Extracts data from PDFs stored in GCS.
    *   Reconciles the data extracted by the OSS module and the initial Gemini extraction.
*   **Reconciliation Logic:** Implemented via a dedicated prompt/call to Vertex AI Gemini, designed to compare, evaluate, and merge the outputs from the two extraction methods.
*   **Excel Generation Module:** A Python module using libraries like `pandas` or `openpyxl` to create an `.xls` file from the final reconciled data structure.
*   **Configuration Management:** Sensitive information (API keys, GCS bucket details, Vertex AI project details) will be managed securely using a `.env` file and loaded at runtime (e.g., using `python-dotenv`).

## 3. Key Requirements

*   Secure handling of file uploads and cloud credentials.
*   Clear separation of concerns between frontend, backend API, and processing modules.
*   Robust error handling throughout the process (upload, extraction, reconciliation, report generation).
*   Configuration via environment variables (`.env`).
*   Output format must be an Excel `.xls` file.

## 4. Assumptions

*   Access to a Google Cloud Platform project with Vertex AI and GCS enabled is available.
*   Necessary permissions are configured for the service account or credentials used by the application.
*   The structure of the PDFs and the specific information to be extracted will be defined.
*   `gemini_client.py` provides the necessary functions for interacting with Vertex AI for both extraction and reconciliation tasks, potentially requiring adaptation.
