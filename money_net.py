import requests  # 確保最上面有匯入
import threading
import time
import os
import io
import pandas as pd
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # 啟用 CORS，允許所有來源的跨域請求，方便開發

# 全局狀態，用於模擬數據庫。在生產環境應替換為實際數據庫。
state = {
    "salary": 0.0,
    "living_expense": 0.0,
    "start_month": 1,   # 1-12
    "repay_list": [],   # [{"name": "小明", "debt": 10000.0}]
    "course_list": [], # [{"fee": 30000.0, "months": 6}]
    "month_records": [], # 計算結果的詳細記錄，用於 CSV 匯出
    "calculation_summary": "" # 計算結果的文字摘要
}

# 根路由，提供前端文件
@app.route('/')
def index():
    """
    提供位於 'template' 資料夾中的 index.html 檔案。
    """
    # 使用 os.path.join 來構建正確的檔案路徑，確保跨作業系統的相容性
    # app.root_path 會指向 money_net.py 所在的目錄
    return send_file(os.path.join(app.root_path, 'template', 'index.html'))

# API 路由區塊

@app.route('/api/get_current_state', methods=['GET'])
def get_current_state():
    """提供當前所有儲存的狀態數據給前端"""
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
        if not (isinstance(months, int) and months > 0):
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
        if not (1 <= start_month <= 12):
            return jsonify({"status": "error", "message": "起始月份必須介於1到12"}), 400
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "起始月份必須是有效數字"}), 400

    state["start_month"] = start_month
    return jsonify({"status": "success", "message": "起始月份設定成功", "start_month": state["start_month"]})


