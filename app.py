from flask import Flask, render_template, request

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calculator')
def calculator():
    return render_template('calculator.html')

@app.route('/result', methods=['POST'])
def result():
    amount = float(request.form['amount'])
    rate = float(request.form['rate'])
    months = int(request.form['months'])
    monthly_rate = rate / 100 / 12
    payment = amount * (monthly_rate * (1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)
    return render_template('result.html', amount=amount, rate=rate, months=months, payment=round(payment, 2))

@app.route('/travel')
def travel():
    return render_template('travel.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

if __name__ == '__main__':
    app.run(debug=True)
