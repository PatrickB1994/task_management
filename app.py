import os
import threading
import time
from datetime import datetime, UTC, timedelta

import schedule
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, desc
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import sessionmaker, declarative_base, joinedload, relationship

# Get environment variables
load_dotenv()

# Init app
app = Flask(__name__)
db_url = os.getenv("DATABASE_URL")
engine = create_engine(db_url)

# Create a Base class
Base = declarative_base()


# Create tasks table
class Tasks(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True)
    title = Column(String(50))
    description = Column(String(100))
    priority_id = Column(Integer, ForeignKey('priorities.id'))
    due_date = Column(DateTime)
    category_id = Column(Integer, ForeignKey('categories.id'))
    completed = Column(Boolean)

    category = relationship("Categories", backref="tasks")
    priority = relationship("Priorities", backref="tasks")


# Create categories table
class Categories(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True)
    name = Column(String(50))


# Create priorities table
class Priorities(Base):
    __tablename__ = 'priorities'
    id = Column(Integer, primary_key=True)
    name = Column(String(50))


# Create tables in the database
Base.metadata.create_all(engine)

# Create session
Session = sessionmaker(bind=engine)


# Add seed data to the database
def seed_data():
    session = Session()
    existing_categories = session.query(Categories).all()
    if not existing_categories:
        categories = [
            Categories(name='Work'),
            Categories(name='Personal')
        ]
        session.add_all(categories)
        session.commit()
        session.close()
    existing_categories = session.query(Priorities).all()
    if not existing_categories:
        priorities = [
            Priorities(name='Normal'),
            Priorities(name='Important'),
            Priorities(name='Very Important')
        ]
        session.add_all(priorities)
        session.commit()
        session.close()


# Schedule the job to send reminder when task is not done and due in an hour
def job():
    print("Scheduled task started")
    late_due_date = datetime.now(UTC) + timedelta(hours=1)
    session = Session()
    late_tasks = session.query(Tasks).filter_by(completed=False).filter(Tasks.due_date <= late_due_date).options(
        joinedload(Tasks.category)).options(
        joinedload(Tasks.priority)).order_by(
        desc(Tasks.due_date), desc(Tasks.priority_id)).all()
    for task in late_tasks:  # we can send an email or notification here...
        print("Send reminder for late task id: " + str(task.id) + " title: " + task.title)


# Schedule the job to run every minute
schedule.every().minute.do(job)


# Run the scheduler
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)


# Run the scheduler in a separate thread
scheduler_thread = threading.Thread(target=run_scheduler)
scheduler_thread.start()


# CRUD operations

# Get all tasks
@app.route('/tasks')
def get_tasks():
    try:
        session = Session()
        # Use joinedload to load the category object for each task
        tasks = session.query(Tasks).options(joinedload(Tasks.category)).options(joinedload(Tasks.priority)).order_by(
            desc(Tasks.priority_id)).all()
        session.close()
        task_list = []
        for task in tasks:
            # Get the category object associated with the task
            category_name = task.category.name if task.category else None
            priority_name = task.priority.name if task.priority else None
            task_info = {
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'priority': priority_name,
                'due_date': task.due_date.strftime("%Y-%m-%d %H:%M:%S"),
                'category': category_name,
                'completed': task.completed
            }
            task_list.append(task_info)
        message = "Tasks retrieved successfully"
        return jsonify(message=message, tasks=task_list)
    except SQLAlchemyError as e:
        print("Error retrieving tasks from the database:", e)
        return jsonify({'message': 'Error retrieving tasks'}), 400


# Get task by id
# Params: task_id (path variable)
@app.route('/tasks/<task_id>')
def get_task(task_id):
    try:
        session = Session()
        task = session.query(Tasks).filter_by(id=task_id).options(joinedload(Tasks.category)).options(
            joinedload(Tasks.priority)).first()
        session.close()
        if task:
            task_list = (
                {'id': task.id, 'title': task.title, 'description': task.description, 'priority': task.priority.name,
                 'due_date': task.due_date.strftime("%Y-%m-%d %H:%M:%S"), 'category': task.category.name,
                 'completed': task.completed})
            message = "Task ID " + task_id + " retrieved successfully"
            return jsonify(message=message, task=task_list)
        else:
            return jsonify({'message': 'Task not found'}), 404
    except SQLAlchemyError as e:
        print("Error retrieving task from the database:", e)
        return jsonify({'message': 'Error retrieving task id: ' + task_id}), 400


