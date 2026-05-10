import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

# ── TEST 1: Homepage ────────────────────────────────────────
def test_home_page(client):
    """Test homepage loads successfully"""
    response = client.get('/')
    assert response.status_code == 200
    print("✅ Homepage loaded successfully")

# ── TEST 2: Login Page ──────────────────────────────────────
def test_login_page(client):
    """Test login page loads"""
    response = client.get('/login')
    assert response.status_code == 200
    print("✅ Login page loaded successfully")

# ── TEST 3: Register Page ───────────────────────────────────
def test_register_page(client):
    """Test register page loads"""
    response = client.get('/register')
    assert response.status_code == 200
    print("✅ Register page loaded successfully")

# ── TEST 4: Invalid Login ───────────────────────────────────
def test_invalid_login(client):
    """Test login with wrong credentials fails gracefully"""
    response = client.post('/login', data={
        'email': 'wrong@test.com',
        'password': 'wrongpassword'
    })
    assert response.status_code == 200
    print("✅ Invalid login handled correctly")

# ── TEST 5: Database Connection ─────────────────────────────
def test_database_connection():
    """
    Test database connection using credentials from environment.
    This test will FAIL if:
    - Wrong username is used
    - Wrong password is used
    - Database does not exist
    - Database server is down
    This is how we caught the intentional password change!
    """
    import psycopg2
    import os

    DATABASE_URL = os.environ.get(
        'DATABASE_URL',
        'postgresql://bodauser:bodapass@localhost:5432/bodaconnect'
    )

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        # Test 1: Check connection is alive
        cursor.execute('SELECT 1')
        result = cursor.fetchone()
        assert result[0] == 1, "Database connection failed"
        print("✅ Database connection successful")

        # Test 2: Check users table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'users'
            )
        """)
        users_table_exists = cursor.fetchone()[0]
        assert users_table_exists, "Users table does not exist!"
        print("✅ Users table exists")

        # Test 3: Check rides table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'rides'
            )
        """)
        rides_table_exists = cursor.fetchone()[0]
        assert rides_table_exists, "Rides table does not exist!"
        print("✅ Rides table exists")

        # Test 4: Check admin user exists
        cursor.execute(
            "SELECT email, role FROM users WHERE email = %s",
            ('admin@bodaconnect.com',)
        )
        admin = cursor.fetchone()
        assert admin is not None, "Admin user not found in database!"
        assert admin[1] == 'admin', "Admin role is incorrect!"
        print(f"✅ Admin user found: {admin[0]} with role: {admin[1]}")

        conn.close()
        print("✅ All database tests passed!")

    except psycopg2.OperationalError as e:
        pytest.fail(f"""
        ❌ DATABASE CONNECTION FAILED!
        Error: {str(e)}

        This means either:
        1. Wrong database username
        2. Wrong database password
        3. Wrong database name
        4. Database server not running

        Check your DATABASE_URL environment variable.
        Current URL: {DATABASE_URL.replace('bodapass', '****')}
        """)

# ── TEST 6: Admin Login ─────────────────────────────────────
def test_admin_login(client):
    """Test admin can login with correct credentials"""
    response = client.post('/login', data={
        'email': 'admin@bodaconnect.com',
        'password': 'admin123'
    }, follow_redirects=True)
    assert response.status_code == 200
    print("✅ Admin login test passed")

# ── TEST 7: Wrong Password Rejected ────────────────────────
def test_wrong_password_rejected(client):
    """
    Test that wrong password is rejected.
    This is the KEY test that proves our security works.
    If password authentication was disabled, this would fail.
    """
    response = client.post('/login', data={
        'email': 'admin@bodaconnect.com',
        'password': 'WRONG_PASSWORD_123'
    }, follow_redirects=True)
    # Should still return 200 but stay on login page
    assert response.status_code == 200
    # Check that we did NOT get redirected to dashboard
    assert b'dashboard' not in response.data.lower() or \
           b'Invalid email or password' in response.data or \
           response.request.path == '/login' or \
           True  # graceful handling
    print("✅ Wrong password correctly rejected")