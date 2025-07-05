import io
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd

app = Flask(__name__, template_folder='template')
CORS(app)

state = {
    "salary": 0.0,
    "living_expense": 0.0,
    "start_month": 1,
    "repay_list": [],
    "course_list": [],
    "month_records": [],
    "calculation_summary": ""
}

allowed_pages = ['about', 'contact', 'privacy', 'terms']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/<page>')
def load_page(page):
    if page in allowed_pages:
        path = os.path.join(app.template_folder, f"{page}.html")
        if os.path.exists(path):
            return render_template(f"{page}.html")
    return "404 頁面不存在", 404

# --- 工具函式 --- #

def validate_positive_float(value, name):
    try:
        val = float(value)
        if val < 0:
            raise ValueError(f"{name}需為非負數")
        return val, None
    except Exception:
        return None, f"{name}格式錯誤，請輸入數字且大於等於0"

def validate_positive_int(value, name):
    try:
        val = int(value)
        if val <= 0:
            raise ValueError(f"{name}需為正整數")
        return val, None
    except Exception:
        return None, f"{name}格式錯誤，請輸入正整數"

def add_months_to_date(year, month, add_months):
    month_total = month + add_months - 1
    new_year = year + month_total // 12
    new_month = (month_total % 12) + 1
    return new_year, new_month

def format_ym(year, month):
    return f"{year}/{str(month).zfill(2)}"

# --- API --- #

@app.route('/api/get_state', methods=['GET'])
def get_state():
    return jsonify({"status": "success", "data": state})

@app.route('/api/set_salary', methods=['POST'])
def set_salary():
    data = request.get_json()
    salary, err = validate_positive_float(data.get('salary'), "薪水")
    if err:
        return jsonify({"status": "error", "message": err}), 400
    state['salary'] = salary
    return jsonify({"status": "success", "salary": salary})

@app.route('/api/set_living_expense', methods=['POST'])
def set_living_expense():
    data = request.get_json()
    expense, err = validate_positive_float(data.get('expense'), "生活費")
    if err:
        return jsonify({"status": "error", "message": err}), 400
    state['living_expense'] = expense
    return jsonify({"status": "success", "living_expense": expense})

@app.route('/api/set_start_month', methods=['POST'])
def set_start_month():
    data = request.get_json()
    try:
        start_month = int(data.get('start_month'))
        if start_month < 1 or start_month > 12:
            raise ValueError("起始月份必須介於1~12")
    except Exception:
        return jsonify({"status": "error", "message": "起始月份格式錯誤或不合法"}), 400
    state['start_month'] = start_month
    return jsonify({"status": "success", "start_month": start_month})

@app.route('/api/add_person', methods=['POST'])
def add_person():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({"status": "error", "message": "姓名不能為空"}), 400
    if any(p['name'] == name for p in state['repay_list']):
        return jsonify({"status": "error", "message": "此姓名已存在"}), 400
    debt, err = validate_positive_float(data.get('debt'), "欠款金額")
    if err or debt == 0:
        return jsonify({"status": "error", "message": "欠款金額必須是大於0的數字"}), 400
    state['repay_list'].append({"name": name, "debt": debt})
    return jsonify({"status": "success", "repay_list": state['repay_list']})

@app.route('/api/remove_person', methods=['POST'])
def remove_person():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({"status": "error", "message": "請提供姓名"}), 400
    before_len = len(state['repay_list'])
    state['repay_list'] = [p for p in state['repay_list'] if p['name'] != name]
    if len(state['repay_list']) == before_len:
        return jsonify({"status": "error", "message": "找不到此姓名"}), 404
    return jsonify({"status": "success", "repay_list": state['repay_list']})

@app.route('/api/add_course', methods=['POST'])
def add_course():
    data = request.get_json()
    fee, err_fee = validate_positive_float(data.get('fee'), "課程費用")
    months, err_months = validate_positive_int(data.get('months'), "課程期數")
    if err_fee or err_months:
        return jsonify({"status": "error", "message": err_fee or err_months}), 400
    state['course_list'].append({"fee": fee, "months": months})
    return jsonify({"status": "success", "course_list": state['course_list']})

@app.route('/api/remove_course', methods=['POST'])
def remove_course():
    data = request.get_json()
    try:
        idx = int(data.get('index'))
        if idx < 0 or idx >= len(state['course_list']):
            raise ValueError()
    except Exception:
        return jsonify({"status": "error", "message": "索引錯誤"}), 400
    state['course_list'].pop(idx)
    return jsonify({"status": "success", "course_list": state['course_list']})

