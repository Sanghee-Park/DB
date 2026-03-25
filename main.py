# 파일명: main.py

import warnings
import os
import json
import base64
import threading
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from datetime import datetime

import database 
from ui_daum import DaumTabUI
from ui_jobkorea import JobKoreaTabUI
from blocklist import BlockList
from updater import extract_update_info, is_newer_version, download_update_file, run_update_file

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

CURRENT_VERSION = "1.1"
AUTH_FILE = "auth_config.json"
UPDATE_DIR = "updates"

class IntegratedExtractorApp(ctk.CTk):
    def __init__(self, user_info):
        super().__init__()
        self.user_info = user_info
        self.blocklist = BlockList()
        self.run_semaphore = threading.BoundedSemaphore(2)
        
        self.user_plan = str(user_info.get('Plan', '무료')).strip()
        self.user_name = str(user_info.get('Name', '')).strip()
        if not self.user_name:
            self.user_name = "VIP 회원"
        
        raw_expiry = str(user_info.get('Expiry', '1970-01-01')).strip()
        try:
            expiry_date = datetime.strptime(raw_expiry, "%Y-%m-%d")
            self.days_left = max(0, (expiry_date - datetime.now()).days + 1)
        except ValueError:
            self.days_left = 0 
        
        self.title(f"B2B 통합 DB 추출기 PRO v{CURRENT_VERSION}")
        self.geometry("900x800")
        
        self.setup_header()
        
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(padx=20, pady=10, fill="both", expand=True)
        
        tab_daum = self.tabview.add("🔍 포털(Daum)")
        tab_jobkorea = self.tabview.add("🏢 잡코리아")
        
        DaumTabUI(tab_daum, plan=self.user_plan, blocklist=self.blocklist, run_semaphore=self.run_semaphore).pack(fill="both", expand=True)
        JobKoreaTabUI(tab_jobkorea, plan=self.user_plan, blocklist=self.blocklist, run_semaphore=self.run_semaphore).pack(fill="both", expand=True)
        self.after(800, self.check_update_in_background)

    def check_update_in_background(self):
        def worker():
            try:
                if not database.sheet:
                    return
                all_users = database.sheet.get_all_records()
                latest_version, update_link = extract_update_info(all_users, getattr(database, "version_sheet", None))
                if latest_version and is_newer_version(latest_version, CURRENT_VERSION):
                    self.after(0, lambda: self.ask_auto_update(latest_version, update_link))
            except Exception:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def ask_auto_update(self, latest_version, update_link):
        ans = messagebox.askyesno(
            "자동 업데이트",
            f"새 버전(v{latest_version})이 있습니다.\n지금 자동 업데이트를 진행할까요?"
        )
        if not ans:
            return
        try:
            target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), UPDATE_DIR)
            file_path = download_update_file(update_link, target_dir)
            messagebox.showinfo("업데이트 다운로드 완료", f"파일 다운로드 완료:\n{file_path}\n\n업데이트 파일을 실행합니다.")
            run_update_file(file_path)
        except Exception as e:
            messagebox.showerror("업데이트 실패", f"자동 업데이트 중 오류가 발생했습니다:\n{e}")

    def setup_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=10)
        
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left")
        
        ctk.CTkLabel(title_frame, text="ENTERPRISE SOLUTION", font=("Arial", 22, "bold"), text_color="#2196F3").pack(anchor="w")
        ctk.CTkLabel(title_frame, text=f"👤 {self.user_name}님, 접속을 환영합니다.", font=("Arial", 13), text_color="#B0BEC5").pack(anchor="w", pady=(2, 0))
        
        badge_frame = ctk.CTkFrame(header, fg_color="transparent")
        badge_frame.pack(side="right", fill="y")

        if self.user_plan == "영구":
            status_text = " 👑 영구 라이선스 (PRO) "
            color = "#9C27B0"
        elif self.user_plan == "무료":
            status_text = " 🆓 무료 체험판 (일일 50건 제한) "
            color = "#757575"
        else: 
            status_text = f" 🟢 기간제 구독 중 | D-{self.days_left} "
            color = "#4CAF50"

        ctk.CTkLabel(badge_frame, text=status_text, fg_color=color, corner_radius=5, font=("Arial", 12, "bold")).pack(side="right", pady=5)


class SignUpWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("새 계정 만들기")
        self.geometry("400x550")
        self.attributes("-topmost", True)
        self.grab_set() 
        
        ctk.CTkLabel(self, text="회원가입", font=("Arial", 22, "bold")).pack(pady=(30, 20))

        self.id_entry = ctk.CTkEntry(self, placeholder_text="아이디", width=280)
        self.id_entry.pack(pady=10)
        self.pw_entry = ctk.CTkEntry(self, placeholder_text="비밀번호", show="*", width=280)
        self.pw_entry.pack(pady=10)
        self.pw_confirm_entry = ctk.CTkEntry(self, placeholder_text="비밀번호 확인", show="*", width=280)
        self.pw_confirm_entry.pack(pady=10)
        self.name_entry = ctk.CTkEntry(self, placeholder_text="회원명", width=280)
        self.name_entry.pack(pady=10)
        
        self.signup_btn = ctk.CTkButton(self, text="가입 신청하기", command=self.process_signup, width=280, height=40, fg_color="#2E7D32", hover_color="#1B5E20")
        self.signup_btn.pack(pady=30)

    def process_signup(self):
        uid = self.id_entry.get().strip()
        upw = self.pw_entry.get().strip()
        upw_confirm = self.pw_confirm_entry.get().strip()
        uname = self.name_entry.get().strip()

        if not uid or not upw or not upw_confirm or not uname:
            messagebox.showwarning("입력 오류", "모든 항목을 입력해 주세요.", parent=self)
            return
            
        if upw != upw_confirm:
            messagebox.showwarning("입력 오류", "비밀번호가 일치하지 않습니다.", parent=self)
            return

        if not database.sheet:
            messagebox.showerror("서버 오류", "데이터베이스에 연결할 수 없습니다.", parent=self)
            return

        self.signup_btn.configure(text="처리 중...", state="disabled")
        self.update()

        try:
            all_users = database.sheet.get_all_records()
            for user in all_users:
                if str(user.get('ID', '')).strip() == uid:
                    messagebox.showerror("가입 불가", "이미 존재하는 아이디입니다.", parent=self)
                    self.signup_btn.configure(text="가입 신청하기", state="normal")
                    return
            
            # 🌟 [핵심 수정] 시트의 9개 기둥에 완벽하게 대응하도록 빈칸 배열 세팅! 🌟
            # A:ID, B:PW, C:Expiry, D:Referral, E:Invites, F:LatestVersion, G:UpdateLink, H:Plan, I:Name
            new_user_data = [
                uid,             # A열 (ID)
                upw,             # B열 (PW)
                "1970-01-01",    # C열 (Expiry)
                "",              # D열 (Referral - 빈칸)
                0,               # E열 (Invites - 숫자 0)
                "",              # F열 (LatestVersion - 빈칸)
                "",              # G열 (UpdateLink - 빈칸)
                "승인대기",       # H열 (Plan)
                uname            # I열 (Name)
            ]
            
            database.sheet.append_row(new_user_data)
            
            messagebox.showinfo("신청 완료", f"환영합니다, {uname}님!\n가입 신청이 완료되었습니다.\n\n관리자 승인 후 로그인이 가능합니다.", parent=self)
            self.destroy() 
            
        except Exception as e:
            messagebox.showerror("오류", f"회원가입 처리 중 오류가 발생했습니다: {e}", parent=self)
            self.signup_btn.configure(text="가입 신청하기", state="normal")


class LoginWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("멤버십 시스템 로그인")
        self.geometry("400x550")
        
        self.label = ctk.CTkLabel(self, text="B2B EXTRACTOR", font=("Arial", 24, "bold"))
        self.label.pack(pady=40)
        self.version_label = ctk.CTkLabel(self, text=f"현재 버전: v{CURRENT_VERSION}", text_color="gray")
        self.version_label.pack(pady=(0, 20))

        self.id_entry = ctk.CTkEntry(self, placeholder_text="아이디", width=280)
        self.id_entry.pack(pady=10)
        self.pw_entry = ctk.CTkEntry(self, placeholder_text="비밀번호", show="*", width=280)
        self.pw_entry.pack(pady=10)
        
        self.login_btn = ctk.CTkButton(self, text="로그인", command=self.login, width=280, height=40)
        self.login_btn.pack(pady=10)

        self.auto_login_var = tk.BooleanVar(value=True)
        self.auto_login_check = ctk.CTkCheckBox(self, text="자동로그인", variable=self.auto_login_var)
        self.auto_login_check.pack(pady=(0, 8))

        self.update_btn = ctk.CTkButton(self, text="업데이트 확인", command=self.check_update_now, width=280, height=36, fg_color="#455A64", hover_color="#37474F")
        self.update_btn.pack(pady=(0, 8))
        
        self.signup_btn = ctk.CTkButton(self, text="회원가입", command=self.open_signup, width=280, height=40, fg_color="transparent", border_width=1, text_color="white")
        self.signup_btn.pack(pady=5)

        self.id_entry.bind("<Return>", self.login)
        self.pw_entry.bind("<Return>", self.login)

    def open_signup(self):
        SignUpWindow(self)

    def _is_user_valid_for_login(self, user_found):
        plan = str(user_found.get('Plan', '무료')).strip()
        if plan == '승인대기':
            messagebox.showinfo("승인 대기 중", "현재 관리자 승인 대기 중입니다.\n\n승인이 완료된 후 다시 시도해 주세요.")
            return False

        if plan == '기간제':
            raw_expiry = str(user_found.get('Expiry', '1970-01-01')).strip()
            try:
                expiry = datetime.strptime(raw_expiry, "%Y-%m-%d")
                if expiry < datetime.now():
                    messagebox.showwarning("만료", "구독 기간이 종료되었습니다.")
                    return False
            except ValueError:
                messagebox.showerror("시트 오류", "구글 시트의 Expiry 칸에는 반드시 날짜(YYYY-MM-DD)를 적어야 합니다.")
                return False
        return True

    def _save_auth_config(self, uid, upw):
        try:
            raw = json.dumps({"uid": uid, "upw": upw}, ensure_ascii=False).encode("utf-8")
            encoded = base64.b64encode(raw).decode("ascii")
            with open(AUTH_FILE, "w", encoding="utf-8") as f:
                json.dump({"auth": encoded}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _run_auto_update(self, latest_version, update_link):
        if not update_link:
            messagebox.showwarning("업데이트 링크 없음", "업데이트 링크가 비어 있습니다. 관리자에게 문의해 주세요.")
            return False
        try:
            self.login_btn.configure(text="업데이트 다운로드 중...", state="disabled")
            self.update()
            target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), UPDATE_DIR)
            file_path = download_update_file(update_link, target_dir)
            messagebox.showinfo("업데이트 완료", f"다운로드 완료:\n{file_path}\n\n업데이트 파일을 실행합니다.")
            run_update_file(file_path)
            return True
        except Exception as e:
            messagebox.showerror("업데이트 실패", f"자동 업데이트 중 오류가 발생했습니다:\n{e}")
            return False
        finally:
            self.login_btn.configure(text="로그인", state="normal")

    def check_update_now(self):
        if not database.sheet:
            messagebox.showerror("서버 오류", "데이터베이스에 연결할 수 없습니다.")
            return
        try:
            all_users = database.sheet.get_all_records()
            latest_version, update_link = extract_update_info(all_users, getattr(database, "version_sheet", None))
            if latest_version and is_newer_version(latest_version, CURRENT_VERSION):
                if messagebox.askyesno("업데이트 확인", f"새 버전(v{latest_version})이 있습니다.\n자동 업데이트를 진행할까요?"):
                    self._run_auto_update(latest_version, update_link)
            else:
                messagebox.showinfo("업데이트 확인", f"현재 최신 버전(v{CURRENT_VERSION})입니다.")
        except Exception as e:
            messagebox.showerror("오류", f"업데이트 확인 중 에러 발생: {e}")

    def login(self, event=None):
        uid = self.id_entry.get().strip()
        upw = self.pw_entry.get().strip()
        if not database.sheet: 
            messagebox.showerror("서버 오류", "데이터베이스에 연결할 수 없습니다.")
            return

        self.login_btn.configure(text="서버 확인 중...", state="disabled")
        self.update()

        try:
            all_users = database.sheet.get_all_records()
            if len(all_users) > 0:
                latest_version, update_link = extract_update_info(all_users, getattr(database, "version_sheet", None))
                
                if latest_version and is_newer_version(latest_version, CURRENT_VERSION):
                    ans = messagebox.askyesno("버전 업데이트", f"새 버전(v{latest_version})이 출시되었습니다.\n자동 업데이트를 진행할까요?")
                    if ans:
                        self._run_auto_update(latest_version, update_link)
                        return

            user_found = next((row for row in all_users if str(row.get('ID', '')).strip() == uid), None)
            
            if user_found and str(user_found.get('PW', '')).strip() == upw:
                if not self._is_user_valid_for_login(user_found):
                    self.login_btn.configure(text="로그인", state="normal")
                    return
                if self.auto_login_var.get():
                    self._save_auth_config(uid, upw)

                self.destroy() 
                IntegratedExtractorApp(user_found).mainloop() 
            else: 
                messagebox.showerror("실패", "아이디 또는 비밀번호가 틀렸습니다.")
                
        except Exception as e: 
            messagebox.showerror("오류", f"로그인 처리 중 에러 발생: {e}")
        finally: 
            self.login_btn.configure(text="로그인", state="normal")

if __name__ == "__main__":
    auto_user = None
    try:
        if os.path.exists(AUTH_FILE) and database.sheet:
            with open(AUTH_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            encoded = cfg.get("auth", "")
            if encoded:
                raw = base64.b64decode(encoded.encode("ascii")).decode("utf-8")
                auth = json.loads(raw)
                uid = str(auth.get("uid", "")).strip()
                upw = str(auth.get("upw", "")).strip()
                if uid and upw:
                    users = database.sheet.get_all_records()
                    user_found = next((row for row in users if str(row.get('ID', '')).strip() == uid and str(row.get('PW', '')).strip() == upw), None)
                    if user_found:
                        plan = str(user_found.get('Plan', '무료')).strip()
                        if plan != '승인대기':
                            if plan == '기간제':
                                raw_expiry = str(user_found.get('Expiry', '1970-01-01')).strip()
                                expiry = datetime.strptime(raw_expiry, "%Y-%m-%d")
                                if expiry >= datetime.now():
                                    auto_user = user_found
                            else:
                                auto_user = user_found
    except Exception:
        auto_user = None

    if auto_user:
        IntegratedExtractorApp(auto_user).mainloop()
    else:
        app = LoginWindow()
        app.mainloop()