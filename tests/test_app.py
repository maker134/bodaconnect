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

def test_home_page(client):
    """Test homepage loads successfully"""
    response = client.get('/')
    assert response.status_code == 200

def test_login_page(client):
    """Test login page loads"""
    response = client.get('/login')
    assert response.status_code == 200

def test_register_page(client):
    """Test register page loads"""
    response = client.get('/register')
    assert response.status_code == 200

def test_invalid_login(client):
    """Test login with wrong credentials"""
    response = client.post('/login', data={
        'email': 'wrong@test.com',
        'password': 'wrongpassword'
    })
    assert response.status_code == 200