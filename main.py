import os
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import uvicorn
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
from fastapi.middleware.cors import CORSMiddleware
from contextlib import contextmanager, asynccontextmanager

# Load .env file
load_dotenv()

# Gather environment variables for database connection
ex_url = os.getenv("ex_url")
host = os.getenv("host")
user = os.getenv("user")
password = os.getenv("pw")
database = os.getenv("new_db")
port = int(os.getenv("port", "5432"))

if not all([ex_url, host, user, password, database, port]):
    raise ValueError("Missing environment variables")

db_params = {
        "host": ex_url,
        "user": user,
        "password": password,
        "dbname": database,
        "port": port
    }


@contextmanager
def get_db_connection():
    """
    Context manager for database connections with proper cleanup.
    """
    conn = None
    try:

        # Using individual parameters
        conn = psycopg2.connect(**db_params, cursor_factory=RealDictCursor,sslmode='require')
        yield conn
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database connection error: {e}")
    finally:
        if conn:
            conn.close()


def init_database(app1: FastAPI):
    """
    Initialize the database with the tasks table if it doesn't exist.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Create tasks table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tasks (
                        id SERIAL PRIMARY KEY,
                        task_name VARCHAR(100) NOT NULL UNIQUE,
                        status BOOLEAN DEFAULT FALSE
                    )
                """)

                conn.commit()
                print("Database initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

async def lifespan(app: FastAPI):
    init_database(app)
    yield


app = FastAPI(
    title="Task Management API",
    description="A simple task management API with PostgreSQL backend",
    version="1.0.0",lifespan=lifespan
)



# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class Task(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Name of task between 1 and 100 chars")
    status: bool = False


class TaskResponse(Task):
    id: int


class UpdateTask(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Name of task between 1 and 100 chars")
    status: Optional[bool] = None


@asynccontextmanager
async def startup_event(app: FastAPI):
    """Initialize database on startup."""
    init_database()


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "Task Management API is running", "status": "healthy"}


@app.get("/health")
async def health_check():
    """Detailed health check."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database health check failed: {e}")


@app.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(task: Task) -> TaskResponse:
    """
    Adds a new task to the database. Task name must be unique.
    :return name, id and status of new task
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Check if task name exists
                cursor.execute("SELECT id FROM tasks WHERE task_name = %s", (task.name,))
                if cursor.fetchone():
                    raise HTTPException(status_code=400, detail="Task name already exists. Enter a task name that doesn't exist.")

                # Insert new task
                cursor.execute(
                    "INSERT INTO tasks (task_name, status) VALUES (%s, %s) RETURNING id",
                    (task.name, task.status)
                )
                task_id = cursor.fetchone()['id']
                conn.commit()

                return TaskResponse(id=task_id, name=task.name, status=task.status)

    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@app.get("/tasks", response_model=list[TaskResponse])
def get_all_tasks(name: str = None, status: bool = None) -> list[TaskResponse]:
    """
    Get all tasks from the database with optional filtering.
    Returns:
          A list of TaskResponse objects

    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Build query based on filters
                query = "SELECT id, task_name, status FROM tasks WHERE 1=1"
                params = []

                if name is not None:
                    query += " AND task_name ILIKE %s"
                    params.append(f"%{name}%")

                if status is not None:
                    query += " AND status = %s"
                    params.append(status)

                # Have most recent tasks first
                query += " ORDER BY id DESC"

                cursor.execute(query, params)
                results = cursor.fetchall()

                return [
                    TaskResponse(id=row['id'], name=row['task_name'], status=row['status'])
                    for row in results
                ]

    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@app.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int) -> TaskResponse:
    """
    Get a specific task by ID.
    Returns:
        The specified task details (id,name, status)
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, task_name, status FROM tasks WHERE id = %s", (task_id,))
                result = cursor.fetchone()

                if not result:
                    raise HTTPException(status_code=404, detail=f"Task ID {task_id} not found")

                return TaskResponse(id=result['id'], name=result['task_name'], status=result['status'])

    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@app.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, task: UpdateTask) -> TaskResponse:
    """
    Update a specific task by ID.
    Returns:
        An updated TaskResponse object
    """
    if task.name is None and task.status is None:
        raise HTTPException(status_code=400, detail="Must provide name or status to update")

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Check if task exists
                cursor.execute("SELECT id FROM tasks WHERE id = %s", (task_id,))
                if not cursor.fetchone():
                    raise HTTPException(status_code=404, detail=f"Task ID {task_id} not found")

                # Build update query
                updates = []
                params = []

                if task.name is not None:
                    updates.append("task_name = %s")
                    params.append(task.name)

                if task.status is not None:
                    updates.append("status = %s")
                    params.append(task.status)

                params.append(task_id)

                query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = %s RETURNING id, task_name, status"
                cursor.execute(query, params)

                result = cursor.fetchone()
                conn.commit()

                return TaskResponse(id=result['id'], name=result['task_name'], status=result['status'])

    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@app.delete("/tasks/{task_id}", response_model=TaskResponse)
def delete_task(task_id: int) -> TaskResponse:
    """
    Delete a specific task by ID. Returns the deleted task.
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                # Get task data before deletion
                cursor.execute("SELECT id, task_name, status FROM tasks WHERE id = %s", (task_id,))
                result = cursor.fetchone()

                if not result:
                    raise HTTPException(status_code=404, detail=f"Task ID {task_id} not found")

                # Delete the task
                cursor.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
                conn.commit()

                return TaskResponse(id=result['id'], name=result['task_name'], status=result['status'])

    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
