# 파일명: ui_daum.py

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
phone_pattern = r'(?:02|0[3-9][0-9]|010|15[0-9]{2}|16[0-9]{2}|18[0-9]{2})-?\d{3,4}-?\d{4}'

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

def extract_valid_phones(text):
    if not text: return set()
    return set(re.findall(phone_pattern, text))

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

def run_daum_crawler(search_keyword, max_pages, ext_email, ext_phone, limit, log_cb, check_running_cb, data_cb,
                     blocklist: BlockList = None, history_manager: LocalHistoryManager = None):
    driver = None
    blocklist = blocklist or BlockList()
    history_manager = history_manager or LocalHistoryManager()
    try: driver = get_chrome_driver()
    except Exception as e:
        log_cb(f"브라우저 오류: {e}"); log_cb("FINISH_SIGNAL")
        return

    collected_sites = []
    extracted_count = 0 

    try:
        log_cb(f"🚀 Daum 백그라운드 탐색 시작...")
        for page_num in range(1, max_pages + 1):
            if not check_running_cb(): break
            url = f"https://search.daum.net/search?w=site&q={search_keyword}&p={page_num}"
            driver.get(url)
            time.sleep(random.uniform(1.5, 2.5))
            
            try:
                main_area = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#mArticle, .c-main, #dnsColl")))
                links = main_area.find_elements(By.CSS_SELECTOR, "a.tit_main, a.c-tit-doc, .wrap_tit a, a.f_link_b, .tit_item a")
                if not links:
                    items = main_area.find_elements(By.CSS_SELECTOR, ".c-list-basic > li, .list_info > li")
                    links = []
                    for item in items:
                        try: links.append(item.find_element(By.TAG_NAME, "a"))
                        except: pass

                found_in_page = 0
                for link in links:
                    try:
                        site_name, site_url = link.text.strip(), link.get_attribute("href")
                        if site_name and len(site_name) < 40 and site_url and site_url.startswith("http"):
                            exclude_words = ["daum.net", "kakao.com", "tistory.com", "brunch.co.kr", "naver.com", "youtube.com", "instagram.com", "facebook.com", "twitter.com", "namu.wiki", "dcinside.com", ".go.kr", ".mil.kr", "korea.kr"]
                            if not any(x in site_url.lower() for x in exclude_words):
                                ind_text = ""
                                try:
                                    parent = link.find_element(By.XPATH, "./ancestor::li[1] | ./ancestor::div[contains(@class, 'c-item')][1] | ./ancestor::div[contains(@class, 'wrap_cont')][1]")
                                    ind_text = parent.find_element(By.CSS_SELECTOR, ".txt_info, .desc_path, .conts_desc").text.strip()
                                except: pass
                                collected_sites.append({"업체명": site_name, "업종": ind_text, "도메인": site_url})
                                found_in_page += 1
                    except: continue
                
                if found_in_page == 0: break
                log_cb(f"⏳ {page_num}페이지 수집 중... (누적: {len(collected_sites)}개)")
            except Exception: break

        unique_sites = {site['도메인']: site for site in collected_sites}
        site_list = list(unique_sites.values())
        log_cb(f"✅ 리스트 {len(site_list)}개 확보 완료! 딥서치 시작...")

        for index, site in enumerate(site_list):
            if not check_running_cb(): break
            if extracted_count >= limit:
                log_cb(f"🛑 무료 체험판 수집 한도({limit}개)에 도달했습니다. 무제한 수집은 PRO로 업그레이드 하세요.")
                break

            company, ind, url = site["업체명"], site["업종"], site["도메인"]
            log_cb(f"🔎 [{index+1}/{len(site_list)}] '{company}' 탐색 중...")
            
            try:
                driver.set_page_load_timeout(10)
                driver.get(url)
                time.sleep(random.uniform(2, 4))
                
                valid_emails, valid_phones = set(), set()
                page_text = driver.find_element(By.TAG_NAME, "body").text
                
                if ext_email: valid_emails.update(extract_valid_emails(page_text))
                if ext_phone: valid_phones.update(extract_valid_phones(page_text))
                
                if (ext_email and not valid_emails) or (ext_phone and not valid_phones):
                    target_links = []
                    for a in driver.find_elements(By.TAG_NAME, "a"):
                        try:
                            txt, hrf = a.text.lower(), a.get_attribute("href")
                            if hrf and hrf.startswith("http") and any(k in txt or k in hrf.lower() for k in ["개인정보", "privacy", "contact", "회사소개", "문의", "오시는"]): target_links.append(hrf)
                        except: continue
                    
                    for link in list(set(target_links))[:3]:
                        try:
                            driver.get(link); time.sleep(2)
                            sub_page_text = driver.find_element(By.TAG_NAME, "body").text
                            if ext_email: valid_emails.update(extract_valid_emails(sub_page_text))
                            if ext_phone: valid_phones.update(extract_valid_phones(sub_page_text))
                            if (not ext_email or valid_emails) and (not ext_phone or valid_phones): break
                        except: continue

                email_str = ", ".join(list(valid_emails)) if valid_emails else ""
                phone_str = ", ".join(list(valid_phones)) if valid_phones else ""

                if email_str or phone_str:
                    domain = ""
                    try:
                        domain = url.split("//", 1)[-1].split("/", 1)[0].replace("www.", "").lower().strip()
                    except Exception:
                        domain = ""
                    email_list = sorted(list(valid_emails)) if valid_emails else []

                    if email_list:
                        if any(blocklist.should_block(company, url, one_email) for one_email in email_list):
                            log_cb(f"⛔ 금지 이메일 포함 업체 스킵: '{company}'")
                            continue
                        domain_added = False
                        for one_email in email_list:
                            if extracted_count >= limit:
                                break
                            if history_manager.is_email_duplicate(one_email):
                                log_cb(f"🟡 이메일 중복 이력으로 스킵: {one_email}")
                                continue
                            extracted_count += 1
                            data_cb({"업체명": company, "업종": ind, "전화번호": phone_str, "이메일": one_email})
                            history_manager.add_email(one_email)
                            if domain and not domain_added:
                                history_manager.add_domain(domain)
                                domain_added = True
                    elif phone_str:
                        if blocklist.should_block(company, url, ""):
                            log_cb(f"⛔ 금지목록 매칭으로 스킵: '{company}'")
                            continue
                        if domain and history_manager.is_domain_duplicate(domain):
                            log_cb(f"🟡 도메인 중복 이력으로 스킵: '{company}'")
                            continue
                        if extracted_count < limit:
                            extracted_count += 1
                            data_cb({"업체명": company, "업종": ind, "전화번호": phone_str, "이메일": ""})
                            if domain:
                                history_manager.add_domain(domain)
            except Exception: pass

    finally:
        if driver: driver.quit()
        log_cb("FINISH_SIGNAL")

