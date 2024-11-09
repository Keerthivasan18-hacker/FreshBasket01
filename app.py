from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import mysql.connector
from mysql.connector import Error
from mysql.connector.pooling import MySQLConnectionPool
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import binascii

app = Flask(__name__)
app.secret_key = binascii.hexlify(os.urandom(24)).decode()  # Needed for flash messages

# Database configuration
db_config = {
    'host': 'freshbasketdb.cza66aqeqs40.us-east-1.rds.amazonaws.com',  # Your RDS endpoint
    'user': 'admin',  # Your DB username
    'password': 'freshbasket',  # Your DB password
    'database': 'fresh'
}

# Connection pool setup
try:
    cnxpool = MySQLConnectionPool(pool_name="mypool", pool_size=5, **db_config)
    print("Database connection pool created successfully.")
except Error as err:
    print(f"Error creating database connection pool: {err}")

# Function to establish a database connection
def get_db_connection():
    try:
        connection = cnxpool.get_connection()
        print("Database connection obtained from pool.")
        return connection
    except Error as err:
        print(f"Database connection error: {err}")
        return None

@app.route('/')
def home():
    print("Home route accessed")
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    print("Register route accessed")
    if request.method == 'POST':
        name = request.form.get('name')
        mobile = request.form.get('mobile')
        email = request.form.get('email')
        password = generate_password_hash(request.form.get('password'))
        default_address = request.form.get('default_address')
        
        if not default_address:
            flash('Default address is required!')
            return redirect(url_for('register'))
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection error.')
            return redirect(url_for('register'))
        
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO users (name, mobile, email, password, address) VALUES (%s, %s, %s, %s, %s)',
                (name, mobile, email, password, default_address)
            )
            conn.commit()
            print(f"User {name} registered successfully.")
            flash('Thank you for registering!')
            return redirect(url_for('login'))
        except Error as e:
            print(f"Error during registration: {e}")
            flash(f"Error: {e}")
        finally:
            cursor.close()
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    print("Login route accessed")
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        if not conn:
            flash('Database connection error.')
            return redirect(url_for('login'))
        
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
            user = cursor.fetchone()
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                print(f"User {user['name']} logged in successfully.")
                flash('Login successful!')
                return redirect(url_for('shop'))
            else:
                print("Invalid email or password.")
                flash('Invalid email or password!')
        except Error as e:
            print(f"Error during login: {e}")
            flash(f"Error: {e}")
        finally:
            cursor.close()
            conn.close()
    return render_template('login.html')

@app.route('/shop')
def shop():
    print("Shop route accessed")
    return render_template('shop.html')

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    item_data = request.get_json()
    item_name = item_data['name']
    item_price = item_data['price']
    item_quantity = int(item_data['quantity'])
    
    print(f"Adding item to cart: {item_name}, Price: {item_price}, Quantity: {item_quantity}")
    
    cart_items = session.get('cart_items', [])
    item_found = False
    for item in cart_items:
        if item['name'] == item_name:
            item['quantity'] += item_quantity
            item_found = True
            break
    if not item_found:
        cart_items.append({
            'name': item_name,
            'price': item_price,
            'quantity': item_quantity
        })
    session['cart_items'] = cart_items
    return jsonify(success=True)

@app.route('/items', methods=['GET', 'POST'])
def items():
    print("Items route accessed")
    if request.method == "POST":
        item_name = request.form.get('name')
        item_price = float(request.form.get('price'))
        item_quantity = int(request.form.get('quantity'))
        
        print(f"Adding {item_name} to cart with quantity {item_quantity} and price {item_price}")
        
        cart_items = session.get('cart_items', [])
        for item in cart_items:
            if item['name'] == item_name:
                item['quantity'] += item_quantity
                break
        else:
            cart_items.append({'name': item_name, 'price': item_price, 'quantity': item_quantity})
        
        session['cart_items'] = cart_items
        flash(f"{item_name} added to your cart!")
        return redirect(url_for('items'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT item_id, item_name, price FROM items')
    items = cursor.fetchall()
    cursor.close()
    conn.close()
    
    cart_items = session.get("cart_items", [])
    return render_template('items.html', items=items, cart_items=cart_items)

@app.route('/place_order', methods=['POST'])
def place_order():
    print("Place order route accessed")
    if 'user_id' not in session:
        return jsonify(success=False, message="User not logged in")
    
    data = request.get_json()
    delivery_address = data.get('address', 'Default Address')
    payment_method = data["payment_method"]
    items = data['items']
    total_price = data['total_price']
    
    conn = get_db_connection()
    if not conn:
        return jsonify(success=False, message="Database connection error.")
    
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO orders (user_id, delivery_address, payment_method, status, order_date, total_price) VALUES (%s, %s, %s, %s, %s, %s)",
            (session['user_id'], delivery_address, payment_method, 'Yet to Ship', datetime.now(), total_price)
        )
        order_id = cursor.lastrowid
        for item in items:
            cursor.execute(
                'INSERT INTO order_items (order_id, item_name, quantity, price) VALUES (%s, %s, %s, %s)',
                (order_id, item['name'], item['quantity'], item['price'])
            )
        conn.commit()
        print("Order placed successfully.")
        return jsonify(success=True)
    except Error as e:
        conn.rollback()
        print(f"Error placing order: {e}")
        return jsonify(success=False, message=str(e))
    finally:
        cursor.close()
        conn.close()

if __name__ == '__main__':
    print("Starting the Flask app...")
    app.run(host='0.0.0.0', port=5000, debug=True)