@app.route('/api/calculate', methods=['POST'])
def calculate_repayment():
    """執行還款試算並更新全局狀態"""
    salary = state["salary"]
    living_expense = state["living_expense"]
    repay_list = state["repay_list"]
    course_list = state["course_list"]
    start_month_num = state["start_month"]

    if not repay_list and not course_list:
        return jsonify({"status": "error", "message": "請至少新增一位還款人或一筆課程費用以進行計算"}), 400
    
    if salary <= living_expense:
        return jsonify({"status": "error", "message": f"薪水 {salary} 元必須大於生活費 {living_expense} 元才能有餘額還款。"}), 400

    disposable_income = salary - living_expense

    total_debt = sum(item["debt"] for item in repay_list)
    total_course_fee = sum(item["fee"] for item in course_list)

    # 初始化每月還款數據
    monthly_repayments = {item["name"]: 0.0 for item in repay_list}
    monthly_course_payments = []
    
    # 計算課程每期還款金額
    for i, course in enumerate(course_list):
        monthly_course_payments.append({
            "name": f"課程{i+1}",
            "monthly_amount": course["fee"] / course["months"],
            "remaining_months": course["months"]
        })

    # 月度記錄
    month_records = []
    current_month_index = 0 # 從第0個月開始計數，方便計算日期
    current_debt_remaining = total_debt
    current_course_remaining_fees = [c["fee"] for c in course_list]

    # 還款人債務的可變副本
    current_person_debts = {person["name"]: person["debt"] for person in repay_list}

    # 紀錄每個還款人何時還清
    repayment_completion_dates = {}
    
    # 紀錄每個課程何時繳清
    course_completion_dates = {}

    while current_debt_remaining > 0.001 or any(f > 0.001 for f in current_course_remaining_fees):
        current_date = datetime(2025, start_month_num, 1) + timedelta(days=30 * current_month_index) # 僅供顯示
        display_month = (start_month_num + current_month_index - 1) % 12 + 1
        display_year = current_date.year # 獲取正確年份

        month_record = {
            "month_num": current_month_index + 1,
            "date": f"{display_year}/{display_month:02d}",
            "disposable_income": disposable_income,
            "total_repaid_this_month": 0.0,
            "remaining_income": disposable_income,
            "repayments_detail": {},
            "course_payments_detail": {},
            "remaining_person_debts": {},
            "remaining_course_fees": {}
        }

        # 先處理課程繳費
        course_payment_this_month = 0.0
        for i, course_item in enumerate(monthly_course_payments):
            if current_course_remaining_fees[i] > 0.001: # 該課程還有餘額
                payment_due = course_item["monthly_amount"]
                actual_payment = min(payment_due, current_course_remaining_fees[i], month_record["remaining_income"])
                
                if actual_payment > 0:
                    month_record["course_payments_detail"][course_item["name"]] = actual_payment
                    current_course_remaining_fees[i] -= actual_payment
                    month_record["remaining_income"] -= actual_payment
                    course_payment_this_month += actual_payment

                    if current_course_remaining_fees[i] <= 0.001 and course_item["name"] not in course_completion_dates:
                        course_completion_dates[course_item["name"]] = f"{display_year}/{display_month:02d}"
            month_record["remaining_course_fees"][course_item["name"]] = max(0, current_course_remaining_fees[i])


        # 然後處理還款人還款 (如果有餘額)
        remaining_to_distribute = month_record["remaining_income"]
        if remaining_to_distribute > 0.001 and current_debt_remaining > 0.001:
            # 計算未還清的還款人總債務
            active_repay_list = [p for p in repay_list if current_person_debts[p["name"]] > 0.001]
            if not active_repay_list:
                break # 所有還款人都還清了

            total_active_debt = sum(current_person_debts[p["name"]] for p in active_repay_list)

            # 按照比例分配剩餘可支配收入
            for person in active_repay_list:
                name = person["name"]
                if current_person_debts[name] > 0.001:
                    proportion = current_person_debts[name] / total_active_debt
                    payment = min(remaining_to_distribute * proportion, current_person_debts[name])
                    
                    if payment > 0:
                        month_record["repayments_detail"][name] = payment
                        current_person_debts[name] -= payment
                        current_debt_remaining -= payment
                        month_record["remaining_income"] -= payment # 更新剩餘可支配收入

                        if current_person_debts[name] <= 0.001 and name not in repayment_completion_dates:
                            repayment_completion_dates[name] = f"{display_year}/{display_month:02d}"

        month_record["total_repaid_this_month"] = disposable_income - month_record["remaining_income"]

        # 記錄每個人當月剩餘債務
        for person in repay_list:
            month_record["remaining_person_debts"][person["name"]] = max(0, current_person_debts[person["name"]])

        # 檢查是否所有課程都已繳清
        all_courses_paid = all(f <= 0.001 for f in current_course_remaining_fees)
        
        # 檢查是否所有還款人債務都已還清
        all_debts_paid = current_debt_remaining <= 0.001

        # 更新剩餘課程費用狀態
        for i, course_item in enumerate(monthly_course_payments):
            month_record["remaining_course_fees"][course_item["name"]] = max(0, current_course_remaining_fees[i])


        month_records.append(month_record)
        current_month_index += 1

        if current_month_index > 2000: # 設定一個上限，避免無限循環
            return jsonify({"status": "error", "message": "計算時間過長，可能存在無限循環或數據量過大。"}), 500

    # 生成摘要結果
    result_text = "還款試算結果：\n\n"
    
    result_text += f"總月數：{current_month_index} 個月\n\n"
    
    result_text += "還款人還清時間：\n"
    if not repayment_completion_dates and repay_list:
        result_text += "   - 所有還款人債務已在計算開始前還清，或無需償還。\n"
    elif not repay_list:
        result_text += "   - 無還款人。\n"
    else:
        for name, date_str in repayment_completion_dates.items():
            result_text += f"   - {name}: {date_str} 還清\n"
    result_text += "\n"

    result_text += "課程繳清時間：\n"
    if not course_completion_dates and course_list:
        result_text += "   - 所有課程費用已在計算開始前繳清，或無需繳納。\n"
    elif not course_list:
        result_text += "   - 無課程費用。\n"
    else:
        for name, date_str in course_completion_dates.items():
            result_text += f"   - {name}: {date_str} 繳清\n"
    result_text += "\n"

    result_text += "每月詳細還款計畫：\n"
    for record in month_records:
        result_text += f"月份: {record['date']} (第 {record['month_num']} 月)\n"
        result_text += f"   可支配收入: {record['disposable_income']:.2f} 元\n"
        
        if record["course_payments_detail"]:
            result_text += "   課程繳納:\n"
            for course_name, amount in record["course_payments_detail"].items():
                result_text += f"     - {course_name}: {amount:.2f} 元\n"
        
        if record["repayments_detail"]:
            result_text += "   還款人分配:\n"
            for name, amount in record["repayments_detail"].items():
                result_text += f"     - {name}: {amount:.2f} 元\n"
        
        result_text += f"   當月總計還款/繳費: {record['total_repaid_this_month']:.2f} 元\n"
        result_text += f"   當月剩餘可支配收入: {record['remaining_income']:.2f} 元\n"
        
        # 顯示當月結束後的剩餘債務和課程費用
        if any(v > 0.001 for v in record['remaining_person_debts'].values()):
            result_text += "   還款人剩餘債務:\n"
            for name, debt in record['remaining_person_debts'].items():
                if debt > 0.001:
                    result_text += f"     - {name}: {debt:.2f} 元\n"
        
        if any(v > 0.001 for v in record['remaining_course_fees'].values()):
            result_text += "   課程剩餘費用:\n"
            for name, fee in record['remaining_course_fees'].items():
                if fee > 0.001:
                    result_text += f"     - {name}: {fee:.2f} 元\n"
        result_text += "--------------------------------------\n"

    state["month_records"] = month_records # 儲存詳細記錄
    state["calculation_summary"] = result_text # 儲存摘要

    return jsonify({"status": "success", "message": "計算完成", "result": result_text})

