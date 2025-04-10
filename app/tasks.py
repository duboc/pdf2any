# Module to manage task status, preventing circular imports.
import datetime

# In a real app, this would be a database or a more robust in-memory store like Redis.
# For simplicity, we use a basic dictionary here.
task_status = {}

def update_task_status(task_id: str, status: str, filename: str = None, result_file: str = None, error: str = None, gcs_uri: str = None):
    """ Safely update task status dictionary. """
    if task_id not in task_status:
        task_status[task_id] = {}

    task_status[task_id]['status'] = status
    if filename:
        task_status[task_id]['filename'] = filename
    if result_file:
        task_status[task_id]['result_file'] = result_file
    if gcs_uri:
        task_status[task_id]['gcs_uri'] = gcs_uri
    if error:
         task_status[task_id]['error'] = error
         # Add error to logs
         add_task_log(task_id, f"ERROR: {error}")
    else:
        # Clear previous error if status is not 'failed'
        if status != 'failed' and 'error' in task_status[task_id]:
             del task_status[task_id]['error']
    
    # Log status change
    add_task_log(task_id, f"Status changed to: {status}")


def get_task_status(task_id: str) -> dict | None:
    """ Get the status of a specific task. """
    return task_status.get(task_id)

def init_task(task_id: str, filename: str):
    """ Initialize a new task entry. """
    task_status[task_id] = {
        "status": "received", 
        "filename": filename, 
        "result_file": None,
        "logs": []  # Initialize logs array
    }
    add_task_log(task_id, f"Task initialized with file: {filename}")

def add_task_log(task_id: str, message: str):
    """ Add a log entry to the task. """
    if task_id not in task_status:
        return
    
    # Ensure logs array exists
    if 'logs' not in task_status[task_id]:
        task_status[task_id]['logs'] = []
    
    # Add timestamp and message
    timestamp = datetime.datetime.now().isoformat()
    task_status[task_id]['logs'].append({
        "timestamp": timestamp,
        "message": message
    })
