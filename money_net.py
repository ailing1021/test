from flask import Flask, request, jsonify, send_file
import csv
import io

app = Flask(__name__)

# 初始預設值
state = {
    "salary": 0.0,
    "living_expense": 0.0,
    "start_month": 1,
    "repay_list": [],
    "course_list": [],
    "month_records": [],
    "names": []
}


@app.route('/api/reset', methods=['POST'])
def reset():
    global state
    state = {
        "salary": 0.0,
        "living_expense": 5000.0,
        "start_month": 1,
        "repay_list": [],
        "course_list": [],
        "month_records": [],
        "names": []
    }
    return jsonify({"status": "success", "message": "所有資料已重置"})


@app.route('/api/add_person', methods=['POST'])
def add_person():
    data = request.json
    name = data.get('name', '').strip()
    debt = data.get('debt', '')
    try:
        debt = float(debt)
        if debt <= 0:
            return jsonify({"status": "error", "message": "欠款金額請輸入大於0的數字！"})
    except:
        return jsonify({"status": "error", "message": "欠款金額請輸入大於0的數字！"})
    if not name:
        return jsonify({"status": "error", "message": "請輸入姓名！"})
    state['repay_list'].append({"name": name, "debt": debt})
    return jsonify({"status": "success", "repay_list": state['repay_list']})


@app.route('/api/add_course', methods=['POST'])
def add_course():
    data = request.json
    fee = data.get('fee', '')
    months = data.get('months', '')
    try:
        fee = float(fee)
        months = int(months)
        if fee < 0 or months <= 0:
            return jsonify({"status": "error", "message": "請輸入正確的費用及期數！"})
    except:
        return jsonify({"status": "error", "message": "請輸入正確的費用及期數！"})
    state['course_list'].append({"fee": fee, "months": months})
    return jsonify({"status": "success", "course_list": state['course_list']})


@app.route('/api/set_salary', methods=['POST'])
def set_salary():
    data = request.json
    try:
        salary = float(data.get('salary', ''))
        if salary <= 0:
            return jsonify({"status": "error", "message": "請輸入大於0的數字！"})
        state['salary'] = salary
        return jsonify({"status": "success", "salary": salary})
    except:
        return jsonify({"status": "error", "message": "請輸入大於0的數字！"})


@app.route('/api/set_living_expense', methods=['POST'])
def set_living_expense():
    data = request.json
    try:
        expense = float(data.get('expense', ''))
        if expense < 0:
            return jsonify({"status": "error", "message": "請輸入正確數字！"})
        state['living_expense'] = expense
        return jsonify({"status": "success", "living_expense": expense})
    except:
        return jsonify({"status": "error", "message": "請輸入正確數字！"})


@app.route('/api/set_start_month', methods=['POST'])
def set_start_month():
    data = request.json
    try:
        start_month = int(data.get('start_month', ''))
        if start_month < 1:
            return jsonify({"status": "error", "message": "請輸入大於等於1的整數！"})
        state['start_month'] = start_month
        return jsonify({"status": "success", "start_month": start_month})
    except:
        return jsonify({"status": "error", "message": "請輸入大於等於1的整數！"})


