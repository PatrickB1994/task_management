## This is a Task Management application using:

### Python language version 3.11.6

### Flask framework which provides tools, libraries and a built-in web server to help creating web applications

### sqlalchemy ORM framework to help access and manipulate SQL databases

### psycopg2 PostgreSQL database adapter

### PS: may need to install some packages (libpq-dev, python3-dev) before installing psycopg2

### Added python-dotenv for environment variables and schedule to send reminders

#### Upon initialization, the application initiates the creation of essential tables tasks, categories, and priorities in the database, ensuring they exist. It proceeds to seed these tables with initial data if empty. After which, a dedicated thread runs a schedule, executing every minute to dispatch reminders for tasks due within the upcoming hour yet remain incomplete. Furthermore, the application launches the web server that exposes endpoints for tasks and categories, facilitating database manipulation via the SQLAlchemy libraries through GET, POST, PUT, and DELETE operations.