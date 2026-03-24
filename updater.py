import os
import re
import shutil
import urllib.request


def _version_to_tuple(v: str):
    nums = re.findall(r"\d+", str(v or "0"))
    if not nums:
        return (0,)
    return tuple(int(x) for x in nums)


def is_newer_version(latest_version: str, current_version: str) -> bool:
    return _version_to_tuple(latest_version) > _version_to_tuple(current_version)


def _extract_from_version_sheet(version_sheet):
    if not version_sheet:
        return "", ""
    try:
        rows = version_sheet.get_all_values() or []
    except Exception:
        return "", ""
    if not rows:
        return "", ""

    # 형식 A: 헤더 행 + 값 행
    # 예) A1=LatestVersion, B1=UpdateLink / A2=6.2, B2=https://...
    if len(rows) >= 2:
        headers = [str(x).strip().lower() for x in rows[0]]
        values = rows[1]
        if any(h in ("latestversion", "latest_version", "version") for h in headers):
            latest = ""
            link = ""
            for idx, h in enumerate(headers):
                val = str(values[idx]).strip() if idx < len(values) else ""
                if h in ("latestversion", "latest_version", "version"):
                    latest = val
                elif h in ("updatelink", "update_link", "link", "url"):
                    link = val
            if latest or link:
                return latest, link

    # 형식 B: key-value 세로형
    # 예) A1=LatestVersion B1=6.2 / A2=UpdateLink B2=https://...
    kv = {}
    for r in rows:
        if not r:
            continue
        k = str(r[0]).strip().lower() if len(r) >= 1 else ""
        v = str(r[1]).strip() if len(r) >= 2 else ""
        if k:
            kv[k] = v
    latest = kv.get("latestversion") or kv.get("latest_version") or kv.get("version", "")
    link = kv.get("updatelink") or kv.get("update_link") or kv.get("link") or kv.get("url", "")
    return latest, link


def extract_update_info(all_users, version_sheet=None):
    # 1순위: 버전 전용 워크시트
    latest_version, update_link = _extract_from_version_sheet(version_sheet)
    if latest_version or update_link:
        return latest_version, update_link

    # 2순위(하위호환): 회원 시트 첫 행
    if not all_users:
        return "", ""
    latest_version = str(all_users[0].get("LatestVersion", "")).strip()
    update_link = str(all_users[0].get("UpdateLink", "")).strip()
    return latest_version, update_link


def download_update_file(update_link: str, download_dir: str):
    if not update_link:
        raise ValueError("업데이트 링크가 비어 있습니다.")

    os.makedirs(download_dir, exist_ok=True)
    filename = os.path.basename(update_link.split("?", 1)[0]).strip() or "update_package.bin"
    target_path = os.path.join(download_dir, filename)

    req = urllib.request.Request(update_link, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as response, open(target_path, "wb") as out:
        shutil.copyfileobj(response, out)
    return target_path


def run_update_file(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    os.startfile(path)

