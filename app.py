import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# SQLite connection function
def get_db_connection():
    conn = sqlite3.connect('fresh.db')  # SQLite database file
    conn.row_factory = sqlite3.Row  # Allows access to columns as dictionaries
    return conn

# Create database tables if they don't exist
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        mobile TEXT NOT NULL,
        email TEXT NOT NULL,
        password TEXT NOT NULL,
        address TEXT NOT NULL
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        total_price REAL NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS order_items (
        order_item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        item_name TEXT NOT NULL,
        price REAL NOT NULL,
        quantity INTEGER NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(order_id)
    )''')
    
    conn.commit()
    conn.close()

# Initialize the database (run this once to create tables)
init_db()

# Home route
@app.route('/')
def index():
    return render_template('index.html')

# Register new user route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        mobile = request.form['mobile']
        email = request.form['email']
        password = request.form['password']
        address = request.form['address']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO users (name, mobile, email, password, address)
        VALUES (?, ?, ?, ?, ?)
        ''', (name, mobile, email, password, address))
        conn.commit()
        conn.close()
        
        return redirect(url_for('index'))

    return render_template('register.html')

# Shop route
@app.route('/shop')
def shop():
    # Mocked items data (replace with database queries if needed)
    items = [
        {"item_id": 1, "item_name": "Apple", "price": 2.5},
        {"item_id": 2, "item_name": "Banana", "price": 1.2},
        {"item_id": 3, "item_name": "Carrot", "price": 3.0}
    ]
    cart_items = session.get("cart_items", [])
    return render_template('shop.html', items=items, cart_items=cart_items)

# Add item to cart
@app.route('/add_to_cart/<int:item_id>', methods=['POST'])
def add_to_cart(item_id):
    item_name = request.form['item_name']
    price = float(request.form['price'])
    quantity = int(request.form['quantity'])

    # Add to session cart
    cart_items = session.get("cart_items", [])
    cart_items.append({"item_id": item_id, "item_name": item_name, "price": price, "quantity": quantity})
    session["cart_items"] = cart_items

    return redirect(url_for('shop'))

# Checkout route (just to show cart)
@app.route('/checkout')
def checkout():
    cart_items = session.get("cart_items", [])
    total_price = sum(item['price'] * item['quantity'] for item in cart_items)
    return render_template('checkout.html', cart_items=cart_items, total_price=total_price)

# Clear cart route
@app.route('/clear_cart')
def clear_cart():
    session.pop("cart_items", None)
    return redirect(url_for('shop'))

# User Login (mocked)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        # Check for user in the database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            return redirect(url_for('index'))
        else:
            return "Login failed, check your credentials."

    return render_template('login.html')

if __name__ == "__main__":
    app.run(debug=True)
