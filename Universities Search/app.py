from flask import Flask, render_template, request
import requests
import csv

app = Flask(__name__)

@app.route("/", methods=["GET","POST"])
def index():
    if request.method == "POST":
        uni_name = request.form.get("uni_name")
        country = request.form.get("country")
        with open("what_search_we_made.csv", "a") as file:
            writer = csv.writer(file)
            writer.writerow([uni_name, country])
        url = f"http://universities.hipolabs.com/search?name={uni_name.title()}&country={country.title()}"
        result = requests.get(url).json()
        return render_template("result.html", result=result)

    return render_template("index.html")

@app.route("/most_searchs")
def most_searchs():
    with open("what_search_we_made.csv") as file:
        reader = csv.DictReader(file)
        return render_template("what_searchs_we_made.html", searchs=reader)
