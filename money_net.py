import requests
import time
import os
import io
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import threading

app = Flask(__name__)
CORS(app)  # 啟用跨域請求

# 全局狀態模擬資料庫
state = {
    "salary": 0.0,
    "living_expense": 0.0,
    "start_month": 1,
    "repay_list": [],
    "course_list": [],
    "month_records": [],
    "calculation_summary": ""
}

# 支援載入的靜態頁面清單
allowed_pages = ['index', 'about', 'contact', 'privacy', 'terms']

@app.route('/')
def index():
    """根路由載入 index.html"""
    return send_file(os.path.join(app.root_path, 'template', 'index.html'))

@app.route('/api/pages/<page>')
def load_page(page):
    """動態載入其他靜態頁面"""
    if page in allowed_pages:
        path = os.path.join(app.root_path, 'template', f'{page}.html')
        if os.path.exists(path):
            return send_file(path)
        else:
            return jsonify({"status": "error", "message": f"{page}.html 不存在"}), 404
    else:
        return jsonify({"status": "error", "message": "無效頁面名稱"}), 404

@app.route('/api/get_current_state', methods=['GET'])
def get_current_state():
    """取得目前狀態"""
    return jsonify({
        "status": "success",
        "salary": state["salary"],
        "living_expense": state["living_expense"],
        "start_month": state["start_month"],
        "repay_list": state["repay_list"],
        "course_list": state["course_list"],
    })

@app.route('/api/add_person', methods=['POST'])
def add_person():
    data = request.get_json()
    name = data.get('name')
    debt = data.get('debt')

    if not name or not isinstance(name, str) or not name.strip():
        return jsonify({"status": "error", "message": "姓名不能為空"}), 400
    try:
        debt = float(debt)
        if debt <= 0:
            return jsonify({"status": "error", "message": "欠款金額必須大於0"}), 400
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "欠款金額必須是有效數字"}), 400

    state["repay_list"].append({"name": name.strip(), "debt": debt})
    return jsonify({"status": "success", "message": "還款人新增成功", "repay_list": state["repay_list"]})

@app.route('/api/add_course', methods=['POST'])
def add_course():
    data = request.get_json()
    fee = data.get('fee')
    months = data.get('months')

    try:
        fee = float(fee)
        if fee <= 0:
            return jsonify({"status": "error", "message": "課程總費用必須大於0"}), 400
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "課程總費用必須是有效數字"}), 400

    try:
        months = int(months)
        if months <= 0:
            return jsonify({"status": "error", "message": "課程期數必須是大於0的整數"}), 400
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "課程期數必須是大於0的整數"}), 400

    state["course_list"].append({"fee": fee, "months": months})
    return jsonify({"status": "success", "message": "課程新增成功", "course_list": state["course_list"]})

@app.route('/api/set_salary', methods=['POST'])
def set_salary():
    data = request.get_json()
    salary = data.get('salary')
    try:
        salary = float(salary)
        if salary < 0:
            return jsonify({"status": "error", "message": "薪水必須是非負數"}), 400
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "薪水必須是有效數字"}), 400

    state["salary"] = salary
    return jsonify({"status": "success", "message": "薪水設定成功", "salary": state["salary"]})

@app.route('/api/set_living_expense', methods=['POST'])
def set_living_expense():
    data = request.get_json()
    expense = data.get('expense')
    try:
        expense = float(expense)
        if expense < 0:
            return jsonify({"status": "error", "message": "生活費必須是非負數"}), 400
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "生活費必須是有效數字"}), 400

    state["living_expense"] = expense
    return jsonify({"status": "success", "message": "生活費設定成功", "living_expense": state["living_expense"]})

@app.route('/api/set_start_month', methods=['POST'])
def set_start_month():
    data = request.get_json()
    start_month = data.get('start_month')
    try:
        start_month = int(start_month)
        if start_month < 1 or start_month > 12:
            return jsonify({"status": "error", "message": "起始月份必須介於1~12"}), 400
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "起始月份必須是有效數字"}), 400

    state["start_month"] = start_month
    return jsonify({"status": "success", "message": "起始月份設定成功", "start_month": state["start_month"]})

