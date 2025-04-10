import asyncio
import pandas as pd
import os
import sys
import json  # Add standard json library
import re  # For regex pattern matching
from .config import settings, logger

# --- Helper Functions for LLM Response Processing ---
def clean_llm_response(text):
    """
    Remove introductory text and other non-data content from LLM response.
    This helps eliminate phrases like "Com certeza! Aqui está a transcrição..."
    """
    # Common introductory phrases in different languages
    intro_patterns = [
        r"^(Com certeza!|Aqui está|Claro|Certainly|Here is|Sure|Of course|Voilà)[^|*#]+",
        r"^[^|*#\n]+?(transcrição|transcription|spreadsheet|planilha)[^|*#\n]+\n+",
        r"^[^|*#\n]+?(tabela|table|data|dados)[^|*#\n]+\n+"
    ]
    
    # Try to find and remove introductory text
    cleaned_text = text
    for pattern in intro_patterns:
        cleaned_text = re.sub(pattern, "", cleaned_text, flags=re.IGNORECASE | re.DOTALL)
    
    # Remove any leading blank lines after cleaning
    cleaned_text = re.sub(r"^\s*\n+", "", cleaned_text)
    
    # If we've removed a significant portion, log it
    if len(cleaned_text) < len(text) * 0.9:
        logger.debug(f"Removed introductory text: {len(text) - len(cleaned_text)} characters")
    
    return cleaned_text

def parse_markdown_table(text):
    """
    Parse a markdown table into a structured format with proper headers and rows.
    Returns a dictionary with 'headers' and 'rows' keys.
    """
    lines = text.strip().split('\n')
    table_data = []
    headers = None
    
    # Find the table start (first line with |)
    table_start = 0
    for i, line in enumerate(lines):
        if '|' in line:
            table_start = i
            break
    
    # Process table lines
    for i, line in enumerate(lines[table_start:]):
        # Skip separator lines (contain only |, -, and spaces)
        if all(c in '|-+ ' for c in line):
            continue
        
        # Skip empty lines
        if not line.strip():
            continue
        
        # Extract cells from the line
        cells = [cell.strip() for cell in line.split('|')]
        # Remove empty cells at the beginning and end (from the | at start/end of line)
        if cells and not cells[0]:
            cells = cells[1:]
        if cells and not cells[-1]:
            cells = cells[:-1]
        
        # If this is the first data line, it's the header
        if headers is None:
            headers = cells
            continue
        
        # Create a row object
        if headers:
            row = {}
            for j, cell in enumerate(cells):
                # Use header if available, otherwise use column index
                column_name = headers[j] if j < len(headers) else f"Column_{j+1}"
                row[column_name] = cell.strip()
            table_data.append(row)
    
    return {"headers": headers, "rows": table_data}

# --- Dependency Imports with Error Handling ---

# Add lib directory to path for gemini_client import
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'lib')))
try:
    # Assuming gemini_client.py is in ../lib/ relative to this file
    from lib.gemini_client import GeminiClient, types
    # Initialize Gemini Client
    gemini = GeminiClient(project_id=settings.gcp_project_id)
    logger.info("GeminiClient initialized successfully.")
except ImportError:
    logger.error("Could not import or initialize GeminiClient from lib directory. AI functions will fail.")
    GeminiClient = None
    gemini = None
    types = None
except Exception as e:
    logger.error(f"Error initializing GeminiClient: {e}", exc_info=True)
    GeminiClient = None
    gemini = None
    types = None

# Import OCR related libraries
try:
    import pytesseract
    from PIL import Image
    from pdf2image import convert_from_bytes
    logger.info("OCR libraries (pytesseract, Pillow, pdf2image) imported successfully.")
except ImportError:
    logger.error("OCR dependencies (pytesseract, Pillow, pdf2image) not installed or importable. OCR functionality will fail.")
    pytesseract = None
    Image = None
    convert_from_bytes = None

# Import GCS client
try:
    from google.cloud import storage
    storage_client = storage.Client(project=settings.gcp_project_id)
    logger.info("Google Cloud Storage client initialized successfully.")
except ImportError:
     logger.error("google-cloud-storage library not installed. GCS operations will fail.")
     storage_client = None
