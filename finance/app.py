import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd


# export API_KEY=pk_b7c90183e31d41f19206659fca28c189 


# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")

# Added a table called transactions to keep track of each buying/selling of stocks
#db.execute("CREATE TABLE transactions (user_id int, t_type TEXT NOT NULL, symbol TEXT NOT NULL, cost int, shares int)")
#db.execute ("ALTER TABLE transactions ADD time DATETIME DEFAULT CURRENT_TIMESTAMP")
#db.execute("DROP TABLE transactions")
#db.execute("CREATE TABLE transactions (user_id int, t_type TEXT NOT NULL, symbol TEXT NOT NULL, cost int, shares int, time DATETIME DEFAULT CURRENT_TIMESTAMP)")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


def get_shares(id):
    table = db.execute("SELECT symbol, shares, t_type, cost FROM transactions WHERE user_id = ?", session["user_id"])

    dict = {}

    for row in table:
        if row["symbol"] in dict:
            if row["t_type"] == "buy":
                dict[row["symbol"]] += row["shares"]
            else:
                dict[row["symbol"]] -= row["shares"]
        else:
            dict[row["symbol"]] = row["shares"]

    return dict


# INDEX - Done
@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    shares = get_shares(session["user_id"])

    table = []

    for row in shares:
        temp = {}
        temp["symbol"] = row
        temp["name"] = lookup(row)["name"]
        temp["shares"] = shares[row]
        temp["price"] = lookup(row)["price"]
        temp["total"] = shares[row] * lookup(row)["price"]
        table.append(temp)

    cash = db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"]
    total = 0

    for row in table:
        total += row["total"]

    total += cash
    if isinstance(total, str):
        print(total)

    return render_template("index.html", table=table, cash=cash, total=total)


# BUY - Done
@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        # Ensure symbol was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # Ensure number of shares was submitted
        if not request.form.get("shares"):
            return apology("must provide number of shares", 400)
        
        if request.form.get("shares").isnumeric() == False:
            return apology("must provide number of shares", 400)

        shares = int(request.form.get("shares"))

        # Ensure number of shares was submitted
        if shares < 1:
            return apology("please input a positive number of shares", 400)    
        
        # Check if lookup was successful
        if lookup(request.form.get("symbol")) is None:
            return apology("lookup unsuccessful", 400)
        else:
            stock = lookup(request.form.get("symbol"))
            stock_cost = stock["price"] * shares
            user_cash = float(db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"])
            
            if stock_cost > user_cash:
                return apology("Insufficient funds", 400)
            else:
                db.execute("INSERT INTO transactions (user_id, t_type, symbol, cost, shares) VALUES (?, ?, ?, ?, ?)", 
                           session["user_id"], "buy", request.form.get("symbol"), stock_cost, shares)
                new_cash = user_cash - stock_cost
                db.execute("UPDATE users SET cash = ? WHERE id = ?", new_cash, session["user_id"])
                
                return index()

    else:
        return render_template("buy.html")


# HISTORY
@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    table = db.execute("SELECT symbol, t_type, shares, cost, time FROM transactions WHERE user_id = ?", session["user_id"])

    for row in table:
        if row["t_type"] == "sell":
            row["shares"] *= -1

    return render_template("history.html", table=table)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


# QUOTE - Done
@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""

    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("symbol"):
            return apology("must provide symbol", 400)

        # Check if lookup was successful
        if lookup(request.form.get("symbol")) is None:
            return apology("lookup unsuccessful", 400)
        else:
            dict = lookup(request.form.get("symbol"))
            return render_template("quoted.html", dict=dict)

    else:
        return render_template("quote.html")


# ADD CASH
@app.route("/cash", methods=["GET", "POST"])
@login_required
def cash():
    """Add cash."""

    if request.method == "POST":
        # Ensure amount was submitted
        if not request.form.get("amount"):
            return apology("must provide amount", 400)
        
        amount = float(request.form.get("amount"))

        # Ensure amount was submitted
        if amount <= 0:
            return apology("must provide a positive amount", 400)

        current_cash = float(db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"])
        new_cash = current_cash + amount
        
        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_cash, session["user_id"])

        return index()

    else:
        current_cash = float(db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"])
        return render_template("cash.html", current_cash=current_cash)


# REGISTER - Done
@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 400)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 400)

        # Ensure password was submitted
        elif not request.form.get("confirmation"):
            return apology("must provide confirmation", 400)

        # Ensure password and confirmation match
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("password and confirmation do not match", 400)

        table = db.execute("SELECT username FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username is not duplicate
        if len(table) > 0:
            return apology("username taken", 400)

        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", request.form.get(
            "username"), generate_password_hash(request.form.get("password")))

        return redirect("/")

    else:
        return render_template("register.html")


# SELL
@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    symbols = []

    table = db.execute("SELECT symbol FROM transactions WHERE user_id = ?", session["user_id"])

    for row in table:
        if not row["symbol"] in symbols:
            symbols.append(row["symbol"])
     
    if request.method == "POST":
        # Ensure username was submitted
        if request.form.get("symbol") not in symbols:
            return apology("must provide symbol", 400)

        if get_shares(session["user_id"])[request.form.get("symbol")] == 0:
            return apology("no stocks to sell", 400)
        
        if not request.form.get("shares"):
            return apology("must provide number of shares", 400)
        
        if request.form.get("shares").isnumeric() == False:
            return apology("must provide number of shares", 400)

        shares = int(request.form.get("shares"))

        if shares < 1:
            return apology("not a valid number of shares", 400)

        if shares > get_shares(session["user_id"])[request.form.get("symbol")]:
            return apology("not a valid number of shares", 400)
        
        stock = lookup(request.form.get("symbol"))
        stock_cost = stock["price"] * shares
        user_cash = float(db.execute("SELECT cash FROM users WHERE id = ?", session["user_id"])[0]["cash"])

        db.execute("INSERT INTO transactions (user_id, t_type, symbol, cost, shares) VALUES (?, ?, ?, ?, ?)", 
                   session["user_id"], "sell", request.form.get("symbol"), stock_cost, shares)
        new_cash = user_cash + stock_cost
        db.execute("UPDATE users SET cash = ? WHERE id = ?", new_cash, session["user_id"])
        
        return index()

    else:
        return render_template("sell.html", symbols=symbols)


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
