# Stockwise — Smart Inventory & Order Management

A beginner-friendly Flask web application for managing a small product catalog, monitoring stock, recording sales, and exporting sales history. It is designed for a local hackathon demonstration and stores its data in two human-readable JSON files.

## Features

- Dashboard with product count, units in stock, inventory value, sales revenue, and restock alerts.
- Product creation, editing, deletion, name search, and category filtering.
- Restocking as a distinct operation; editing product details cannot change its stock.
- Server-validated single-product checkout, automatic stock reduction, and printable-style receipt page.
- Sales history, order totals, and CSV export.
- CSRF tokens on all forms that change data, confirmation before deleting, and clear empty/error states.
- Responsive layout for desktop and mobile.

## Technology

- Python 3.10 or newer
- Flask
- HTML5, CSS3, and Jinja templates
- Python's built-in `json`, `csv`, and related standard-library modules

## Project structure

```text
smart_inventory/
├── app.py
├── products.json
├── sales.json
├── requirements.txt
├── README.md
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── products.html
│   ├── product_form.html
│   ├── checkout.html
│   ├── sales.html
│   ├── receipt.html
│   └── data_error.html
└── static/
    └── style.css
```

## Install and run

Open a terminal in this project folder and run:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000). Flask debug mode is off by default. To enable it for local development only, set `FLASK_DEBUG=1` in the environment before starting the application. Set `FLASK_SECRET_KEY` to a stable random secret if you need browser sessions to remain valid across application restarts.

## JSON storage

`products.json` stores each product's ID, name, category, price, quantity, and low-stock threshold. `sales.json` stores completed orders and their receipt details. If either file is missing, it is created automatically. A missing or genuinely empty product file is seeded with demonstration products; a missing or empty sales file starts with no sales. Existing non-empty data is never reset on startup.

Files are saved immediately after each change using a temporary file and atomic replacement. A malformed JSON file is reported on screen and is not silently replaced. Keep backups before manually editing data. A sale is validated before stock changes and the application attempts to restore the previous product file if saving the sale record fails.

JSON files are intended for this small, single-user demonstration. They do not provide database transactions, concurrent-write protection, multi-user access control, or production-grade recovery if the machine loses power between updating the two files.

## Demonstration flow for judges

1. Open the dashboard and point out the live product, stock, inventory-value, revenue, and low-stock summaries.
2. Open **Products**, search by name or select a category, then add a product.
3. Edit its descriptive information and note that quantity is read-only on the edit form.
4. Restock the item from its row; the saved stock and low-stock status update immediately.
5. Make a checkout with a valid quantity and show the generated receipt.
6. Try a quantity larger than available stock; the application rejects it without completing the sale.
7. Open **Sales reports** to see the order and revenue, and use **Export CSV**.
8. Delete a product and confirm the browser prompt.

## Tests

Run the automated application tests with:

```powershell
python -m unittest discover -s tests -v
```

The tests use temporary JSON files and do not modify the demonstration data in the project root.

## Limitations and future improvements

- Single-product checkout, no customer accounts, taxes, discounts, or payment processing.
- JSON storage is appropriate only for a small, single-user demo; a production deployment should use a transactional database and authentication.
- Future work could include multi-item orders, role-based access, inventory movement history, supplier management, and configurable currency.