except Exception as e:
    logger.error(f"Failed to initialize Google Cloud Storage client: {e}", exc_info=True)
    storage_client = None

# --- OCR Implementation ---
async def perform_ocr(gcs_uri: str) -> str:
    """
    Downloads PDF from GCS, performs OCR on each page using Tesseract via pdf2image,
    and returns the concatenated raw text. Requires Poppler and Tesseract executables.
    """
    # Check library dependencies explicitly
    if not pytesseract: raise ImportError("pytesseract library not available.")
    if not Image: raise ImportError("Pillow (PIL) library not available.")
    if not convert_from_bytes: raise ImportError("pdf2image library not available.")
    if not storage_client: raise ValueError("Google Cloud Storage client not initialized.")

    # Check for Tesseract executable (pdf2image errors out if Poppler is missing)
    try:
        tesseract_version = pytesseract.get_tesseract_version()
        logger.debug(f"Tesseract version detected: {tesseract_version}")
    except Exception as tess_err:
         error_msg = f"Tesseract executable not found or failed: {tess_err}. OCR cannot proceed."
         logger.error(error_msg)
         raise RuntimeError(error_msg) # Raise critical error

    logger.info(f"Starting OCR process for {gcs_uri}")

    try:
        # 1. Parse GCS URI and Download PDF blob content
        if not gcs_uri.startswith("gs://"):
            raise ValueError("Invalid GCS URI format. Must start with gs://")
        bucket_name, blob_name = gcs_uri[5:].split("/", 1)

        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        logger.debug(f"Downloading blob: {blob_name} from bucket: {bucket_name}")
        pdf_bytes = blob.download_as_bytes()
        logger.debug(f"Downloaded {len(pdf_bytes)} bytes for OCR.")

        # 2. Convert PDF bytes to list of PIL Images using pdf2image
        loop = asyncio.get_running_loop()
        logger.debug("Converting PDF bytes to images (using thread pool)...")
        # Increased DPI for potentially better OCR quality
        # Ensure Poppler path is correct if not in system PATH (using poppler_path argument)
        images = await loop.run_in_executor(None, lambda: convert_from_bytes(pdf_bytes, dpi=300))
        logger.info(f"Converted PDF ({gcs_uri}) to {len(images)} images for OCR.")

        if not images:
            logger.warning(f"pdf2image returned no images for {gcs_uri}. PDF might be empty or corrupt.")
            return "" # Return empty string if no images

        # 3. Perform OCR on each image and concatenate text
        all_text = []
        logger.debug(f"Performing OCR on {len(images)} pages (using thread pool)...")
        for i, img in enumerate(images):
            # Run tesseract in executor thread
            # Specify language ('eng' or others like 'por' for Portuguese if needed)
            page_text = await loop.run_in_executor(None, lambda: pytesseract.image_to_string(img, lang='eng'))
            all_text.append(page_text)
            logger.debug(f"OCR for page {i+1} of {len(images)} complete.")
            # Close image object to free memory
            img.close()

        concatenated_text = "\n\n--- Page Break ---\n\n".join(all_text)
        logger.info(f"OCR completed successfully for {gcs_uri}. Total characters extracted: {len(concatenated_text)}")
        return concatenated_text

    except ImportError as ie:
         logger.error(f"OCR Import Error during processing for {gcs_uri}: {ie}")
         raise # Re-raise critical dependency errors
    except ValueError as ve:
         logger.error(f"OCR Value Error for {gcs_uri}: {ve}", exc_info=True)
         raise # Re-raise configuration/input errors
    except storage.blob.NotFound:
         logger.error(f"PDF not found in GCS at {gcs_uri}")
         raise FileNotFoundError(f"PDF not found in GCS at {gcs_uri}")
    except Exception as e:
        # Catch potential errors from GCS download, pdf2image conversion, or tesseract
        error_type = type(e).__name__
        logger.error(f"An error occurred during OCR for {gcs_uri}: {error_type} - {e}", exc_info=True)
        # Check for known pdf2image/Poppler errors
        if "poppler" in str(e).lower() or "PDFInfoNotInstalledError" in error_type:
             logger.error("This likely indicates Poppler utilities are not installed or not in the system PATH.")
        raise Exception(f"OCR processing failed for {gcs_uri} due to {error_type}") from e

