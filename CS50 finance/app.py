from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


# this will be the home/default page after user have register/login
@app.route("/")
@login_required
def index():
    user_stock_information = db.execute(
        "SELECT symbol, SUM(shares) as total_shares FROM transactions WHERE person_id=? GROUP BY symbol HAVING total_shares > 0",
        session["user_id"],
    )
    user_cash = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])[0][
        "cash"
    ]
    total_value = user_cash
    # updating the values of user stock like price
    for stock in user_stock_information:
        quote = lookup(stock["symbol"])
        stock["symbol"] = quote["name"]
        stock["price"] = quote["price"]
        total_share_price = stock["price"] * stock["total_shares"]
        total_value += total_share_price

    return render_template(
        "default.html",
        stocks=user_stock_information,
        user_cash=user_cash,
        total_value=usd(total_value),
    )


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Symbol can't be empty", 400)
        quote = lookup(symbol)
        if quote in ["Request error", "Data parsing error", None]:
            return apology("NOT a Valid Symbol/Sign", 400)

        shares = request.form.get("shares")
        if not shares or float(shares) <= 0:
            return apology("enter correct number", 400)

        # this user cash
        user_cash = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])[
            0
        ]["cash"]

        # this shares information like price, company, price okay
        stock_information = lookup(symbol)
        # multiply how many shares user want and share price
        total_cash_require = stock_information["price"] * float(shares)
        # now minus(-) the total cash reuired for the shares and cash that user have
        left_cash_of_user = user_cash - total_cash_require
        # if doesn't have the enough cash then telling them "don't have enough money"
        if left_cash_of_user < 0:
            return apology("Don't have enough Fund")

        # now updating the cash that user have
        db.execute(
            "INSERT INTO transactions(person_id, company, shares, price, symbol) VALUES(?,?,?,?,?)",
            session["user_id"],
            stock_information["name"],
            shares,
            stock_information["price"],
            stock_information["symbol"],
        )
        db.execute(
            "UPDATE users SET cash=? WHERE id=?", left_cash_of_user, session["user_id"]
        )
        flash(
            f"Bought {shares} shares of {symbol.upper()} for {usd(total_cash_require)}"
        )
        return redirect("/")

    return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    historys = db.execute(
        "SELECT * FROM transactions WHERE person_id=? ORDER BY timestamp DESC",
        session["user_id"],
    )
    return render_template("history.html", historys=historys)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
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


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Symbol can't be empty")
        quote = lookup(symbol)
        if quote in ["Request error", "Data parsing error", None]:
            return apology("NOT a Valid Symbol/Sign", 400)

        price = usd(quote["price"])
        return render_template("quote.html", quote=quote, price=price)

    return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    session.clear()

    if request.method == "POST":
        name = request.form.get("username")

        if name == db.execute("SELECT username FROM users WHERE username = ?", name):
            return apology("Username Already Taken!", 400)
        if not name:
            return apology("UserName required")

        first_password = request.form.get("password")
        confirm_password = request.form.get("confirmation")
        if not first_password or not confirm_password:
            return apology("Password Required", 400)
        if confirm_password != first_password:
            return apology("Password Doesn't match!", 400)

        hash = generate_password_hash(first_password)
        if db.execute("SELECT username FROM users WHERE username=?", name):
            return apology("Use differnent Username/password for Register!")

        else:
            db.execute("INSERT INTO users(username, hash) VALUES(?, ?)", name, hash)
            id = db.execute("SELECT id FROM users WHERE username=?", name)
            session["user_id"] = id[0]["id"]
            flash("Congrats,You have been registered!")
            return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    stocks_information = db.execute(
        "SELECT price, symbol, SUM(shares) as total_shares FROM transactions WHERE person_id=? GROUP BY symbol HAVING total_shares > 0",
        session["user_id"],
    )

    if request.method == "POST":
        # getting symbol and amount of shares to sell from html form
        symbol = request.form.get("symbol").upper()
        shares = request.form.get("shares")
        # if shares and symbol doesn't have these thing like minus value wroung symbol
        if not symbol:
            return apology("must provide symbol")
        if not shares or not int(shares):
            return apology("Must provide correct format")
        shares = int(shares)
        # if user have one shares of company or multiple it can done by loop
        for stock in stocks_information:
            # if user have the stock of that company then proceed futher

            if stock["symbol"] == symbol:
                # if user doesn't have the enough shares like user have enter more shares then user have

                if stock["total_shares"] < shares:
                    return apology("not enough shares")
                quote = lookup(symbol)
                if quote is None:
                    return apology("symbol not found")
                price = quote["price"]
                total_shares_for_sale = shares * price
                cash = db.execute(
                    "SELECT cash FROM users WHERE id=?", session["user_id"]
                )[0]["cash"]
                db.execute(
                    "UPDATE users SET cash=? WHERE id=?",
                    cash + total_shares_for_sale,
                    session["user_id"],
                )

                db.execute(
                    "INSERT INTO transactions (person_id, symbol, shares, price, company) VALUES(?, ?, ?, ?, ?)",
                    session["user_id"],
                    symbol,
                    -shares,
                    price,
                    quote["name"],
                )

                flash(
                    f"SOLD {shares} shares of {symbol} for {usd(total_shares_for_sale)}"
                )
                return redirect("/")

        else:
            return apology("symbol not found")
    else:
        return render_template("sell.html", stocks=stocks_information)


@app.route("/add_cash", methods=["POST", "GET"])
@login_required
def add_cash():
    if request.method == "POST":
        cash = request.form.get("add_cash")
        if int(cash) < 0:
            return apology("Invalid number")
        if not int(cash):
            return apology("Invalid format")
        if not cash:
            return apology("Must enter cash")

        current_cash = db.execute(
            "SELECT cash FROM users WHERE id=?", session["user_id"]
        )[0]["cash"]
        db.execute(
            "UPDATE users SET cash=? WHERE id=?",
            int(current_cash) + int(cash),
            session["user_id"],
        )
        flash(f"${cash} added successfully!")
        return redirect("/")
    return render_template("add_cash.html")


@app.route("/change_password", methods=["POST", "GET"])
def change_password():
    if request.method == "POST":
        password = request.form.get("change_password")
        user_name = request.form.get("user_name")
        if not user_name:
            return apology("enter username")
        if not password:
            return apology("enter password")
        current_hash = db.execute("SELECT hash FROM users WHERE username=?", user_name)
        if check_password_hash(current_hash[0]["hash"], password):
            return apology("Already have this password")

        db.execute(
            "UPDATE users SET hash=? WHERE username=?",
            generate_password_hash(password),
            user_name,
        )
        flash(f"{user_name} your password have change")
        return redirect("/login")

    return render_template("change_password.html")
