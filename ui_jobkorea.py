# 파일명: ui_jobkorea.py

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import pandas as pd
import re
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from blocklist import BlockList
from history_manager import LocalHistoryManager
from datetime import datetime
import os

email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

def extract_valid_emails(text):
    if not text: return set()
    emails = re.findall(email_pattern, text)
    valid_emails = set()
    for e in emails:
        e_lower = e.lower()
        if not e_lower.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')) and not any(gov in e_lower for gov in ['.go.kr', '.mil.kr', 'spo.go.kr', 'kisa.or.kr', '0000.co.kr', 'jobkorea.co.kr']):
            if not any(e_lower.startswith(prefix) for prefix in ['noreply@', 'no-reply@', 'donotreply@', 'abuse@', 'spam@', 'privacy@', 'webmaster@', 'admin@']):
                valid_emails.add(e)
    return valid_emails

def get_chrome_driver():
    options = Options()
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.page_load_strategy = 'eager'
    prefs = {"profile.managed_default_content_settings.images": 2, "profile.managed_default_content_settings.stylesheets": 2, "profile.managed_default_content_settings.plugins": 2}
    options.add_experimental_option("prefs", prefs)
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def run_jobkorea_crawler(search_keyword, max_pages, log_cb, check_running_cb, data_cb,
                         blocklist: BlockList = None, history_manager: LocalHistoryManager = None):
    driver = None
    blocklist = blocklist or BlockList()
    history_manager = history_manager or LocalHistoryManager()
    try: driver = get_chrome_driver()
    except Exception as e:
        log_cb(f"브라우저 오류: {e}"); log_cb("FINISH_SIGNAL")
        return

    collected_companies = []
    try:
        log_cb("🚀 잡코리아 백그라운드 접속 중...")
        driver.get("https://www.jobkorea.co.kr/Review/Home")
        driver.maximize_window()
        time.sleep(3)
        
        try:
            for btn in driver.find_elements(By.XPATH, "//*[contains(text(), '초기화')]"):
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1.5); break
        except: pass

        try:
            keyword_btn = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, f"//*[contains(text(), '{search_keyword}')]")))
            driver.execute_script("arguments[0].click();", keyword_btn)
            time.sleep(1)
            search_btn = driver.find_element(By.XPATH, "//button[contains(text(), '선택된 조건 검색')]")
            driver.execute_script("arguments[0].click();", search_btn)
            time.sleep(4) 
        except Exception:
            log_cb(f"⚠️ '{search_keyword}' 조건을 찾지 못했습니다."); log_cb("FINISH_SIGNAL")
            return

        current_page = 1
        log_cb("🚀 기업 리스트 수집 시작...")
        while current_page <= max_pages:
            if not check_running_cb(): break
            time.sleep(2)
            
            js_extract = """
            let results = [];
            let rows = document.querySelectorAll('li, div[class*="item"], div[class*="list"]');
            for (let row of rows) {
                let text = row.innerText || "";
                if (text.includes('리뷰보기')) {
                    let name = "";
                    let nameEl = row.querySelector('.name, .tit, strong, h2, h3, .coName');
                    if (nameEl) name = nameEl.innerText.trim();
                    else {
                        let lines = text.split('\\n').map(s => s.trim()).filter(s => s !== '');
                        if (lines.length > 0) name = lines[0];
                    }
                    let ind = "";
                    let indEl = row.querySelector('.exp, .desc, .sTit');
                    if (indEl) ind = indEl.innerText.split('|')[0].trim();

                    let url = "";
                    let links = row.querySelectorAll('a');
                    for (let a of links) {
                        if ((a.innerText || "").includes('리뷰보기')) { url = a.href; break; }
                    }
                    if (!url && links.length > 0) url = links[0].href;
                    if (name && url && !results.some(r => r.url === url)) results.push({업체명: name, 업종: ind, url: url});
                }
            }
            return results;
            """
            page_data = driver.execute_script(js_extract)
            if not page_data: break
            collected_companies.extend(page_data)
            log_cb(f"⏳ {current_page}페이지 수집 중... (누적: {len(collected_companies)}개)")
            if current_page >= max_pages: break

            try:
                next_page_num = current_page + 1
                page_link = driver.find_element(By.XPATH, f"//*[contains(@class, 'paging') or contains(@class, 'tplPagination')]//a[normalize-space(text())='{next_page_num}']")
                driver.execute_script("arguments[0].click();", page_link)
            except:
                try: driver.execute_script("arguments[0].click();", driver.find_element(By.XPATH, "//a[contains(text(), '다음')]"))
                except: break 
            current_page += 1
            
        unique_companies = {v['url']:v for v in collected_companies}.values()
        company_list = list(unique_companies)
        log_cb(f"✅ 리스트 {len(company_list)}개 확보 완료! 이메일 딥서치 시작...")

        for index, comp in enumerate(company_list):
            if not check_running_cb(): break
            company_name, company_ind, review_url = comp["업체명"], comp["업종"], comp["url"]
            log_cb(f"🔎 [{index+1}/{len(company_list)}] '{company_name}' 탐색 중...")
            
            try:
                driver.set_page_load_timeout(15)
                driver.get(review_url)
                time.sleep(random.uniform(2, 3))
                
                try:
                    info_link = driver.find_element(By.XPATH, "//a[contains(text(), '기업 정보 보기') or contains(text(), '기업정보 보기')]")
                    info_url = info_link.get_attribute("href")
                    if info_url and info_url.startswith("http"): driver.get(info_url)
                    else: driver.execute_script("arguments[0].click();", info_link)
                    time.sleep(random.uniform(2, 3))
                except: pass
                
                target_homepage = None
                try:
                    hp_element = driver.find_element(By.XPATH, "//*[normalize-space(text())='홈페이지']/following-sibling::*[1]")
                    try: target_homepage = hp_element.find_element(By.TAG_NAME, "a").get_attribute("href")
                    except: target_homepage = hp_element.text.strip()
                except: pass
                
                if not target_homepage or target_homepage == "-" or target_homepage == "" or "jobkorea" in target_homepage.lower(): continue
                if not target_homepage.startswith("http"): target_homepage = "http://" + target_homepage
                
                try:
                    driver.get(target_homepage)
                    time.sleep(random.uniform(3, 5))
                    valid_emails = set()
                    footers = driver.find_elements(By.CSS_SELECTOR, "footer, address, .footer, #footer, .bottom")
                    footer_text = " ".join([f.text for f in footers])
                    valid_emails.update(extract_valid_emails(footer_text))
                    
                    if not valid_emails:
                        target_links = []
                        for a in driver.find_elements(By.TAG_NAME, "a"):
                            try:
                                txt, hrf = a.text.lower(), a.get_attribute("href")
                                if hrf and hrf.startswith("http") and any(k in txt or k in hrf.lower() for k in ["개인정보", "privacy", "contact", "회사소개", "문의"]): target_links.append(hrf)
                            except: continue
                        for link in list(set(target_links))[:3]:
                            try:
                                driver.get(link); time.sleep(2)
                                valid_emails.update(extract_valid_emails(driver.find_element(By.TAG_NAME, "body").text))
                                if valid_emails: break
                            except: continue

                    if valid_emails:
                        email_list = sorted(list(valid_emails))
                        if any(blocklist.should_block(company_name, target_homepage, one_email) for one_email in email_list):
                            log_cb(f"⛔ 금지 이메일 포함 업체 스킵: '{company_name}'")
                            continue
                        domain = ""
                        try:
                            domain = target_homepage.split("//", 1)[-1].split("/", 1)[0].replace("www.", "").lower().strip()
                        except Exception:
                            domain = ""
                        domain_added = False
                        for one_email in email_list:
                            if history_manager.is_email_duplicate(one_email):
                                log_cb(f"🟡 이메일 중복 이력으로 스킵: {one_email}")
                                continue
                            log_cb(f"   🟢 이메일 수집 성공!: {one_email}")
                            data_cb({"업체명": company_name, "업종": company_ind, "이메일": one_email})
                            history_manager.add_email(one_email)
                            if domain and not domain_added:
                                history_manager.add_domain(domain)
                                domain_added = True
                except: pass
            except Exception: continue 

    finally:
        if driver: driver.quit()
        log_cb("FINISH_SIGNAL")

