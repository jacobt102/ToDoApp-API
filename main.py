import os
import mysql.connector
import uvicorn
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from pydantic import BaseModel, Field
import requests

#Load .env file
if not load_dotenv():
    print("No env variables found. Specify a environment variable in a .env file")
    raise RuntimeError("No env variables were found")

# Gather environment variables for database connection
host= os.getenv("host")
user=os.getenv("user")
password= os.getenv("password")
database= os.getenv("database")

#Ensure all environment variables are present
if host is None or user is None or password is None or database is None:
    raise HTTPException(status_code=500, detail="Missing environment variable")

def db_connection():
   try:
       conn = mysql.connector.connect(
        host=host,
        user=user,
        password=password,
        database=database)
   except Exception as e:
       print(e)
       raise HTTPException(status_code=500, detail="Database connection error: {e}")
   return conn

connection=db_connection()

app = FastAPI()

#Pydantic task models
class Task(BaseModel):
    name: str = Field(...,min_length=1,max_length=100,description="Name of task between 1 and 100 chars")
    status: bool = False

class TaskResponse(Task):
    id: int


@app.post("/addtask", response_model=TaskResponse)
def create_task(task: Task) -> TaskResponse | None:
    """
    Adds a new task to the database.

    Args:
    - task (Task): The task object containing the task name and status.

    Returns:
    - TaskResponse: The created task with its id, name, and status.

    Raises:
    - HTTPException: If the task name already exists, or if there is a database connection, query, or constraint violation error.
    """
    try:
        cursor = connection.cursor()

        #Check if task name exists
        cursor.execute(f"SELECT id from tasks where task_name=%s", (task.name,))
        exist = cursor.fetchone()
        if exist:
            raise HTTPException(status_code=400,detail="Task name already exists")

        #Inserting into DB
        values=(task.name, task.status)
        query="INSERT INTO tasks (task_name, status) VALUES (%s, %s)"
        cursor.execute(query, values)
        connection.commit()
        task_id=cursor.lastrowid
    #Possible database errors
    except mysql.connector.errors.InterfaceError as e:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Database connection error: {e}")
    except mysql.connector.errors.ProgrammingError as e:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Database query error: {e}")
    except mysql.connector.errors.IntegrityError as e:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Database constraint violation: {e}")
    finally:
        cursor.close()
    #Returns inserted object back with id, name and status
    return TaskResponse(id=task_id, name=task.name, status=task.status)


@app.get("/tasks", response_model=list[TaskResponse])
def get_all_tasks(name: str = None, status:bool = None) -> list[TaskResponse] | None:
    """
    Get all tasks from the database. Can be filtered by name and status

    Args:
    - name (str): optional, filter by task name
    - status (bool): optional, filter by task status

    Returns:
    - list[TaskResponse]: list of tasks with id,name and status
    """
    try:
        cursor=connection.cursor()
        #query includes  name and status
        if name is not None and status is not None:
            query = "SELECT * from tasks where task_name = %s and status = %s"
            values = (name,status)
            cursor.execute(query,values)
        elif name is not None and status is None:
            query = "SELECT * from tasks where task_name = %s"
            values = (name,)
            cursor.execute(query,values)
        elif name is None and status is not None:
            query = "SELECT * from tasks where status = %s"
            values = (status,)
            cursor.execute(query,values)
        elif name is None and status is None:
            query = "SELECT * from tasks"
            cursor.execute(query)

    except mysql.connector.errors.InterfaceError as e:
            raise HTTPException(status_code=500, detail=f"Database connection error: {e}")
    except mysql.connector.errors.ProgrammingError as e:
        raise HTTPException(status_code=500, detail=f"Database query error: {e}")
    except mysql.connector.errors.IntegrityError as e:
        raise HTTPException(status_code=500, detail=f"Database constraint violation: {e}")
    else:
        results = cursor.fetchall()

    finally:
        cursor.close()

    if results is None:
        return None
    return [TaskResponse(id=row[0],name=row[1],status=row[2]) for row in results]

@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int) -> TaskResponse:
    """
    Get a specific task by ID from the database.

    Args:
    - task_id (int): The id of the task to retrieve

    Returns:
    - TaskResponse: The task object with id, name and status

    Raises:
    - HTTPException: If task ID not found, or if there is a database connection, query, or constraint violation error.
    """
    try:
        cursor = connection.cursor()
        value = (task_id,)
        cursor.execute("SELECT * from tasks where id = %s",value)
        results = cursor.fetchone()
        if not results:
            raise HTTPException(status_code=404,detail=f"Specific Task ID {task_id} not found")
        return TaskResponse(id=results[0],name=results[1],status=results[2])
    except mysql.connector.errors.InterfaceError as e:
        raise HTTPException(status_code=500, detail=f"Database connection error: {e}")
    except mysql.connector.errors.ProgrammingError as e:
        raise HTTPException(status_code=500, detail=f"Database query error: {e}")
    except mysql.connector.errors.IntegrityError as e:
        raise HTTPException(status_code=500, detail=f"Database constraint violation: {e}")

