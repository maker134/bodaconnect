from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import os
import time

app = Flask(__name__)

# ── MQTT Integration (optional - won't crash if broker unavailable) ──
try:
    from mqtt_service import start_mqtt_background, publish_ride_request, publish_ride_status
    import threading
    import time

    def init_mqtt():
        time.sleep(5)
        try:
            start_mqtt_background(app)
        except Exception as e:
            print(f"⚠️ MQTT not available: {e}")

    mqtt_thread = threading.Thread(target=init_mqtt, daemon=True)
    mqtt_thread.start()
    print("✅ MQTT service initialized")
except ImportError:
    print("⚠️ paho-mqtt not installed - MQTT features disabled")
except Exception as e:
    print(f"⚠️ MQTT initialization failed: {e}")

app.secret_key = 'bodaconnect_secret_2024'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://bodauser:bodapass@localhost:5432/bodaconnect')

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    """
    Initialize database tables.
    Retries up to 10 times waiting for PostgreSQL to be ready.
    Fixed: conn is now guaranteed to exist before use, or app exits cleanly.
    """
    conn = None  # ← This prevents the UnboundLocalError
    for i in range(10):
        try:
            conn = get_db()
            print("✅ Connected to database!")
            break
        except Exception as e:
            print(f"Waiting for database... ({i+1}/10)")
            time.sleep(3)

    # If all 10 retries failed, conn is still None — exit clearly
    if conn is None:
        print("❌ Could not connect to database after 10 attempts. Exiting.")
        return

    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'customer'
    )''')

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

    c.execute('SELECT id FROM users WHERE email = %s', ('admin@bodaconnect.com',))
    if not c.fetchone():
        c.execute('''INSERT INTO users (first_name, last_name, email, phone, password, role)
                     VALUES (%s, %s, %s, %s, %s, %s)''',
                  ('Admin', 'BodaConnect', 'admin@bodaconnect.com',
                   '+255000000000', generate_password_hash('admin123'), 'admin'))

    conn.commit()
    conn.close()
    print("✅ Database ready!")

class User(UserMixin):
    def __init__(self, id, first_name, last_name, email, phone, role):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.phone = phone
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        user = c.fetchone()
        conn.close()
        if user:
            return User(user[0], user[1], user[2], user[3], user[4], user[6])
    except:
        pass
    return None

# ─── AUTH ──────────────────────────────────────────────────

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name']
        last_name  = request.form['last_name']
        email      = request.form['email']
        phone      = request.form['phone']
        password   = request.form['password']
        role       = request.form['role']
        if role == 'admin':
            flash('You cannot self-register as admin.', 'danger')
            return redirect(url_for('register'))
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT id FROM users WHERE email = %s', (email,))
        if c.fetchone():
            flash('Email already registered.', 'danger')
            conn.close()
            return redirect(url_for('register'))
        c.execute('''INSERT INTO users (first_name, last_name, email, phone, password, role)
                     VALUES (%s, %s, %s, %s, %s, %s)''',
                  (first_name, last_name, email, phone,
                   generate_password_hash(password), role))
        conn.commit()
        conn.close()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form['email']
        password = request.form['password']
        conn = get_db()
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE email = %s', (email,))
        user = c.fetchone()
        conn.close()
        if user and check_password_hash(user[5], password):
            u = User(user[0], user[1], user[2], user[3], user[4], user[6])
            login_user(u)
            flash(f"Welcome back, {u.first_name}!", 'success')
            if u.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif u.role == 'rider':
                return redirect(url_for('rider_dashboard'))
            else:
                return redirect(url_for('customer_dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# ─── CUSTOMER ──────────────────────────────────────────────

@app.route('/customer/dashboard')
@login_required
def customer_dashboard():
    if current_user.role != 'customer':
        return redirect(url_for('home'))
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT rides.id, rides.pickup, rides.destination,
               rides.status, rides.created_at,
               users.first_name, users.last_name, users.phone
        FROM rides
        LEFT JOIN users ON rides.rider_id = users.id
        WHERE rides.customer_id = %s
        ORDER BY rides.created_at DESC
    ''', (current_user.id,))
    rides = c.fetchall()
    conn.close()
    return render_template('customer_dashboard.html', rides=rides)

