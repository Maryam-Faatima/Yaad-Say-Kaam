import json
import os
from datetime import datetime, timedelta

# Store tasks in the root data directory
TASKS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'tasks.json')

def load_tasks() -> list:
    """Load tasks from the JSON file."""
    if not os.path.exists(TASKS_FILE):
        return []
    try:
        with open(TASKS_FILE, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
            return prune_old_tasks(tasks)
    except json.JSONDecodeError:
        return []

def prune_old_tasks(tasks: list) -> list:
    """Removes tasks that have been completed or missed for > 7 days."""
    now = datetime.now()
    kept_tasks = []
    changed = False
    
    for t in tasks:
        status = t.get('status')
        deadline_str = t.get('deadline')
        
        should_keep = True
        if deadline_str:
            try:
                dt = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    dt = datetime.strptime(deadline_str, "%Y-%m-%d")
                except ValueError:
                    dt = now
                    
            if status == 'completed' or dt < now:
                age_days = (now - dt).days
                if age_days > 7:
                    should_keep = False
                    
        if should_keep:
            kept_tasks.append(t)
        else:
            changed = True
            
    if changed:
        # Don't call save_tasks recursively without checking to avoid infinite loop on load
        os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
        with open(TASKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(kept_tasks, f, indent=4)
            
    return kept_tasks

def save_tasks(tasks: list):
    """Save all tasks to the JSON file."""
    os.makedirs(os.path.dirname(TASKS_FILE), exist_ok=True)
    with open(TASKS_FILE, 'w', encoding='utf-8') as f:
        json.dump(tasks, f, indent=4)

def calculate_next_alarm(deadline_str: str, acknowledged_alarms: list) -> str:
    """Calculates the next alarm threshold that should trigger."""
    if not deadline_str:
        return None
        
    try:
        dt = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            dt = datetime.strptime(deadline_str, "%Y-%m-%d")
        except ValueError:
            return None

    thresholds = [
        ("24h", 24 * 3600),
        ("12h", 12 * 3600),
        ("30m", 1800),
        ("5m", 300),
        ("0m", 0)
    ]
    
    for label, seconds in thresholds:
        if label not in acknowledged_alarms:
            trigger_time = dt - timedelta(seconds=seconds)
            return trigger_time.strftime("%Y-%m-%d %H:%M:%S")
            
    return None

def add_task(task_data: dict):
    """Add a new task, or update if it already exists."""
    tasks = load_tasks()
    task_id = task_data.get('task_id')
    
    # Deduplication check based on summary and action exactly matching an active task
    summary = task_data.get('summary', '')
    action = task_data.get('action', '')
    for t in tasks:
        if t.get('status') != 'completed':
            if t.get('summary') == summary and t.get('action') == action:
                print(f"Duplicate task detected, skipping: {action}")
                return

    task_data['acknowledged_alarms'] = task_data.get('acknowledged_alarms', [])
    task_data['next_alarm_time'] = calculate_next_alarm(task_data.get('deadline'), task_data['acknowledged_alarms'])
    
    replaced = False
    if task_id:
        for i, t in enumerate(tasks):
            if t.get('task_id') == task_id:
                tasks[i] = task_data
                replaced = True
                break
                
    if not replaced:
        tasks.append(task_data)
        
    save_tasks(tasks)

def update_task_status(task_id: str, new_status: str):
    tasks = load_tasks()
    for i, t in enumerate(tasks):
        if t.get('task_id') == task_id:
            tasks[i]['status'] = new_status
            break
    save_tasks(tasks)

def snooze_task(task_id: str, minutes: int = 15):
    tasks = load_tasks()
    for i, t in enumerate(tasks):
        if t.get('task_id') == task_id:
            cur_alarm = t.get('next_alarm_time')
            if cur_alarm:
                try:
                    dt = datetime.strptime(cur_alarm, "%Y-%m-%d %H:%M:%S")
                    new_dt = dt + timedelta(minutes=minutes)
                    tasks[i]['next_alarm_time'] = new_dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass
            break
    save_tasks(tasks)

def acknowledge_alarm(task_id: str):
    tasks = load_tasks()
    for i, t in enumerate(tasks):
        if t.get('task_id') == task_id:
            deadline_str = t.get('deadline')
            if deadline_str:
                try:
                    dt = datetime.strptime(deadline_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    try:
                        dt = datetime.strptime(deadline_str, "%Y-%m-%d")
                    except ValueError:
                        break
                        
                now = datetime.now()
                time_left = (dt - now).total_seconds()
                
                thresholds = [
                    ("24h", 24 * 3600),
                    ("12h", 12 * 3600),
                    ("30m", 1800),
                    ("5m", 300),
                    ("0m", 0)
                ]
                
                ack_list = t.get('acknowledged_alarms', [])
                
                # Acknowledge ALL thresholds that have already passed
                for label, seconds in thresholds:
                    if time_left <= seconds:
                        if label not in ack_list:
                            ack_list.append(label)
                        
                t['acknowledged_alarms'] = ack_list
                t['next_alarm_time'] = calculate_next_alarm(deadline_str, ack_list)
            break
    save_tasks(tasks)
