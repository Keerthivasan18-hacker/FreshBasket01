from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import mysql.connector
from datetime import datetime
import mysql.connector.pooling
import os
import binascii

app = Flask(__name__)
app.secret_key = binascii.hexlify(os.urandom(24)).decode()  # Needed for flash messages

# Database configuration
db_config = {
    'host': 'freshdb-1.cza66aqeqs40.us-east-1.rds.amazonaws.com',  # Your RDS endpoint
    'user': 'admin',  # Your DB username
    'password': 'freshbasket',  # Your DB password
    'database': 'fresh'
}

# Connection pool setup
cnxpool = mysql.connector.pooling.MySQLConnectionPool(pool_name="mypool", pool_size=5, **db_config)

# Function to establish a database connection
def get_db_connection():
    try:
        return cnxpool.get_connection()
    except mysql.connector.Error as err: 
        print(f"Error: {err}")
        return None

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        mobile = request.form.get('mobile')
        email = request.form.get('email')
        password = request.form.get('password')
        default_address = request.form.get('default_address')
        if not default_address:
            flash('Default address is required!')
            return redirect(url_for('register'))
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (name, mobile, email, password, address) VALUES (%s, %s, %s, %s, %s)',
            (name, mobile, email, password, default_address)
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash('Thank you for registering!')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE email = %s AND password = %s', (email, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        if user:
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            flash('Login successful!')
            return redirect(url_for('shop'))
        else: 
            flash('Invalid email or password!')
    return render_template('login.html')

@app.route('/shop')
def shop():
    return render_template('shop.html')

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    item_data = request.get_json()
    item_name = item_data['name']
    item_price = item_data['price']
    item_quantity = item_data['quantity']
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
    if request.method == "POST":
        item_name = request.form.get('name')
        item_price = float(request.form.get('price'))
        item_quantity = int(request.form.get('quantity'))
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
    if 'user_id' not in session:
        return jsonify(success=False, message="User not logged in")
    data = request.get_json()
    delivery_address = data.get('address', 'Default Address')
    payment_method = data["payment_method"]
    items = data['items']
    total_price = data['total_price']
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
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
        cursor.close()
        conn.close()
        return jsonify(success=True)
    except Exception as e:
        conn.rollback()
        return jsonify(success=False, message=str(e))

@app.route('/user_dashboard')
def user_dashboard():
    if 'user_id' not in session:
        flash('You need to log in to access your dashboard!')
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        SELECT o.id, o.total_price, o.status, o.order_date,
        GROUP_CONCAT(CONCAT(oi.item_name, ' (x', oi.quantity, ')')) AS items
        FROM orders o
        JOIN order_items oi ON o.id = oi.order_id
        WHERE o.user_id = %s
        GROUP BY o.id
    ''', (session['user_id'],))
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('user_dashboard.html', orders=orders)

@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if request.method == "POST":
        order_id = request.form['order_id']
        status = request.form['status']
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE orders SET status = %s WHERE id = %s', (status, order_id))
        conn.commit()
        cursor.close()
        conn.close()
        flash('Order status updated successfully!', 'success')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('''
        SELECT o.id, o.total_price, o.status, o.order_date, u.name AS user_name,
        GROUP_CONCAT(CONCAT(oi.item_name, ' (x', oi.quantity, ')') SEPARATOR ', ') AS items
        FROM orders o
        JOIN users u ON o.user_id = u.id
        JOIN order_items oi ON o.id = oi.order_id
        GROUP BY o.id
    ''')
    orders = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('admin_dashboard.html', orders=orders)

if __name__ == '__main__':
    app.run(host-"0.0.0.0",port=5000,debug=True)