# Create task
# Request body: task{title, description, priority, due_date, category, completed}
# priority, due_date and category have default values in case not given
@app.route('/tasks', methods=['POST'])
def create_task():
    try:
        default_due_date = datetime.now(UTC) + timedelta(days=1)
        data = request.json
        new_task = Tasks(title=data['title'], description=data.get('description'),
                         priority_id=data.get('priority_id', 1),
                         due_date=data.get('due_date', default_due_date.strftime("%Y-%m-%d %H:%M:%S")),
                         category_id=data.get('category_id', 1),
                         completed=data.get('completed', False))
        session = Session()
        session.add(new_task)
        session.commit()
        session.close()
        return jsonify({'message': 'Task created successfully'})
    except IntegrityError as e:
        print("Foreign key constraint violation:", e)
        return jsonify({'message': 'Foreign key constraint violation'}), 400
    except SQLAlchemyError as e:
        print("Error creating task to the database:", e)
        return jsonify({'message': 'Error creating task'}), 400


# Update task by id
# Params: task_id (path variable)
# Request body: task{title, description, priority, due_date, category, completed}
@app.route('/tasks/<task_id>', methods=['PUT'])
def update_task(task_id):
    try:
        data = request.json
        session = Session()
        task = session.query(Tasks).filter_by(id=task_id).first()
        if task:
            task.title = data.get('title', task.title)
            task.description = data.get('description', task.description)
            task.priority_id = data.get('priority_id', task.priority_id)
            task.due_date = data.get('due_date', task.due_date)
            task.category_id = data.get('category_id', task.category_id)
            task.completed = data.get('completed', task.completed)
            session.commit()
            session.close()
            return jsonify({'message': 'Task updated successfully'})
        else:
            session.close()
            return jsonify({'message': 'Task not found'}), 404
    except IntegrityError as e:
        print("Foreign key constraint violation:", e)
        return jsonify({'message': 'Foreign key constraint violation'}), 400
    except SQLAlchemyError as e:
        print("Error updating task to the database:", e)
        return jsonify({'message': 'Error updating task id: ' + task_id}), 400


# Delete task by id
# # Params: task_id (path variable)
@app.route('/tasks/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    try:
        session = Session()
        task = session.query(Tasks).filter_by(id=task_id).first()
        if task:
            session.delete(task)
            session.commit()
            session.close()
            return jsonify({'message': 'Task deleted successfully'})
        else:
            session.close()
            return jsonify({'message': 'Task not found'}), 404
    except SQLAlchemyError as e:
        print("Error deleting task to the database:", e)
        return jsonify({'message': 'Error deleting task id: ' + task_id}), 400


# Get all categories
@app.route('/categories')
def get_categories():
    try:
        session = Session()
        categories = session.query(Categories).all()
        session.close()
        categories_list = (
            [{'id': category.id, 'name': category.name} for
             category in categories])
        message = "Categories retrieved successfully"
        return jsonify(message=message, categories=categories_list)
    except SQLAlchemyError as e:
        print("Error retrieving categories from the database:", e)
        return jsonify({'message': 'Error retrieving categories'}), 400


# Create category
# Request body: category{name}
@app.route('/categories', methods=['POST'])
def create_category():
    try:
        data = request.json
        new_category = Categories(name=data['name'])
        session = Session()
        session.add(new_category)
        session.commit()
        session.close()
        return jsonify({'message': 'Category created successfully'})
    except SQLAlchemyError as e:
        print("Error creating category to the database:", e)
        return jsonify({'message': 'Error creating category'}), 400


# Update category by id
# Params: category_id (path variable)
# Request body: category{name}
@app.route('/categories/<category_id>', methods=['PUT'])
def update_category(category_id):
    try:
        data = request.json
        session = Session()
        category = session.query(Categories).filter_by(id=category_id).first()
        if category:
            category.name = data.get('name', category.name)
            session.commit()
            session.close()
            return jsonify({'message': 'Category updated successfully'})
        else:
            session.close()
            return jsonify({'error': 'Category not found'}), 404
    except SQLAlchemyError as e:
        print("Error updating category to the database:", e)
        return jsonify({'message': 'Error updating category id: ' + category_id}), 400


# Delete category by id
# # Params: category_id (path variable)
@app.route('/categories/<category_id>', methods=['DELETE'])
def delete_category(category_id):
    try:
        session = Session()
        category = session.query(Categories).filter_by(id=category_id).first()
        if category:
            session.delete(category)
            session.commit()
            session.close()
            return jsonify({'message': 'Category deleted successfully'})
        else:
            session.close()
            return jsonify({'error': 'Category not found'}), 404
    except SQLAlchemyError as e:
        print("Error deleting category to the database:", e)
        return jsonify({'message': 'Error deleting category id: ' + category_id}), 400


# Global exception handling
@app.errorhandler(404)
def not_found(exception):
    return jsonify({'message': 'Not found'}), 404


@app.errorhandler(405)
def not_found(exception):
    return jsonify({'message': 'Method not allowed'}), 405


@app.errorhandler(400)
def bad_request(exception):
    return jsonify({'message': 'Bad request'}), 400


@app.errorhandler(500)
def bad_request(exception):
    return jsonify({'message': 'Error occurred'}), 400


# Run server
if __name__ == "__main__":
    seed_data()
    app.run()
