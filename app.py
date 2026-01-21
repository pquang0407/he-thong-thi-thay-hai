import os
import json
import pandas as pd
import shutil
import uuid
import hashlib
import subprocess
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'super_secret_key_chong_gian_lan_2026'

# --- CẤU HÌNH HỆ THỐNG ĐA NGƯỜI DÙNG ---
BASE_DATA_DIR = 'instance'
ADMINS_FILE = 'instance/admins.json'
BACKUP_FOLDER = 'instance/backups'

# Khởi tạo các thư mục cơ bản nếu chưa có
for folder in [BASE_DATA_DIR, BACKUP_FOLDER, 'static/uploads', 'static/solutions']:
    if not os.path.exists(folder):
        os.makedirs(folder)

# --- QUẢN LÝ DỮ LIỆU CÔ LẬP (MỖI ADMIN 1 KHO) ---
def get_paths(admin_id):
    """Tạo đường dẫn thư mục riêng biệt cho từng thầy cô"""
    folder = os.path.join(BASE_DATA_DIR, admin_id)
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    # Thư mục static riêng cho file PDF của từng admin
    up_path = os.path.join('static/uploads', admin_id)
    sol_path = os.path.join('static/solutions', admin_id)
    for p in [up_path, sol_path]:
        if not os.path.exists(p): os.makedirs(p)
        
    return {
        "exams": os.path.join(folder, 'exams.json'),
        "users": os.path.join(folder, 'users.json'),
        "scores": os.path.join(folder, 'scores.json'),
        "uploads": up_path,
        "solutions": sol_path
    }

