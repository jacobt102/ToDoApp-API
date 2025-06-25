from taipy.gui import Gui, Markdown, State, notify
import taipy.gui.builder as tgb
import requests
import pandas as pd
from typing import Optional

# Configuration
API_BASE_URL = "http://127.0.0.1:8001"

# Initial state variables
task_name = ""
task_status = False
filter_name = ""
filter_status = None
show_completed = True
show_pending = True

# Empty DataFrame with proper structure
tasks = pd.DataFrame(columns=["ID", "Task Name", "Status"])


def get_tasks(state: Optional[State] = None, name_filter: str = "",
              status_filter: Optional[bool] = None) -> pd.DataFrame:
    """
    Retrieves tasks from the API with optional filtering.

    Args:
        state: GUI state (optional)
        name_filter: Filter by task name
        status_filter: Filter by status (True/False/None)

    Returns:
        DataFrame with tasks
    """
    try:
        params = {}
        if name_filter:
            params["name"] = f"%{name_filter}%"
        if status_filter is not None:
            params["status"] = status_filter

        response = requests.get(f"{API_BASE_URL}/tasks", params=params, timeout=5)
        response.raise_for_status()

        data = response.json()
        if not data:
            return pd.DataFrame(columns=["ID", "Task Name", "Status"])

        df = pd.DataFrame(data)
        df.rename(columns={"id": "ID", "name": "Task Name", "status": "Status"}, inplace=True)

        # Convert status to readable format
        df["Status"] = df["Status"].map({True: "✅ Completed", False: "⏳ Pending"})

        return df

    except requests.exceptions.RequestException as e:
        print(f"Error fetching tasks: {e}")
        if state:
            notify(state, "error", "Failed to fetch tasks from server")
        return pd.DataFrame(columns=["ID", "Task Name", "Status"])


def add_task(state: State, id: str, payload: dict) -> None:
    """Add a new task to the system."""
    if not state.task_name.strip():
        notify(state, "warning", "Task name cannot be empty")
        return

    try:
        response = requests.post(
            f"{API_BASE_URL}/addtask",
            json={"name": state.task_name.strip(), "status": bool(state.task_status)},
            timeout=5
        )

        if response.status_code == 200:
            state.task_name = ""  # Clear input
            state.task_status = False  # Reset status
            refresh_tasks(state)
            notify(state, "success", f"Task '{response.json()['name']}' added successfully")
        else:
            error_msg = response.json().get("detail", "Unknown error")
            notify(state, "error", f"Failed to add task: {error_msg}")

    except requests.exceptions.RequestException as e:
        print(f"Error adding task: {e}")
        notify(state, "error", "Failed to connect to server")


def update_task(state: State, var_name: str, payload: dict) -> None:
    """Update an existing task."""
    try:
        new_value = payload["value"]
        task_id = state.tasks.iloc[payload["index"]]["ID"]
        col_name = payload["col"]

        # Map column names to API fields
        api_field = {
            "Task Name": "name",
            "Status": "status"
        }.get(col_name)

        if not api_field:
            notify(state, "error", "Invalid column for update")
            return

        # Handle status conversion
        if api_field == "status":
            new_value = new_value == "✅ Completed"
        elif api_field == "name" and not (1 <= len(new_value.strip()) <= 100):
            notify(state, "error", "Task name must be between 1 and 100 characters")
            return

        response = requests.patch(
            f"{API_BASE_URL}/tasks/{task_id}",
            json={api_field: new_value},
            timeout=5
        )

        if response.status_code == 200:
            refresh_tasks(state)
            notify(state, "success", "Task updated successfully")
        else:
            error_msg = response.json().get("detail", "Unknown error")
            notify(state, "error", f"Failed to update task: {error_msg}")

    except (KeyError, IndexError, ValueError) as e:
        print(f"Error updating task: {e}")
        notify(state, "error", "Invalid update operation")
    except requests.exceptions.RequestException as e:
        print(f"Error updating task: {e}")
        notify(state, "error", "Failed to connect to server")


def delete_task(state: State, var_name: str, payload: dict) -> None:
    """Delete a task from the system."""
    try:
        task_id = state.tasks.iloc[payload["index"]]["ID"]
        task_name = state.tasks.iloc[payload["index"]]["Task Name"]

        response = requests.delete(f"{API_BASE_URL}/tasks/{task_id}", timeout=5)

        if response.status_code == 200:
            refresh_tasks(state)
            notify(state, "success", f"Task '{task_name}' deleted successfully")
        else:
            error_msg = response.json().get("detail", "Unknown error")
            notify(state, "error", f"Failed to delete task: {error_msg}")

    except (KeyError, IndexError) as e:
        print(f"Error deleting task: {e}")
        notify(state, "error", "Invalid delete operation")
    except requests.exceptions.RequestException as e:
        print(f"Error deleting task: {e}")
        notify(state, "error", "Failed to connect to server")


