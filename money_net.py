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
CORS(app)  # 啟用跨域請求，允許前端從不同源（如果有的話）請求

# 全局狀態模擬資料庫
# 注意：這是一個簡單的記憶體儲存，當伺服器重啟時，所有資料都會丟失。
state = {
    "salary": 0.0,
    "living_expense": 0.0,
    "start_month": 1,
    "repay_list": [],  # 格式: [{"name": "人A", "debt": 10000.0}]
    "course_list": [], # 格式: [{"fee": 50000.0, "months": 12}]
    "month_records": [], # 計算結果的詳細記錄
    "calculation_summary": "" # 計算結果的文字摘要
}

# 支援載入的靜態頁面清單
allowed_pages = ['index', 'about', 'contact', 'privacy', 'terms']

@app.route('/')
def index():
    """根路由載入 index.html (包含 React 應用)"""
    return send_file(os.path.join(app.root_path, 'template', 'index.html'))

@app.route('/api/pages/<page>')
def load_page(page):
    """動態載入其他靜態頁面 (例如 /api/pages/privacy)"""
    if page in allowed_pages:
        path = os.path.join(app.root_path, 'template', f'{page}.html')
        if os.path.exists(path):
            return send_file(path)
        else:
            return jsonify({"status": "error", "message": f"頁面檔案 {page}.html 不存在"}), 404
    else:
        return jsonify({"status": "error", "message": "無效頁面名稱"}), 404

@app.route('/api/get_current_state', methods=['GET'])
def get_current_state():
    """取得目前所有狀態數據，供前端初始化或同步使用"""
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
    """新增還款人及其欠款金額"""
    data = request.get_json()
    name = data.get('name')
    debt = data.get('debt')

    if not name or not isinstance(name, str) or not name.strip():
        return jsonify({"status": "error", "message": "姓名不能為空"}), 400
    
    # 檢查姓名是否重複
    if any(p['name'] == name.strip() for p in state["repay_list"]):
        return jsonify({"status": "error", "message": f"還款人 '{name.strip()}' 已存在，請使用不同姓名"}), 400

    try:
        debt = float(debt)
        if debt <= 0:
            return jsonify({"status": "error", "message": "欠款金額必須大於0"}), 400
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "欠款金額必須是有效數字"}), 400

    state["repay_list"].append({"name": name.strip(), "debt": debt})
    return jsonify({"status": "success", "message": "還款人新增成功", "repay_list": state["repay_list"]})

@app.route('/api/remove_person', methods=['POST'])
def remove_person():
    """移除還款人"""
    data = request.get_json()
    name_to_remove = data.get('name')

    if not name_to_remove:
        return jsonify({"status": "error", "message": "請提供要移除的還款人姓名"}), 400
    
    original_len = len(state["repay_list"])
    state["repay_list"] = [p for p in state["repay_list"] if p['name'] != name_to_remove]

    if len(state["repay_list"]) == original_len:
        return jsonify({"status": "error", "message": f"找不到還款人 '{name_to_remove}'"}), 404
    
    return jsonify({"status": "success", "message": "還款人移除成功", "repay_list": state["repay_list"]})


@app.route('/api/add_course', methods=['POST'])
def add_course():
    """新增課程費用"""
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

@app.route('/api/remove_course', methods=['POST'])
def remove_course():
    """移除課程費用 (根據索引)"""
    data = request.get_json()
    index_to_remove = data.get('index')

    try:
        index_to_remove = int(index_to_remove)
        if not (0 <= index_to_remove < len(state["course_list"])):
            return jsonify({"status": "error", "message": "無效的課程索引"}), 400
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "課程索引必須是有效數字"}), 400

    del state["course_list"][index_to_remove]
    return jsonify({"status": "success", "message": "課程移除成功", "course_list": state["course_list"]})