# --- Gemini Extraction Implementation ---
async def extract_with_gemini(gcs_uri: str) -> dict:
    """
    Uses Gemini (gemini-2.0-flash-001) via gemini_client to extract structured data
    from the PDF specified by the GCS URI.
    """
    if not gemini: raise ImportError("GeminiClient not initialized.")
    if not types: raise ImportError("google.genai.types not available.")

    logger.info(f"Starting Gemini extraction for {gcs_uri}")

    # Construct the prompt and content parts
    try:
        pdf_part = types.Part.from_uri(
            file_uri=gcs_uri,
            mime_type="application/pdf",
        )
    except Exception as e:
        logger.error(f"Failed to create types.Part from GCS URI {gcs_uri}: {e}", exc_info=True)
        raise ValueError(f"Could not process GCS URI: {gcs_uri}") from e

    # Improved prompt requesting structured JSON with tables
    prompt = """
    Analyze the provided PDF document and extract ALL information presented.
    Structure the extracted information into a JSON object with the following format:
    {
      "metadata": {
        "document_title": "string (optional, inferred title)",
        "page_count": "integer"
      },
      "key_value_pairs": {
        "key1": "value1",
        "key2": "value2",
        ...
      },
      "text_sections": {
         "section_title_or_header_1": "Full text of the section...",
         "section_title_or_header_2": "Full text of the section...",
         ...
      },
      "tables": [
        {
          "table_title": "string (optional, title or description of the table)",
          "headers": ["Header 1", "Header 2", ...],
          "rows": [
            ["Row 1 Cell 1", "Row 1 Cell 2", ...],
            ["Row 2 Cell 1", "Row 2 Cell 2", ...]
          ]
        },
        ...
      ]
    }

    - Extract all key-value pairs found.
    - Group coherent blocks of text under meaningful section titles or headers.
    - Identify all tables. For each table, provide an optional title, a list of headers, and a list of rows (where each row is a list of cell values as strings).
    - Ensure the JSON is valid.
    """
    contents = [types.Content(role="user", parts=[pdf_part, types.Part.from_text(text=prompt)])]

    # Define a more specific schema for the expected JSON output
    json_schema = {
        "type": "OBJECT",
        "properties": {
            "metadata": {
                "type": "OBJECT",
                "properties": {
                    "document_title": {"type": "STRING"},
                    "page_count": {"type": "INTEGER"}
                }
            },
            "key_value_pairs": {"type": "OBJECT"},
            "text_sections": {"type": "OBJECT"},
            "tables": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "table_title": {"type": "STRING"},
                        "headers": {"type": "ARRAY", "items": {"type": "STRING"}},
                        "rows": {"type": "ARRAY", "items": {"type": "ARRAY", "items": {"type": "STRING"}}}
                    },
                    "required": ["headers", "rows"] # Headers and rows are essential for a table
                }
            }
        },
        "required": ["tables"] # We expect at least the tables array, even if empty
    }

    try:
        logger.debug(f"Calling Gemini for extraction with schema for {gcs_uri}...")
        # Create generation config similar to the example script
        generation_config = types.GenerateContentConfig(
            temperature=0.2,
            top_p=0.8,
            max_output_tokens=8096,
            response_modalities=["TEXT"],
            safety_settings=[
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF")
            ]
        )
        
        # Use the async method from gemini_client with the custom generation config
        # Use return_json=True and the defined json_schema
        response_data, token_count = await gemini.generate_content_async(
            contents=contents,
            model="gemini-2.0-flash-001", # Use confirmed model
            generation_config=generation_config,
            return_json=True,       # Request JSON output
            json_schema=json_schema, # Provide the schema
            count_tokens=True        # Request token count
        )

        if token_count:
             logger.info(f"Gemini extraction token usage for {gcs_uri}: Prompt={token_count.prompt_tokens}, Completion={token_count.completion_tokens}, Total={token_count.total_tokens}")
        else:
             logger.warning(f"Gemini extraction call for {gcs_uri} did not return token count.") # Should usually return count

        logger.info(f"Gemini extraction successful for {gcs_uri}.")

        # Expecting a dictionary response due to return_json=True
        if isinstance(response_data, dict):
            logger.debug(f"Received structured JSON response: {json.dumps(response_data, indent=2, ensure_ascii=False)}")

            # Validate the structure (basic check)
            if not isinstance(response_data.get("tables"), list):
                 logger.warning("Response 'tables' field is missing or not a list. Initializing as empty list.")
                 response_data["tables"] = []
            else:
                 # Log details about extracted tables
                 num_tables = len(response_data["tables"])
                 logger.info(f"Extracted {num_tables} tables.")
                 for i, table in enumerate(response_data["tables"]):
                     if isinstance(table, dict) and isinstance(table.get("rows"), list):
                         logger.debug(f"Table {i+1} ('{table.get('table_title', 'N/A')}') has {len(table['rows'])} rows.")
                     else:
                         logger.warning(f"Table {i+1} structure is invalid: {table}")

            # Ensure other keys exist even if empty, for consistency
            if "metadata" not in response_data: response_data["metadata"] = {}
            if "key_value_pairs" not in response_data: response_data["key_value_pairs"] = {}
            if "text_sections" not in response_data: response_data["text_sections"] = {}

            return response_data

        # Handle unexpected response types (e.g., if JSON parsing failed on Gemini's side or client library bug)
        else:
            logger.error(f"Unexpected response type from Gemini: {type(response_data)}. Expected dict.")
            # Try to parse if it looks like JSON string
            if isinstance(response_data, str):
                try:
                    parsed_data = json.loads(response_data)
                    logger.warning("Response was string but parsed as JSON. Using parsed data.")
                    # Re-run validation
                    if not isinstance(parsed_data.get("tables"), list): parsed_data["tables"] = []
                    if "metadata" not in parsed_data: parsed_data["metadata"] = {}
                    if "key_value_pairs" not in parsed_data: parsed_data["key_value_pairs"] = {}
                    if "text_sections" not in parsed_data: parsed_data["text_sections"] = {}
                    return parsed_data
                except json.JSONDecodeError:
                    logger.error("String response could not be parsed as JSON.")

            # Fallback: return a default structure with the raw response
            return {
                "metadata": {"error": "Unexpected response type"},
                "key_value_pairs": {"raw_response": str(response_data)},
                "text_sections": {},
                "tables": []
            }

    except Exception as e:
        logger.error(f"Gemini extraction failed for {gcs_uri}: {type(e).__name__} - {e}", exc_info=True)
        raise Exception(f"Gemini extraction failed for {gcs_uri}") from e