def refresh_tasks(state: State) -> None:
    """Refresh the task list with current filters."""
    name_filter = getattr(state, 'filter_name', "")
    status_filter = None

    # Apply status filter based on checkboxes
    if hasattr(state, 'show_completed') and hasattr(state, 'show_pending'):
        if state.show_completed and not state.show_pending:
            status_filter = True
        elif state.show_pending and not state.show_completed:
            status_filter = False

    state.tasks = get_tasks(state, name_filter, status_filter)


def on_filter_change(state: State, var_name: str, value) -> None:
    """Handle filter changes."""
    refresh_tasks(state)


def clear_filters(state: State, id: str, payload: dict) -> None:
    """Clear all filters and refresh."""
    state.filter_name = ""
    state.show_completed = True
    state.show_pending = True
    refresh_tasks(state)


def on_task_name_change(state: State, var_name: str, value) -> None:
    """Handle task name input changes."""
    state.task_name = value


# Initialize tasks on startup
tasks = get_tasks()

# Define custom CSS for better styling


# Build the page
with tgb.Page() as page:
    # Header
    with tgb.part(class_name="task-header"):
        tgb.text("# Task Management System", mode="md")
        header="""
*Organize your tasks efficiently!*  
This task management system allows you to:

- Add new tasks to your list
- Update existing tasks
- Delete tasks
- Filter tasks by name and status

##How to Use
1. Enter a task name in the input field and its status and click the "Add Task" button
2. Use the table to edit task details
3. Use the filter options to view specific task status or names
         
        """
        tgb.text("{header}", mode="md")
    # Statistics row
    tgb.text("### Task Statistics", mode="md")
    with tgb.layout("1fr 1fr 1fr", gap="2rem"):

        with tgb.part(class_name="stats-card"):
            tgb.text("**Total Tasks**", mode="md")
            tgb.text("{len(tasks)}")
        with tgb.part(class_name="stats-card"):
            tgb.text("**Completed**", mode="md")
            tgb.text("{len(tasks[tasks['Status'].str.contains('Completed', na=False)])}")
        with tgb.part(class_name="stats-card"):
            tgb.text("**Pending**", mode="md")
            tgb.text("{len(tasks[tasks['Status'].str.contains('Pending', na=False)])}")


    # Add task section
    with tgb.part(class_name="add-task-section"):
        tgb.text("### Add New Task", mode="md")
        with tgb.layout("2fr 1fr auto", gap="1rem"):
            tgb.input(
                "{task_name}",
                label="Task Name",
                placeholder="Enter your task here...",
                on_change=on_task_name_change
            )
            tgb.toggle(
                "{task_status}",
                label="Mark as Completed",
                hover_text="Check if task is already completed"
            )
            tgb.button(
                "Add Task",
                on_action=add_task,
                hover_text="Click to add the task"
            )

    # Filter section
    with tgb.part(class_name="filter-section"):
        tgb.text("###  Filters", mode="md")
        with tgb.layout("2fr 1fr 1fr auto", gap="1rem"):
            tgb.input(
                "{filter_name}",
                label="Filter by Name",
                placeholder="Search tasks...",
                on_change=on_filter_change
            )
            tgb.toggle(
                "{show_completed}",
                label="Show Completed",
                on_change=on_filter_change,
                hover_text="Show or hide completed tasks"
            )
            tgb.toggle(
                "{show_pending}",
                label="Show Pending",
                on_change=on_filter_change,
                hover_text="Show or hide pending tasks"
            )
            tgb.button(
                "Clear Filters",
                on_action=clear_filters,
                hover_text="Reset all filters"
            )

    # Tasks table
    tgb.text("### Your Tasks", mode="md")
    tgb.table(
        "{tasks}",
        columns=["Task Name", "Status"],
        editable=True,
        editable__ID=False,
        on_edit=update_task,
        on_delete=delete_task,
        hover_text="Click to edit tasks inline, or use delete button to remove",
        class_name="task-table",
        page_size=10
    )

# Run the application
if __name__ == "__main__":
    gui = Gui(page,css_file="styles.css")
    gui.run(
        title="Task Management System",
        port=5000,
        host="127.0.0.1",
        use_reloader=True,
        watermark="Task Management System by Jacob Turner"
    )