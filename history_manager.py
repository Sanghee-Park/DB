import json
import os
import threading
import re


class LocalHistoryManager:
    def __init__(self, file_path: str = None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.file_path = file_path or os.path.join(base_dir, "local_history.json")
        self._lock = threading.Lock()
        self._emails = set()
        self._domains = set()
        self._load_from_file()

    def _load_from_file(self):
        with self._lock:
            if not os.path.exists(self.file_path):
                self._save_unlocked()
                return

            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                emails = data.get("emails", []) if isinstance(data, dict) else []
                domains = data.get("domains", []) if isinstance(data, dict) else []
                self._emails = set(str(x).strip().lower() for x in emails if str(x).strip())
                self._domains = set(str(x).strip().lower() for x in domains if str(x).strip())
            except Exception:
                # 파일이 깨진 경우 안전하게 초기화
                self._emails = set()
                self._domains = set()
                self._save_unlocked()

    def _save_unlocked(self):
        payload = {
            "emails": sorted(self._emails),
            "domains": sorted(self._domains),
        }
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    def save_to_file(self):
        with self._lock:
            self._save_unlocked()

    def is_duplicate(self, email: str = "", domain: str = "") -> bool:
        e = (email or "").strip().lower()
        d = (domain or "").strip().lower()
        with self._lock:
            return (e and e in self._emails) or (d and d in self._domains)

    def is_email_duplicate(self, email: str = "") -> bool:
        e = (email or "").strip().lower()
        if not e:
            return False
        with self._lock:
            return e in self._emails

    def is_domain_duplicate(self, domain: str = "") -> bool:
        d = (domain or "").strip().lower()
        if not d:
            return False
        with self._lock:
            return d in self._domains

    def add_record(self, email: str = "", domain: str = ""):
        e = (email or "").strip().lower()
        d = (domain or "").strip().lower()
        changed = False
        with self._lock:
            if e and e not in self._emails:
                self._emails.add(e)
                changed = True
            if d and d not in self._domains:
                self._domains.add(d)
                changed = True
            if changed:
                self._save_unlocked()

    def add_email(self, email: str = ""):
        self.add_record(email=email, domain="")

    def add_domain(self, domain: str = ""):
        self.add_record(email="", domain=domain)

    def merge_from_excel(self, file_path: str):
        """
        기존 추출 엑셀을 로컬 이력(local_history.json)에 병합합니다.
        - 이메일 컬럼: 이메일 / email
        - 도메인 컬럼: 도메인 / domain / 홈페이지 / homepage / url
        """
        import pandas as pd

        email_added = 0
        domain_added = 0

        def norm_domain(v: str):
            s = (v or "").strip().lower()
            if not s:
                return ""
            s = re.sub(r"^https?://", "", s)
            s = s.split("/", 1)[0]
            s = s.replace("www.", "")
            return s

        xls = pd.ExcelFile(file_path)
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            cols = {str(c).strip().lower(): c for c in df.columns}

            email_col = None
            for key in ("이메일", "email"):
                if key.lower() in cols:
                    email_col = cols[key.lower()]
                    break

            domain_col = None
            for key in ("도메인", "domain", "홈페이지", "homepage", "url"):
                if key.lower() in cols:
                    domain_col = cols[key.lower()]
                    break

            if email_col is not None:
                for val in df[email_col].tolist():
                    s = str(val).strip()
                    if not s or s.lower() in ("nan", "none"):
                        continue
                    for e in [x.strip().lower() for x in s.split(",") if x.strip()]:
                        if not self.is_email_duplicate(e):
                            self.add_email(e)
                            email_added += 1

            if domain_col is not None:
                for val in df[domain_col].tolist():
                    d = norm_domain(str(val))
                    if not d or d in ("nan", "none"):
                        continue
                    if not self.is_domain_duplicate(d):
                        self.add_domain(d)
                        domain_added += 1

        return {"emails": email_added, "domains": domain_added}