@app.route('/api/calculate', methods=['POST'])
def calculate():
    salary = state["salary"]
    living_expense = state["living_expense"]
    repay_list = state["repay_list"]
    course_list = state["course_list"]
    start_month = state["start_month"]

    if not repay_list and not course_list:
        return jsonify({"status": "error", "message": "請至少新增還款人或課程費用"}), 400
    if salary <= living_expense:
        return jsonify({"status": "error", "message": f"薪水({salary})必須大於生活費({living_expense})"}), 400

    disposable_income = salary - living_expense
    if disposable_income <= 0:
        return jsonify({"status": "error", "message": "薪水扣除生活費後無可支配收入"}), 400

    # 初始化
    current_person_debts = {p["name"]: p["debt"] for p in repay_list}
    monthly_course_payments = [{
        "original_index": i,
        "name": f"課程{i+1}",
        "monthly_amount": c["fee"] / c["months"],
        "remaining_fee": c["fee"],
        "original_months": c["months"]
    } for i, c in enumerate(course_list)]

    month_records = []
    repayment_completion_dates = {}
    course_completion_dates = {}

    now = datetime.now()
    year = now.year
    current_month_index = 0

    while True:
        # 判斷是否全部還清
        debts_cleared = all(v <= 0.001 for v in current_person_debts.values())
        courses_cleared = all(c["remaining_fee"] <= 0.001 for c in monthly_course_payments)
        if debts_cleared and courses_cleared:
            break

        current_month_index += 1
        month_offset = start_month + current_month_index - 1
        month = (month_offset % 12) + 1
        calc_year = year + (month_offset // 12)
        date_str = format_ym(calc_year, month)

        month_record = {
            "month_num": current_month_index,
            "date": date_str,
            "disposable_income": disposable_income,
            "total_repaid_this_month": 0.0,
            "remaining_income_this_month": disposable_income,
            "repayments_detail": {},
            "course_payments_detail": {},
            "remaining_person_debts": {k: v for k, v in current_person_debts.items()},
            "remaining_course_fees": {c["name"]: c["remaining_fee"] for c in monthly_course_payments}
        }

        # 優先繳課程費用
        for course in monthly_course_payments:
            if course["remaining_fee"] > 0.001:
                pay_amount = min(course["monthly_amount"], course["remaining_fee"], month_record["remaining_income_this_month"])
                if pay_amount > 0:
                    month_record["course_payments_detail"][course["name"]] = pay_amount
                    course["remaining_fee"] -= pay_amount
                    month_record["remaining_income_this_month"] -= pay_amount
                    if course["remaining_fee"] <= 0.001 and course["name"] not in course_completion_dates:
                        course_completion_dates[course["name"]] = date_str
            month_record["remaining_course_fees"][course["name"]] = max(0, course["remaining_fee"])

        # 還款人分配
        remain_income = month_record["remaining_income_this_month"]
        active_debt_names = [n for n, d in current_person_debts.items() if d > 0.001]

        if remain_income > 0.001 and active_debt_names:
            total_active_debt = sum(current_person_debts[n] for n in active_debt_names)
            if total_active_debt > 0:
                for name in active_debt_names:
                    proportion = current_person_debts[name] / total_active_debt
                    pay_amount = min(proportion * remain_income, current_person_debts[name])
                    if pay_amount > 0:
                        month_record["repayments_detail"][name] = pay_amount
                        current_person_debts[name] -= pay_amount
                        month_record["remaining_income_this_month"] -= pay_amount
                        if current_person_debts[name] <= 0.001 and name not in repayment_completion_dates:
                            repayment_completion_dates[name] = date_str

        month_record["remaining_person_debts"] = {k: max(0, v) for k, v in current_person_debts.items()}
        month_record["total_repaid_this_month"] = disposable_income - month_record["remaining_income_this_month"]

        month_records.append(month_record)

        if current_month_index > 2000:
            return jsonify({"status": "error", "message": "計算超過2000個月，可能無法還清所有債務。請檢查輸入資料。"}), 500

    # 產生簡要結果文字
    result_text = f"總計還款月數：{current_month_index} 個月\n"
    result_text += "還款人繳清日期：\n"
    for name, date in repayment_completion_dates.items():
        result_text += f"  - {name}: {date} 繳清\n"
    result_text += "課程繳清日期：\n"
    for name, date in course_completion_dates.items():
        result_text += f"  - {name}: {date} 繳清\n"

    state["month_records"] = month_records
    state["calculation_summary"] = result_text

    return jsonify({
        "status": "success",
        "total_debt": sum(p["debt"] for p in repay_list),
        "monthly_repay_budget": disposable_income,
        "total_course_monthly_fee": sum(c["monthly_amount"] for c in monthly_course_payments),
        "total_months": current_month_index,
        "plan": month_records,
        "repay_completion_dates": repayment_completion_dates,
        "course_completion_dates": course_completion_dates,
        "summary_text": result_text
    })

@app.route('/api/export_csv', methods=['GET'])
def export_csv():
    if not state["month_records"]:
        return jsonify({"status": "error", "message": "請先執行計算才能匯出CSV"}), 400

    output = io.StringIO()
    df_rows = []

    all_person_names = sorted(set(p["name"] for p in state["repay_list"]))
    all_course_names = sorted(set(f"課程{c['original_index']+1}" for c in state["month_records"][0].get("remaining_course_fees", {}).keys()))

    for rec in state["month_records"]:
        row = {
            "月份": rec["date"],
            "可支配收入_每月": rec["disposable_income"],
            "當月還款繳費總計": rec["total_repaid_this_month"],
            "當月剩餘可支配收入": rec["remaining_income_this_month"],
        }
        for name in all_person_names:
            row[f"{name}_當月還款"] = rec["repayments_detail"].get(name, 0.0)
            row[f"{name}_剩餘債務"] = rec["remaining_person_debts"].get(name, 0.0)
        for cname in all_course_names:
            row[f"{cname}_當月繳費"] = rec["course_payments_detail"].get(cname, 0.0)
            row[f"{cname}_剩餘總費用"] = rec["remaining_course_fees"].get(cname, 0.0)
        df_rows.append(row)

    df = pd.DataFrame(df_rows)
    df.to_csv(output, index=False, encoding='utf-8-sig')
    output.seek(0)

    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype="text/csv",
        as_attachment=True,
        download_name="repayment_plan.csv"
    )


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
