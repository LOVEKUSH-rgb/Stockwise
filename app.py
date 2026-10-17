import json
import csv
import io
import os
import uuid
from datetime import datetime
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, abort, make_response
)

app = Flask(__name__)
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY", "change-this-key-for-your-project"
)

BASE_FOLDER = Path(__file__).resolve().parent
PRODUCTS_FILE = BASE_FOLDER / "products.json"
SALES_FILE = BASE_FOLDER / "sales.json"


# -------------------------
# JSON FILE FUNCTIONS
# -------------------------

def read_data(file_path):
    """Read a list from a JSON file. Create an empty list if missing."""
    if not file_path.exists():
        save_data(file_path, [])
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError:
        raise ValueError(
            f"{file_path.name} is not valid JSON. Please check the file."
        )

    if not isinstance(data, list):
        raise ValueError(f"{file_path.name} must contain a JSON list.")

    return data


def save_data(file_path, data):
    """Save a list to a JSON file."""
    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4)


def get_products():
    return read_data(PRODUCTS_FILE)


def get_sales():
    return read_data(SALES_FILE)


# -------------------------
# HELPER FUNCTIONS
# -------------------------

def find_product(products, product_id):
    for product in products:
        if product["product_id"] == product_id:
            return product
    return None


def is_low_stock(product):
    return product["quantity"] <= product["low_stock_threshold"]


def calculate_revenue(sales):
    # An empty sales list returns 0.00.
    total = sum(float(sale["total"]) for sale in sales)
    return round(total, 2)


def get_number(value, field_name, allow_zero=True):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a whole number.")

    if number < 0:
        raise ValueError(f"{field_name} cannot be negative.")

    if not allow_zero and number == 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return number


def get_price(value):
    try:
        price = float(value)
    except (TypeError, ValueError):
        raise ValueError("Please enter a valid price.")

    if price < 0 or price != price or price == float("inf"):
        raise ValueError("Price cannot be negative or invalid.")

    return round(price, 2)


def make_product(form, old_product=None):
    name = form.get("name", "").strip()
    category = form.get("category", "").strip()

    if not name:
        raise ValueError("Product name is required.")

    if not category:
        raise ValueError("Category is required.")

    price = get_price(form.get("price", ""))

    if old_product:
        # Keep stock quantity unchanged when editing product details.
        quantity = old_product["quantity"]
        product_id = old_product["product_id"]
    else:
        quantity = get_number(form.get("quantity", ""), "Quantity")
        product_id = "PRD-" + uuid.uuid4().hex[:8].upper()

    threshold = get_number(
        form.get("low_stock_threshold", "5"),
        "Low-stock threshold"
    )

    return {
        "product_id": product_id,
        "name": name,
        "category": category,
        "price": price,
        "quantity": quantity,
        "low_stock_threshold": threshold
    }


@app.context_processor
def template_helpers():
    return {
        "csrf_token": lambda: "",
        "product_is_low": is_low_stock
    }


@app.errorhandler(ValueError)
def handle_data_error(error):
    return render_template(
        "data_error.html",
        message=str(error),
        title="Data file problem"
    ), 500


# -------------------------
# DASHBOARD
# -------------------------

@app.route("/")
def dashboard():
    products = get_products()
    sales = get_sales()

    low_stock_products = [
        product for product in products if is_low_stock(product)
    ]

    total_units = sum(product["quantity"] for product in products)
    inventory_value = sum(
        product["price"] * product["quantity"] for product in products
    )

    return render_template(
        "dashboard.html",
        products=products,
        total_products=len(products),
        total_units=total_units,
        inventory_value=round(inventory_value, 2),
        total_revenue=calculate_revenue(sales),
        low_stock_products=low_stock_products
    )


# -------------------------
# PRODUCTS, SEARCH AND FILTER
# -------------------------

@app.route("/products")
def products_page():
    products = get_products()
    search = request.args.get("search", "").strip().lower()
    category = request.args.get("category", "").strip()

    categories = sorted({product["category"] for product in products})
    filtered_products = []

    for product in products:
        name_matches = search in product["name"].lower()
        category_matches = not category or product["category"] == category

        if name_matches and category_matches:
            filtered_products.append(product)

    return render_template(
        "products.html",
        products=filtered_products,
        categories=categories,
        search=search,
        selected_category=category
    )


# -------------------------
# ADD PRODUCT
# -------------------------

@app.route("/products/new", methods=["GET", "POST"])
def add_product():
    if request.method == "POST":
        try:
            product = make_product(request.form)
            products = get_products()

            # Avoid accidentally creating a duplicate ID.
            while find_product(products, product["product_id"]):
                product["product_id"] = "PRD-" + uuid.uuid4().hex[:8].upper()

            products.append(product)
            save_data(PRODUCTS_FILE, products)

            flash("Product added successfully.", "success")
            return redirect(url_for("products_page"))

        except ValueError as error:
            flash(str(error), "error")
            return render_template(
                "product_form.html",
                product=None,
                form=request.form
            ), 400

    return render_template("product_form.html", product=None, form={})


