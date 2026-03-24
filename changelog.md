# Changelog

## 2026-03-10

### Phase 1 완료 - 로컬 추출 이력 관리 시스템
- `history_manager.py` 신규 생성
  - `LocalHistoryManager` 구현
  - `local_history.json` 자동 생성/로드/저장
  - `is_duplicate(email, domain)`, `add_record(email, domain)`, `save_to_file()` 구현
  - `threading.Lock` 기반 스레드 안전 처리

### Phase 2 완료 - 클라우드 차단목록 연동
- `database.py`
  - `connect_block_sheet()` 추가
  - 구글 시트 `BlockList` 워크시트 연결 객체 `database.block_sheet` 생성
- `blocklist.py`
  - 초기화 시 `sync_with_cloud()` 호출
  - `sync_with_cloud()` 메서드 추가: 시트의 업체명/도메인/이메일 데이터를 공용 차단목록으로 병합

### Phase 3 완료 - 다중 키워드 예약 및 자동 저장
- `ui_daum.py`
  - 키워드를 쉼표(,) 기준 큐로 분리하여 순차 처리
  - 키워드 1개 완료 시 `save_to_excel(auto=True)` 자동 저장 후 다음 키워드 진행
  - 무료 플랜의 전체 큐 누적 한도(50/일) 연동
  - `history_manager` 기반 중복 이력 스킵(이메일/도메인)
  - 자동 저장 경로 `autosave/` 폴더 생성 및 타임스탬프 파일명 적용
- `ui_jobkorea.py`
  - 키워드 큐 기반 순차 수집 + 키워드 단위 자동 저장
  - `history_manager` 기반 중복 이력 스킵(이메일/도메인)
  - 자동 저장 경로 `autosave/` 폴더 적용

### Phase 4 완료 - 자동로그인
- `main.py`
  - 로그인 화면에 `자동로그인` 체크박스 추가
  - 로그인 성공 + 체크 활성화 시 `auth_config.json`에 계정정보 인코딩(base64) 저장
  - 앱 시작 시 `auth_config.json` 존재 시 자동 인증 시도
  - 자동 인증 시에도 `승인대기`, `기간제 만료` 검증 후 통과 시 메인 화면 즉시 진입

## 2026-03-24

### Added
- 공용 금지목록 모듈 `blocklist.py` 추가
  - `BlockList` 클래스 도입
  - 업체명/도메인/이메일 차단 세트 관리
  - 스레드 안전(`threading.Lock`)
  - UI 동기화를 위한 구독/알림(`subscribe`, `unsubscribe`, `_notify`)
  - 엑셀 로딩(`load_from_excel`) 지원
  - 통합 차단 판정(`should_block`) 제공

- Daum UI에 금지목록 관리 기능 추가
  - 직접 입력 추가
  - 엑셀 불러오기
  - 초기화
  - 카운트 표시

- 잡코리아 UI에 금지목록 관리 기능 추가
  - 직접 입력 추가
  - 엑셀 불러오기
  - 초기화
  - 카운트 표시

### Changed
- 금지목록을 탭별 독립 상태에서 **앱 공용 상태**로 변경
  - `main.py`에서 `BlockList()` 인스턴스 1개 생성
  - `DaumTabUI`와 `JobKoreaTabUI`에 동일 객체 주입
  - Daum 내부 다중 추출 탭도 동일 공용 객체 공유

- 크롤러 함수 시그니처 정리
  - `run_daum_crawler(..., blocklist=...)`
  - `run_jobkorea_crawler(..., blocklist=...)`
  - 수집 직전 `blocklist.should_block(...)` 적용

- 입력 검증 UX 개선
  - 페이지/키워드/옵션 미입력 시 무반응 `return` 대신 경고 메시지 제공

### Fixed
- Windows cp949 콘솔 인코딩 에러 대응
  - `database.py`의 이모지 출력 제거
  - `[OK]`, `[ERROR]` 텍스트 로그로 변경

### Notes
- 현재 금지목록은 메모리 기반으로 동작하며 앱 종료 시 초기화됨
- 필요 시 다음 단계로 금지목록 영속화(JSON/Excel 자동 저장/로드) 확장 가능