def load_json(path):
    """Sửa lỗi JSONDecodeError khi file hỏng hoặc rỗng"""
    if not os.path.exists(path):
        return [] if "scores" in path else {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content: return [] if "scores" in path else {}
            return json.loads(content)
    except:
        return [] if "scores" in path else {}

def save_json(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    
    if "exams.json" in path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        admin_name = os.path.basename(os.path.dirname(path))
        shutil.copy2(path, os.path.join(BACKUP_FOLDER, f"backup_{admin_name}_{timestamp}.json"))

# --- BẢO MẬT: KIỂM TRA THIẾT BỊ ---
@app.before_request
def security_check():
    allowed_routes = ['login', 'logout', 'static', 'index']
    if request.endpoint in allowed_routes or not request.endpoint: return

    # 1. Bảo mật Admin: Khóa chặt vào thiết bị đầu tiên đăng nhập
    if session.get('user_role') == 'admin':
        admins = load_json(ADMINS_FILE)
        admin_id = session.get('admin_id')
        if admins.get(admin_id, {}).get('device_id') != session.get('device_token'):
            session.clear()
            flash("Thiết bị không hợp lệ! Admin chỉ được dùng trên máy đã đăng ký.")
            return redirect(url_for('login'))

    # 2. Bảo mật Học sinh: 1 thiết bị tại 1 thời điểm
    if session.get('user_role') == 'student':
        paths = get_paths(session.get('owner_id'))
        users = load_json(paths['users'])
        student = session.get('student_name')
        if users.get(student, {}).get('current_session') != session.get('session_token'):
            session.clear()
            flash("Tài khoản của bạn đã được đăng nhập từ thiết bị khác!")
            return redirect(url_for('login'))

# --- ROUTES ĐĂNG NHẬP ---

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        role = request.form.get('role')
        admins = load_json(ADMINS_FILE)
        
        if role == 'teacher':
            user_id = request.form.get('admin_username')
            password = request.form.get('admin_pass')
            fingerprint = request.form.get('device_fingerprint')
            
            if user_id in admins and admins[user_id]['password'] == password:
                if not admins[user_id].get('device_id'):
                    admins[user_id]['device_id'] = fingerprint
                    save_json(admins, ADMINS_FILE)
                
                if admins[user_id]['device_id'] == fingerprint:
                    session.update({
                        'user_role': 'admin', 'admin_id': user_id, 
                        'device_token': fingerprint, 'teacher_name': admins[user_id]['name']
                    })
                    return redirect(url_for('admin_dashboard'))
                else:
                    flash("Lỗi: Tài khoản Admin chỉ dùng được trên máy đã đăng ký!")
            else:
                flash("Sai tài khoản hoặc mật khẩu Quản trị!")

        else: # Học sinh đăng nhập
            fullname = request.form.get('fullname')
            class_name = request.form.get('class_name')
            teacher_code = request.form.get('teacher_code')
            
            if teacher_code in admins:
                if request.form.get('student_pass') == "HS1234":
                    paths = get_paths(teacher_code)
                    users = load_json(paths['users'])
                    if fullname not in users:
                        users[fullname] = {"balance": 0, "purchased": [], "class": class_name, "pending_topups": []}
                    
                    new_token = str(uuid.uuid4())
                    users[fullname]['current_session'] = new_token
                    save_json(users, paths['users'])
                    
                    session.update({
                        'user_role': 'student', 'student_name': fullname, 
                        'student_class': class_name, 'owner_id': teacher_code, 
                        'session_token': new_token, 'teacher_name': admins[teacher_code]['name']
                    })
                    return redirect(url_for('dashboard'))
                else:
                    flash("Mật khẩu học sinh không chính xác!")
            else:
                flash("Mã giáo viên không tồn tại!")

    return render_template('login.html', teacher_name="HỆ THỐNG LUYỆN THI")

# --- ROUTES ADMIN (DỮ LIỆU RIÊNG) ---

@app.route('/admin')
def admin_dashboard():
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    paths = get_paths(session['admin_id'])
    exams = load_json(paths['exams'])
    users = load_json(paths['users'])
    waiting_list = []
    for name, data in users.items():
        for req in data.get('pending_topups', []):
            waiting_list.append({"name": name, "amount": req['amount'], "time": req['time'], "id": req['id']})
    return render_template('admin.html', teacher_name=session['teacher_name'], exams=exams, waiting_list=waiting_list)

@app.route('/admin/grades')
def admin_grades():
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    paths = get_paths(session['admin_id'])
    scores = load_json(paths['scores'])
    grades = sorted(list(set(item['grade'] for item in scores))) if scores else []
    return render_template('admin_grades.html', grades=grades, teacher_name=session['teacher_name'])

@app.route('/admin/grades/<grade_name>')
def admin_class_scores(grade_name):
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    paths = get_paths(session['admin_id'])
    all_scores = load_json(paths['scores'])
    class_scores = [s for s in all_scores if s['grade'] == grade_name]
    return render_template('admin_class_scores.html', grade_name=grade_name, scores=class_scores, teacher_name=session['teacher_name'])

@app.route('/admin/approve_topup', methods=['POST'])
def approve_topup():
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    student_name, req_id = request.form.get('student_name'), request.form.get('req_id')
    paths = get_paths(session['admin_id'])
    users = load_json(paths['users'])
    if student_name in users:
        for req in users[student_name]['pending_topups']:
            if req['id'] == req_id:
                users[student_name]['balance'] += req['amount']
                break
        users[student_name]['pending_topups'] = [r for r in users[student_name]['pending_topups'] if r['id'] != req_id]
        save_json(users, paths['users'])
    return redirect(url_for('admin_dashboard'))

@app.route('/add_exam', methods=['POST'])
def add_exam():
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    paths = get_paths(session['admin_id'])
    exams = load_json(paths['exams'])
    ma_de = request.form.get('ma_de')
    
    f_pdf = request.files.get('file_pdf')
    pdf_url = ""
    if f_pdf and f_pdf.filename != '':
        fname = secure_filename(f"de_{ma_de}.pdf")
        f_pdf.save(os.path.join(paths['uploads'], fname))
        pdf_url = f"/{paths['uploads']}/{fname}"

    f_sol = request.files.get('file_sol')
    sol_url = ""
    if f_sol and f_sol.filename != '':
        fname = secure_filename(f"sol_{ma_de}.pdf")
        f_sol.save(os.path.join(paths['solutions'], fname))
        sol_url = f"/{paths['solutions']}/{fname}"

    file_ans = request.files.get('file_ans')
    p1, p2, p3, p2_type = "", "", "", "TF"
    if file_ans:
        try:
            df = pd.read_excel(file_ans)
            df.columns = [str(col).strip() for col in df.columns]
            def get_ans(phan):
                res = df[df['Phan'].astype(str).str.strip().str.upper() == phan.upper()]['DapAn']
                return str(res.values[0]).strip() if not res.empty else ""
            p1, p2, p3 = get_ans('P1'), get_ans('P2'), get_ans('P3')
            if p2 and not any(x in p2.upper() for x in ['Đ', 'S']): p2_type = "MC"
        except: pass

    exams[ma_de] = {
        "name": request.form.get('ten_de'), "grade": request.form.get('khoi_lop'),
        "time": request.form.get('thoi_gian'), "pdf": pdf_url, "solution": sol_url,
        "p1": p1, "p2": p2, "p2_type": p2_type, "p3": p3, "price": 10000
    }
    save_json(exams, paths['exams'])
    return redirect(url_for('admin_dashboard'))

@app.route('/delete_exam', methods=['POST'])
def delete_exam():
    if session.get('user_role') != 'admin': return redirect(url_for('login'))
    paths = get_paths(session['admin_id'])
    exams = load_json(paths['exams'])
    ma_de = request.form.get('ma_de_xoa')
    if ma_de in exams:
        for key in ['pdf', 'solution']:
            path = exams[ma_de].get(key)
            if path:
                full_p = os.path.join(os.getcwd(), path.lstrip('/'))
                if os.path.exists(full_p): os.remove(full_p)
        del exams[ma_de]
        save_json(exams, paths['exams'])
    return redirect(url_for('admin_dashboard'))

# --- HỌC SINH ---

@app.route('/dashboard')
def dashboard():
    if session.get('user_role') != 'student': return redirect(url_for('login'))
    paths = get_paths(session['owner_id'])
    users = load_json(paths['users'])
    student_data = users.get(session['student_name'], {"balance": 0, "purchased": []})
    return render_template('dashboard.html', teacher_name=session['teacher_name'], exams=load_json(paths['exams']), 
                           user_balance=student_data['balance'], purchased_list=student_data.get('purchased', []))

@app.route('/profile')
def profile():
    if 'student_name' not in session: return redirect(url_for('login'))
    paths = get_paths(session['owner_id'])
    user_data = load_json(paths['users']).get(session['student_name'], {"balance": 0})
    return render_template('profile.html', user=user_data)

@app.route('/topup', methods=['POST'])
def topup():
    """Gửi thông báo chờ duyệt nạp tiền thủ công cho giáo viên"""
    paths = get_paths(session['owner_id'])
    users = load_json(paths['users'])
    student = session['student_name']
    
    # Ở bản Zalo, amount sẽ được giáo viên nạp thủ công. 
    # Nút này chỉ để 'đánh tiếng' trong danh sách duyệt của Admin.
    new_req = {
        "id": datetime.now().strftime("%f"), 
        "amount": 0, # Chờ giáo viên nhập số tiền thực tế
        "time": datetime.now().strftime("%H:%M %d/%m"),
        "status": "pending"
    }
    if "pending_topups" not in users[student]: users[student]["pending_topups"] = []
    users[student]["pending_topups"].append(new_req)
    save_json(users, paths['users'])
    flash("Đã gửi thông báo! Thầy Hải sẽ kiểm tra tin nhắn Zalo của bạn.")
    return redirect(url_for('profile'))

@app.route('/buy_solution/<ma_de>')
def buy_solution(ma_de):
    paths = get_paths(session['owner_id'])
    users = load_json(paths['users'])
    student = session['student_name']
    if ma_de in users[student]['purchased']: return redirect(url_for('view_sol', ma_de=ma_de))
    
    if users[student]['balance'] >= 10000:
        users[student]['balance'] -= 10000
        users[student]['purchased'].append(ma_de)
        save_json(users, paths['users'])
        flash("Mở khóa bài giải thành công!")
        return redirect(url_for('dashboard'))
    flash("Số dư không đủ! Hãy liên hệ Zalo Thầy Hải để nạp thêm.")
    return redirect(url_for('profile'))

@app.route('/view_sol/<ma_de>')
def view_sol(ma_de):
    paths = get_paths(session['owner_id'])
    users = load_json(paths['users'])
    if ma_de not in users[session['student_name']]['purchased']: return "Bạn chưa mua bài giải này!"
    exam = load_json(paths['exams']).get(ma_de)
    return render_template('view_solution.html', sol_url=exam['solution'])

# --- CHẤM ĐIỂM ---

@app.route('/exam/<exam_id>')
def exam_page(exam_id):
    if session.get('user_role') != 'student': return redirect(url_for('login'))
    paths = get_paths(session['owner_id'])
    return render_template('exam.html', exam=load_json(paths['exams']).get(exam_id), exam_id=exam_id)

@app.route('/submit_exam/<exam_id>', methods=['POST'])
def submit_exam(exam_id):
    if session.get('user_role') != 'student': return redirect(url_for('login'))
    paths = get_paths(session['owner_id'])
    exam = load_json(paths['exams']).get(exam_id)
    score = 0.0
    detail = {"p1": [], "p2": [], "p3": []}
    
    # Phần I (0.25đ/câu)
    ans_p1 = exam.get('p1', "")
    for i in range(1, 19):
        st = request.form.get(f'p1_q{i}', "").upper()
        cr = ans_p1[i-1].upper() if i <= len(ans_p1) else ""
        if st == cr and st != "": score += 0.25
        detail["p1"].append({"q": i, "st": st, "cr": cr, "ok": (st == cr and st != "")})

    # Phần II (Đúng/Sai 2025)
    ans_p2_list = exam.get('p2', "").split(';')
    p2_type = exam.get('p2_type', 'TF')
    for i in range(1, 5):
        if p2_type == "TF":
            raw_cr = ans_p2_list[i-1].upper() if (i-1) < len(ans_p2_list) else ""
            cr_clean = "".join([x for x in raw_cr if x in ['Đ', 'S']])
            sub, count = [], 0
            for j, label in enumerate(['a', 'b', 'c', 'd']):
                st_v = request.form.get(f'p2_q{i}_{label.upper()}', "").upper()
                cr_v = cr_clean[j] if j < len(cr_clean) else ""
                if st_v == cr_v and st_v != "": count += 1
                sub.append({"label": label, "st": st_v, "cr": cr_v, "ok": (st_v == cr_v)})
            pts = {1: 0.1, 2: 0.25, 3: 0.5, 4: 1.0}.get(count, 0)
            score += pts
            detail["p2"].append({"q": i, "type": "TF", "sub": sub, "points": pts})
        else:
            st = request.form.get(f'p2_q{i}_MC', "").upper()
            cr = ans_p2_list[i-1].upper() if (i-1) < len(ans_p2_list) else ""
            if st == cr and st != "": score += 0.25
            detail["p2"].append({"q": i, "type": "MC", "st": st, "cr": cr, "ok": (st == cr)})

    # Phần III (0.25đ/câu)
    ans_p3 = exam.get('p3', "").split(';')
    for i in range(1, 7):
        st = request.form.get(f'p3_q{i}', "").strip().replace(',', '.')
        cr = ans_p3[i-1].strip().replace(',', '.') if (i-1) < len(ans_p3) else ""
        if st == cr and st != "": score += 0.25
        detail["p3"].append({"q": i, "st": st, "cr": cr, "ok": (st == cr and st != "")})

    # Lưu điểm vào hệ thống
    all_scores = load_json(paths['scores'])
    all_scores.append({
        "student_name": session['student_name'], "exam_id": exam_id,
        "exam_name": exam['name'], "grade": exam['grade'], "class": session.get('student_class'),
        "score": round(score, 2), "time": datetime.now().strftime("%H:%M %d/%m/%Y")
    })
    save_json(all_scores, paths['scores'])
    return render_template('results.html', score=round(score, 2), detail=detail, exam_id=exam_id, exam_name=exam['name'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