# -------------------------
# EDIT PRODUCT
# -------------------------

@app.route("/products/<product_id>/edit", methods=["GET", "POST"])
def edit_product(product_id):
    products = get_products()
    product = find_product(products, product_id)

    if product is None:
        abort(404)

    if request.method == "POST":
        try:
            updated_product = make_product(request.form, product)
            products[products.index(product)] = updated_product
            save_data(PRODUCTS_FILE, products)

            flash("Product updated successfully.", "success")
            return redirect(url_for("products_page"))

        except ValueError as error:
            flash(str(error), "error")
            return render_template(
                "product_form.html",
                product=product,
                form=request.form
            ), 400

    return render_template(
        "product_form.html",
        product=product,
        form=product
    )


# -------------------------
# DELETE PRODUCT
# -------------------------

@app.route("/products/<product_id>/delete", methods=["POST"])
def delete_product(product_id):
    products = get_products()

    if find_product(products, product_id) is None:
        abort(404)

    products = [
        product for product in products
        if product["product_id"] != product_id
    ]

    save_data(PRODUCTS_FILE, products)
    flash("Product deleted successfully.", "success")
    return redirect(url_for("products_page"))


# -------------------------
# RESTOCK PRODUCT
# -------------------------

@app.route("/products/<product_id>/restock", methods=["POST"])
def restock_product(product_id):
    products = get_products()
    product = find_product(products, product_id)

    if product is None:
        abort(404)

    try:
        amount = get_number(
            request.form.get("amount", ""),
            "Restock quantity",
            allow_zero=False
        )

        product["quantity"] += amount
        save_data(PRODUCTS_FILE, products)
        flash(f"{amount} units added to {product['name']}.", "success")

    except ValueError as error:
        flash(str(error), "error")

    return redirect(url_for("products_page"))


# -------------------------
# CHECKOUT
# -------------------------

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    products = get_products()

    if request.method == "POST":
        try:
            product_id = request.form.get("product_id", "")
            quantity = get_number(
                request.form.get("quantity", ""),
                "Quantity",
                allow_zero=False
            )

            product = find_product(products, product_id)

            if product is None:
                raise ValueError("Please select a valid product.")

            if quantity > product["quantity"]:
                raise ValueError(
                    f"Only {product['quantity']} units are available."
                )

            total = round(product["price"] * quantity, 2)

            sale = {
                "order_id": "ORD-" + uuid.uuid4().hex[:10].upper(),
                "product_id": product["product_id"],
                "product_name": product["name"],
                "quantity": quantity,
                "unit_price": product["price"],
                "total": total,
                "date": datetime.now().astimezone().isoformat(
                    timespec="seconds"
                )
            }

            # Reduce stock and record the sale.
            product["quantity"] -= quantity
            sales = get_sales()
            sales.insert(0, sale)

            save_data(PRODUCTS_FILE, products)
            save_data(SALES_FILE, sales)

            flash("Order completed successfully.", "success")
            return redirect(url_for("receipt", order_id=sale["order_id"]))

        except ValueError as error:
            flash(str(error), "error")
            return render_template("checkout.html", products=products), 400

    return render_template("checkout.html", products=products)


# -------------------------
# RECEIPT
# -------------------------

@app.route("/receipt/<order_id>")
def receipt(order_id):
    sales = get_sales()

    for sale in sales:
        if sale["order_id"] == order_id:
            return render_template("receipt.html", sale=sale)

    abort(404)


# -------------------------
# SALES HISTORY
# -------------------------

@app.route("/sales")
def sales_page():
    sales = get_sales()

    return render_template(
        "sales.html",
        sales=sales,
        total_revenue=calculate_revenue(sales)
    )


# -------------------------
# RESET SALES AND REVENUE
# -------------------------

@app.route("/sales/reset", methods=["POST"])
def reset_sales():
    # Clear sales history. This makes calculated revenue zero.
    save_data(SALES_FILE, [])

    flash("Sales history cleared. Sales revenue is now zero.", "success")
    return redirect(url_for("sales_page"))


# -------------------------
# EXPORT SALES TO CSV
# -------------------------

@app.route("/sales/export.csv")
def export_sales():
    sales = get_sales()
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Order ID", "Product", "Quantity",
        "Unit Price", "Total", "Date"
    ])

    for sale in sales:
        writer.writerow([
            sale["order_id"],
            sale["product_name"],
            sale["quantity"],
            sale["unit_price"],
            sale["total"],
            sale["date"]
        ])

    response = make_response("\ufeff" + output.getvalue())
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    response.headers["Content-Disposition"] = (
        'attachment; filename="sales-report.csv"'
    )

    return response


if __name__ == "__main__":
    app.run(debug=True)