# 🌟 중요: 반드시 파일 맨 아래 위치! 🌟
class JobKoreaTabUI(ctk.CTkFrame):
    def __init__(self, master, plan="기간제", blocklist: BlockList = None):
        super().__init__(master, fg_color="transparent")
        self.data_list = []
        self.is_running = False
        self.plan = plan
        self.blocklist = blocklist or BlockList()
        self.history_manager = LocalHistoryManager()
        self.keyword_queue = []
        self.reserved_keywords = []
        self.current_keyword = ""
        self.queue_total_collected = 0
        self.all_results_by_keyword = {}
        self.max_pages = 9999
        self.save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "autosave")
        
        # 🌟 무료 버전은 잡코리아 화면 자체를 막아버립니다.
        if self.plan == "무료":
            self.setup_locked_ui()
        else:
            self.setup_ui()

    def setup_locked_ui(self):
        locked_label = ctk.CTkLabel(
            self, 
            text="🔒 잡코리아 B2B 정밀 수집은\nPRO (기간제/영구권) 전용 프리미엄 기능입니다.\n\n유료 플랜으로 업그레이드 하시면 즉시 이용 가능합니다.", 
            font=("Arial", 18, "bold"), 
            text_color="#F44336"
        )
        locked_label.pack(expand=True)

    def setup_ui(self):
        input_frame = ctk.CTkFrame(self)
        input_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(input_frame, text="잡코리아 검색 조건:", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.entry_keyword = ctk.CTkEntry(input_frame, width=250)
        self.entry_keyword.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        
        ctk.CTkLabel(input_frame, text="탐색 페이지 (숫자 or '전체'):", font=("Arial", 12, "bold")).grid(row=0, column=2, padx=10, pady=10, sticky="e")
        self.entry_page = ctk.CTkEntry(input_frame, width=100)
        self.entry_page.grid(row=0, column=3, padx=10, pady=10, sticky="w")
        self.entry_page.insert(0, "전체")

        queue_frame = ctk.CTkFrame(self)
        queue_frame.pack(fill="x", padx=10, pady=(0, 5))
        ctk.CTkLabel(queue_frame, text="🗂 예약 키워드:", font=("Arial", 12, "bold"), text_color="#90CAF9").grid(row=0, column=0, padx=10, pady=8, sticky="nw")
        self.keyword_batch = ctk.CTkTextbox(queue_frame, width=320, height=60)
        self.keyword_batch.grid(row=0, column=1, padx=10, pady=8, sticky="w")
        self.btn_queue_add = ctk.CTkButton(queue_frame, text="예약 등록", width=90, command=self.add_reserved_keywords)
        self.btn_queue_add.grid(row=0, column=2, padx=5, pady=8)
        self.queue_info = ctk.CTkLabel(queue_frame, text="(예약 0개)", text_color="#B0BEC5")
        self.queue_info.grid(row=0, column=3, padx=10, pady=8, sticky="w")

        block_frame = ctk.CTkFrame(self)
        block_frame.pack(fill="x", padx=10, pady=(0, 5))

        ctk.CTkLabel(block_frame, text="⛔ 금지목록:", font=("Arial", 12, "bold"), text_color="#FF7043").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self.block_entry = ctk.CTkEntry(block_frame, width=320, placeholder_text="업체명/도메인/이메일 입력 후 추가 (부분일치: 업체명)")
        self.block_entry.grid(row=0, column=1, padx=10, pady=8, sticky="w")

        self.btn_block_add = ctk.CTkButton(block_frame, text="➕ 추가", width=70, command=self.add_block_item)
        self.btn_block_add.grid(row=0, column=2, padx=5, pady=8)

        self.btn_block_sync = ctk.CTkButton(block_frame, text="☁ 시트 동기화", width=120, command=self.sync_blocklist_from_cloud)
        self.btn_block_sync.grid(row=0, column=3, padx=5, pady=8)

        self.btn_block_clear = ctk.CTkButton(block_frame, text="🧹 초기화", width=80, fg_color="#757575", hover_color="#616161", command=self.clear_blocklist)
        self.btn_block_clear.grid(row=0, column=4, padx=5, pady=8)

        self.block_info = ctk.CTkLabel(block_frame, text="(0개)", text_color="#B0BEC5")
        self.block_info.grid(row=0, column=5, padx=10, pady=8, sticky="w")
        
        self._blocklist_listener = lambda: self.after(0, self._update_block_info)
        try:
            self.blocklist.subscribe(self._blocklist_listener)
        except Exception:
            pass
        self._update_block_info()

        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background="#2b2b2b", foreground="white", rowheight=30, fieldbackground="#2b2b2b", borderwidth=0)
        style.configure("Treeview.Heading", background="#1f538d", foreground="white", font=("Arial", 11, "bold"))
        style.map("Treeview", background=[('selected', '#14375e')])

        columns = ("no", "company", "industry", "email")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        self.tree.heading("no", text="번호")
        self.tree.heading("company", text="업체명")
        self.tree.heading("industry", text="업종")
        self.tree.heading("email", text="이메일")
        self.tree.column("no", width=60, anchor="center")
        self.tree.column("company", width=200, anchor="w")
        self.tree.column("industry", width=150, anchor="center")
        self.tree.column("email", width=250, anchor="w")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=10, pady=10)
        
        self.status_label = ctk.CTkLabel(bottom_frame, text="대기 중... 검색 조건을 설정해주세요.", text_color="#FFC107", font=("Arial", 12, "bold"))
        self.status_label.pack(side="left", padx=10)

        self.btn_save = ctk.CTkButton(bottom_frame, text="💾 엑셀 저장", font=("Arial", 13, "bold"), fg_color="#1976D2", hover_color="#1565C0", width=110, state="disabled", command=self.save_to_excel)
        self.btn_save.pack(side="right", padx=5)
        self.btn_save_dir = ctk.CTkButton(bottom_frame, text="📁 저장폴더", font=("Arial", 13, "bold"), fg_color="#455A64", hover_color="#37474F", width=100, command=self.choose_save_dir)
        self.btn_save_dir.pack(side="right", padx=5)
        self.btn_reset = ctk.CTkButton(bottom_frame, text="🔄 초기화", font=("Arial", 13, "bold"), fg_color="#757575", hover_color="#616161", width=90, command=self.reset_crawling)
        self.btn_reset.pack(side="right", padx=5)
        self.btn_stop = ctk.CTkButton(bottom_frame, text="🛑 정지", font=("Arial", 13, "bold"), fg_color="#D32F2F", hover_color="#C62828", width=90, command=self.stop_crawling)
        self.btn_stop.pack(side="right", padx=5)
        self.btn_start = ctk.CTkButton(bottom_frame, text="🚀 추출 시작", font=("Arial", 14, "bold"), fg_color="#2E7D32", hover_color="#1B5E20", width=130, command=self.start_crawling)
        self.btn_start.pack(side="right", padx=10)

    def _update_block_info(self):
        c, d, e = self.blocklist.counts()
        total = c + d + e
        self.block_info.configure(text=f"(총 {total}개 | 업체:{c} 도메인:{d} 이메일:{e})")

    def _parse_keywords(self, raw_text: str):
        text = (raw_text or "").replace("\n", ",")
        return [k.strip() for k in text.split(",") if k.strip()]

    def _refresh_reserved_info(self):
        self.queue_info.configure(text=f"(예약 {len(self.reserved_keywords)}개)")

    def add_reserved_keywords(self):
        raw = self.keyword_batch.get("1.0", "end")
        items = self._parse_keywords(raw)
        if not items:
            messagebox.showwarning("입력 오류", "예약 키워드를 입력해 주세요. (쉼표/줄바꿈 구분)")
            return
        for k in items:
            if k not in self.reserved_keywords:
                self.reserved_keywords.append(k)
        self.keyword_batch.delete("1.0", "end")
        self._refresh_reserved_info()
        self.status_label.configure(text=f"✅ 예약 키워드 등록 완료 (+{len(items)}개)")

    def choose_save_dir(self):
        selected = filedialog.askdirectory(title="저장 폴더 선택", initialdir=self.save_dir)
        if selected:
            self.save_dir = selected
            self.status_label.configure(text=f"📁 저장 폴더 설정: {self.save_dir}")

    def add_block_item(self):
        raw = (self.block_entry.get() or "").strip()
        if not raw:
            return
        local_added, cloud_saved = self.blocklist.add_item_and_sync(raw)
        self.block_entry.delete(0, "end")
        if local_added and cloud_saved:
            self.status_label.configure(text="⛔ 금지목록 추가 + 구글시트 저장 완료")
        elif local_added:
            self.status_label.configure(text="⛔ 금지목록 로컬 추가 완료 (시트 저장 실패)")
        else:
            self.status_label.configure(text="ℹ️ 이미 등록된 금지 항목입니다.")

    def clear_blocklist(self):
        if self.is_running:
            return
        self.blocklist.clear()
        self.status_label.configure(text="🧹 금지목록이 초기화되었습니다.")

    def sync_blocklist_from_cloud(self):
        if self.is_running:
            return
        loaded = self.blocklist.sync_with_cloud()
        self.status_label.configure(text=f"☁ 구글시트 금지목록 동기화 완료 (+{loaded}개)")

    def reset_crawling(self):
        if self.is_running: return
        self.data_list.clear()
        self.all_results_by_keyword.clear()
        for item in self.tree.get_children(): self.tree.delete(item)
        self.status_label.configure(text="🧹 테이블이 초기화되었습니다.")
        self.btn_save.configure(state="disabled")

    def stop_crawling(self):
        if self.is_running:
            self.is_running = False
            self.status_label.configure(text="🛑 수집 중단 요청됨 (작업 정리 중...)")

    def start_crawling(self):
        if self.is_running: return
        keyword_raw = self.entry_keyword.get().strip()
        pages_input = self.entry_page.get().strip()

        if pages_input == "전체": max_pages = 9999
        elif pages_input.isdigit(): max_pages = int(pages_input)
        else:
            messagebox.showwarning("입력 오류", "페이지는 숫자 또는 '전체'만 입력할 수 있습니다.")
            return
        inline_keywords = self._parse_keywords(keyword_raw)
        reserved = list(self.reserved_keywords)
        self.reserved_keywords.clear()
        self._refresh_reserved_info()
        keywords = reserved + [k for k in inline_keywords if k not in reserved]
        if not keywords:
            messagebox.showwarning("입력 오류", "키워드를 입력해 주세요. (입력창 또는 예약 키워드)")
            return

        self.is_running = True
        self.keyword_queue = keywords
        self.queue_total_collected = 0
        self.all_results_by_keyword = {}
        self.max_pages = max_pages
        self.data_list.clear() 
        for item in self.tree.get_children(): self.tree.delete(item) 

        self.btn_start.configure(state="disabled", text="수집 중...")
        self.btn_save.configure(state="disabled")
        self._run_next_keyword()

    def _run_next_keyword(self):
        if not self.is_running:
            return
        if not self.keyword_queue:
            self.is_running = False
            self.btn_start.configure(state="normal", text="🚀 추출 시작")
            self.btn_save.configure(state="normal" if self.data_list else "disabled")
            saved_path = self.save_all_results_auto()
            if saved_path:
                self.status_label.configure(text=f"✅ 전체 키워드 완료 + 자동 저장 완료: {os.path.basename(saved_path)}")
            else:
                self.status_label.configure(text="✅ 전체 키워드 작업 완료!")
            return

        # JobKorea는 유료 전용 탭이라 사실상 제한 없음, 그래도 안전하게 동일 규칙 지원
        if self.plan == "무료" and self.queue_total_collected >= 50:
            self.is_running = False
            self.btn_start.configure(state="normal", text="🚀 추출 시작")
            self.btn_save.configure(state="normal" if self.data_list else "disabled")
            self.status_label.configure(text="🛑 무료 한도(50) 도달로 전체 큐를 중단했습니다.")
            return

        self.current_keyword = self.keyword_queue.pop(0)
        self.all_results_by_keyword.setdefault(self.current_keyword, [])
        self.entry_keyword.delete(0, "end")
        self.entry_keyword.insert(0, self.current_keyword)
        self.data_list.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)

        def log_cb(msg):
            if msg == "FINISH_SIGNAL":
                self.after(0, self._run_next_keyword)
            else:
                self.after(0, lambda: self.status_label.configure(text=msg))

        def data_cb(row_dict):
            self.data_list.append(row_dict)
            self.all_results_by_keyword.setdefault(self.current_keyword, []).append(row_dict)
            self.queue_total_collected += 1
            idx = len(self.data_list)
            tree_values = (idx, row_dict.get("업체명", ""), row_dict.get("업종", ""), row_dict.get("이메일", ""))
            self.after(0, lambda: self.tree.insert("", "end", values=tree_values))
            self.after(0, lambda: self.tree.yview_moveto(1)) 

        threading.Thread(
            target=run_jobkorea_crawler,
            args=(self.current_keyword, self.max_pages, log_cb, lambda: self.is_running, data_cb,
                  self.blocklist, self.history_manager),
            daemon=True
        ).start()

    def _safe_sheet_name(self, raw_name: str):
        name = (raw_name or "Sheet").strip()
        invalid = ['\\', '/', '*', '?', ':', '[', ']']
        for ch in invalid:
            name = name.replace(ch, "_")
        if not name:
            name = "Sheet"
        return name[:31]

    def save_all_results_auto(self):
        if not self.all_results_by_keyword:
            return None
        try:
            os.makedirs(self.save_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = os.path.join(self.save_dir, f"{ts}_JobKorea_ALL.xlsx")
            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                for keyword, rows in self.all_results_by_keyword.items():
                    if not rows:
                        continue
                    df = pd.DataFrame(rows)[["업체명", "업종", "이메일"]]
                    df.to_excel(writer, sheet_name=self._safe_sheet_name(keyword), index=False)
            return file_path
        except Exception:
            return None

    def save_to_excel(self, auto=False, keyword_override=None):
        if not self.data_list: return
        keyword = (keyword_override or self.entry_keyword.get().strip() or "keyword")
        default_name = f"잡코리아_추출결과_{keyword}.xlsx"
        if auto:
            os.makedirs(self.save_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = os.path.join(self.save_dir, f"{ts}_{default_name}")
        else:
            file_path = filedialog.asksaveasfilename(title="엑셀 저장", initialfile=default_name, initialdir=self.save_dir, defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")])
        if file_path:
            try:
                pd.DataFrame(self.data_list)[["업체명", "업종", "이메일"]].to_excel(file_path, index=False)
                if not auto:
                    messagebox.showinfo("저장 완료", f"총 {len(self.data_list)}건 저장 완료!")
            except Exception as e: messagebox.showerror("오류", f"저장 실패: {e}")