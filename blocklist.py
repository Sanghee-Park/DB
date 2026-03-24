import re
import threading
import database


def _norm_token(s: str) -> str:
    if s is None:
        return ""
    return re.sub(r"\s+", "", str(s)).strip().lower()


def _norm_domain_from_url(url: str) -> str:
    if not url:
        return ""
    u = str(url).strip().lower()
    u = re.sub(r"^https?://", "", u)
    u = u.split("/")[0]
    u = u.split("?")[0]
    if u.startswith("www."):
        u = u[4:]
    return u


class BlockList:
    """
    공용 금지목록 관리자.
    - 업체명: 공백 제거 후 '부분일치' 차단
    - 도메인: 정확히 일치 차단 (www 제거)
    - 이메일: 정확히 일치 차단 (소문자)
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._blocked_companies = set()  # normalized tokens (no spaces, lower)
        self._blocked_domains = set()    # example.com
        self._blocked_emails = set()     # user@example.com
        self._listeners = set()
        self.sync_with_cloud()

    def subscribe(self, cb):
        with self._lock:
            self._listeners.add(cb)

    def unsubscribe(self, cb):
        with self._lock:
            self._listeners.discard(cb)

    def _notify(self):
        # listeners는 UI 콜백이므로 예외가 전체를 죽이지 않게 보호
        listeners = None
        with self._lock:
            listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb()
            except Exception:
                pass

    def counts(self):
        with self._lock:
            return (
                len(self._blocked_companies),
                len(self._blocked_domains),
                len(self._blocked_emails),
            )

    def clear(self):
        with self._lock:
            self._blocked_companies.clear()
            self._blocked_domains.clear()
            self._blocked_emails.clear()
        self._notify()

    def add_item(self, raw: str) -> bool:
        if not raw:
            return False
        token = str(raw).strip()
        if not token:
            return False

        t = token.lower().strip()
        changed = False
        with self._lock:
            if "@" in t:
                if t not in self._blocked_emails:
                    self._blocked_emails.add(t)
                    changed = True
            elif "." in t and " " not in t and "/" not in t:
                d = t.replace("www.", "")
                if d and d not in self._blocked_domains:
                    self._blocked_domains.add(d)
                    changed = True
            else:
                c = _norm_token(token)
                if c and c not in self._blocked_companies:
                    self._blocked_companies.add(c)
                    changed = True

        if changed:
            self._notify()
        return changed

    def _classify_item(self, raw: str):
        token = str(raw or "").strip()
        if not token:
            return "", ""
        t = token.lower().strip()
        if "@" in t:
            return "email", t
        if "." in t and " " not in t and "/" not in t:
            return "domain", t.replace("www.", "")
        return "company", token

    def add_item_to_cloud(self, raw: str) -> bool:
        """
        BlockList 워크시트에 항목 1건을 추가합니다.
        컬럼 기준: A=업체명, B=도메인, C=이메일
        """
        ws = getattr(database, "block_sheet", None)
        if not ws:
            return False
        item_type, value = self._classify_item(raw)
        if not item_type:
            return False
        try:
            if item_type == "company":
                ws.append_row([value, "", ""])
            elif item_type == "domain":
                ws.append_row(["", value, ""])
            else:
                ws.append_row(["", "", value])
            return True
        except Exception:
            return False

    def add_item_and_sync(self, raw: str):
        """
        로컬 금지목록 추가 후 클라우드 저장까지 시도합니다.
        반환: (local_added, cloud_saved)
        """
        local_added = self.add_item(raw)
        cloud_saved = False
        if local_added:
            cloud_saved = self.add_item_to_cloud(raw)
        return local_added, cloud_saved

    def load_from_excel(self, file_path: str) -> int:
        # pandas는 외부 의존이라 여기서만 import
        import pandas as pd

        df = pd.read_excel(file_path)
        cols = {str(c).strip(): c for c in df.columns}
        loaded = 0

        def add_val(v):
            nonlocal loaded
            if v is None:
                return
            s = str(v).strip()
            if not s or s.lower() in ("nan", "none"):
                return
            if self.add_item(s):
                loaded += 1

        # 권장 컬럼 우선
        if any(k in cols for k in ("업체명", "금지업체")):
            for v in df[cols.get("업체명", cols.get("금지업체"))].tolist():
                add_val(v)
        if "도메인" in cols:
            for v in df[cols["도메인"]].tolist():
                add_val(v)
        if "이메일" in cols:
            for v in df[cols["이메일"]].tolist():
                add_val(v)

        # 위에서 아무것도 못 읽었으면 전체 훑기
        if loaded == 0 and len(df.columns) > 0:
            for c in df.columns:
                for v in df[c].tolist():
                    add_val(v)

        return loaded

    def sync_with_cloud(self) -> int:
        """
        구글 시트 BlockList 워크시트의 데이터를 병합합니다.
        기대 컬럼명: 업체명/금지업체, 도메인, 이메일
        - 헤더가 달라서 get_all_records()가 비정상인 경우를 대비해
          get_all_values()로 C열(이메일) fallback 로딩도 수행합니다.
        """
        ws = getattr(database, "block_sheet", None)
        if not ws:
            return 0

        loaded = 0

        # 1) 헤더 기반 로딩
        try:
            records = ws.get_all_records()
        except Exception:
            records = []

        for row in records:
            if not isinstance(row, dict):
                continue
            company = row.get("업체명", row.get("금지업체", ""))
            domain = row.get("도메인", "")
            email = row.get("이메일", "")
            if company and self.add_item(str(company)):
                loaded += 1
            if domain and self.add_item(str(domain)):
                loaded += 1
            if email and self.add_item(str(email)):
                loaded += 1

        # 2) C열 이메일 fallback (헤더 무관)
        try:
            rows = ws.get_all_values() or []
            for idx, row in enumerate(rows):
                # 일반적으로 첫 줄은 헤더일 수 있으므로 스킵
                if idx == 0:
                    continue
                if len(row) >= 3:
                    c_email = str(row[2]).strip()
                    if c_email and c_email.lower() not in ("email", "이메일"):
                        if self.add_item(c_email):
                            loaded += 1
        except Exception:
            pass

        return loaded

    def should_block(self, company: str, url: str, email_str: str) -> bool:
        c = _norm_token(company)
        d = _norm_domain_from_url(url)
        e = _norm_token(email_str)

        with self._lock:
            blocked_companies = tuple(self._blocked_companies)
            blocked_domains = set(self._blocked_domains)
            blocked_emails = set(self._blocked_emails)

        if c and any(b and (b in c) for b in blocked_companies):
            return True
        if d and (d in blocked_domains):
            return True
        if e and (e in blocked_emails):
            return True

        if email_str:
            parts = [p.strip().lower() for p in str(email_str).split(",") if p.strip()]
            if any(p in blocked_emails for p in parts):
                return True
            for p in parts:
                if "@" in p:
                    md = p.split("@", 1)[1].strip().lower()
                    if md.startswith("www."):
                        md = md[4:]
                    if md in blocked_domains:
                        return True

        return False