@app.get("/tasks", response_model=list[TaskResponse])
def get_tasks(search: str = None) -> list[TaskResponse]:
    """
    Get all tasks from the database, or search by a specific task name.

    Args:
    - search (str): optional, filter by task name

    Returns:
    - list[TaskResponse]: list of tasks with id, name and status

    Raises:
    - HTTPException: If there is a database connection, query, or constraint violation error.
    """
    try:
        cursor = connection.cursor()

        if search is not None:
            query = "SELECT * from tasks where task_name = %s"
            values = (search,)
            cursor.execute(query,values)
        else:
            query = "SELECT * from tasks"
            cursor.execute(query)
        results = cursor.fetchall()
    except mysql.connector.errors.InterfaceError as e:
        raise HTTPException(status_code=500, detail=f"Database connection error: {e}")
    except mysql.connector.errors.ProgrammingError as e:
        raise HTTPException(status_code=500, detail=f"Database query error: {e}")
    except mysql.connector.errors.IntegrityError as e:
        raise HTTPException(status_code=500, detail=f"Database constraint violation: {e}")
    finally:
        cursor.close()
    return [TaskResponse(id=row[0],name=row[1],status=row[2]) for row in results]

@app.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, task: Task) -> TaskResponse:
    """
    Update a specific task by ID in the database.

    Args:
    - task_id (int): The id of the task to update
    - task (Task): The task object containing the task name and status

    Returns:
    - TaskResponse: The updated task with id, name and status

    Raises:
    - HTTPException: If task ID not found, or if there is a database connection, query, or constraint violation error.
    """
    try:
        cursor = connection.cursor()

        #Check if task ID exists
        cursor.execute(f"SELECT id from tasks where id=%s", (task_id,))
        exist = cursor.fetchone()
        if not exist:
            raise HTTPException(status_code=404,detail=f"Specific Task ID {task_id} not found")

        if task.name is not None and task.status is not None:
            value = (task.name, task.status, task_id)
            query = "UPDATE tasks SET task_name = %s, status = %s WHERE id = %s"
        elif task.name is not None and task.status is None:
            value = (task.name, task_id)
            query = "UPDATE tasks SET task_name = %s WHERE id = %s"
        elif task.name is None and task.status is not None:
            value = (task.status, task_id)
            query = "UPDATE tasks SET status = %s WHERE id = %s"
        elif task.name is None and task.status is None:
            raise HTTPException(status_code=400,detail="No task name or status provided. Must provide name or status to update task")
        cursor.execute(query,value)
        connection.commit()
    #database error catching
    except mysql.connector.errors.InterfaceError as e:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Database connection error: {e}")
    except mysql.connector.errors.ProgrammingError as e:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Database query error: {e}")
    except mysql.connector.errors.IntegrityError as e:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Database constraint violation: {e}")
    finally:
        cursor.close()
    return TaskResponse(id=task_id,name=task.name,status=task.status)

@app.delete("/tasks/{task_id}", response_model=TaskResponse)
def delete_task(task_id: int,status: bool = True) -> TaskResponse | None:
    """
    Delete a specific task by ID from the database.

    Args:
    - task_id (int): The id of the task to delete

    Returns:
    - TaskResponse: The deleted task with id, name and status

    Raises:
    - HTTPException: If task ID not found, or if there is a database connection, query, or constraint violation error.
    """
    try:
        cursor = connection.cursor()

        #Check if task ID exists
        cursor.execute(f"SELECT id from tasks where id=%s", (task_id,))
        exist = cursor.fetchone()
        if not exist:
            raise HTTPException(status_code=404,detail=f"Specific Task ID {task_id} not found")

        #Get task data to return:
        cursor.execute(f"SELECT * from tasks where id=%s", (task_id,))
        results = cursor.fetchone()
        if results:
            name = results[1]
            status = results[2]




        #Delete task
        cursor.execute(f"DELETE from tasks where id=%s", (task_id,))
        connection.commit()
    #database error catching
    except mysql.connector.errors.InterfaceError as e:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Database connection error: {e}")
    except mysql.connector.errors.ProgrammingError as e:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Database query error: {e}")
    except mysql.connector.errors.IntegrityError as e:
        connection.rollback()
        raise HTTPException(status_code=500, detail=f"Database constraint violation: {e}")
    finally:
        cursor.close()
    return TaskResponse(id=task_id,name=name, status=status)

if __name__ == '__main__':
    uvicorn.run(app, host="127.0.0.1", port=8001)


