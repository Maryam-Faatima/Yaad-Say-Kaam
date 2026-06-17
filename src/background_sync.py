import threading
import time
from datetime import datetime
from gmail_fetcher import fetch_unread_emails, mark_as_read
from main import run_pipeline
from task_store import add_task

def background_sync_loop(interval_seconds=60):
    """
    Infinite loop that runs in a background thread.
    Fetches unread emails, runs them through the pipeline, stores tasks, and marks emails as read.
    """
    print(f"Background sync thread started. Checking emails every {interval_seconds} seconds.")
    while True:
        try:
            emails = fetch_unread_emails()
            for email in emails:
                print(f"Background Sync processing email: {email.get('subject')}")
                raw_message = f"Subject: {email.get('subject')}\nBody: {email.get('body')}"
                created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Run the agent pipeline
                results = run_pipeline(raw_message, status="pending", created_at=created_at)
                final_task = results["forgetting_result"]
                
                # Save task
                add_task(final_task)
                
                # Mark as read
                mark_as_read(email['id'])
                
        except Exception as e:
            print(f"Background sync encountered an error: {e}")
            
        time.sleep(interval_seconds)

def start_background_sync(interval_seconds=60):
    """Starts the background sync loop in a separate daemon thread."""
    thread = threading.Thread(target=background_sync_loop, args=(interval_seconds,), daemon=True)
    thread.start()
    return thread