# --- Gemini Reconciliation Implementation ---
async def reconcile_with_gemini(extracted_json: dict, ocr_text: str) -> dict:
    """
    Uses Gemini (gemini-2.0-flash-001) via gemini_client to reconcile the initially
    extracted JSON (Source 1) against the raw OCR text (Source 2).
    """
    if not gemini: raise ImportError("GeminiClient not initialized.")
    if not types: raise ImportError("google.generativeai.types not available.")

    logger.info("Starting Gemini reconciliation...")

    extracted_json_str = None
    # Prepare input data as strings for the prompt, handle potential large inputs
    try:
        # Use standard json library instead of pandas.io.json
        extracted_json_str = json.dumps(extracted_json, indent=2) if extracted_json else "{}"
        logger.debug("Successfully serialized initial JSON for reconciliation prompt.")
    except Exception as json_e:
        logger.error(f"Failed to serialize extracted JSON for reconciliation prompt: {json_e}", exc_info=True)
        extracted_json_str = str(extracted_json) # Fallback

    # Basic truncation for extremely long OCR text to avoid request limits.
    # A better approach might involve chunking or smarter summarization if this becomes an issue.
    MAX_OCR_LEN = 300000 # Adjust based on model/API constraints and typical document size
    if len(ocr_text) > MAX_OCR_LEN:
       logger.warning(f"Truncating long OCR text ({len(ocr_text)} chars) for reconciliation prompt.")
       ocr_text_for_prompt = ocr_text[:MAX_OCR_LEN] + "\n\n... [OCR TEXT TRUNCATED]"
    else:
       ocr_text_for_prompt = ocr_text
    logger.debug(f"Using OCR text of length {len(ocr_text_for_prompt)} for reconciliation prompt.")


    # Simplified reconciliation prompt
    prompt = """transcreva o documento no formato planilha"""
    # Instead of using the complex reconciliation, we'll just return the extracted data
    # This is a workaround since the reconciliation seems to be losing the table data
    logger.debug("Using simplified reconciliation approach to preserve table data")
    
    # Just return the extracted data directly
    return extracted_json

    # Use the same basic schema as extraction, assuming reconciliation maintains structure
    final_json_schema = {
        "type": "OBJECT",
        "properties": {
            "metadata": {"type": "OBJECT"},
            "key_value_pairs": {"type": "OBJECT"},
            "text_sections": {"type": "OBJECT"},
            "tables": {"type": "ARRAY", "items": {"type": "OBJECT"}}
        }
    }

    try:
        logger.debug("Calling Gemini for reconciliation...")
        # Create generation config similar to the example script
        generation_config = types.GenerateContentConfig(
            temperature=0.2,
            top_p=0.8,
            max_output_tokens=1024,
            response_modalities=["TEXT"],
            safety_settings=[
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF")
            ]
        )
        
        # Use the async method from gemini_client with the custom generation config
        response_data, token_count = await gemini.generate_content_async(
            contents=contents,
            model="gemini-2.0-flash-001", # Use confirmed model
            generation_config=generation_config,
            return_json=True,
            json_schema=final_json_schema,
            count_tokens=True # Request token count
        )
        if token_count:
             logger.info(f"Gemini reconciliation token usage: Prompt={token_count.prompt_tokens}, Completion={token_count.completion_tokens}, Total={token_count.total_tokens}")
        else:
             logger.info("Gemini reconciliation call successful.")

        # For the reconciliation, we might get either a dictionary or text response
        logger.info("Gemini reconciliation successful.")
        
        # If we got a dictionary response, use it directly
        if isinstance(response_data, dict):
            logger.debug(f"Received dictionary response: {json.dumps(response_data, indent=2)}")
            logger.debug(f"Reconciled metadata keys: {list(response_data.get('metadata', {}).keys()) if isinstance(response_data.get('metadata'), dict) else 'None'}")
            logger.debug(f"Reconciled key-value pairs count: {len(response_data.get('key_value_pairs', {})) if isinstance(response_data.get('key_value_pairs'), dict) else 0}")
            logger.debug(f"Reconciled text sections count: {len(response_data.get('text_sections', {})) if isinstance(response_data.get('text_sections'), dict) else 0}")
            logger.debug(f"Reconciled tables count: {len(response_data.get('tables', [])) if isinstance(response_data.get('tables'), list) else 0}")
            
            # Add more detailed logging for tables
            if 'tables' in response_data and isinstance(response_data['tables'], list) and len(response_data['tables']) > 0:
                for i, table in enumerate(response_data['tables']):
                    logger.debug(f"Reconciled Table {i+1} details:")
                    if isinstance(table, dict):
                        for key, value in table.items():
                            logger.debug(f"  {key}: {value}")
                        
                        # Log rows if present
                        if 'rows' in table and isinstance(table['rows'], list):
                            logger.debug(f"  Table has {len(table['rows'])} rows")
                            if len(table['rows']) > 0:
                                logger.debug(f"  First row keys: {list(table['rows'][0].keys()) if isinstance(table['rows'][0], dict) else 'Not a dict'}")
                        else:
                            logger.debug("  Table has no rows or rows is not a list")
                    else:
                        logger.debug(f"  Table is not a dictionary: {type(table)}")
            
            # Log the input extracted_json tables for comparison
            logger.debug("Original extracted_json tables for comparison:")
            if 'tables' in extracted_json and isinstance(extracted_json['tables'], list) and len(extracted_json['tables']) > 0:
                for i, table in enumerate(extracted_json['tables']):
                    logger.debug(f"Original Table {i+1} details:")
                    if isinstance(table, dict):
                        for key, value in table.items():
                            logger.debug(f"  {key}: {value}")
                        
                        # Log rows if present
                        if 'rows' in table and isinstance(table['rows'], list):
                            logger.debug(f"  Table has {len(table['rows'])} rows")
                            if len(table['rows']) > 0:
                                logger.debug(f"  First row keys: {list(table['rows'][0].keys()) if isinstance(table['rows'][0], dict) else 'Not a dict'}")
                        else:
                            logger.debug("  Table has no rows or rows is not a list")
                    else:
                        logger.debug(f"  Table is not a dictionary: {type(table)}")
            else:
                logger.debug("  No tables in original extracted_json")
            
            return response_data
            
        # If we got a string response, convert it to our expected structure
        elif isinstance(response_data, str):
            logger.debug(f"Received text response: {response_data[:500]}...")
            
            # Create a structured format from the text response
            structured_data = {
                "metadata": {"document_type": "spreadsheet"},
                "key_value_pairs": {},
                "text_sections": {"extracted_text": response_data},
                "tables": []
            }
            
            # Try to parse the text into key-value pairs
            lines = response_data.strip().split('\n')
            for line in lines:
                if ':' in line or '\t' in line:
                    parts = line.split(':', 1) if ':' in line else line.split('\t', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        if key and value:
                            structured_data["key_value_pairs"][key] = value
            
            logger.debug(f"Converted text to structured data with {len(structured_data['key_value_pairs'])} key-value pairs")
            return structured_data
            
        # If we got something else, create a minimal structure with the string representation
        else:
            logger.warning(f"Unexpected response type: {type(response_data)}")
            return {
                "metadata": {"document_type": "unknown"},
                "key_value_pairs": {"raw_response": str(response_data)},
                "text_sections": {},
                "tables": []
            }

    except Exception as e:
        logger.error(f"Gemini reconciliation failed: {type(e).__name__} - {e}", exc_info=True)
        raise Exception("Gemini reconciliation failed") from e

# --- Excel Generation Implementation ---
def _write_excel_sheets(data: dict, output_path: str):
    """Synchronous helper function to write data dictionary to Excel sheets using pandas."""
    try:
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            sheets_written = 0
            logger.debug(f"Attempting to write Excel file: {output_path}")

            # --- Sheet 1: Metadata & Key-Value Pairs ---
            summary_data = {}
            if data and isinstance(data.get('metadata'), dict):
                summary_data.update({f"meta_{k}": v for k, v in data['metadata'].items() if k != 'raw_response'}) # Exclude potential raw response

            if data and isinstance(data.get('key_value_pairs'), dict):
                summary_data.update({k: v for k, v in data['key_value_pairs'].items() if k != 'raw_response'}) # Exclude potential raw response

            if summary_data:
                 summary_df = pd.DataFrame(list(summary_data.items()), columns=['Field', 'Value'])
                 summary_df.to_excel(writer, sheet_name='Summary', index=False)
                 logger.debug(f"Wrote Summary sheet with {len(summary_df)} rows.")
                 sheets_written += 1
            else:
                 logger.debug("No metadata or key-value pairs found to write.")

            # --- Sheet 2: Text Sections (Optional) ---
            # Only write if there are meaningful text sections
            if data and isinstance(data.get('text_sections'), dict) and data['text_sections']:
                 # Convert dict to DataFrame
                 text_df = pd.DataFrame(list(data['text_sections'].items()), columns=['Section Title', 'Text'])
                 text_df.to_excel(writer, sheet_name='Text Sections', index=False)
                 logger.debug(f"Wrote Text Sections sheet with {len(text_df)} sections.")
                 sheets_written += 1
            else:
                 logger.debug("No text sections found to write.")


            # --- Subsequent Sheets: Tables ---
            # Process tables according to the new expected format: list of lists for rows
            if data and isinstance(data.get('tables'), list):
                logger.debug(f"Found {len(data['tables'])} tables in the data.")
                for i, table_info in enumerate(data['tables']):
                    # Check structure: dict with 'headers' (list) and 'rows' (list of lists)
                    if (isinstance(table_info, dict) and
                        isinstance(table_info.get('headers'), list) and
                        isinstance(table_info.get('rows'), list) and
                        table_info['rows']): # Ensure rows is not empty

                        headers = table_info['headers']
                        rows = table_info['rows']

                        # Validate row structure (all rows should be lists, ideally matching header count)
                        valid_rows = []
                        for r_idx, row in enumerate(rows):
                            if isinstance(row, list):
                                valid_rows.append(row)
                            else:
                                logger.warning(f"Table {i+1} ('{table_info.get('table_title', 'N/A')}') row {r_idx+1} is not a list: {row}. Skipping row.")

                        if not valid_rows:
                             logger.warning(f"Table {i+1} ('{table_info.get('table_title', 'N/A')}') has no valid rows. Skipping table.")
                             continue

                        # Sanitize sheet name
                        raw_title = table_info.get('table_title', f"Table_{i+1}")
                        safe_sheet_name = "".join(c if c.isalnum() else "_" for c in str(raw_title))[:31]

                        try:
                             # Create DataFrame directly from list of lists and headers
                             table_df = pd.DataFrame(valid_rows, columns=headers)

                             # Write DataFrame to Excel
                             table_df.to_excel(writer, sheet_name=safe_sheet_name, index=False)

                             # Auto-adjust column widths
                             worksheet = writer.sheets[safe_sheet_name]
                             for idx, col in enumerate(table_df.columns):
                                 max_len = max(
                                     table_df[col].astype(str).map(len).max(),
                                     len(str(col))
                                 ) + 2
                                 worksheet.column_dimensions[worksheet.cell(row=1, column=idx+1).column_letter].width = max_len

                             logger.debug(f"Wrote sheet '{safe_sheet_name}' with {len(table_df)} rows and {len(headers)} columns.")
                             sheets_written += 1
                        except Exception as table_e:
                             logger.error(f"Could not process table '{safe_sheet_name}' into DataFrame/Sheet: {table_e}", exc_info=True)
                    else:
                         logger.warning(f"Skipping table at index {i} due to invalid structure or empty rows: {table_info}")
            else:
                logger.debug("No 'tables' list found or it's empty in the data.")


            # If no actual data sheets were written, create a dummy sheet
            if sheets_written == 0:
                 pd.DataFrame([{"Status": "No structured data extracted or processed"}]).to_excel(writer, sheet_name='Info', index=False)
                 logger.warning("No data sheets generated, writing default Info sheet.")

        logger.info(f"Successfully wrote Excel file: {output_path}")

    except Exception as e:
        # Catch errors during Excel writing process
        logger.error(f"Pandas/ExcelWriter failed for {output_path}: {type(e).__name__} - {e}", exc_info=True)
        raise Exception(f"Failed to write Excel file {output_path}") from e


async def generate_excel(data: dict, task_id: str) -> str:
    """
    Generates an Excel (.xlsx) file from the final reconciled data dictionary.
    Writes summary/metadata, text sections, and tables to separate sheets using a sync helper.
    """
    if not isinstance(data, dict):
         logger.error(f"Invalid data type for Excel generation (expected dict): {type(data)}")
         raise TypeError("Data for Excel generation must be a dictionary.")

    logger.info(f"Generating Excel report for Task ID {task_id}")
    # Define a temporary directory and path for the output file
    output_dir = "/tmp/pdf2any_results" # Consider making this configurable
    try:
        os.makedirs(output_dir, exist_ok=True)
    except OSError as oe:
         logger.error(f"Could not create output directory {output_dir}: {oe}", exc_info=True)
         raise # Re-raise if directory creation fails

    output_path = os.path.join(output_dir, f"{task_id}_report.xlsx")

    try:
        # Run the synchronous pandas operations in a thread pool executor
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _write_excel_sheets, data, output_path)

        logger.info(f"Asynchronous Excel writing initiated for {output_path}")
        # Note: errors from _write_excel_sheets will be raised here by await
        return output_path
    except Exception as e:
        logger.error(f"Failed to generate Excel file for Task {task_id}: {e}", exc_info=True)
        raise Exception(f"Excel generation failed for Task {task_id}") from e
