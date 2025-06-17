from taipy.gui import Gui, Markdown, State
import taipy.gui.builder as tgb
import requests
import pandas as pd
import time
import threading


task_name = ""
task_status = False

#Empty Dataframe
tasks=pd.DataFrame(columns=["ID","Task Name","Status"])

def add_task(state: State,id: str,payload: dict):
    """
    Adds a new task to the task API.

    Args:
    :param state: Used for GUI
    :param id: Unused
    :param payload: Carries data about event that caused the action
    :return: JSON response
    """
    try:


        response = requests.post("http://127.0.0.1:8001/addtask", json={"name": state.task_name, "status": bool(state.task_status)})
        if response.status_code==200:
            state.tasks=get_tasks()

        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error adding task: {e}\n{e.response.text}\n{state.task_name} and {state.task_status} and {type(state.task_status)}")
        return None

def change_task_name(state: State, var_name: str, value):
    state.task_name = value



def get_tasks(state: State=None):
    """
    Retrieves all tasks from the task API.

    Args:
        state (State): Unused, but present for compatibility with the GUI event handler.

    Returns:
        pd.DataFrame: A DataFrame containing the tasks with their 'id', 'name', and 'status'.
    """
    response = requests.get("http://127.0.0.1:8001/tasks")
    ret_frame = pd.DataFrame(response.json())
    ret_frame.rename(columns={"id": "ID", "name": "Task Name", "status": "Status"},inplace=True)
    return ret_frame if response.json() else pd.DataFrame(columns=["ID","Name","Status"])

def delete_task(state: State,var_name: str,payload):
    """
    Deletes a task specified by a given index in the payload.

    Args:
        state (State): The state of the GUI.
        var_name (str): The name of the variable to bind the result to.
        payload (dict): The payload of the event, must contain a key "index".

    Returns:
        The response of the API call as JSON.
    """
    print(payload["index"])

    task_id = payload["index"]
    del_id = state.tasks.iloc[task_id]["ID"]
    response = requests.delete(f"http://127.0.0.1:8001/tasks/{del_id}")
    response.raise_for_status()
    if response.status_code==200:
        state.tasks=get_tasks()

    print(payload["index"])
    return response.json()



def update_task(state:State,var_name: str,payload: dict):
    try:
        new_value = payload["value"]
        #Get database ID to update
        update_id = state.tasks.iloc[payload["index"]]["ID"]
        col_name = payload["col"]
        if col_name == "Task Name":
            if not 1<=len(new_value)<=100:
                raise ValueError("Task name must be between 1 and 100 characters")
            col_name = "name"
        elif col_name == "Status":
            col_name = "status"

        #Updating table
        response = requests.patch(f"http://127.0.0.1:8001/tasks/{update_id}",json={col_name: new_value})
        response.raise_for_status()
        if response.status_code==200:
            state.tasks=get_tasks()
    except ValueError as e:
        print(f"Validation Error: {e}")


    return response.json()



tasks=get_tasks()
#Debug
print(f"Tasks: {tasks}")

#Page Content
with tgb.Page() as page:
    tgb.text("## Task Management App",mode="md")
    with tgb.layout("1fr 1fr auto",gap="1rem"):
        tgb.input("{task_name}",label="Task Name",hover_text="Enter task name here...",width="100%",on_change=change_task_name)
        tgb.toggle("{task_status}",label="Completed?",hover_text="Select if task is completed",allow_unselect=True)
        tgb.button("Add Task",on_action=add_task, class_name="my-style")

    tgb.table("{tasks}",on_delete=delete_task, on_add=add_task,editable=True,columns=["Task Name","Status"],editable__ID=False,on_edit=update_task,use_checkbox=True)



style = """

.fullwidth{
    width: 100%;
}
"""

Gui(page).run(title="Task Management", use_reloader=True, watermark="Made by Jacob Turner")