@app.route('/api/export_csv', methods=['GET'])
def export_csv():
    """匯出計算結果為 CSV 檔案"""
    if not state["month_records"]:
        return jsonify({"status": "error", "message": "請先執行計算才能匯出 CSV"}), 400

    # 準備 DataFrame 的數據
    csv_data = []
    
    # 獲取所有還款人和課程名稱作為列名
    all_names = sorted(list(set(p["name"] for p in state["repay_list"])))
    all_course_names = sorted([f"課程{i+1}" for i in range(len(state["course_list"]))])

    for record in state["month_records"]:
        row = {
            "月份": record["date"],
            "可支配收入": record["disposable_income"],
            "當月總計還款_繳費": record["total_repaid_this_month"],
            "當月剩餘可支配收入": record["remaining_income"],
        }
        
        # 還款人當月還款
        for name in all_names:
            row[f"{name}_當月還款"] = record["repayments_detail"].get(name, 0.0)

        # 課程當月繳費
        for course_name in all_course_names:
            row[f"{course_name}_當月繳費"] = record["course_payments_detail"].get(course_name, 0.0)

        # 還款人剩餘債務
        for name in all_names:
            row[f"{name}_剩餘債務"] = record["remaining_person_debts"].get(name, 0.0)

        # 課程剩餘費用
        for course_name in all_course_names:
            row[f"{course_name}_剩餘費用"] = record["remaining_course_fees"].get(course_name, 0.0)
            
        csv_data.append(row)

    df = pd.DataFrame(csv_data)

    # 將 DataFrame 寫入 CSV 格式的 StringIO 物件
    output = io.StringIO()
    df.to_csv(output, index=False, encoding='utf-8-sig') # utf-8-sig 處理中文亂碼
    output.seek(0)

    # 返回 CSV 文件
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')), # 再次編碼以確保正確傳輸
        mimetype='text/csv',
        as_attachment=True,
        download_name='repayment_plan.csv'
    )

@app.route('/api/reset', methods=['POST'])
def reset_data():
    """清空所有數據"""
    global state # 聲明使用全局變數
    state = {
        "salary": 0.0,
        "living_expense": 0.0,
        "start_month": 1,
        "repay_list": [],
        "course_list": [],
        "month_records": [],
        "calculation_summary": ""
    }
    return jsonify({"status": "success", "message": "所有資料已清空！"})

# 每五分鐘使用無頭瀏覽器訪問網頁的後台任務

def ping_webpage_periodically(interval_minutes):
    """
    每隔 interval_minutes 分鐘，使用 requests 發送 GET 請求保活
    """
    interval_seconds = interval_minutes * 60
    URL_TO_VISIT = "https://test-10-2h45.onrender.com"

    print(f"\n[後台訪問] 已啟動背景任務：每 {interval_minutes} 分鐘發送 GET 請求到 {URL_TO_VISIT}")

    while True:
        try:
            response = requests.get(URL_TO_VISIT)
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] PING: {response.status_code}")
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] PING ERROR: {e}")
        
        time.sleep(interval_seconds)
# 運行 Flask 應用
if __name__ == '__main__':
    # 檢查 index.html 是否存在於 template 資料夾中
    template_path = os.path.join(app.root_path, 'template', 'index.html')
    if not os.path.exists(template_path):
        print(f"錯誤：index.html 檔案未找到。請確保 index.html 位於 '{os.path.join(app.root_path, 'template')}' 資料夾中。")
        print("程式將退出。")
        exit()

    # 自動開啟瀏覽器的函式 (保留原有功能，在伺服器啟動時開啟一次可見的瀏覽器)
    def open_browser_on_startup():
        time.sleep(1)   # 稍微延遲，確保 server 有啟動再開瀏覽器
        try:
            # 這裡開啟的是本地 Flask 應用程式
            webbrowser.open("http://127.0.0.1:5000/")
            print("\n[啟動] 已在瀏覽器中開啟 http://127.0.0.1:5000/")
        except Exception as e:
            print(f"\n[啟動] 開啟瀏覽器失敗: {e}")

    # 啟動瀏覽器線程，在程式啟動時開啟一次本地網頁
    threading.Thread(target=open_browser_on_startup).start()

    # **新增：啟動每五分鐘使用無頭瀏覽器訪問網頁的後台線程**
    # 這個線程將在後台運行，不會彈出視窗
    threading.Thread(target=ping_webpage_periodically, args=(5,), daemon=True).start()
    # daemon=True 會讓這個線程在主程式（Flask 應用）結束時自動終止。

    # 啟動 Flask server
    # 注意：在開發環境下 (debug=True) Flask 會啟動兩個進程（一個用於主應用，一個用於重新加載器），
    # 這可能會導致 Selenium 驅動或自動開啟瀏覽器的線程被啟動兩次。
    # 如果您看到重複的初始化訊息，這是預期行為。
    # 在生產環境中，您會使用 Gunicorn 或 uWSGI 等 WSGI 服務器，它們通常只運行一個進程。
