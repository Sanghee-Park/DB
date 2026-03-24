# B2B DB Extractor PRO v1.0 Update Plan

## 1. 개요 (Overview)
본 프로젝트는 `customtkinter`, `selenium`, `gspread`를 활용한 B2B 연락처(이메일, 전화번호) 수집 데스크톱 애플리케이션이다. 
기존 v6.1에 이어, 다음 4가지 핵심 자동화 및 고도화 기능을 추가한다.

## 2. 작업 프로세스 및 보고 규칙 (Workflow & Reporting Rules) 🌟
Cursor AI는 아래의 작업을 수행하면서 반드시 다음 두 가지 규칙을 엄격하게 지켜야 한다.
1. **진척도 체크 (Task Tracking)**: 아래 '3. 파일별 세부 구현 지침'에 있는 체크박스(`[ ]`)를 작업이 완료될 때마다 완료(`[x]` 또는 ✅)로 변경하여 진행 상황을 실시간으로 표시할 것.
2. **체인지로그 보고 (Changelog Update)**: 하나의 Phase 작업이 끝날 때마다 반드시 `changelog.md` 파일의 최신 날짜(Today) 항목에 진입하여, 어떤 파일을 어떻게 수정/추가했는지 작업 내역을 상세히 기록(보고)할 것.

---

## 3. 파일별 세부 구현 지침 (Implementation Guide)

### Phase 1: 로컬 추출 이력 관리 시스템 구축 (Anti-Duplicate)
- [x] **신규 파일 생성**: `history_manager.py`
  - `LocalHistoryManager` 클래스 구현.
  - 앱 실행 경로에 `local_history.json` 파일을 생성하고 읽기/쓰기 수행.
  - 저장 데이터 포맷: `{"emails": ["a@a.com", ...], "domains": ["abc.com", ...]}`
  - 메서드: `is_duplicate(email, domain)`, `add_record(email, domain)`, `save_to_file()`
  - 스레드 안전성(Threading Lock) 보장 필수.

### Phase 2: 클라우드 차단목록 연동 (Cloud Blocklist)
- [x] **대상 파일**: `database.py`, `blocklist.py`
  - `database.py`: 구글 시트에서 `BlockList` 워크시트를 불러오는 로직 추가 (`database.block_sheet` 객체 생성).
  - `blocklist.py`: 초기화 시 `database.block_sheet`의 데이터를 읽어와서 `self.blocked_companies`, `self.blocked_domains`, `self.blocked_emails`에 병합하는 `sync_with_cloud()` 메서드 추가.

### Phase 3: 다중 키워드 예약 및 자동 저장 (Keyword Queuing)
- [x] **대상 파일**: `ui_daum.py`, `ui_jobkorea.py`
  - 입력부 변경: `entry_keyword`에서 입력받은 문자열을 쉼표(,) 기준으로 split 하여 리스트화.
  - 크롤링 엔진 변경: 한 키워드의 수집이 끝나면 자동으로 `save_to_excel(auto=True)`를 호출하여 저장한 뒤, UI 테이블을 클리어하고 큐에 있는 다음 키워드 수집을 즉시 시작.
  - 무료 플랜(50개 제한) 적용 시, 전체 키워드 누적 카운트가 50개가 넘으면 전체 큐를 즉시 중단.
  - 중복 방지 연동: 추출된 데이터가 `history_manager`에 존재하는지 확인하고, 존재하면 엑셀 및 UI에 추가하지 않고 스킵.

### Phase 4: 자동로그인 (Auto-Login)
- [x] **대상 파일**: `main.py`
  - UI 추가: `LoginWindow`에 `[v] 자동로그인` Checkbox 추가.
  - 인증 로직: 체크박스 활성화 상태로 로그인 성공 시 `auth_config.json`에 계정 정보 인코딩 저장.
  - 앱 초기 진입점(`if __name__ == "__main__":`)에서 `auth_config.json`이 존재하면 즉시 `database.sheet`를 조회하여 계정 유효성(승인대기, 만료일) 검사 후 바로 메인 화면 진입.

---

## 4. Cursor AI를 위한 ⚠️ 엄격한 코딩 규칙 (Constraints)
1. **기존 로직 파괴 금지**: 요금제(`무료`, `기간제`, `영구`, `승인대기`)에 따른 예외 처리 및 탭 잠금 로직, 날짜 방어 로직은 절대 건드리지 말 것.
2. **스레드 안전성 (Thread Safety)**: UI 업데이트는 반드시 `self.after(0, ...)`를 사용하고, 데이터 충돌을 막기 위해 락(`Lock`)을 적극 활용할 것.
3. **가독성 및 모듈화**: 코드를 한 곳에 욱여넣지 말고, 기능별로 깔끔하게 분리할 것.