@app.route('/api/calculate', methods=['POST'])
def calculate():
    if state['salary'] <= 0:
        return jsonify({"status": "error", "message": "請先設定薪水（薪水需大於0）！"})
    if state['salary'] < state['living_expense']:
        return jsonify({"status": "error",
                        "message": f"薪水 ({state['salary']:.2f}) 需大於生活費 ({state['living_expense']:.2f})，否則無法還款！"})
    if not state['repay_list'] and not state['course_list']:
        return jsonify({"status": "error", "message": "請先新增還款人或課程！"})

    total_debt = sum(p['debt'] for p in state['repay_list'])
    total_course_fee = sum(c['fee'] for c in state['course_list'])
    monthly_course_fee_total = sum(c['fee'] / c['months'] if c['months'] > 0 else 0 for c in state['course_list'])
    max_course_months = max((c['months'] for c in state['course_list']), default=0)

    remain_debts = [p['debt'] for p in state['repay_list']]
    pay_off_month = [None] * len(state['repay_list'])
    month_records = []
    months = 0
    MAX_MONTHS = 1200

    result = f"每月薪水: {state['salary']:.2f} 元\n"
    result += f"每月生活費: {state['living_expense']:.2f} 元\n"
    result += f"總還款金額: {total_debt:.2f} 元\n"
    result += f"總課程費用: {total_course_fee:.2f} 元\n"
    result += f"每月課程費用總計: {monthly_course_fee_total:.2f} 元\n"
    result += f"最長課程期數: {max_course_months} 月\n"
    result += f"還款起始月: 第 {state['start_month']} 個月\n"
    result += "-" * 50 + "\n"

    while (any(d > 0 for d in remain_debts) or months < max_course_months) and months < MAX_MONTHS:
        months += 1
        current_monthly_course_fee = sum(c['fee'] / c['months'] for c in state['course_list'] if months <= c['months'])
        available_amount = state['salary'] - state['living_expense'] - current_monthly_course_fee
        if available_amount < 0:
            return jsonify({"status": "error", "message": f"第 {months} 月後，生活費與課程費用已超過薪水，試算停止。"})

        pays = [0] * len(remain_debts)
        if months >= state['start_month']:
            debtors_left = sum(1 for d in remain_debts if d > 0)
            if debtors_left == 0 and months >= max_course_months:
                break
            if debtors_left > 0:
                per_person = available_amount // debtors_left
                total_paid = 0
                for i in range(len(remain_debts)):
                    if remain_debts[i] > 0:
                        pay = min(per_person, remain_debts[i])
                        remain_debts[i] -= pay
                        pays[i] = pay
                        total_paid += pay
                        if remain_debts[i] <= 0 and pay_off_month[i] is None:
                            pay_off_month[i] = months
                leftover = available_amount - total_paid
                for i in range(len(remain_debts)):
                    if remain_debts[i] > 0 and leftover > 0:
                        extra = min(remain_debts[i], leftover)
                        remain_debts[i] -= extra
                        pays[i] += extra
                        leftover -= extra
                        if remain_debts[i] <= 0 and pay_off_month[i] is None:
                            pay_off_month[i] = months
        month_records.append((pays, available_amount))

    if months == MAX_MONTHS:
        return jsonify({"status": "error", "message": "試算已達最大月數，可能無法完全還清。"})

    result += f"共試算 {months} 個月完成所有還款與課程繳費。\n\n"
    col_w = 10
    names = [p['name'] for p in state['repay_list']]
    header = f"{'月份':>{col_w}}{'可用資金':>{col_w}}" + "".join(f"{n:>{col_w}}" for n in names)
    result += header + "\n"
    result += "-" * (col_w * (len(names) + 2)) + "\n"
    for m, (record, avail) in enumerate(month_records, 1):
        row = f"{m:>{col_w}}{avail:>{col_w}.2f}" + "".join(f"{int(v):>{col_w}}" for v in record)
        result += row + "\n"
    result += "\n還清月份：\n"
    for i, n in enumerate(names):
        result += f"{n} → 第 {pay_off_month[i] if pay_off_month[i] else '尚未還清'} 個月還清\n"

    state['month_records'] = month_records
    state['names'] = names
    return jsonify({"status": "success", "result": result})


@app.route('/api/export_csv', methods=['GET'])
def export_csv():
    if not state['month_records'] or not state['names']:
        return jsonify({"status": "error", "message": "無試算結果可匯出，請先執行試算"})

    output = io.StringIO()
    writer = csv.writer(output)
    header = ["月份", "可用資金"] + state['names']
    writer.writerow(header)
    for m, (record, avail) in enumerate(state['month_records'], 1):
        writer.writerow([m, f"{avail:.2f}"] + [int(x) for x in record])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='repay_result.csv'
    )


@app.route('/')
def index():
    return app.send_static_file('index.html')


if __name__ == '__main__':
    app.run(debug=True)
