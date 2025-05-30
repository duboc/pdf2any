# PDF2Any: PDF Data Extractor & Reconciler

A web application that extracts data from PDF documents using both OCR and AI techniques, reconciles the results, and generates structured Excel reports.

## Overview

PDF2Any automates the extraction of information from PDF documents by combining two powerful approaches:
1. **OCR Extraction**: Uses Tesseract OCR to extract raw text from image-based PDFs
2. **AI Extraction**: Leverages Google Vertex AI's Gemini model to extract structured data
3. **Reconciliation**: Combines and validates both extraction methods for improved accuracy
4. **Excel Generation**: Outputs the extracted data as downloadable Excel (.xlsx) files

Built with FastAPI for the backend and a simple HTML/JS frontend, PDF2Any streamlines the process of converting unstructured PDF data into structured, analyzable spreadsheets.

## Features

- **Simple Web UI** for PDF file uploads
- **Secure Cloud Storage** of PDFs in Google Cloud Storage (GCS)
- **Multi-step Extraction Workflow**:
  - OCR extraction using Tesseract
  - Structured data extraction using Vertex AI Gemini (`gemini-2.0-flash-001`)
  - Reconciliation of OCR and Gemini results
- **Excel Report Generation** with extracted data organized into sheets
- **Real-time Status Updates** on processing progress

## Architecture

```mermaid
sequenceDiagram
    actor User
    participant Frontend as Web UI
    participant API as Backend API
    participant UploadHandler as Upload Handler
    participant WorkflowManager as Workflow Manager
    participant GCS as Google Cloud Storage
    participant OSS_Extractor as OCR Module
    participant GeminiClient as Gemini Client
    participant VertexAI as Vertex AI
    participant Reconciler as Reconciliation Logic
    participant ExcelGen as Excel Generator
    
    User->>Frontend: Upload PDF
    Frontend->>API: Send PDF file
    API->>UploadHandler: Process upload
    UploadHandler->>GCS: Store PDF
    UploadHandler->>WorkflowManager: Trigger extraction
    
    par Parallel Extraction
        WorkflowManager->>OSS_Extractor: Start OCR extraction
        OSS_Extractor->>GCS: Read PDF
        OSS_Extractor->>WorkflowManager: Return raw text
        
        and AI Extraction
        WorkflowManager->>GeminiClient: Start AI extraction
        GeminiClient->>GCS: Read PDF
        GeminiClient->>VertexAI: Request structured extraction
        VertexAI->>GeminiClient: Return extraction result (JSON)
        GeminiClient->>WorkflowManager: Return structured JSON
    end
    
    WorkflowManager->>Reconciler: Start reconciliation
    Reconciler->>VertexAI: Request result validation
    VertexAI->>Reconciler: Return reconciled result
    Reconciler->>WorkflowManager: Return final data
    
    WorkflowManager->>ExcelGen: Generate Excel report
    ExcelGen->>WorkflowManager: Return report
    WorkflowManager->>API: Send report URL/data
    API->>Frontend: Return download link
    Frontend->>User: Display download button
    User->>Frontend: Request download
    Frontend->>User: Download Excel file
```

## Prerequisites

- **Python 3.8+**
- **Google Cloud Platform (GCP) Project** with:
  - Google Cloud Storage (GCS) enabled
  - Vertex AI API enabled
  - Service Account with appropriate permissions
- **Tesseract OCR Engine** installed and available in the system's PATH
  - [Tesseract Installation Guide](https://tesseract-ocr.github.io/tessdoc/Installation.html)
- **Poppler utilities** installed (required by `pdf2image`)
  - [Poppler Installation Guide](https://pdf2image.readthedocs.io/en/latest/installation.html)

## Setup & Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd pdf2any
   ```

2. **Create and activate a virtual environment**
   ```bash
   # Create virtual environment
   python -m venv venv
   
   # Activate on macOS/Linux
   source venv/bin/activate
   
   # Activate on Windows
   venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   
   Create a `.env` file in the project root directory with the following variables:
   ```dotenv
   GCP_PROJECT_ID=your-gcp-project-id
   GCS_BUCKET_NAME=your-gcs-bucket-name-for-uploads
   GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json
   VERTEX_AI_LOCATION=your-gcp-region # e.g., us-central1
   ```

## Running the Application

1. **Ensure the virtual environment is active**

2. **Start the FastAPI server**
   ```bash
   uvicorn app.main:app --reload
   ```

3. **Access the application**
   
   Open your web browser and navigate to `http://127.0.0.1:8000`

## How to Use

1. **Access the web interface** in your browser at `http://127.0.0.1:8000`

2. **Upload a PDF file** using the form on the page

3. **Monitor the extraction process**
   - The page will display status updates as the PDF is processed
   - The workflow includes: uploading, OCR processing, Gemini extraction, reconciliation, and report generation

4. **Download the results**
   - Once processing is complete, a download link for the Excel report will appear
   - Click the link to download the `.xlsx` file containing the extracted data

## Configuration Details

The `.env` file contains the following configuration variables:

- **GCP_PROJECT_ID**: Your Google Cloud Platform project ID
- **GCS_BUCKET_NAME**: The name of the GCS bucket where PDF files will be uploaded
- **GOOGLE_APPLICATION_CREDENTIALS**: Path to your GCP service account key file (JSON)
- **VERTEX_AI_LOCATION**: The GCP region for Vertex AI API calls (e.g., us-central1)

## License

This project is licensed under the MIT License - see the LICENSE file for details.
