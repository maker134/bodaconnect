import pytest
import psycopg2
import os
from werkzeug.security import generate_password_hash

# This file runs automatically before any test
# It sets up the database tables and test data

DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://bodauser:bodapass@localhost:5432/bodaconnect'
)

@pytest.fixture(scope='session', autouse=True)
def setup_database():
    """
    Runs once before all tests.
    Creates tables and inserts the default admin user.
    This mirrors what init_db() does when the app starts normally.
    """
    conn = psycopg2.connect(DATABASE_URL)
    c = conn.cursor()

    # Create users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'customer'
    )''')

    # Create rides table
    c.execute('''CREATE TABLE IF NOT EXISTS rides (
        id SERIAL PRIMARY KEY,
        customer_id INTEGER NOT NULL REFERENCES users(id),
        rider_id INTEGER REFERENCES users(id),
        pickup TEXT NOT NULL,
        destination TEXT NOT NULL,
        customer_phone TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Insert default admin user for login tests
    c.execute('SELECT id FROM users WHERE email = %s', ('admin@bodaconnect.com',))
    if not c.fetchone():
        c.execute('''INSERT INTO users (first_name, last_name, email, phone, password, role)
                     VALUES (%s, %s, %s, %s, %s, %s)''',
                  ('Admin', 'BodaConnect', 'admin@bodaconnect.com',
                   '+255000000000', generate_password_hash('admin123'), 'admin'))

    conn.commit()
    conn.close()
    print("✅ Test database tables created")

@pytest.fixture
def client(setup_database):
    """Provides a Flask test client for route testing"""
    from app import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client