@app.route('/api/calculate', methods=['POST'])
def calculate_repayment():
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

    total_debt = sum(p["debt"] for p in repay_list)
    total_course_fee = sum(c["fee"] for c in course_list)

    current_person_debts = {p["name"]: p["debt"] for p in repay_list}
    current_course_fees = [c["fee"] for c in course_list]

    monthly_course_payments = [
        {
            "name": f"課程{i+1}",
            "monthly_amount": c["fee"] / c["months"],
            "remaining_months": c["months"]
        } for i, c in enumerate(course_list)
    ]

    month_records = []
    repayment_completion_dates = {}
    course_completion_dates = {}

    current_month_index = 0
    year = datetime.now().year  # 動態取得今年

    while True:
        # 判斷是否都還清
        if (all(v <= 0.001 for v in current_person_debts.values()) and
            all(f <= 0.001 for f in current_course_fees)):
            break

        # 日期計算
        month = (start_month + current_month_index -1) % 12 +1
        year_shift = (start_month + current_month_index -1) // 12
        current_year = year + year_shift
        date_str = f"{current_year}/{month:02d}"

        month_record = {
            "month_num": current_month_index + 1,
            "date": date_str,
            "disposable_income": disposable_income,
            "total_repaid_this_month": 0.0,
            "remaining_income": disposable_income,
            "repayments_detail": {},
            "course_payments_detail": {},
            "remaining_person_debts": {},
            "remaining_course_fees": {}
        }

        # 先繳課程費用
        for i, course_payment in enumerate(monthly_course_payments):
            if current_course_fees[i] > 0.001:
                pay = min(course_payment["monthly_amount"], current_course_fees[i], month_record["remaining_income"])
                if pay > 0:
                    month_record["course_payments_detail"][course_payment["name"]] = pay
                    current_course_fees[i] -= pay
                    month_record["remaining_income"] -= pay
                    if current_course_fees[i] <= 0.001 and course_payment["name"] not in course_completion_dates:
                        course_completion_dates[course_payment["name"]] = date_str

        # 再還款人分配
        remaining_income = month_record["remaining_income"]
        active_debt_names = [name for name, debt in current_person_debts.items() if debt > 0.001]

        if remaining_income > 0.001 and active_debt_names:
            total_active_debt = sum(current_person_debts[n] for n in active_debt_names)
            for name in active_debt_names:
                proportion = current_person_debts[name] / total_active_debt
                pay = min(proportion * remaining_income, current_person_debts[name])
                if pay > 0:
                    month_record["repayments_detail"][name] = pay
                    current_person_debts[name] -= pay
                    month_record["remaining_income"] -= pay
                    if current_person_debts[name] <= 0.001 and name not in repayment_completion_dates:
                        repayment_completion_dates[name] = date_str

        month_record["total_repaid_this_month"] = disposable_income - month_record["remaining_income"]

        # 剩餘債務與費用
        month_record["remaining_person_debts"] = {k: max(0, v) for k, v in current_person_debts.items()}
        month_record["remaining_course_fees"] = {mp["name"]: max(0, current_course_fees[i]) for i, mp in enumerate(monthly_course_payments)}

        month_records.append(month_record)
        current_month_index += 1

        if current_month_index > 2000:
            return jsonify({"status": "error", "message": "計算超過2000個月，可能無法還清，請檢查輸入資料"}), 500

    # 結果文字
    result_text = "還款試算結果：\n\n"
    result_text += f"總月數：{current_month_index} 個月\n\n"

    result_text += "還款人還清時間：\n"
    if repayment_completion_dates:
        for name, date_str in repayment_completion_dates.items():
            result_text += f"  - {name}: {date_str} 還清\n"
    else:
        result_text += "  - 無還款人或債務已清。\n"
    result_text += "\n"

    result_text += "課程繳清時間：\n"
    if course_completion_dates:
        for name, date_str in course_completion_dates.items():
            result_text += f"  - {name}: {date_str} 繳清\n"
    else:
        result_text += "  - 無課程費用或已繳清。\n"
    result_text += "\n"

    result_text += "每月詳細還款計畫：\n"
    for rec in month_records:
        result_text += f"{rec['date']} (第{rec['month_num']}月):\n"
        result_text += f"  可支配收入: {rec['disposable_income']:.2f} 元\n"
        if rec["course_payments_detail"]:
            result_text += "  課程繳納:\n"
            for k, v in rec["course_payments_detail"].items():
                result_text += f"    - {k}: {v:.2f} 元\n"
        if rec["repayments_detail"]:
            result_text += "  還款人分配:\n"
            for k, v in rec["repayments_detail"].items():
                result_text += f"    - {k}: {v:.2f} 元\n"
        result_text += f"  當月還款/繳費總計: {rec['total_repaid_this_month']:.2f} 元\n"
        result_text += f"  當月剩餘可支配收入: {rec['remaining_income']:.2f} 元\n"
        if any(v > 0.001 for v in rec["remaining_person_debts"].values()):
            result_text += "  剩餘債務:\n"
            for k, v in rec["remaining_person_debts"].items():
                if v > 0.001:
                    result_text += f"    - {k}: {v:.2f} 元\n"
        if any(v > 0.001 for v in rec["remaining_course_fees"].values()):
            result_text += "  剩餘課程費用:\n"
            for k, v in rec["remaining_course_fees"].items():
                if v > 0.001:
                    result_text += f"    - {k}: {v:.2f} 元\n"
        result_text += "----------------------------------------\n"

    state["month_records"] = month_records
    state["calculation_summary"] = result_text

    return jsonify({"status": "success", "message": "計算完成", "result": result_text})

@app.route('/api/export_csv', methods=['GET'])
def export_csv():
    if not state["month_records"]:
        return jsonify({"status": "error", "message": "請先執行計算才能匯出CSV"}), 400

    output = io.StringIO()
    df_rows = []

    all_names = sorted(set(p["name"] for p in state["repay_list"]))
    all_course_names = [f"課程{i+1}" for i in range(len(state["course_list"]))]

    for rec in state["month_records"]:
        row = {
            "月份": rec["date"],
            "可支配收入": rec["disposable_income"],
            "當月總計還款_繳費": rec["total_repaid_this_month"],
            "當月剩餘可支配收入": rec["remaining_income"],
        }
        for name in all_names:
            row[f"{name}_當月還款"] = rec["repayments_detail"].get(name, 0.0)
            row[f"{name}_剩餘債務"] = rec["remaining_person_debts"].get(name, 0.0)
        for cname in all_course_names:
            row[f"{cname}_當月繳費"] = rec["course_payments_detail"].get(cname, 0.0)
            row[f"{cname}_剩餘費用"] = rec["remaining_course_fees"].get(cname, 0.0)

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

# 啟動背景 Ping 例子（如需要）
def background_ping():
    while True:
        try:
            requests.get("https://render.com")
        except:
            pass
        time.sleep(60 * 60)

def start_background_task():
    t = threading.Thread(target=background_ping, daemon=True)
    t.start()

if __name__ == '__main__':
    start_background_task()
    app.run(host="0.0.0.0", port=8000, debug=True)