class DaumCrawlerInstance(ctk.CTkFrame):
    def __init__(self, master, tab_name, daily_limit, blocklist: BlockList):
        super().__init__(master, fg_color="transparent")
        self.tab_name = tab_name
        self.daily_limit = daily_limit 
        self.data_list = []
        self.is_running = False
        self.blocklist = blocklist
        self.history_manager = LocalHistoryManager()
        self.keyword_queue = []
        self.reserved_keywords = []
        self.current_keyword = ""
        self.queue_total_collected = 0
        self.all_results_by_keyword = {}
        self.max_pages = 100
        self.ext_email = True
        self.ext_phone = True
        self.save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "autosave")
        self.setup_ui()

    def setup_ui(self):
        input_frame = ctk.CTkFrame(self)
        input_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(input_frame, text="검색 키워드:", font=("Arial", 12, "bold")).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.entry_keyword = ctk.CTkEntry(input_frame, width=220)
        self.entry_keyword.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        
        ctk.CTkLabel(input_frame, text="페이지 (최대 100):", font=("Arial", 12, "bold")).grid(row=0, column=2, padx=10, pady=10, sticky="e")
        self.entry_page = ctk.CTkEntry(input_frame, width=80)
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

        opt_frame = ctk.CTkFrame(self, fg_color="transparent")
        opt_frame.pack(fill="x", padx=15, pady=0)
        ctk.CTkLabel(opt_frame, text="✅ 옵션:", font=("Arial", 12, "bold"), text_color="#FFC107").pack(side="left", padx=(0, 10))
        
        self.chk_phone_var = tk.BooleanVar(value=True)
        self.chk_email_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(opt_frame, text="☎️ 전화번호", variable=self.chk_phone_var).pack(side="left", padx=10)
        ctk.CTkCheckBox(opt_frame, text="📧 이메일", variable=self.chk_email_var).pack(side="left", padx=10)

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

        # 공용 금지목록 변경 시 카운트 자동 갱신
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
        style.configure("Treeview", background="#2b2b2b", foreground="white", rowheight=25, fieldbackground="#2b2b2b", borderwidth=0)
        style.configure("Treeview.Heading", background="#1f538d", foreground="white", font=("Arial", 10, "bold"))
        style.map("Treeview", background=[('selected', '#14375e')])

        columns = ("no", "company", "industry", "phone", "email")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings")
        self.tree.heading("no", text="No")
        self.tree.heading("company", text="업체명")
        self.tree.heading("industry", text="업종")
        self.tree.heading("phone", text="전화번호")
        self.tree.heading("email", text="이메일")
        self.tree.column("no", width=40, anchor="center")
        self.tree.column("company", width=150, anchor="w")
        self.tree.column("industry", width=100, anchor="center")
        self.tree.column("phone", width=120, anchor="center")
        self.tree.column("email", width=180, anchor="w")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=10, pady=5)
        
        limit_text = f" (한도: {self.daily_limit}개)" if self.daily_limit != 999999 else ""
        self.status_label = ctk.CTkLabel(bottom_frame, text=f"[{self.tab_name}] 대기 중...{limit_text}", text_color="#FFC107", font=("Arial", 11, "bold"))
        self.status_label.pack(side="left", padx=10)

        self.btn_save = ctk.CTkButton(bottom_frame, text="💾 저장", font=("Arial", 12, "bold"), fg_color="#1976D2", hover_color="#1565C0", width=80, state="disabled", command=self.save_to_excel)
        self.btn_save.pack(side="right", padx=5)
        self.btn_save_dir = ctk.CTkButton(bottom_frame, text="📁 저장폴더 선택", font=("Arial", 12, "bold"), fg_color="#455A64", hover_color="#37474F", width=100, command=self.choose_save_dir)
        self.btn_save_dir.pack(side="right", padx=5)
        self.btn_import_db = ctk.CTkButton(bottom_frame, text="📂 기존 추출 DB 불러오기", font=("Arial", 12, "bold"), fg_color="#5D4037", hover_color="#4E342E", width=160, command=self.import_existing_db)
        self.btn_import_db.pack(side="right", padx=5)
        self.btn_reset = ctk.CTkButton(bottom_frame, text="🔄 초기화", font=("Arial", 12, "bold"), fg_color="#757575", hover_color="#616161", width=70, command=self.reset_crawling)
        self.btn_reset.pack(side="right", padx=5)
        self.btn_stop = ctk.CTkButton(bottom_frame, text="🛑 정지", font=("Arial", 12, "bold"), fg_color="#D32F2F", hover_color="#C62828", width=70, command=self.stop_crawling)
        self.btn_stop.pack(side="right", padx=5)
        self.btn_start = ctk.CTkButton(bottom_frame, text="🚀 시작", font=("Arial", 12, "bold"), fg_color="#2E7D32", hover_color="#1B5E20", width=90, command=self.start_crawling)
        self.btn_start.pack(side="right", padx=5)

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

    def import_existing_db(self):
        if self.is_running:
            return
        file_path = filedialog.askopenfilename(title="기존 추출 DB 엑셀 선택", filetypes=[("Excel Files", "*.xlsx;*.xls")])
        if not file_path:
            return
        try:
            merged = self.history_manager.merge_from_excel(file_path)
            self.status_label.configure(text=f"📂 기존 DB 병합 완료 (이메일 +{merged['emails']}, 도메인 +{merged['domains']})")
        except Exception as e:
            messagebox.showerror("오류", f"기존 DB 병합 실패: {e}")

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
        ext_email = self.chk_email_var.get()
        ext_phone = self.chk_phone_var.get()

        if not ext_email and not ext_phone:
            messagebox.showwarning("입력 오류", "전화번호 또는 이메일 중 최소 1개는 체크해 주세요.")
            return
            
        if pages_input == "전체": max_pages = 100
        elif pages_input.isdigit(): max_pages = min(int(pages_input), 100)
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
        self.ext_email = ext_email
        self.ext_phone = ext_phone
        self.data_list.clear()
        for item in self.tree.get_children(): self.tree.delete(item)
        self.btn_start.configure(state="disabled", text="수집 중...")
        self.btn_save.configure(state="disabled")
        self._run_next_keyword()

    def _run_next_keyword(self):
        if not self.is_running:
            # 정지 후에도 시작 버튼이 disabled로 남지 않도록 즉시 복구
            self.btn_start.configure(state="normal", text="🚀 시작")
            self.keyword_queue = []
            self.status_label.configure(text="🛑 수집이 중단되었습니다.")
            return
        if not self.keyword_queue:
            self.is_running = False
            self.btn_start.configure(state="normal", text="🚀 시작")
            self.btn_save.configure(state="normal" if self.data_list else "disabled")
            self.status_label.configure(text="✅ 전체 키워드 작업 완료!")
            return

        if self.daily_limit != 999999 and self.queue_total_collected >= self.daily_limit:
            self.is_running = False
            self.btn_start.configure(state="normal", text="🚀 시작")
            self.btn_save.configure(state="normal" if self.data_list else "disabled")
            self.status_label.configure(text=f"🛑 무료 한도({self.daily_limit}) 도달로 전체 큐를 중단했습니다.")
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
                if self.data_list:
                    self.after(0, lambda: self.save_keyword_result_auto(self.current_keyword))
                    self.after(0, self.clear_current_results)
                self.after(0, self._run_next_keyword)
            else:
                self.after(0, lambda: self.status_label.configure(text=msg))

        def data_cb(row_dict):
            self.data_list.append(row_dict)
            self.all_results_by_keyword.setdefault(self.current_keyword, []).append(row_dict)
            self.queue_total_collected += 1
            idx = len(self.data_list)
            tree_values = (idx, row_dict.get("업체명", ""), row_dict.get("업종", ""), row_dict.get("전화번호", ""), row_dict.get("이메일", ""))
            self.after(0, lambda: self.tree.insert("", "end", values=tree_values))
            self.after(0, lambda: self.tree.yview_moveto(1)) 

        remaining_limit = self.daily_limit - self.queue_total_collected if self.daily_limit != 999999 else 999999
        threading.Thread(
            target=run_daum_crawler,
            args=(self.current_keyword, self.max_pages, self.ext_email, self.ext_phone, remaining_limit, log_cb, lambda: self.is_running, data_cb,
                  self.blocklist, self.history_manager),
            daemon=True
        ).start()

    def clear_current_results(self):
        self.data_list.clear()
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _safe_keyword_filename(self, keyword: str):
        safe = re.sub(r'[\\/:*?"<>|]+', "_", (keyword or "keyword")).strip()
        safe = safe.replace(" ", "_")
        return safe or "keyword"

    def _build_keyword_result_path(self, keyword: str):
        os.makedirs(self.save_dir, exist_ok=True)
        base_name = f"{self._safe_keyword_filename(keyword)}_결과.xlsx"
        path = os.path.join(self.save_dir, base_name)
        if not os.path.exists(path):
            return path
        idx = 2
        while True:
            candidate = os.path.join(self.save_dir, f"{self._safe_keyword_filename(keyword)}_결과_{idx}.xlsx")
            if not os.path.exists(candidate):
                return candidate
            idx += 1

    def save_keyword_result_auto(self, keyword):
        if not self.data_list:
            return None
        try:
            file_path = self._build_keyword_result_path(keyword)
            pd.DataFrame(self.data_list)[["업체명", "업종", "전화번호", "이메일"]].to_excel(file_path, index=False)
            self.status_label.configure(text=f"💾 자동 저장 완료: {os.path.basename(file_path)}")
            return file_path
        except Exception as e:
            messagebox.showerror("오류", f"자동 저장 실패: {e}")
            return None

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
            file_path = os.path.join(self.save_dir, f"{ts}_Daum_{self.tab_name.replace(' ', '')}_ALL.xlsx")
            with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                for keyword, rows in self.all_results_by_keyword.items():
                    if not rows:
                        continue
                    df = pd.DataFrame(rows)[["업체명", "업종", "전화번호", "이메일"]]
                    df.to_excel(writer, sheet_name=self._safe_sheet_name(keyword), index=False)
            return file_path
        except Exception:
            return None

    def save_to_excel(self, auto=False, keyword_override=None):
        if not self.data_list: return
        keyword = (keyword_override or self.entry_keyword.get().strip() or "keyword")
        default_name = f"Daum_{self.tab_name.replace(' ', '')}_{keyword}.xlsx"
        if auto:
            os.makedirs(self.save_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = os.path.join(self.save_dir, f"{ts}_{default_name}")
        else:
            file_path = filedialog.asksaveasfilename(title="엑셀 저장", initialfile=default_name, initialdir=self.save_dir, defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")])
        if file_path:
            try:
                pd.DataFrame(self.data_list)[["업체명", "업종", "전화번호", "이메일"]].to_excel(file_path, index=False)
                if not auto:
                    messagebox.showinfo("저장 완료", f"[{self.tab_name}] 총 {len(self.data_list)}건 저장 완료!")
            except Exception as e: messagebox.showerror("오류", f"저장 실패: {e}")

# 🌟 중요: 반드시 파일 맨 아래 위치! 🌟
class DaumTabUI(ctk.CTkFrame):
    def __init__(self, master, plan="기간제", blocklist: BlockList = None):
        super().__init__(master, fg_color="transparent")
        self.plan = plan
        self.blocklist = blocklist or BlockList()
        
        self.inner_tabview = ctk.CTkTabview(self)
        self.inner_tabview.pack(fill="both", expand=True, padx=5, pady=0)
        
        for i in range(1, 6):
            tab_name = f"추출 {i}"
            tab = self.inner_tabview.add(tab_name)
            
            if self.plan == "무료" and i > 1:
                locked_label = ctk.CTkLabel(tab, text="🔒 무료 버전에서는 1개의 추출 탭만 제공됩니다.\n\n동시 다중 수집을 원하시면 PRO(기간제/영구)로 업그레이드 하세요.", font=("Arial", 16, "bold"), text_color="#FF9800")
                locked_label.pack(expand=True)
            else:
                daily_limit = 50 if self.plan == "무료" else 999999
                worker = DaumCrawlerInstance(tab, tab_name=tab_name, daily_limit=daily_limit, blocklist=self.blocklist)
                worker.pack(fill="both", expand=True)