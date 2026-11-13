"""냉장고 ON · 로그인 없는 가족 공용 최종 버전
GitHub 최상위에 app.py와 requirements.txt를 업로드하고 Streamlit Cloud에서
Main file path를 app.py로 지정합니다. SQL 실행이나 Secrets 입력은 필요 없습니다.
DB는 실행 시 자동 생성됩니다. Cloud 로컬 디스크는 영구 보장되지 않습니다.
로컬 실행: streamlit run app.py
"""
from __future__ import annotations

import copy
import html
import io
import json
import re
import secrets
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit

import pandas as pd
import qrcode
import streamlit as st
import sqlite3
import hashlib
from pathlib import Path

st.set_page_config(page_title="냉장고 ON", page_icon="🥬", layout="wide", initial_sidebar_state="collapsed")
KST = ZoneInfo("Asia/Seoul")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;600;700;800&display=swap');
html,body,[class*="css"],.stApp{font-family:'Noto Sans KR',sans-serif;color:#19362a}
.stApp{background:#f5f8f3}
.block-container{max-width:1160px;padding-top:1.5rem;padding-bottom:2rem}
header[data-testid="stHeader"]{background:transparent}
.hero{background:linear-gradient(110deg,#e3f4cd,#f5fbe9);border:1px solid #d8e8c8;border-radius:24px;padding:22px 26px;margin-bottom:14px}
.hero .eyebrow{font-size:11px;letter-spacing:3px;color:#467236;font-weight:800}
.hero h1{font-size:30px;letter-spacing:-1.5px;padding:4px 0;margin:0;color:#193e28}
.hero p{margin:4px 0 0;color:#486442;font-size:13px}
.card{background:white;border:1px solid #e0e9db;border-radius:16px;padding:14px 16px;margin:7px 0}
.card h4{margin:0 0 6px;font-size:16px}.card p{margin:3px 0;font-size:13px;color:#4b6556}
.pill{display:inline-block;background:#edf6e5;color:#365a27;border-radius:20px;padding:3px 9px;font-size:11px;font-weight:700}
.bad{background:#fff0ec;color:#9a382b}.warn{background:#fff5d6;color:#795400}
[data-testid="stMetric"]{background:#fff;border:1px solid #e0e9db;padding:12px;border-radius:16px}
[data-testid="stMetricLabel"]{font-size:12px}[data-testid="stMetricValue"]{font-size:25px}
.stButton>button,.stDownloadButton>button,.stFormSubmitButton>button{border-radius:12px;min-height:42px;font-weight:600;border-color:#d6e4cd}
.stButton>button[kind="primary"],.stFormSubmitButton>button[kind="primary"]{background:#426d32;color:white;border-color:#426d32}
[data-testid="stExpander"]{background:white;border:1px solid #e0e9db;border-radius:14px}
button[data-baseweb="tab"]{font-weight:700;font-size:14px}
[data-testid="stVerticalBlock"]{gap:.65rem}
@media(max-width:640px){.block-container{padding:1rem .8rem 1.5rem}.hero{padding:17px}.hero h1{font-size:26px}
[data-testid="stHorizontalBlock"]{gap:.55rem}[data-testid="stMetric"]{padding:9px}[data-testid="stMetricValue"]{font-size:21px}}

:root{color-scheme:light}
[data-testid="stAppViewContainer"], [data-testid="stMain"]{background:#f5f8f3;color:#19362a}
[data-testid="stWidgetLabel"] p, [data-testid="stMetricLabel"] p, [data-testid="stMetricValue"],label,summary{color:#19362a!important}
input,textarea,[data-baseweb="input"],[data-baseweb="base-input"],[data-baseweb="select"]>div{background:#fff!important;color:#19362a!important;-webkit-text-fill-color:#19362a!important}
input::placeholder{color:#64775e!important;-webkit-text-fill-color:#64775e!important}
[data-baseweb="popover"],[role="listbox"],[role="option"]{background:#fff!important;color:#19362a!important}
[data-testid="stExpander"] details,[data-testid="stExpander"] summary, [data-testid="stForm"]{background:#fff;color:#19362a}
button{color:#19362a}button[kind="primary"]{color:#fff!important}
[data-baseweb="tab-list"]{background:#f5f8f3}button[role="tab"]{color:#294b30!important}

/* 테마와 관계없이 페이지 이동 버튼의 대비 확보 */
[data-testid="stButton"] > button {
 background-color:#e6f3d8 !important;
 color:#234327 !important;
 border:1px solid #7aa657 !important;
 border-radius:12px !important;
 min-height:44px;
 font-weight:700 !important;
}
[data-testid="stButton"] > button p {
 color:#234327 !important;
 -webkit-text-fill-color:#234327 !important;
}
[data-testid="stButton"] > button:hover:not(:disabled) {
 background-color:#cfe7b7 !important;
 border-color:#47752d !important;
}
[data-testid="stButton"] > button:disabled {
 background-color:#edf0e9 !important;
 border-color:#c6cebe !important;
 color:#687562 !important;
 opacity:1 !important;
}
[data-testid="stButton"] > button:disabled p {
 color:#687562 !important;
 -webkit-text-fill-color:#687562 !important;
}
[data-testid="stButton"] > button:focus-visible {
 outline:3px solid #47752d !important;
 outline-offset:2px;
}

</style>
"""
CATEGORIES = ["채소", "과일", "육류", "수산물", "유제품·달걀", "곡물·면", "양념", "가공식품", "기타"]
LOCATIONS = ["냉장", "냉동", "실온"]
UNITS = ["개", "g", "kg", "ml", "L", "팩", "봉", "병", "단"]
BASICS = {"달걀":"유제품·달걀", "우유":"유제품·달걀", "치즈":"유제품·달걀", "양파":"채소", "대파":"채소", "당근":"채소", "감자":"채소", "양배추":"채소", "애호박":"채소", "토마토":"채소", "김치":"가공식품", "두부":"가공식품", "참치":"가공식품", "돼지고기":"육류", "닭고기":"육류", "소고기":"육류", "밥":"곡물·면", "파스타":"곡물·면", "식빵":"곡물·면", "사과":"과일", "바나나":"과일"}
# 재료 일치 여부 기반 추천입니다. 분량 충족을 보장하지 않으며 양념도 누락시키지 않습니다.
RECIPES = [('김치볶음밥', ['김치', '대파', '소시지', '달걀', '밥', '설탕', '간장', '고춧가루', '식용유'], '대파와 소시지를 기름에 볶고 설탕과 간장을 넣습니다. 잘게 썬 김치와 고춧가루를 넣어 볶은 뒤 밥을 섞고 완전히 익힌 달걀을 곁들입니다.'), ('참치김치찌개', ['참치', '김치', '두부', '마늘', '고추', '양파', '대파', '참기름', '설탕', '고춧가루', '간장'], '김치를 참기름에 볶고 설탕과 양파를 넣습니다. 물을 부어 끓이고 참치, 두부, 마늘, 고추, 대파를 넣어 익힌 뒤 고춧가루와 간장으로 간합니다.'), ('제육볶음', ['돼지고기', '양배추', '양파', '버섯', '당근', '고추', '대파', '참기름', '깨', '식용유', '설탕', '고추장', '고춧가루', '간장', '마늘', '맛술', '후추'], '채소와 얇게 썬 돼지고기를 준비합니다. 팬에 기름을 두르고 고기와 설탕을 볶습니다. 고추장·고춧가루·간장·마늘·맛술·후추와 물을 조금 넣고 볶다가 채소를 넣습니다. 고기 중심까지 완전히 익히고 참기름과 깨로 마무리합니다.'), ('된장찌개', ['된장', '두부', '애호박', '감자', '양파', '대파', '마늘'], '감자와 양파를 물에 끓이고 된장을 풉니다. 애호박과 두부를 넣어 익힌 뒤 대파와 다진 마늘을 넣어 끓입니다.'), ('순두부찌개', ['순두부', '돼지고기', '양파', '대파', '고춧가루', '간장', '마늘', '식용유', '달걀'], '기름에 대파와 고기를 볶고 불을 줄여 고춧가루를 섞습니다. 물과 양파, 간장, 마늘을 넣고 끓입니다. 순두부와 달걀을 넣어 고기와 달걀을 완전히 익힙니다.'), ('소고기미역국', ['소고기', '미역', '참기름', '간장', '마늘', '소금'], '불린 미역을 씻어 자릅니다. 소고기와 미역을 참기름에 볶고 물을 부어 충분히 끓인 뒤 마늘과 간장, 소금으로 간합니다.'), ('콩나물국', ['콩나물', '대파', '마늘', '소금'], '콩나물을 씻어 물에 넣고 충분히 익힙니다. 대파와 다진 마늘을 넣고 소금으로 간합니다.'), ('감자채볶음', ['감자', '당근', '양파', '식용유', '소금'], '감자를 채 썰어 전분을 헹구고 물기를 뺍니다. 채 썬 당근, 양파와 함께 기름에 볶아 완전히 익힌 뒤 소금으로 간합니다.'), ('달걀말이', ['달걀', '당근', '대파', '식용유', '소금'], '잘게 썬 당근과 대파를 달걀에 섞고 소금으로 간합니다. 기름 두른 팬에 얇게 부어 말아 가며 속까지 완전히 익힙니다.'), ('달걀찜', ['달걀', '대파', '소금'], '달걀을 풀어 물과 소금을 섞습니다. 내열 그릇에 담아 대파를 넣고 찜기에 쪄 중심까지 완전히 익힙니다.'), ('두부조림', ['두부', '양파', '대파', '간장', '고춧가루', '마늘', '설탕', '식용유'], '두부 물기를 제거하고 팬에 노릇하게 굽습니다. 양파와 대파, 나머지 양념과 물을 넣어 양념이 배도록 졸입니다.'), ('두부김치', ['두부', '김치', '돼지고기', '양파', '식용유', '간장', '설탕'], '두부를 데쳐 썹니다. 돼지고기를 기름에 완전히 익히고 김치와 양파, 간장, 설탕을 넣어 볶아 두부와 담습니다.'), ('김치전', ['김치', '부침가루', '식용유'], '잘게 썬 김치에 부침가루와 물을 넣어 반죽합니다. 기름 두른 팬에 얇게 펼쳐 양면을 충분히 익힙니다.'), ('감자전', ['감자', '소금', '식용유'], '감자를 갈아 물기를 조금 빼고 가라앉은 전분을 다시 섞습니다. 소금으로 간해 기름 두른 팬에 얇게 부쳐 속까지 익힙니다.'), ('잡채', ['당면', '소고기', '시금치', '당근', '양파', '버섯', '간장', '설탕', '참기름', '식용유', '깨'], '당면은 제품 안내대로 삶습니다. 채소와 고기를 각각 익히고 간장과 설탕으로 간합니다. 당면과 섞고 참기름과 깨로 마무리합니다.'), ('불고기', ['소고기', '양파', '대파', '당근', '간장', '설탕', '마늘', '참기름', '후추'], '얇은 소고기에 간장, 설탕, 마늘, 참기름, 후추를 섞어 냉장 상태에서 양념합니다. 썬 채소와 팬에서 고기 중심까지 충분히 익힙니다.'), ('닭볶음탕', ['닭고기', '감자', '당근', '양파', '대파', '고추장', '고춧가루', '간장', '설탕', '마늘'], '손질한 닭과 물을 끓이고 양념을 넣습니다. 감자와 당근, 양파를 넣어 닭고기 중심까지 완전히 익힌 뒤 대파를 넣어 끓입니다.'), ('오징어볶음', ['오징어', '양파', '당근', '양배추', '대파', '고추장', '고춧가루', '간장', '설탕', '마늘', '식용유'], '손질한 오징어와 채소를 썹니다. 양념을 섞고 기름 두른 팬에서 채소와 오징어를 볶아 완전히 익힙니다.'), ('고등어조림', ['고등어', '무', '양파', '대파', '간장', '고춧가루', '마늘', '설탕'], '냄비에 무를 깔고 손질한 고등어와 양파를 올립니다. 양념과 물을 넣고 생선과 무가 완전히 익도록 졸여 대파를 넣습니다.'), ('떡볶이', ['떡', '어묵', '대파', '고추장', '고춧가루', '설탕', '간장'], '물에 고추장과 고춧가루, 설탕, 간장을 풀어 끓입니다. 떡과 어묵을 넣어 익히고 대파를 넣어 농도를 맞춥니다.'), ('잔치국수', ['국수', '애호박', '당근', '달걀', '멸치', '다시마', '간장', '소금'], '멸치와 다시마로 국물을 내 간장과 소금으로 간합니다. 채소와 달걀 고명을 익혀 준비합니다. 삶아 헹군 국수에 뜨거운 국물과 고명을 올립니다.'), ('비빔국수', ['국수', '오이', '김치', '고추장', '식초', '설탕', '간장', '참기름'], '국수를 삶아 찬물에 헹굽니다. 고추장, 식초, 설탕, 간장, 참기름으로 양념을 만들어 썬 김치와 오이, 국수를 섞습니다.'), ('오이무침', ['오이', '양파', '고춧가루', '식초', '설탕', '간장', '마늘', '깨'], '오이와 양파를 썰고 고춧가루, 식초, 설탕, 간장, 마늘을 넣어 먹기 직전에 무쳐 깨를 뿌립니다.'), ('시금치나물', ['시금치', '마늘', '참기름', '소금', '깨'], '시금치를 씻어 끓는 물에 데치고 찬물에 헹궈 물기를 짭니다. 마늘, 참기름, 소금, 깨를 넣어 무칩니다.'), ('프렌치토스트', ['식빵', '달걀', '우유', '버터', '설탕'], '달걀과 우유, 설탕을 섞어 식빵을 적십니다. 버터를 녹인 팬에서 양면과 중심까지 완전히 익힙니다.'), ('토마토달걀볶음', ['토마토', '달걀', '식용유', '소금'], '달걀을 풀어 기름에 익혀 덜어 둡니다. 토마토를 볶아 부드러워지면 달걀을 다시 넣고 소금으로 간해 충분히 익힙니다.'), ('알리오올리오', ['파스타', '마늘', '올리브유', '고추', '소금'], '파스타를 삶습니다. 팬에 올리브유, 썬 마늘과 고추를 넣어 약불로 향을 낸 뒤 면과 면수를 넣어 섞고 간합니다.'), ('볶음우동', ['우동', '양배추', '양파', '당근', '돼지고기', '간장', '굴소스', '식용유'], '우동 면을 제품 안내대로 준비합니다. 팬에 고기를 완전히 익히고 채소를 볶은 뒤 면, 간장, 굴소스를 넣어 고루 볶습니다.')]
# 원문을 확인한 메뉴만 직접 출처를 연결합니다. 나머지는 일반 가정식의 간단한 조리 예시입니다.
RECIPE_SOURCES = {
 "김치볶음밥": ("만개의레시피 · 공개 레시피 참고", "https://www.10000recipe.com/recipe/6932188"),
 "참치김치찌개": ("공감신문 · 공개 레시피 참고", "https://www.gokorea.kr/news/articleView.html?idxno=294324"),
 "제육볶음": ("Samsung Food · 공개 레시피 참고", "https://app.samsungfood.com/recipes/10701930e56db1a72f48e1d09f8b09a2211")
}
ALIASES = {"계란":"달걀", "흰쌀밥":"밥", "쌀밥":"밥", "캔참치":"참치", "참치캔":"참치", "스파게티면":"파스타", "식용유":"식용유", "계란":"달걀", "요구르트":"요거트", "닭가슴살":"닭고기", "흰우유":"우유", "양송이버섯":"버섯", "느타리버섯":"버섯", "고추가루":"고춧가루", "다진마늘":"마늘", "청양고추":"고추", "홍고추":"고추", "국간장":"간장", "떡볶이떡":"떡", "우동면":"우동", "소면":"국수", "통깨":"깨", "깨소금":"깨", "새송이버섯":"버섯"}


def today():
    return datetime.now(KST).date()


def now():
    return datetime.now(KST).isoformat()


def esc(x):
    return html.escape(str(x))


def uid():
    return uuid.uuid4().hex


def clean_name(value, label="이름"):
    value = re.sub(r"\s+", " ", str(value)).strip()
    if not value or len(value) > 60:
        raise ValueError(f"{label}은 1~60자로 입력하세요.")
    return value


def qty(value):
    try:
        v = Decimal(str(value)).quantize(Decimal("0.001"))
    except (InvalidOperation, ValueError):
        raise ValueError("수량을 숫자로 입력하세요.")
    if not v.is_finite() or v < 0 or v > 1000000:
        raise ValueError("수량은 0~1,000,000 범위로 입력하세요.")
    return float(v)


def norm(s):
    s = str(s).replace(" ", "").lower()
    return ALIASES.get(s, s)


def days(item):
    return (date.fromisoformat(item["expiry"]) - today()).days


def active(state):
    return [i for i in state["items"] if i["status"] == "active" and i["quantity"] > 0]


def event(state, kind, item, amount=0, terminal=False, note=""):
    state["events"].append({"id":uid(), "at":now(), "actor":st.session_state.get("member", "가족"), "kind":kind,
        "item_id":item.get("id", ""), "name":item["name"], "quantity":qty(amount),
        "unit":item.get("unit", "개"), "terminal":terminal, "note":note[:500]})


def make_item(name, category, quantity, unit, bought, expiry, location):
    name = clean_name(name, "식재료 이름")
    quantity = qty(quantity)
    if quantity <= 0:
        raise ValueError("등록 수량은 0보다 커야 합니다.")
    if bought > today():
        raise ValueError("구매일은 오늘 이후로 설정할 수 없습니다.")
    if expiry < bought:
        raise ValueError("유통기한은 구매일보다 빠를 수 없습니다.")
    return {"id":uid(), "name":name, "category":category, "quantity":quantity, "unit":unit,
            "bought":bought.isoformat(), "expiry":expiry.isoformat(), "location":location,
            "status":"active", "created_by":st.session_state.member, "updated_by":st.session_state.member,
            "created_at":now(), "updated_at":now()}


def touch(item):
    item.update(updated_at=now(), updated_by=st.session_state.member)


DB_PATH = Path(__file__).resolve().with_name("fridge_on.sqlite3")


def rpc(action, revision=None, state=None):
    token = st.session_state.token
    if not re.fullmatch(r"[A-Za-z0-9_-]{22,128}", token):
        raise ValueError("INVALID_TOKEN")
    hashed = hashlib.sha256(token.encode()).hexdigest()
    with sqlite3.connect(str(DB_PATH), timeout=20) as conn:
        conn.execute("PRAGMA busy_timeout=20000")
        conn.execute("CREATE TABLE IF NOT EXISTS families (token_hash TEXT PRIMARY KEY, state TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL)")
        conn.execute("BEGIN IMMEDIATE")
        if action == "create":
            initial = {"members":[], "items":[], "shopping":[], "events":[]}
            conn.execute("INSERT INTO families VALUES (?, ?, 0, ?)", (hashed, json.dumps(initial), now()))
        elif action not in ("load", "save"):
            raise ValueError("허용되지 않는 작업입니다.")
        row = conn.execute("SELECT state, revision, updated_at FROM families WHERE token_hash=?", (hashed,)).fetchone()
        if not row:
            raise ValueError("FAMILY_NOT_FOUND")
        if action == "save":
            if row[1] != revision:
                raise ValueError("REVISION_CONFLICT")
            if not isinstance(state, dict) or not all(isinstance(state.get(k),list) for k in ("members","items","shopping","events")):
                raise ValueError("백업 데이터 구조가 올바르지 않습니다.")
            encoded = json.dumps(state, ensure_ascii=False, allow_nan=False)
            if len(encoded.encode()) > 5000000:
                raise ValueError("STATE_TOO_LARGE")
            timestamp = now()
            conn.execute("UPDATE families SET state=?, revision=revision+1, updated_at=? WHERE token_hash=? AND revision=?", (encoded, timestamp, hashed, revision))
            row = (encoded, revision+1, timestamp)
        return {"state":json.loads(row[0]), "revision":row[1], "updated_at":row[2]}


def error_message(exc):
    text = str(exc)
    if "REVISION_CONFLICT" in text:
        return "다른 가족이 먼저 변경했습니다. 최신 내용을 확인한 뒤 다시 시도하세요. 이번 변경은 저장되지 않았습니다."
    if "FAMILY_NOT_FOUND" in text:
        return "해당 가족 코드를 찾을 수 없습니다. 코드를 확인하세요."
    if "STATE_TOO_LARGE" in text:
        return "가족 데이터가 5MB 한도에 도달했습니다. 운영자에게 데이터 보관 정책을 문의하세요."
    if "INVALID_TOKEN" in text:
        return "가족 코드 형식이 올바르지 않습니다. 생성된 코드를 그대로 입력하세요."
    if isinstance(exc, ValueError):
        return text
    return "데이터를 읽거나 저장하지 못했습니다. 잠시 후 다시 시도하세요. 서버 디스크와 앱 로그를 확인해 주세요."


def commit(snapshot, mutate):
    """읽은 revision에 대한 원자적 저장. 충돌 시 자동 재시도하지 않음."""
    try:
        state = copy.deepcopy(snapshot["state"])
        mutate(state)
        rpc("save", snapshot["revision"], state)
        st.session_state.flash = ("success", "저장했습니다. 다른 가족은 새로고침 버튼으로 확인할 수 있습니다.")
        st.rerun()
    except Exception as exc:
        st.error(error_message(exc))


def auto_category(name):
    text = re.sub(r"\s+", "", str(name)).lower()
    if text in BASICS:
        return BASICS[text]
    rules = [
        ("가공식품", "김치 두부 참치캔 통조림 햄 소시지 만두 어묵 맛살 냉동피자"),
        ("유제품·달걀", "달걀 계란 우유 치즈 요구르트 요거트 버터 생크림"),
        ("육류", "돼지고기 소고기 쇠고기 닭고기 삼겹살 목살 닭가슴살 다짐육 베이컨 오리고기"),
        ("수산물", "연어 고등어 갈치 새우 오징어 문어 조개 홍합 바지락 멸치 미역 다시마 참치"),
        ("과일", "사과 배 바나나 귤 오렌지 포도 딸기 복숭아 키위 망고 수박 멜론 레몬 블루베리"),
        ("채소", "양파 대파 쪽파 당근 감자 고구마 양배추 배추 애호박 호박 오이 토마토 상추 시금치 브로콜리 버섯 마늘 생강 무 파프리카 고추 콩나물 숙주 깻잎 가지"),
        ("곡물·면", "쌀 밥 현미 귀리 밀가루 국수 파스타 스파게티 라면 식빵 빵 떡 우동 소면 당면"),
        ("양념", "소금 설탕 간장 된장 고추장 식초 식용유 올리브유 참기름 후추 케첩 마요네즈 소스 카레가루")]
    # 긴 식재료 이름을 먼저 비교해 '배추'를 '배'로 분류하지 않습니다.
    candidates = [(word, cat) for cat, words in rules for word in words.split()]
    for word, cat in sorted(candidates, key=lambda x: len(x[0]), reverse=True):
        if text == word or (len(word) >= 2 and word in text):
            return cat
    return "기타"


def item_inputs(prefix, initial=None):
    initial = initial or {}
    name = st.text_input("식재료 이름", value=initial.get("name", ""), max_chars=60, key=prefix+"name")
    c1, c2 = st.columns(2)
    quantity = c1.number_input("수량", min_value=0, max_value=1000000, value=int(initial.get("quantity", 1)), step=1, format="%d", key=prefix+"qty")
    expiry = c2.date_input("유통기한", value=date.fromisoformat(initial["expiry"]) if "expiry" in initial else today(), key=prefix+"exp")
    with st.expander("추가 설정 · 단위 / 위치 / 카테고리 / 구매일"):
        c1, c2 = st.columns(2)
        unit = c1.selectbox("단위", UNITS, index=UNITS.index(initial.get("unit", "개")), key=prefix+"unit")
        location = c2.selectbox("보관 위치", LOCATIONS, index=LOCATIONS.index(initial.get("location", "냉장")), key=prefix+"loc")
        c1, c2 = st.columns(2)
        category = c1.selectbox("카테고리 · 자동 분류 또는 직접 지정", ["자동 분류"] + CATEGORIES, key=prefix+"cat")
        if category == "자동 분류":
            category = auto_category(name)
        bought = c2.date_input("구매일", value=date.fromisoformat(initial["bought"]) if "bought" in initial else today(), key=prefix+"buy")
    return name, category, quantity, unit, bought, expiry, location


def parse_bulk(text, unit, bought, expiry, location):
    """공백/쉼표/줄바꿈으로 재료 분리. 수량은 '사과 3' 또는 '사과, 3'."""
    tokens = re.findall(r"[^\s,，;；]+", text.strip())
    entries = []
    for token in tokens:
        if re.fullmatch(r"[0-9]+", token):
            if not entries or entries[-1][1] is not None:
                raise ValueError("수량 앞에 재료 이름을 입력하세요. 예: 사과 3 복숭아 2")
            count = int(token)
            if not 1 <= count <= 1000000:
                raise ValueError("수량은 1~1,000,000의 정수로 입력하세요.")
            entries[-1][1] = count
        else:
            if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", token):
                raise ValueError("수량은 1 이상의 정수만 입력하세요.")
            entries.append([clean_name(token, "식재료 이름"), None])
    if not entries:
        raise ValueError("등록할 재료를 입력하세요.")
    if len(entries) > 200:
        raise ValueError("한 번에 최대 200개 재료까지 등록할 수 있습니다.")
    return [make_item(name, auto_category(name), count or 1, unit, bought, expiry, location)
            for name, count in entries]


def new_ingredient(snapshot):
    with st.expander("＋ 식재료 한 번에 등록", expanded=False):
        st.caption("공백·쉼표·줄바꿈으로 재료를 나누면 각각 등록됩니다. 예: 사과 복숭아 귤 → 3개 재고 항목. 수량은 사과 3 복숭아 2처럼 입력하며 생략하면 1입니다. 띄어쓴 이름은 각각 나뉘므로 닭가슴살처럼 붙여 쓰세요.")
        generation = st.session_state.get("bulk_generation", 0)
        with st.form(f"bulk_text_form_{generation}"):
            text = st.text_area("여러 식재료 입력", height=180, placeholder="사과 복숭아 귤\n양파 3 달걀 10", key=f"bulk_text_{generation}")
            c1, c2 = st.columns(2)
            unit = c1.selectbox("공통 단위", UNITS, key=f"bulk_unit_{generation}")
            location = c2.selectbox("공통 보관 위치", LOCATIONS, key=f"bulk_location_{generation}")
            c1, c2 = st.columns(2)
            bought = c1.date_input("공통 구매일", value=today(), key=f"bulk_bought_{generation}")
            expiry = c2.date_input("공통 유통기한", value=today(), key=f"bulk_expiry_{generation}")
            st.caption("이 날짜·단위·위치는 이번에 입력한 모든 재료에 적용됩니다. 서로 다르면 나누어 등록하거나 등록 후 재료별로 수정하세요.")
            submitted = st.form_submit_button("입력한 재료 모두 등록", type="primary", use_container_width=True)
        if submitted:
            try:
                prepared = parse_bulk(text, unit, bought, expiry, location)
                state = copy.deepcopy(snapshot["state"])
                # 같은 입력의 연속 제출을 동일 작업으로 처리합니다.
                signature = hashlib.sha256(json.dumps([generation, text.strip(), unit, str(bought), str(expiry), location], ensure_ascii=False).encode()).hexdigest()
                if st.session_state.get("last_bulk_signature") == signature:
                    st.info("이미 저장한 입력입니다. 새 재료를 입력해 주세요.")
                    return
                for item in prepared:
                    state["items"].append(item)
                    event(state, "등록", item, item["quantity"])
                rpc("save", snapshot["revision"], state)
            except Exception as exc:
                st.error(error_message(exc))
            else:
                st.session_state.last_bulk_signature = signature
                st.session_state.bulk_generation = generation + 1
                st.session_state.flash = ("success", f"식재료 {len(prepared)}건을 저장했습니다. 입력창을 비웠습니다.")
                st.rerun()


def inventory(snapshot):
    state = snapshot["state"]
    new_ingredient(snapshot)
    c1, c2, c3 = st.columns([2, 1, 1])
    query = c1.text_input("검색", placeholder="식재료 검색", label_visibility="collapsed", key="search")
    category = c2.selectbox("분류", ["전체"] + CATEGORIES, label_visibility="collapsed")
    location = c3.selectbox("위치", ["전체 위치"] + LOCATIONS, label_visibility="collapsed")
    items = sorted([i for i in active(state) if query.strip().lower() in i["name"].lower()
        and (category == "전체" or i["category"] == category)
        and (location == "전체 위치" or i["location"] == location)], key=lambda i: i["expiry"])
    if not items:
        st.info("표시할 식재료가 없습니다. 식재료를 등록하거나 필터를 바꿔 주세요.")
    page_size = 6
    pages = max(1, (len(items)+page_size-1)//page_size)
    signature = (query.strip().lower(), category, location)
    if st.session_state.get("inventory_filter_signature") != signature:
        st.session_state.inventory_page = 1
        st.session_state.inventory_filter_signature = signature
    page = max(1, min(int(st.session_state.get("inventory_page", 1)), pages))
    st.session_state.inventory_page = page
    def turn_page(delta):
        st.session_state.inventory_page = max(1, min(st.session_state.inventory_page + delta, pages))
    def pagination(position):
        previous, status, following = st.columns([1, 1.4, 1])
        previous.button("← 이전", disabled=page == 1, key="inv_prev_"+position,
                        on_click=turn_page, args=(-1,), use_container_width=True)
        status.markdown(f"**{page} / {pages} 페이지**", help=f"검색 결과 전체 {len(items)}개")
        following.button("다음 →", disabled=page == pages, key="inv_next_"+position,
                         on_click=turn_page, args=(1,), use_container_width=True)
    if items:
        start = (page-1)*page_size
        st.caption(f"전체 {len(items)}개 중 {start+1}–{min(start+page_size,len(items))}개 표시 · 유통기한순")
        pagination("top")
    for item in items[(page-1)*page_size:page*page_size]:
        delta = days(item)
        label, tone = (f"기한 경과 {abs(delta)}일", "bad") if delta < 0 else (("오늘까지" if delta == 0 else f"D-{delta}", "warn") if delta <= 3 else (f"D-{delta}", ""))
        st.markdown(f'<div class="card"><h4>{esc(item["name"])} <span class="pill {tone}">{label}</span></h4><p><b>{item["quantity"]:g} {esc(item["unit"])}</b> · {esc(item["location"])} · {esc(item["category"])} · {esc(item["expiry"])}</p><p>등록 {esc(item["created_by"])} · 최근 수정 {esc(item["updated_by"])}</p></div>', unsafe_allow_html=True)
        with st.expander("사용 · 수정 · 폐기 / "+item["name"]+" · "+item["id"][:4]):
            with st.form("use_"+item["id"]):
                used = st.number_input("사용 또는 폐기 수량", min_value=0, max_value=int(item["quantity"]), value=int(item["quantity"]), step=1, format="%d", key="use_qty_"+item["id"])
                action = st.radio("처리", ["소비", "폐기"], horizontal=True, key="use_action_"+item["id"])
                if delta < 0:
                    st.warning("기한이 지난 재료입니다. 안전을 확인하고 섭취 여부를 판단하세요. 추천 요리에서는 제외됩니다.")
                if st.form_submit_button("선택 수량 처리", use_container_width=True):
                    def consume(s, item_id=item["id"]):
                        target = next(i for i in s["items"] if i["id"] == item_id)
                        amount = qty(used)
                        if amount <= 0 or amount > target["quantity"]:
                            raise ValueError("현재 재고 이하의 양수를 입력하세요.")
                        target["quantity"] = qty(Decimal(str(target["quantity"]))-Decimal(str(amount)))
                        terminal = target["quantity"] == 0
                        if terminal:
                            target["status"] = "consumed" if action == "소비" else "discarded"
                        touch(target)
                        event(s, action, target, amount, terminal)
                    commit(snapshot, consume)
            with st.form("edit_"+item["id"]+item["updated_at"]):
                # 다른 기기에서 이 항목이 바뀌면 입력 위젯도 새 버전으로 교체합니다.
                vals = item_inputs("edit_"+item["id"]+item["updated_at"], item)
                st.caption("수량 감소는 소비 이력에 자동 반영되지 않습니다. 실제 사용은 위의 소비 처리를 이용하세요. 0으로 수정하면 잔량을 소비 완료 처리합니다.")
                if st.form_submit_button("정보 수정 저장", use_container_width=True):
                    def edit(s, item_id=item["id"]):
                        target = next(i for i in s["items"] if i["id"] == item_id)
                        v = list(vals)
                        newq = qty(v[2])
                        v[2] = newq if newq > 0 else 1
                        replacement = make_item(*v)
                        oldq = target["quantity"]
                        for key in ("name", "category", "quantity", "unit", "bought", "expiry", "location"):
                            target[key] = replacement[key]
                        target["quantity"] = newq
                        if newq == 0:
                            target["status"] = "consumed"
                            event(s, "소비", target, oldq, True, "수량 0으로 수정")
                        touch(target)
                        event(s, "수정", target, note=f"이전 수량 {oldq:g}, 새 수량 {newq:g}")
                    commit(snapshot, edit)
            with st.form("delete_"+item["id"]):
                confirm = st.checkbox("잘못 등록한 재고를 삭제합니다. 폐기 이력에는 포함하지 않습니다.", key="delete_confirm_"+item["id"])
                if st.form_submit_button("재고 삭제", use_container_width=True):
                    def delete(s, item_id=item["id"]):
                        if not confirm:
                            raise ValueError("삭제 확인에 체크하세요.")
                        target = next(i for i in s["items"] if i["id"] == item_id)
                        target["status"] = "deleted"
                        touch(target)
                        event(s, "삭제", target, target["quantity"])
                    commit(snapshot, delete)

    if items and pages > 1:
        pagination("bottom")


def recommend_recipes(items):
    usable = [i for i in items if i.get("status", "active") == "active" and i.get("quantity", 0) > 0 and days(i) >= 0]
    owned = {norm(i["name"]) for i in usable}
    remaining = {}
    for item in usable:
        name = norm(item["name"])
        remaining[name] = min(remaining.get(name, 1000000), days(item))
    results = []
    for title, required, method in RECIPES:
        have = [r for r in required if norm(r) in owned]
        missing = [r for r in required if norm(r) not in owned]
        soon = [r for r in have if remaining[norm(r)] <= 3]
        if len({norm(r) for r in have}) < 2:
            continue
        coverage = len(have) / len(required)
        nearest = min((remaining[norm(r)] for r in soon), default=999)
        results.append({"title":title, "required":required, "method":method,
                        "have":have, "missing":missing, "soon":soon,
                        "coverage":coverage, "nearest":nearest})
    # 추천 우선순위: 임박 여부 → 충족률 → 부족 수 → 가장 가까운 기한 → 임박 수.
    return sorted(results, key=lambda r:(-bool(r["soon"]), -r["coverage"], len(r["missing"]),
                                         r["nearest"], -len(r["soon"]), -len(r["have"]), r["title"]))


def cooking(snapshot):
    st.caption("기한이 지나지 않은 보유 재료를 서로 다른 종류로 2개 이상 활용하는 메뉴만 추천합니다. 임박 재료 활용을 우선하며, 재료명 일치 기준이므로 필요한 분량·알레르기·보관 상태는 직접 확인하세요. 양념도 보유 재료로 등록해야 보유로 표시됩니다.")
    results = recommend_recipes(active(snapshot["state"]))
    only = st.checkbox("부족한 재료 없는 메뉴만", value=False)
    results = [r for r in results if not only or not r["missing"]]
    if not results:
        st.info("보유 재료를 2종 이상 활용할 수 있는 메뉴가 없습니다. 재료를 더 등록하거나 부족 재료 필터를 해제하세요.")
    st.caption(f"기본 레시피 {len(RECIPES)}종 중 조건에 맞는 {len(results)}개를 모두 표시합니다. 정렬: 임박 재료 포함 → 보유 충족률 → 부족 재료 적은 순 → 가장 가까운 기한.")
    for recipe in results:
        with st.expander("🍽️ "+recipe["title"]+(" · 임박 재료 활용" if recipe["soon"] else "")+f' · 보유 {len(recipe["have"])}/{len(recipe["required"])}', expanded=False):
            st.write(f"**보유 충족률 {recipe['coverage']:.0%} · 부족 {len(recipe['missing'])}종**")
            st.write("**필요 재료** · "+", ".join(recipe["required"]))
            st.success("보유 · "+", ".join(recipe["have"]))
            if recipe["soon"]:
                st.write("**먼저 사용할 재료** · "+", ".join(recipe["soon"]))
            if recipe["missing"]:
                st.warning("부족 · "+", ".join(recipe["missing"]))
                st.caption("필요 분량은 레시피·인원에 따라 달라집니다. 장보기에는 각 1개(분량 확인 필요)로 추가합니다.")
                if st.button("부족 재료를 장보기에 추가", key="recipe_"+recipe["title"], use_container_width=True):
                    def missing(s, names=recipe["missing"]):
                        pending = {norm(x["name"]) for x in s["shopping"] if x["status"] == "pending"}
                        for name in names:
                            if norm(name) not in pending:
                                row = {"id":uid(), "name":name,"quantity":1.0,"unit":"개", "status":"pending", "note":"레시피 분량 확인 필요", "created_by":st.session_state.member,"updated_by":st.session_state.member,"created_at":now()}
                                s["shopping"].append(row)
                                event(s, "장보기 추가", row, 1, note=row["note"])
                                pending.add(norm(name))
                    commit(snapshot, missing)
            st.write("**조리 방법**")
            st.write(recipe["method"])
            source = RECIPE_SOURCES.get(recipe["title"])
            if source:
                st.link_button(source[0]+" · 분량 확인", source[1])
                st.caption("앱에는 재료를 정규화하고 조리법을 요약해 표시합니다. 정확한 계량과 선택 재료는 원문을 확인하세요.")
            else:
                st.caption("일반적으로 알려진 가정식의 간단한 조리 예시입니다. 특정 요리사나 사이트의 검증 레시피를 그대로 수록한 것은 아닙니다. 분량과 간은 인원에 맞게 조절하세요.")
    st.caption("확장 지점: recommend_recipes()를 교체하면 외부 AI 추천을 연결할 수 있습니다. 현재 앱은 별도 AI API 키 없이 동작하는 기본 레시피 추천입니다.")


def shopping(snapshot):
    state = snapshot["state"]
    with st.expander("＋ 장보기 항목 추가", expanded=False):
        with st.form("shopping_add", clear_on_submit=True):
            name = st.text_input("필요한 식재료", max_chars=60)
            c1, c2 = st.columns(2)
            count = c1.number_input("필요 수량", min_value=1, max_value=1000000, value=1, step=1, format="%d")
            unit = c2.selectbox("구매 단위", UNITS)
            override = st.checkbox("현재 재고가 있어도 추가합니다.")
            if name.strip():
                matches = [i for i in active(state) if norm(i["name"]) == norm(name)]
                if matches:
                    st.caption("현재 재고: "+", ".join(f'{i["quantity"]:g}{i["unit"]} ({i["location"]}, {i["expiry"]})' for i in matches))
            if st.form_submit_button("장보기에 추가", type="primary", use_container_width=True):
                def add(s):
                    n = clean_name(name, "식재료 이름")
                    if any(norm(x["name"]) == norm(n) and x["status"] == "pending" for x in s["shopping"]):
                        raise ValueError("이미 장보기 목록에 있습니다. 기존 항목을 확인하세요.")
                    stock = sum(i["quantity"] for i in active(s) if norm(i["name"]) == norm(n) and i["unit"] == unit and days(i) >= 0)
                    if stock >= count and not override:
                        raise ValueError(f"같은 단위의 사용 가능한 재고가 {stock:g}{unit} 있습니다. 그래도 필요하면 확인에 체크하세요.")
                    row = {"id":uid(),"name":n,"quantity":qty(count),"unit":unit,"status":"pending", "note":"", "created_by":st.session_state.member,"updated_by":st.session_state.member,"created_at":now()}
                    s["shopping"].append(row)
                    event(s, "장보기 추가", row, count)
                commit(snapshot, add)
    st.caption("재고 알림은 품목명·동일 단위 기준입니다. kg↔g, 팩↔개 등의 단위 변환은 추정하지 않습니다.")
    rows = [r for r in state["shopping"] if r["status"] in ("pending", "purchased")]
    if not rows:
        st.info("장보기 목록이 비어 있습니다.")
    pages = max(1, (len(rows)+5)//6)
    page = int(st.number_input("장보기 페이지 · 한 번에 6개", 1, pages, 1, key=f"shop_page_{pages}"))
    for row in rows[(page-1)*6:page*6]:
        label = "구매 완료 · 재고 등록 대기" if row["status"] == "purchased" else "구매 대기"
        with st.expander(f'{row["name"]} · {row["quantity"]:g}{row["unit"]} · {label} · {row["id"][:4]}'):
            st.caption(f'추가: {row["created_by"]} · 최근 변경: {row["updated_by"]} · {row.get("note", "")}')
            matches = [i for i in active(state) if norm(i["name"]) == norm(row["name"])]
            if matches:
                st.warning("중복 구매 확인: "+", ".join(f'{i["quantity"]:g}{i["unit"]} ({i["location"]}, {i["expiry"]})' for i in matches))
            purchased = st.checkbox("구매 완료", value=row["status"] == "purchased", key="bought_"+row["id"])
            if purchased != (row["status"] == "purchased"):
                def mark(s, rid=row["id"], value=purchased):
                    target = next(x for x in s["shopping"] if x["id"] == rid)
                    target["status"] = "purchased" if value else "pending"
                    target["updated_by"] = st.session_state.member
                    event(s, "구매 완료" if value else "구매 취소", target, target["quantity"])
                commit(snapshot, mark)
            if row["status"] == "purchased":
                with st.form("transfer_"+row["id"]):
                    vals = item_inputs("transfer_"+row["id"], {"name":row["name"],"quantity":row["quantity"],"unit":row["unit"],"category":BASICS.get(row["name"],"기타")})
                    if st.form_submit_button("구매 재료를 냉장고로 이동", type="primary", use_container_width=True):
                        def transfer(s, rid=row["id"]):
                            target = next(x for x in s["shopping"] if x["id"] == rid)
                            if target["status"] != "purchased":
                                raise ValueError("이미 이동했거나 구매 상태가 바뀌었습니다.")
                            item = make_item(*vals)
                            s["items"].append(item)
                            target.update(status="transferred", updated_by=st.session_state.member, item_id=item["id"])
                            event(s, "등록", item, item["quantity"], note="장보기에서 이동")
                            event(s, "재고 이동", target, item["quantity"])
                        commit(snapshot, transfer)
            if st.button("장보기 항목 삭제", key="remove_shop_"+row["id"], use_container_width=True):
                def remove(s, rid=row["id"]):
                    target = next(x for x in s["shopping"] if x["id"] == rid)
                    target.update(status="deleted", updated_by=st.session_state.member)
                    event(s, "장보기 삭제", target, target["quantity"])
                commit(snapshot, remove)


def monthly_stats(events):
    rows = [{"월":e["at"][:7], "처리":e["kind"], "건수":1} for e in events if e["kind"] in ("소비", "폐기")]
    if not rows:
        return pd.DataFrame(columns=["월", "처리", "건수"])
    frame = pd.DataFrame(rows)
    months = pd.period_range(start=min(frame["월"]), end=today().strftime("%Y-%m"), freq="M").astype(str)
    index = pd.MultiIndex.from_product([months, ["소비", "폐기"]], names=["월", "처리"])
    return frame.groupby(["월", "처리"])["건수"].sum().reindex(index, fill_value=0).reset_index()


def validate_backup(data):
    if not isinstance(data, dict) or not all(isinstance(data.get(k), list) for k in ("members","items","shopping","events")):
        raise ValueError("지원하지 않는 백업입니다.")
    for name in data["members"]:
        if not isinstance(name,str) or not name.strip() or len(name)>30:
            raise ValueError("가족 이름이 올바르지 않습니다.")
    ids = set()
    for row in data["items"]+data["shopping"]:
        if not isinstance(row,dict) or not isinstance(row.get("id"),str) or row["id"] in ids:
            raise ValueError("재료 ID가 올바르지 않습니다.")
        ids.add(row["id"])
        clean_name(row.get("name", ""))
        qty(row.get("quantity"))
        if row.get("unit") not in UNITS or not isinstance(row.get("created_by"),str) or not isinstance(row.get("updated_by"),str):
            raise ValueError("재료 정보가 올바르지 않습니다.")
    for row in data["items"]:
        if row.get("category") not in CATEGORIES or row.get("location") not in LOCATIONS or row.get("status") not in ("active","consumed","discarded","deleted"):
            raise ValueError("재고 상태가 올바르지 않습니다.")
        bought = date.fromisoformat(row["bought"])
        expiry = date.fromisoformat(row["expiry"])
        datetime.fromisoformat(row["updated_at"])
        if expiry < bought:
            raise ValueError("재고 날짜가 올바르지 않습니다.")
    for row in data["shopping"]:
        if row.get("status") not in ("pending","purchased","transferred","deleted"):
            raise ValueError("장보기 상태가 올바르지 않습니다.")
    for e in data["events"]:
        if not isinstance(e,dict) or not all(isinstance(e.get(k),str) for k in ("id","at","actor","kind","item_id","name","unit")):
            raise ValueError("활동 이력이 올바르지 않습니다.")
        datetime.fromisoformat(e["at"])
        qty(e.get("quantity"))
        if e["unit"] not in UNITS:
            raise ValueError("활동 이력 단위가 올바르지 않습니다.")


def backup_tools(snapshot):
    state = snapshot["state"]
    st.subheader("데이터 백업·복원")
    export = json.dumps({"exported_at":now(), **state}, ensure_ascii=False, indent=2)
    st.download_button("가족 데이터 백업(JSON)", export, "fridge_on_backup.json", "application/json", use_container_width=True)
    with st.expander("백업 가져오기 · 현재 가족 데이터 전체 교체"):
        uploaded = st.file_uploader("이 앱에서 내보낸 JSON 백업", type=["json"], key="restore_file")
        confirm = st.checkbox("현재 데이터가 백업 내용으로 교체되는 것을 확인합니다.", key="restore_confirm")
        if st.button("백업 복원", disabled=not uploaded or not confirm, use_container_width=True):
            def restore(current):
                if uploaded.size > 5000000:
                    raise ValueError("5MB 이하 파일만 가져올 수 있습니다.")
                incoming = json.loads(uploaded.getvalue().decode("utf-8"))
                validate_backup(incoming)
                current.clear()
                current.update({k:incoming[k] for k in ("members","items","shopping","events")})
                if st.session_state.member not in current["members"]:
                    current["members"].append(st.session_state.member)
            commit(snapshot, restore)



def sharing(snapshot):
    st.warning("이 앱은 로그인 없는 공용 냉장고입니다. 링크를 아는 누구나 재고를 읽고 수정할 수 있습니다. 민감한 개인 정보는 입력하지 마세요.")
    entered_url = st.text_input("현재 앱 주소 · 다른 주소로 배포했다면 수정", value="https://evtdsp3zyxy8ajlwoj3va5.streamlit.app", key="public_url")
    if entered_url:
        parts = urlsplit(entered_url.strip())
        if parts.scheme == "https" and parts.hostname and not parts.username and not parts.password and not parts.query and not parts.fragment:
            st.code(entered_url.strip(), language=None)
            st.link_button("앱 접속 링크 열기", entered_url.strip(), use_container_width=True)
            buffer = io.BytesIO()
            qrcode.make(entered_url.strip()).save(buffer, format="PNG")
            st.image(buffer.getvalue(), width=180, caption="가족이 스캔하면 같은 냉장고가 열립니다")
            st.download_button("접속 QR 다운로드", buffer.getvalue(), "fridge_on_qr.png", "image/png", use_container_width=True)
        else:
            st.warning("쿼리나 비밀 정보가 없는 https 앱 주소를 입력하세요.")
    with st.expander("배포 및 저장 안내"):
        st.markdown("""GitHub 최상위에 **app.py**와 **requirements.txt**를 올리고 실행 경로를 **app.py**로 지정하세요. Python 3.12를 권장합니다. SQL 실행이나 Secrets 설정은 필요 없습니다.

SQLite 저장 파일은 자동 생성됩니다. 일반적인 새로고침이나 다른 기기의 접속 시 같은 서버 데이터를 사용합니다. **Cloud 재배포·서버 교체 시 데이터가 사라질 수 있습니다.** 공유·관리 탭에서 정기적으로 JSON 백업을 받으세요. 실제 영구 저장 보장에는 외부 저장소가 필요합니다.

한글 입력 보호를 위해 자동 갱신은 사용하지 않습니다. 다른 가족의 변경은 새로고침 버튼으로 확인하세요. 인터넷 연결이 필요하며 푸시 알림은 제공하지 않습니다.
""")


@st.fragment(run_every=None)
def dashboard():
    try:
        snapshot = rpc("load")
    except Exception as exc:
        st.error(error_message(exc))
        st.warning("최신 데이터를 불러오지 못했으므로 수정 기능을 잠시 중지합니다. 다음 자동 갱신 또는 아래 버튼으로 다시 시도하세요.")
        if st.button("연결 다시 시도"):
            st.rerun()
        return
    state = snapshot["state"]
    st.markdown('<div class="hero"><div class="eyebrow">FRIDGE ON · FAMILY KITCHEN</div><h1>🥬 냉장고 ON</h1><p>오늘도 신선하게, 함께 쓰는 우리 가족 냉장고</p></div>', unsafe_allow_html=True)
    if "flash" in st.session_state:
        _, message = st.session_state.pop("flash")
        st.success(message)
    display_name = st.text_input("사용자 이름 · 선택 입력", value=st.session_state.get("member", "가족"), max_chars=30, key="actor_input", placeholder="입력하지 않으면 가족으로 기록")
    st.session_state.member = display_name.strip() or "가족"
    st.caption(f'👤 {st.session_state.member} · 한국 시간 {datetime.now(KST):%m.%d %H:%M:%S} 확인 · 입력 보호 모드')
    stock = active(state)
    st.metric("보유 재고 항목", f"{len(stock)}건")
    totals = {}
    for i in stock:
        totals[i["unit"]] = totals.get(i["unit"], Decimal("0")) + Decimal(str(i["quantity"]))
    st.caption("보유 총수량 · "+(" / ".join(f"{v:g}{u}" for u,v in totals.items()) if totals else "없음"))
    urgent = sorted([i for i in stock if days(i) <= 3], key=lambda i:i["expiry"])
    if urgent:
        overdue = sum(days(i)<0 for i in urgent)
        with st.expander(f"⏰ 먼저 확인해요 · 임박 {len(urgent)-overdue}건 / 기한 경과 {overdue}건", expanded=True):
            st.write(" · ".join(f'{i["name"]} ({"경과 "+str(-days(i))+"일" if days(i)<0 else "오늘까지" if days(i)==0 else "D-"+str(days(i))})' for i in urgent[:5]))
            if len(urgent)>5:
                st.caption(f"외 {len(urgent)-5}건 · 재고 탭에서 기한순으로 확인하세요.")
            st.caption("표시 날짜는 등록한 유통기한 기준입니다. 소비기한·실제 보관 상태와 다를 수 있으며 안전을 보장하지 않습니다.")
    else:
        st.success("기한이 임박한 재료가 없어요. 신선한 냉장고를 유지해 보세요.")
    st.caption("서버 내 자동 저장 · Cloud 재배포/서버 교체 시 유실 가능 · 공유·관리 탭에서 정기 백업하세요.")
    tabs = st.tabs(["🥬 재고", "🍳 요리", "🛒 장보기", "🔗 공유·관리"])
    with tabs[0]: inventory(snapshot)
    with tabs[1]: cooking(snapshot)
    with tabs[2]: shopping(snapshot)
    with tabs[3]:
        sharing(snapshot)
        backup_tools(snapshot)


def main():
    st.markdown(CSS, unsafe_allow_html=True)
    # 모든 방문자가 하나의 공용 냉장고를 사용합니다. 인증용 비밀이 아닙니다.
    st.session_state.token = "fridge_on_shared_household_v2"
    st.session_state.setdefault("member", "가족")
    try:
        rpc("load")
    except Exception as exc:
        if "FAMILY_NOT_FOUND" in str(exc):
            try:
                rpc("create")
            except sqlite3.IntegrityError:
                pass  # 두 기기가 처음에 동시에 접속했을 때 이미 생성된 가족을 사용
            except Exception:
                st.error("저장 공간을 만들지 못했습니다. 앱 로그와 서버 저장 공간을 확인해 주세요.")
                return
        else:
            st.error("저장 공간을 열지 못했습니다. 잠시 후 앱을 새로고침해 주세요.")
            return
    st.caption("입력 중 화면이 초기화되지 않도록 자동 갱신을 껐습니다. 다른 가족의 변경은 아래 버튼으로 확인하세요.")
    if st.button("↻ 가족 재고 새로고침", key="manual_refresh"):
        st.rerun()
    dashboard()


if __name__ == "__main__":
    main()
