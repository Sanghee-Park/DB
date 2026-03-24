# 파일명: database.py

import gspread
import os
from oauth2client.service_account import ServiceAccountCredentials

def connect_sheet():
    """구글 시트와 연결하고 시트 객체를 반환합니다."""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cred_path = os.path.join(base_dir, "credentials.json")
        creds = ServiceAccountCredentials.from_json_keyfile_name(cred_path, scope)
        client = gspread.authorize(creds)
        worksheet = client.open("마케팅 프로그램 관리 시트").get_worksheet(0)
        # Windows 콘솔(cp949) 환경에서 이모지 출력 시 UnicodeEncodeError가 날 수 있어 안전한 문자열만 출력합니다.
        print("[OK] 구글 시트(DB) 연결 성공!")
        return worksheet
    except Exception as e:
        print(f"[ERROR] 구글 시트 연결 실패: {e}")
        return None

def connect_block_sheet():
    """구글 시트의 BlockList 워크시트를 연결합니다."""
    if not sheet:
        return None
    try:
        spreadsheet = sheet.spreadsheet
        # 1) 우선 후보명을 직접 시도
        for name in ("BlockList", "blacklist", "Blacklist"):
            try:
                ws = spreadsheet.worksheet(name)
                print(f"[OK] {name} 워크시트 연결 성공!")
                return ws
            except Exception:
                pass

        # 2) 대소문자/표기 변형 대응: 워크시트 이름 전체 스캔
        try:
            for ws in spreadsheet.worksheets():
                title = str(getattr(ws, "title", "")).strip()
                if title.lower() == "blacklist":
                    print(f"[OK] {title} 워크시트 연결 성공!")
                    return ws
        except Exception:
            pass

        print("[WARN] blacklist 워크시트를 찾지 못했습니다.")
        return None
    except Exception as e:
        print(f"[WARN] BlockList 워크시트 연결 실패: {e}")
        return None

def connect_version_sheet():
    """구글 시트의 버전 관리 워크시트를 연결합니다."""
    if not sheet:
        return None
    try:
        spreadsheet = sheet.spreadsheet
        # 권장명: app_version
        for name in ("app_version", "AppVersion", "version", "Version", "업데이트"):
            try:
                ws = spreadsheet.worksheet(name)
                print(f"[OK] {name} 워크시트 연결 성공!")
                return ws
            except Exception:
                pass

        # 대소문자/공백 무시 탐색
        try:
            for ws in spreadsheet.worksheets():
                title = str(getattr(ws, "title", "")).strip().lower().replace(" ", "")
                if title in ("app_version", "appversion", "version", "업데이트"):
                    print(f"[OK] {getattr(ws, 'title', '')} 워크시트 연결 성공!")
                    return ws
        except Exception:
            pass

        print("[WARN] 버전 워크시트를 찾지 못했습니다. (권장: app_version)")
        return None
    except Exception as e:
        print(f"[WARN] 버전 워크시트 연결 실패: {e}")
        return None

# 다른 파일에서 database.sheet 로 바로 쓸 수 있게 미리 연결해둡니다.
sheet = connect_sheet()
block_sheet = connect_block_sheet()
version_sheet = connect_version_sheet()