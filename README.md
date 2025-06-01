# Task Management API

A robust RESTful Task Management API built with **FastAPI**, **MySQL**, and **Pydantic**, designed for efficient task tracking and CRUD operations. This simple project emphasizes clean software design, API reliability, and secure environment handling.

## Features

- Create, retrieve, update, and delete tasks
- Filter tasks by name and completion status
- Built-in input validation and detailed error handling
- Secure `.env` loading for credentials and sensitive configs
- Modular database connection with transaction safety
- RESTful architecture with full OpenAPI docs via FastAPI

## Tech Stack

- **Python 3.10+**
- **FastAPI** for high-performance web API
- **MySQL** for relational task storage
- **Pydantic** for request validation and serialization
- **Uvicorn** as the ASGI server
- **dotenv** for managing environment variables

## Endpoints

| Method | Endpoint            | Description                            |
|--------|---------------------|----------------------------------------|
| POST   | `/addtask`          | Add a new task                         |
| GET    | `/tasks`            | Retrieve all tasks (with filters)      |
| GET    | `/tasks/{id}`       | Retrieve a task by ID                  |
| PATCH  | `/tasks/{id}`       | Update task name/status                |
| DELETE | `/tasks/{id}`       | Delete a task by ID                    |

## Setup Instructions

1. Clone the repository
2. Create a `.env` file in the project root with the following:
   ```dotenv
   host=your_mysql_host
   user=your_mysql_user
   password=your_mysql_password
   database=your_mysql_database
Install dependencies:

```bash
pip install -r requirements.txt
```
Run the application:

```bash
uvicorn main:app --reload
```
Example MySQL Schema
```sql
CREATE TABLE tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_name VARCHAR(100) NOT NULL UNIQUE,
    status BOOLEAN DEFAULT FALSE
);
```