@app.route('/api/set_salary', methods=['POST'])
def set_salary():
    """設定每月薪水"""
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
    """設定每月生活費"""
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
    """設定還款起始月份"""
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
    """執行還款計畫的核心計算邏輯"""
    # 從全局狀態獲取最新數據
    salary = state["salary"]
    living_expense = state["living_expense"]
    repay_list = state["repay_list"]
    course_list = state["course_list"]
    start_month = state["start_month"]

    if not repay_list and not course_list:
        return jsonify({"status": "error", "message": "請至少新增還款人或課程費用"}), 400

    if salary <= living_expense:
        return jsonify({"status": "error", "message": f"薪水({salary})必須大於生活費({living_expense})"}), 400

    # 每月可支配收入 (扣除生活費)
    disposable_income = salary - living_expense

    # 初始化債務和課程費用追蹤
    current_person_debts = {p["name"]: p["debt"] for p in repay_list}
    
    # 處理課程費用為每月固定金額
    monthly_course_payments = []
    for i, c in enumerate(course_list):
        if c["months"] > 0:
            monthly_course_payments.append({
                "original_index": i, # 為了方便前端辨識，保留原始索引
                "name": f"課程{i+1}", # 給課程一個預設名稱
                "monthly_amount": c["fee"] / c["months"],
                "remaining_fee": c["fee"], # 追蹤課程總剩餘費用
                "original_months": c["months"] # 紀錄原始期數
            })
        else: # 避免除以零
            monthly_course_payments.append({
                "original_index": i,
                "name": f"課程{i+1}",
                "monthly_amount": 0,
                "remaining_fee": c["fee"],
                "original_months": c["months"]
            })

    month_records = []
    repayment_completion_dates = {}
    course_completion_dates = {}

    current_month_index = 0
    # 動態取得當前年份，確保日期計算從今年開始
    current_datetime = datetime.now() 
    year = current_datetime.year

    # 循環計算直到所有債務和課程費用都還清
    while True:
        # 檢查是否所有債務和課程費用都已清零 (考慮浮點數精度)
        all_debts_cleared = all(v <= 0.001 for v in current_person_debts.values())
        all_courses_cleared = all(c["remaining_fee"] <= 0.001 for c in monthly_course_payments)

        if all_debts_cleared and all_courses_cleared:
            break

        current_month_index += 1
        
        # 計算當前年月
        month_offset = start_month + current_month_index - 1
        calculated_month = (month_offset % 12) + 1
        calculated_year = year + (month_offset // 12)
        date_str = f"{calculated_year}/{calculated_month:02d}"

        month_record = {
            "month_num": current_month_index,
            "date": date_str,
            "disposable_income": disposable_income,
            "total_repaid_this_month": 0.0,
            "remaining_income_this_month": disposable_income, # 本月剩餘可支配收入
            "repayments_detail": {}, # 當月還款給每個還款人的金額
            "course_payments_detail": {}, # 當月繳納課程的金額
            "remaining_person_debts": {k: v for k, v in current_person_debts.items()}, # 本月結束時剩餘的個人債務
            "remaining_course_fees": {c["name"]: c["remaining_fee"] for c in monthly_course_payments} # 本月結束時剩餘的課程總費用
        }

        # --- 優先繳納課程費用 ---
        for i, course_info in enumerate(monthly_course_payments):
            if course_info["remaining_fee"] > 0.001:
                # 實際可支付金額： min(課程每月應繳, 課程總剩餘, 本月可用收入)
                pay_amount_for_course = min(course_info["monthly_amount"], course_info["remaining_fee"], month_record["remaining_income_this_month"])
                
                if pay_amount_for_course > 0:
                    month_record["course_payments_detail"][course_info["name"]] = pay_amount_for_course
                    course_info["remaining_fee"] -= pay_amount_for_course
                    month_record["remaining_income_this_month"] -= pay_amount_for_course
                    
                    if course_info["remaining_fee"] <= 0.001 and course_info["name"] not in course_completion_dates:
                        course_completion_dates[course_info["name"]] = date_str
            
            # 更新剩餘課程費用到 month_record 中
            month_record["remaining_course_fees"][course_info["name"]] = max(0, course_info["remaining_fee"])

        # --- 分配還款給還款人 ---
        remaining_income_for_debts = month_record["remaining_income_this_month"]
        active_debt_names = [name for name, debt in current_person_debts.items() if debt > 0.001]

        if remaining_income_for_debts > 0.001 and active_debt_names:
            total_active_debt = sum(current_person_debts[n] for n in active_debt_names)
            
            # 確保總債務不為零，避免除以零
            if total_active_debt > 0:
                for name in active_debt_names:
                    # 按比例分配，但不能超過單個人的剩餘欠款，也不能超過本月剩餘收入
                    proportion = current_person_debts[name] / total_active_debt
                    pay_amount_for_person = min(proportion * remaining_income_for_debts, current_person_debts[name])
                    
                    if pay_amount_for_person > 0:
                        month_record["repayments_detail"][name] = pay_amount_for_person
                        current_person_debts[name] -= pay_amount_for_person
                        month_record["remaining_income_this_month"] -= pay_amount_for_person
                        
                        if current_person_debts[name] <= 0.001 and name not in repayment_completion_dates:
                            repayment_completion_dates[name] = date_str
        
        # 更新剩餘個人債務到 month_record 中
        month_record["remaining_person_debts"] = {k: max(0, v) for k, v in current_person_debts.items()}

        # 計算當月總還款/繳費金額
        month_record["total_repaid_this_month"] = disposable_income - month_record["remaining_income_this_month"]
        
        month_records.append(month_record)

        # 設定一個最大月數限制，防止無限循環 (例如，如果收入不足以還清)
        if current_month_index > 2000: # 設置一個合理的上限，防止無限循環
            return jsonify({"status": "error", "message": "計算超過2000個月，可能無法還清所有債務。請檢查輸入資料（如薪水、生活費、債務總額）。"}), 500

    # --- 生成結果文字摘要 ---
    result_text = "還款試算結果：\n\n"
    result_text += f"總計還款月數：{current_month_index} 個月\n\n"

    result_text += "還款人繳清日期：\n"
    if repayment_completion_dates:
        for name, date_str in repayment_completion_dates.items():
            result_text += f"  - {name}: {date_str} 繳清\n"
    else:
        result_text += "  - 無還款人或債務已清。\n"
    result_text += "\n"

    result_text += "課程繳清日期：\n"
    if course_completion_dates:
        for name, date_str in course_completion_dates.items():
            result_text += f"  - {name}: {date_str} 繳清\n"
    else:
        result_text += "  - 無課程費用或已繳清。\n"
    result_text += "\n"

    result_text += "每月詳細還款計畫：\n"
    for rec in month_records:
        result_text += f"{rec['date']} (第{rec['month_num']}月):\n"
        result_text += f"  可支配收入 (扣生活費前): {salary:.2f} 元\n"
        result_text += f"  每月生活費: {living_expense:.2f} 元\n"
        result_text += f"  當月實際可支配收入: {rec['disposable_income']:.2f} 元\n"

        if rec["course_payments_detail"]:
            result_text += "  課程繳納:\n"
            for k, v in rec["course_payments_detail"].items():
                result_text += f"    - {k}: {v:.2f} 元\n"
        if rec["repayments_detail"]:
            result_text += "  還款人分配:\n"
            for k, v in rec["repayments_detail"].items():
                result_text += f"    - {k}: {v:.2f} 元\n"
        
        result_text += f"  當月還款/繳費總計: {rec['total_repaid_this_month']:.2f} 元\n"
        result_text += f"  當月剩餘可支配收入: {rec['remaining_income_this_month']:.2f} 元\n"
        
        # 輸出本月結束時的剩餘債務/費用
        remaining_person_debts_str = ", ".join([f"{k}: {v:.2f}" for k, v in rec["remaining_person_debts"].items() if v > 0.001])
        if remaining_person_debts_str:
            result_text += f"  本月結束剩餘個人債務: {remaining_person_debts_str} 元\n"
        
        remaining_course_fees_str = ", ".join([f"{k}: {v:.2f}" for k, v in rec["remaining_course_fees"].items() if v > 0.001])
        if remaining_course_fees_str:
            result_text += f"  本月結束剩餘課程費用: {remaining_course_fees_str} 元\n"
        
        result_text += "----------------------------------------\n"

    state["month_records"] = month_records
    state["calculation_summary"] = result_text

    # --- 返回結構化數據給前端 ---
    total_debt_sum = sum(p["debt"] for p in repay_list)
    total_course_fee_sum = sum(c["fee"] for c in course_list)

    return jsonify({
        "status": "success",
        "message": "計算完成",
        "total_debt": total_debt_sum,
        "monthly_repay_budget": disposable_income, # 可以是可支配收入，或者更精確的「扣除課程後剩餘」
        "total_course_monthly_fee": sum(mp["monthly_amount"] for mp in monthly_course_payments), # 所有課程每月總額
        "total_months": current_month_index,
        "plan": month_records, # 詳細的每月計畫，前端可用來渲染表格
        "repay_completion_dates": repayment_completion_dates,
        "course_completion_dates": course_completion_dates,
        "summary_text": result_text # 仍然保留完整的文字摘要
    })

@app.route('/api/export_csv', methods=['GET'])
def export_csv():
    """匯出計算結果為 CSV 檔案"""
    if not state["month_records"]:
        return jsonify({"status": "error", "message": "請先執行計算才能匯出CSV"}), 400

    output = io.StringIO()
    df_rows = []

    # 獲取所有還款人名稱和課程名稱，用於 CSV 標頭
    all_person_names = sorted(set(p["name"] for p in state["repay_list"]))
    all_course_names = sorted(set(f"課程{c['original_index']+1}" for c in state["month_records"][0].get("remaining_course_fees", {}).keys())) # 從第一個record獲取課程名稱

    for rec in state["month_records"]:
        row = {
            "月份": rec["date"],
            "可支配收入_每月": rec["disposable_income"], # 每月總可支配收入
            "當月還款繳費總計": rec["total_repaid_this_month"],
            "當月剩餘可支配收入": rec["remaining_income_this_month"],
        }
        
        # 加入個人還款與剩餘債務
        for name in all_person_names:
            row[f"{name}_當月還款"] = rec["repayments_detail"].get(name, 0.0)
            row[f"{name}_剩餘債務"] = rec["remaining_person_debts"].get(name, 0.0)
        
        # 加入課程繳費與剩餘費用
        for cname in all_course_names:
            row[f"{cname}_當月繳費"] = rec["course_payments_detail"].get(cname, 0.0)
            row[f"{cname}_剩餘總費用"] = rec["remaining_course_fees"].get(cname, 0.0)

        df_rows.append(row)

    df = pd.DataFrame(df_rows)
    df.to_csv(output, index=False, encoding='utf-8-sig') # 'utf-8-sig' 支援中文
    output.seek(0) # 將文件指針移回開頭

    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype="text/csv",
        as_attachment=True,
        download_name="repayment_plan.csv"
    )

# 啟動背景 Ping 例子（例如在 Render.com 等免費服務上保持活躍）
def background_ping():
    while True:
        try:
            # 這裡的 URL 應該是你實際部署後，能夠被外部訪問的 URL
            # 如果是本地運行，這行可以註釋掉或修改為你本地的地址
            # 例如: requests.get("http://localhost:5000/") 
            pass # 暫時不執行實際的 ping，因為在本地通常不需要
        except Exception as e:
            print(f"Background ping failed: {e}")
        time.sleep(60 * 60) # 每小時 ping 一次

def start_background_task():
    t = threading.Thread(target=background_ping, daemon=True)
    t.start()

if __name__ == '__main__':
    # start_background_task() # 如果你部署到像 Render.com 這樣的平台，才需要啟用
    # 本地開發時，通常不需要 background ping
    app.run(host="0.0.0.0", port=5000, debug=True)