@app.route('/customer/request-ride', methods=['GET', 'POST'])
@login_required
def request_ride():
    if current_user.role != 'customer':
        return redirect(url_for('home'))
    if request.method == 'POST':
        pickup      = request.form['pickup']
        destination = request.form['destination']
        conn = get_db()
        c = conn.cursor()
        c.execute('''INSERT INTO rides (customer_id, pickup, destination, customer_phone)
                     VALUES (%s, %s, %s, %s) RETURNING id''',
                  (current_user.id, pickup, destination, current_user.phone))
        ride_id = c.fetchone()[0]
        conn.commit()
        conn.close()

        # Publish to MQTT broker
        try:
            if hasattr(app, 'mqtt_client'):
                publish_ride_request(
                    app.mqtt_client,
                    user_id=current_user.id,
                    pickup=pickup,
                    destination=destination,
                    phone=current_user.phone
                )
                print(f"✅ Ride request published to MQTT!")
        except Exception as e:
            print(f"⚠️ MQTT publish failed: {e}")

        flash('Ride requested! A rider will contact you on ' + current_user.phone, 'success')
        return redirect(url_for('customer_dashboard'))
    return render_template('request_ride.html')

# ─── RIDER ─────────────────────────────────────────────────

@app.route('/rider/dashboard')
@login_required
def rider_dashboard():
    if current_user.role != 'rider':
        return redirect(url_for('home'))
    conn = get_db()
    c = conn.cursor()

    c.execute('''
        SELECT rides.id, rides.pickup, rides.destination,
               rides.status, rides.created_at,
               users.first_name, users.last_name, users.phone
        FROM rides
        JOIN users ON rides.customer_id = users.id
        WHERE rides.rider_id = %s AND rides.status != 'completed'
        ORDER BY rides.created_at DESC
    ''', (current_user.id,))
    my_rides = c.fetchall()

    c.execute('''
        SELECT rides.id, rides.pickup, rides.destination,
               rides.status, rides.created_at,
               users.first_name, users.last_name, users.phone
        FROM rides
        JOIN users ON rides.customer_id = users.id
        WHERE rides.status = 'pending'
        ORDER BY rides.created_at DESC
    ''')
    pending_rides = c.fetchall()

    c.execute('''
        SELECT rides.id, rides.pickup, rides.destination,
               rides.status, rides.created_at,
               users.first_name, users.last_name
        FROM rides
        JOIN users ON rides.customer_id = users.id
        WHERE rides.rider_id = %s AND rides.status = 'completed'
        ORDER BY rides.created_at DESC
    ''', (current_user.id,))
    completed_rides = c.fetchall()
    conn.close()

    return render_template('rider_dashboard.html',
                           my_rides=my_rides,
                           pending_rides=pending_rides,
                           completed_rides=completed_rides)

@app.route('/rider/approve/<int:ride_id>')
@login_required
def approve_ride(ride_id):
    if current_user.role != 'rider':
        return redirect(url_for('home'))
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE rides SET status = %s, rider_id = %s WHERE id = %s',
              ('approved', current_user.id, ride_id))
    conn.commit()
    conn.close()
    flash('Ride accepted! Call the customer and head to pickup.', 'success')
    return redirect(url_for('rider_dashboard'))

@app.route('/rider/complete/<int:ride_id>')
@login_required
def complete_ride(ride_id):
    if current_user.role != 'rider':
        return redirect(url_for('home'))
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE rides SET status = %s WHERE id = %s AND rider_id = %s',
              ('completed', ride_id, current_user.id))
    conn.commit()
    conn.close()
    flash('Ride completed! Great job.', 'success')
    return redirect(url_for('rider_dashboard'))

# ─── ADMIN ─────────────────────────────────────────────────

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('home'))
    conn = get_db()
    c = conn.cursor()

    c.execute('SELECT id, first_name, last_name, email, phone, role FROM users WHERE role != %s', ('admin',))
    users = c.fetchall()

    c.execute('''
        SELECT rides.id, rides.pickup, rides.destination,
               rides.status, rides.created_at,
               c.first_name, c.last_name, c.phone,
               r.first_name, r.last_name
        FROM rides
        LEFT JOIN users c ON rides.customer_id = c.id
        LEFT JOIN users r ON rides.rider_id = r.id
        ORDER BY rides.created_at DESC
    ''')
    rides = c.fetchall()
    conn.close()

    total_rides = len(rides)
    pending   = sum(1 for r in rides if r[3] == 'pending')
    completed = sum(1 for r in rides if r[3] == 'completed')

    return render_template('admin_dashboard.html',
                           users=users, rides=rides,
                           total_rides=total_rides,
                           pending=pending,
                           completed=completed)

@app.route('/admin/delete-user/<int:user_id>')
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        return redirect(url_for('home'))
    conn = get_db()
    c = conn.cursor()
    c.execute('DELETE FROM users WHERE id = %s', (user_id,))
    conn.commit()
    conn.close()
    flash('User deleted.', 'info')
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)