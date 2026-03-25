# Changelog

## 2026-03-26

### Phase 5 완료 - 기존 추출 DB 병합 및 지정 폴더 저장 개편

### Added
- `history_manager.py`
  - `merge_from_excel(file_path)` 메서드 추가
  - 기존 추출 엑셀(다중 시트 포함)에서 이메일/도메인(홈페이지/URL 포함)을 읽어 `local_history.json`로 병합

- `ui_daum.py`, `ui_jobkorea.py`
  - 하단 컨트롤에 `📂 기존 추출 DB 불러오기` 버튼 추가
  - 선택한 엑셀 파일의 과거 데이터(이메일/도메인)를 로컬 중복 이력에 대량 반영

### Changed
- `ui_daum.py`, `ui_jobkorea.py`
  - 다중 키워드 큐 완료 시 전체 통합 파일 저장 로직을 키워드 단위 저장으로 개편
  - 키워드 1개 완료 즉시 사용자 지정 폴더에 `키워드명_결과.xlsx` 형식으로 자동 저장
  - 동일 파일명 충돌 시 `키워드명_결과_2.xlsx` 형태로 자동 분기 저장
  - 저장 후 `data_list`와 UI 테이블을 즉시 초기화하여 다음 키워드 데이터와 완전 분리
  - `📁 저장폴더` 버튼명을 `📁 저장폴더 선택`으로 명확화

## 2026-03-25

### Added
- 자동업데이트 모듈 `updater.py` 신규 추가
  - 버전 비교(`is_newer_version`)
  - 업데이트 정보 추출(`extract_update_info`)
  - 업데이트 파일 다운로드(`download_update_file`)
  - 다운로드 파일 실행(`run_update_file`)

- 로그인 화면 기능 확장 (`main.py`)
  - `업데이트 확인` 버튼 추가
  - 로그인 직전 새 버전 감지 시 자동 다운로드/실행 플로우 연결
  - 메인 진입 후 백그라운드 업데이트 체크 추가

- 저장/수집 UX 확장 (`ui_daum.py`, `ui_jobkorea.py`)
  - `📁 저장폴더` 선택 버튼 추가
  - 예약 키워드 입력 박스(줄바꿈/쉼표 일괄 등록) 추가
  - 전체 키워드 완료 시 단일 엑셀 자동 저장(키워드별 시트 분리)

### Changed
- 앱 버전값을 `1.0`으로 변경 (`main.py`)

- 버전 정보 조회 구조 개선
  - 회원 시트 첫 행 의존 방식에서 버전 전용 워크시트 우선 조회 방식으로 확장
  - `database.version_sheet` 연결 추가 (`database.py`)
  - 지원 워크시트명: `app_version`, `version`, `업데이트` 등(탐색 로직 포함)
  - 버전 시트 미존재 시 기존 회원 시트 첫 행 데이터로 fallback

- 금지목록 클라우드 연동 강화
  - `blacklist` 워크시트명(소문자) 자동 인식 지원
  - C열 이메일 fallback 로딩 유지/보강
  - 금지 이메일이 하나라도 포함된 업체는 업체 전체 스킵 처리

- 중복 이력 로직 강화
  - 대표 이메일 1건 중심에서 이메일 개별 저장/검사로 확장
  - 다중 이메일 추출 시 이메일별 개별 행 저장(동일 업체명 유지)

### Fixed
- 로그인 시 업데이트 안내에서 `아니오`를 눌렀을 때 로그인까지 차단되던 흐름 수정
- `credentials.json` 상대경로 문제 수정 (파일 기준 절대경로 사용)
- 패키징 EXE에서 `pyi_rth_pyqt5` 인코딩 오류 회피를 위해 경량 portable 빌드 라인 추가

### Build / Release
- PyInstaller 배포본 생성
  - 폴더형: `dist/B2B_Extractor_v1.0/`
  - 단일 실행형: `dist/B2B_Extractor_v1.0_portable.exe`

- GitHub 업로드 진행
  - 저장소 초기화/커밋/원격 푸시 완료
  - 태그 `v1.0.0` 생성 및 푸시 완료
  - `dist/B2B_Extractor_v1.0_portable.exe` 파일을 저장소에 커밋하여 다운로드 가능 상태로 반영
  - 참고: Release Assets 첨부는 GitHub CLI 인증 완료 후 추가 게시 가능

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

