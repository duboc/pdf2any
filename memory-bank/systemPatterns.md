# System Patterns: PDF Data Extractor & Reconciler

## 1. Architecture Overview

A web application architecture separating frontend and backend concerns will be used. The backend will orchestrate the multi-step PDF processing workflow involving external services (GCS, Vertex AI) and internal modules (OSS extraction, Excel generation).

```mermaid
graph LR
    subgraph User Browser
        Frontend[Web UI (HTML/JS/CSS)]
    end

    subgraph Backend Server (Python/FastAPI - Confirmed)
        API[API Endpoints]
        UploadHandler[Upload Handler]
        WorkflowManager[Workflow Manager]
        OSS_Extractor[OSS OCR Module (Tesseract)]
        GeminiClient[Gemini Client (gemini_client.py)]
        Reconciler[Reconciliation Logic (via Gemini)]
        ExcelGen[Excel Generator (xlsx)]
        EnvConfig[Config Loader (.env)]
    end

    subgraph Google Cloud Platform
        GCS[GCS Bucket]
        VertexAI[Vertex AI (Gemini API)]
    end

    User[User] --> Frontend;
    Frontend -- Upload PDF --> API;
    API --> UploadHandler;
    UploadHandler -- Save PDF --> GCS;
    UploadHandler -- Trigger --> WorkflowManager;

    WorkflowManager -- Start OSS --> OSS_Extractor;
    WorkflowManager -- Start Gemini Extraction --> GeminiClient;
    GeminiClient -- Reads PDF --> GCS;
    GeminiClient -- Calls --> VertexAI;

    OSS_Extractor -- Raw Text --> WorkflowManager;
    VertexAI -- Extraction Result (JSON) --> GeminiClient;
    GeminiClient -- Structured JSON --> WorkflowManager;

    WorkflowManager -- Start Reconciliation (Structured JSON, Raw OCR Text) --> Reconciler;
    Reconciler -- Calls --> VertexAI;
    VertexAI -- Reconciled Result --> Reconciler;
    Reconciler -- Result --> WorkflowManager;

    WorkflowManager -- Generate Report (Final Data) --> ExcelGen;
    ExcelGen -- Report --> WorkflowManager;
    WorkflowManager -- Send Report URL/Data --> API;
    API -- Download Link/File --> Frontend;
    Frontend -- Display/Download --> User;

    EnvConfig -- Loads Config --> Backend Server;

```

## 2. Key Design Patterns & Decisions

*   **API Framework:** FastAPI confirmed. It offers built-in data validation (Pydantic) and async capabilities, beneficial for potential long-running tasks.
*   **Separation of Concerns:** Each major step (upload, OCR, Gemini extraction, reconciliation, Excel generation) will be handled by distinct modules or functions within the backend.
*   **OSS Extraction Strategy:** Use Tesseract OCR via `pytesseract` to get raw text from the image-based PDFs. This provides a baseline text representation without attempting complex structure parsing via OSS.
*   **Gemini Extraction Strategy:** Use Gemini (`gemini-2.0-flash-001` model) with the GCS URI and a prompt designed to extract all identifiable information into a structured JSON format.
*   **Reconciliation Strategy:** Use Gemini (`gemini-2.0-flash-001` model) to compare the structured JSON from the initial Gemini extraction against the raw text from OCR. The prompt will guide Gemini to refine its initial structured output based on the OCR text, aiming for completeness and accuracy.
*   **Asynchronous Processing (Consideration):** For potentially long-running extraction/reconciliation tasks, consider using asynchronous task queues (like Celery with Redis/RabbitMQ) or leveraging async capabilities within FastAPI. This prevents blocking the main API thread and improves responsiveness. Initially, synchronous processing might be sufficient for simplicity, but scalability requires async.
*   **Configuration Management:** Use `python-dotenv` to load sensitive configurations (GCP project ID, bucket name, API keys/credentials paths) from a `.env` file, keeping secrets out of the codebase.
*   **Error Handling:** Implement robust try-except blocks around external API calls (GCS, Vertex AI) and file processing steps. Provide clear error messages back to the user via the API.
*   **Modularity:** Design the `gemini_client.py` interactions and the OSS extraction logic to be as modular as possible, allowing potential future swapping or upgrading of models or libraries.
*   **State Management:** The `WorkflowManager` component will track the state of a PDF's processing journey (e.g., uploaded, performing_ocr, extracting_gemini, reconciling, generating_report, completed, failed).

## 3. Data Flow (Refined)

1.  **Upload:** User uploads PDF -> Frontend sends to Backend API -> Backend saves to GCS -> Backend records task start.
2.  **Processing Trigger:** Backend initiates the workflow via `WorkflowManager`.
3.  **Step 1: OSS OCR:** `WorkflowManager` triggers OCR module -> OCR module reads PDF from GCS -> Performs OCR -> Returns raw text to `WorkflowManager`.
4.  **Step 2: Gemini Extraction:** `WorkflowManager` triggers Gemini extraction -> Calls `gemini_client.py` with GCS URI and extraction prompt (requesting JSON output) -> Returns structured JSON to `WorkflowManager`.
5.  **Step 3: Reconciliation:** `WorkflowManager` triggers reconciliation -> Calls `gemini_client.py` with structured JSON (from Step 2), raw OCR text (from Step 1), and reconciliation prompt (requesting refined JSON output) -> Returns final reconciled JSON to `WorkflowManager`.
6.  **Step 4: Report Generation:** `WorkflowManager` passes final JSON to Excel generation module -> Module creates `.xlsx` file -> Saves file (e.g., to GCS or temp storage).
7.  **Delivery:** Backend API provides a download link/mechanism for the user to retrieve the generated `.xlsx` file.

## 4. Frontend Approach

*   A simple HTML form for file upload.
*   JavaScript to handle the asynchronous upload request to the backend API.
*   Mechanism to display processing status updates received from the backend (e.g., polling, WebSockets - start simple with polling or basic status updates on completion).
*   Display a download link upon successful completion.
