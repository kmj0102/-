"""냉장고 ON · Python 3.11+ / Streamlit Community Cloud
호환성: 반드시 함께 제공한 requirements.txt를 사용하세요.
Python 3.14의 TypedDict 호환 문제를 피하기 위해 Altair 6 이상을 사용합니다.
권장 배포 Python 버전은 3.12입니다.
배포: GitHub 저장소에 app.py, requirements.txt 업로드 → Streamlit 앱 생성.
Supabase SQL Editor에서 앱에 표시되는 INITIAL_SQL 실행 후 Streamlit Secrets 설정:
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_ANON_KEY = "YOUR_ANON_OR_PUBLISHABLE_KEY"
APP_URL = "https://YOUR_APP.streamlit.app"
service_role / secret 키는 사용하지 않습니다. 가족 코드는 비밀번호처럼 보관합니다.
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

import altair as alt
import pandas as pd
import qrcode
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="냉장고 ON", page_icon="🥬", layout="wide", initial_sidebar_state="collapsed")
KST = ZoneInfo("Asia/Seoul")

# 초기 테이블과 RPC를 같은 파일에 포함합니다. 별도 SQL 파일이 필요하지 않습니다.
# 모든 데이터 접근은 해시된 128비트 이상의 가족 코드로만 허용됩니다.
# anon 직접 테이블 접근 차단 + SECURITY DEFINER 함수 + CAS revision 검사.
INITIAL_SQL = r"""
CREATE TABLE IF NOT EXISTS public.fridge_on_families (
  token_hash text PRIMARY KEY,
  state jsonb NOT NULL,
  revision bigint NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.fridge_on_families ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.fridge_on_families FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION public.fridge_on_rpc(
  p_action text, p_token text, p_revision bigint DEFAULT NULL,
  p_state jsonb DEFAULT NULL
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public
AS $$
DECLARE
  h text;
  r public.fridge_on_families%ROWTYPE;
BEGIN
  IF p_token IS NULL OR p_token !~ '^[A-Za-z0-9_-]{22,128}$' THEN
    RAISE EXCEPTION 'INVALID_TOKEN';
  END IF;
  h := encode(sha256(convert_to(p_token, 'UTF8')), 'hex');
  IF p_action = 'create' THEN
    INSERT INTO public.fridge_on_families(token_hash, state)
    VALUES (h, jsonb_build_object('members', '[]'::jsonb,
      'items', '[]'::jsonb, 'shopping', '[]'::jsonb, 'events', '[]'::jsonb))
    ON CONFLICT DO NOTHING;
    IF NOT FOUND THEN RAISE EXCEPTION 'TOKEN_ALREADY_EXISTS'; END IF;
  ELSIF p_action NOT IN ('load', 'save') THEN
    RAISE EXCEPTION 'INVALID_ACTION';
  END IF;
  SELECT * INTO r FROM public.fridge_on_families WHERE token_hash=h FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'FAMILY_NOT_FOUND'; END IF;
  IF p_action = 'save' THEN
    IF p_revision IS NULL OR p_revision <> r.revision THEN
      RAISE EXCEPTION 'REVISION_CONFLICT';
    END IF;
    IF p_state IS NULL OR jsonb_typeof(p_state) <> 'object'
      OR jsonb_typeof(p_state->'members') IS DISTINCT FROM 'array'
      OR jsonb_typeof(p_state->'items') IS DISTINCT FROM 'array'
      OR jsonb_typeof(p_state->'shopping') IS DISTINCT FROM 'array'
      OR jsonb_typeof(p_state->'events') IS DISTINCT FROM 'array' THEN
      RAISE EXCEPTION 'INVALID_STATE';
    END IF;
    IF octet_length(p_state::text) > 5000000 THEN
      RAISE EXCEPTION 'STATE_TOO_LARGE';
    END IF;
    UPDATE public.fridge_on_families SET state=p_state,
      revision=revision+1, updated_at=now() WHERE token_hash=h RETURNING * INTO r;
  END IF;
  RETURN jsonb_build_object('state', r.state, 'revision', r.revision,
                           'updated_at', r.updated_at);
END;
$$;
REVOKE ALL ON FUNCTION public.fridge_on_rpc(text,text,bigint,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.fridge_on_rpc(text,text,bigint,jsonb) TO anon, authenticated;
"""

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
</style>
"""
CATEGORIES = ["채소", "과일", "육류", "수산물", "유제품·달걀", "곡물·면", "양념", "가공식품", "기타"]
LOCATIONS = ["냉장", "냉동", "실온"]
UNITS = ["개", "g", "kg", "ml", "L", "팩", "봉", "병", "단"]
BASICS = {"달걀":"유제품·달걀", "우유":"유제품·달걀", "치즈":"유제품·달걀", "양파":"채소", "대파":"채소", "당근":"채소", "감자":"채소", "양배추":"채소", "애호박":"채소", "토마토":"채소", "김치":"가공식품", "두부":"가공식품", "참치":"가공식품", "돼지고기":"육류", "닭고기":"육류", "소고기":"육류", "밥":"곡물·면", "파스타":"곡물·면", "식빵":"곡물·면", "사과":"과일", "바나나":"과일"}
# 재료 일치 여부 기반 추천입니다. 분량 충족을 보장하지 않으며 양념도 누락시키지 않습니다.
RECIPES = [
 ("김치볶음밥", ["밥","김치","달걀","식용유"], "김치를 잘게 썰어 기름에 볶고 밥을 넣어 볶습니다. 달걀을 완전히 익혀 곁들입니다."),
 ("달걀볶음밥", ["밥","달걀","대파","식용유","간장"], "대파를 볶아 향을 내고 달걀을 익힌 뒤 밥과 간장을 넣고 고루 볶습니다."),
 ("감자채볶음", ["감자","당근","식용유","소금"], "감자와 당근을 가늘게 썰고 감자의 전분을 헹굽니다. 기름에 충분히 익혀 소금으로 간합니다."),
 ("두부김치", ["두부","김치","식용유"], "두부를 끓는 물에 데칩니다. 김치를 기름에 볶아 따뜻한 두부와 함께 담습니다."),
 ("채소달걀전", ["달걀","양파","당근","식용유","소금"], "채소를 잘게 썰어 달걀과 섞습니다. 소금으로 간하고 팬에서 앞뒤로 완전히 익힙니다."),
 ("토마토달걀볶음", ["토마토","달걀","식용유","소금"], "달걀을 먼저 볶아 덜어 놓습니다. 토마토를 볶다가 달걀을 다시 넣어 충분히 익힙니다."),
 ("참치김치찌개", ["참치","김치","두부","대파"], "냄비에 김치와 물을 넣어 끓입니다. 참치와 두부를 넣고 끓인 뒤 대파를 넣습니다."),
 ("닭고기채소볶음", ["닭고기","양파","당근","간장","식용유"], "닭고기를 잘라 기름에 볶습니다. 채소와 간장을 넣고 닭고기 중심까지 완전히 익힙니다."),
 ("양배추달걀토스트", ["식빵","양배추","달걀","식용유"], "양배추를 잘게 썰어 달걀과 섞어 속까지 익힙니다. 구운 식빵 사이에 넣습니다."),
 ("소고기미역국", ["소고기","미역","참기름","간장"], "미역을 불려 씻습니다. 소고기와 미역을 참기름에 볶고 물을 넣어 충분히 끓인 뒤 간합니다."),
 ("돼지고기김치볶음", ["돼지고기","김치","양파","식용유"], "돼지고기를 충분히 익힌 뒤 김치와 양파를 넣고 볶습니다. 고기 중심까지 익었는지 확인합니다."),
 ("우유달걀프렌치토스트", ["식빵","우유","달걀","식용유"], "우유와 달걀을 섞어 식빵을 적십니다. 기름을 두른 팬에서 양면과 속을 완전히 익힙니다."),
 ("애호박볶음", ["애호박","양파","식용유","소금"], "애호박과 양파를 썰어 기름에 볶습니다. 부드럽게 익으면 소금으로 간합니다."),
 ("치즈오믈렛", ["달걀","치즈","우유","식용유","소금"], "달걀과 우유를 섞고 간합니다. 팬에 부어 익힌 뒤 치즈를 올리고 접어 속까지 익힙니다."),
]
ALIASES = {"계란":"달걀", "흰쌀밥":"밥", "쌀밥":"밥", "캔참치":"참치", "참치캔":"참치", "스파게티면":"파스타", "식용유":"식용유"}


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


@st.cache_resource
def db(url, key):
    return create_client(url, key)


def rpc(action, revision=None, state=None):
    args = {"p_action":action, "p_token":st.session_state.token}
    if revision is not None:
        args["p_revision"] = revision
    if state is not None:
        args["p_state"] = state
    return CLIENT.rpc("fridge_on_rpc", args).execute().data


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
    return "서버에 연결하거나 저장하지 못했습니다. 인터넷 연결, Supabase 설정과 SQL 실행 여부를 확인하고 다시 시도하세요."


def commit(snapshot, mutate):
    """읽은 revision에 대한 원자적 저장. 충돌 시 자동 재시도하지 않음."""
    try:
        state = copy.deepcopy(snapshot["state"])
        mutate(state)
        rpc("save", snapshot["revision"], state)
        st.session_state.flash = ("success", "저장했습니다. 가족 화면에도 최대 약 10초 이내 반영됩니다.")
        st.rerun()
    except Exception as exc:
        st.error(error_message(exc))


def item_inputs(prefix, initial=None):
    initial = initial or {}
    name = st.text_input("식재료 이름", value=initial.get("name", ""), max_chars=60, key=prefix+"name")
    c1, c2 = st.columns(2)
    category = c1.selectbox("카테고리", CATEGORIES, index=CATEGORIES.index(initial.get("category", "기타")), key=prefix+"cat")
    location = c2.selectbox("보관 위치", LOCATIONS, index=LOCATIONS.index(initial.get("location", "냉장")), key=prefix+"loc")
    c1, c2 = st.columns(2)
    quantity = c1.number_input("수량", min_value=0.0, max_value=1000000.0, value=float(initial.get("quantity", 1)), step=0.1, format="%.3f", key=prefix+"qty")
    unit = c2.selectbox("단위", UNITS, index=UNITS.index(initial.get("unit", "개")), key=prefix+"unit")
    c1, c2 = st.columns(2)
    bought = c1.date_input("구매일", value=date.fromisoformat(initial["bought"]) if "bought" in initial else today(), key=prefix+"buy")
    expiry = c2.date_input("유통기한", value=date.fromisoformat(initial["expiry"]) if "expiry" in initial else today(), key=prefix+"exp")
    return name, category, quantity, unit, bought, expiry, location


def new_ingredient(snapshot):
    with st.expander("＋ 식재료 등록", expanded=not active(snapshot["state"])):
        preset = st.selectbox("기본 목록 또는 직접 입력", ["직접 입력"] + list(BASICS), key="preset")
        initial = {} if preset == "직접 입력" else {"name":preset, "category":BASICS[preset]}
        with st.form("new_item_"+preset, clear_on_submit=True):
            vals = item_inputs("new_"+preset, initial)
            if st.form_submit_button("냉장고에 추가", type="primary", use_container_width=True):
                def add(s):
                    item = make_item(*vals)
                    s["items"].append(item)
                    event(s, "등록", item, item["quantity"])
                commit(snapshot, add)


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
    pages = max(1, (len(items)+5)//6)
    page = int(st.number_input("재고 페이지 · 한 번에 6개", min_value=1, max_value=pages, value=1, key=f"page_{pages}"))
    for item in items[(page-1)*6:page*6]:
        delta = days(item)
        label, tone = (f"기한 경과 {abs(delta)}일", "bad") if delta < 0 else (("오늘까지" if delta == 0 else f"D-{delta}", "warn") if delta <= 3 else (f"D-{delta}", ""))
        st.markdown(f'<div class="card"><h4>{esc(item["name"])} <span class="pill {tone}">{label}</span></h4><p><b>{item["quantity"]:g} {esc(item["unit"])}</b> · {esc(item["location"])} · {esc(item["category"])} · {esc(item["expiry"])}</p><p>등록 {esc(item["created_by"])} · 최근 수정 {esc(item["updated_by"])}</p></div>', unsafe_allow_html=True)
        with st.expander("사용 · 수정 · 폐기 / "+item["name"]+" · "+item["id"][:4]):
            with st.form("use_"+item["id"]):
                used = st.number_input("사용 또는 폐기 수량", min_value=0.0, max_value=float(item["quantity"]), value=float(item["quantity"]), step=.1, format="%.3f")
                action = st.radio("처리", ["소비", "폐기"], horizontal=True)
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
                st.caption("수량 감소는 소비 통계에 자동 반영되지 않습니다. 실제 사용은 위의 소비 처리를 이용하세요. 0으로 수정하면 잔량을 소비 완료 처리합니다.")
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
                confirm = st.checkbox("잘못 등록한 재고를 삭제합니다. 폐기 통계에는 포함하지 않습니다.")
                if st.form_submit_button("재고 삭제", use_container_width=True):
                    def delete(s, item_id=item["id"]):
                        if not confirm:
                            raise ValueError("삭제 확인에 체크하세요.")
                        target = next(i for i in s["items"] if i["id"] == item_id)
                        target["status"] = "deleted"
                        touch(target)
                        event(s, "삭제", target, target["quantity"])
                    commit(snapshot, delete)


def recommend_recipes(items):
    usable = [i for i in items if days(i) >= 0]
    owned = {norm(i["name"]) for i in usable}
    urgent = {norm(i["name"]) for i in usable if days(i) <= 3}
    results = []
    for title, required, method in RECIPES:
        have = [r for r in required if norm(r) in owned]
        missing = [r for r in required if norm(r) not in owned]
        soon = [r for r in have if norm(r) in urgent]
        if have:
            results.append({"title":title, "required":required, "method":method, "have":have, "missing":missing, "soon":soon,
                            "score":len(soon)*10 + len(have)/len(required)*5 - len(missing)})
    return sorted(results, key=lambda r:r["score"], reverse=True)


def cooking(snapshot):
    st.caption("기한이 지나지 않은 재료만 사용합니다. 임박 재료 활용을 우선해 추천하며, 재료명 일치 기준이므로 필요한 분량·알레르기·보관 상태는 직접 확인하세요. 양념도 보유 재료로 등록해야 보유로 표시됩니다.")
    results = recommend_recipes(active(snapshot["state"]))
    only = st.checkbox("부족한 재료 없는 메뉴만", value=False)
    results = [r for r in results if not only or not r["missing"]]
    if not results:
        st.info("현재 조건에 맞는 메뉴가 없습니다. 재료를 더 등록하거나 필터를 해제하세요.")
    for recipe in results[:6]:
        with st.expander("🍽️ "+recipe["title"]+(" · 임박 재료 활용" if recipe["soon"] else "")+f' · 보유 {len(recipe["have"])}/{len(recipe["required"])}', expanded=False):
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
    st.caption("확장 지점: recommend_recipes()를 교체하면 외부 AI 추천을 연결할 수 있습니다. 현재 앱은 별도 AI API 키 없이 동작하는 기본 레시피 추천입니다.")


def shopping(snapshot):
    state = snapshot["state"]
    with st.expander("＋ 장보기 항목 추가", expanded=False):
        with st.form("shopping_add", clear_on_submit=True):
            name = st.text_input("필요한 식재료", max_chars=60)
            c1, c2 = st.columns(2)
            count = c1.number_input("필요 수량", min_value=.001, max_value=1000000.0, value=1.0, step=.1, format="%.3f")
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


def statistics(snapshot):
    state = snapshot["state"]
    st.caption("월별 그래프는 부분 소비·부분 폐기를 포함한 처리 횟수입니다. 수량은 서로 다른 단위를 합산하지 않습니다. 폐기량 감소는 아래 동일 단위 월별 수량으로 비교하세요.")
    frame = monthly_stats(state["events"])
    if frame.empty:
        st.info("소비 또는 폐기를 기록하면 월별 그래프가 표시됩니다.")
    else:
        chart = alt.Chart(frame).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
            x=alt.X("월:N", title=None), y=alt.Y("건수:Q", title="처리 횟수", axis=alt.Axis(tickMinStep=1)),
            color=alt.Color("처리:N", scale=alt.Scale(domain=["소비","폐기"], range=["#648f45","#d47b57"])),
            xOffset="처리:N", tooltip=["월", "처리", "건수"]).properties(height=220)
        st.altair_chart(chart, use_container_width=True)
        selected = st.selectbox("월별 수량 비교 단위", UNITS, key="stat_unit")
        quantities = [{"월":e["at"][:7], "처리":e["kind"], "수량":e["quantity"]} for e in state["events"] if e["kind"] in ("소비","폐기") and e["unit"] == selected]
        if quantities:
            q = pd.DataFrame(quantities).pivot_table(index="월", columns="처리", values="수량", aggfunc="sum", fill_value=0)
            q = q.reindex(index=sorted(frame["월"].unique()), columns=["소비","폐기"], fill_value=0).fillna(0)
            q["폐기 비중(%)"] = (q["폐기"] / (q["소비"] + q["폐기"]).replace(0,float("nan"))*100).round(1)
            st.dataframe(q, use_container_width=True)
            st.caption("같은 단위라도 품목·구매량이 다르므로 단순 수치만으로 낭비 감소를 단정하지 마세요. 폐기 비중 = 폐기 ÷ (소비+폐기). 무처리 월은 비중을 비워 둡니다.")
        else:
            st.info("이 단위의 소비·폐기 이력이 없습니다.")
    with st.expander("최근 활동 · 최대 50건"):
        events = list(reversed(state["events"]))[:50]
        if events:
            display = [{"시각":e["at"][:19].replace("T"," "),"가족":e["actor"],"활동":e["kind"],"재료":e["name"],"수량":f'{e["quantity"]:g}{e["unit"]}',"메모":e.get("note","")} for e in events]
            st.dataframe(display, hide_index=True, use_container_width=True)
        else:
            st.caption("아직 활동이 없습니다.")
    export = json.dumps({"exported_at":now(), **state}, ensure_ascii=False, indent=2)
    st.download_button("가족 데이터 백업(JSON)", export, "fridge_on_backup.json", "application/json", use_container_width=True)


def sharing(snapshot):
    st.info("가족 코드를 아는 사람은 이 냉장고의 모든 데이터를 읽고 수정할 수 있습니다. 이름 선택은 활동 표시용이며 본인 인증이 아닙니다. QR에는 비밀 코드를 넣지 않아 링크 유출만으로 재고에 접근할 수 없습니다.")
    st.code(st.session_state.token, language=None)
    st.caption("코드는 가족에게 별도의 안전한 경로로 공유하세요. 코드 분실 시 복구 기능은 없습니다. 공용 기기에서는 사용 후 로그아웃하세요.")
    app_url = str(st.secrets.get("APP_URL", "")).strip()
    entered_url = st.text_input("앱 공개 주소", value=app_url, placeholder="https://your-app.streamlit.app", key="public_url")
    if entered_url:
        parts = urlsplit(entered_url)
        if parts.scheme == "https" and parts.hostname and not parts.username and not parts.password and not parts.query and not parts.fragment:
            st.link_button("공유 접속 링크 열기", entered_url, use_container_width=True)
            image = qrcode.make(entered_url)
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            st.image(buffer.getvalue(), width=180, caption="접속 후 가족 코드와 이름을 입력하세요")
            st.download_button("접속 QR 다운로드", buffer.getvalue(), "fridge_on_qr.png", "image/png", use_container_width=True)
        else:
            st.warning("쿼리·비밀 정보가 없는 https 앱 주소를 입력하세요.")
    st.caption("화면이 열린 동안 약 10초마다 최신 내용을 가져옵니다. 백그라운드 모바일 브라우저는 갱신이 지연될 수 있습니다. 푸시 알림 서비스는 아닙니다.")
    with st.expander("배포·운영 안내"):
        setup_text()


def setup_text():
    st.markdown("""**1. Supabase 준비**  
Supabase에서 프로젝트를 만든 후 SQL Editor에 아래 SQL 전체를 붙여 실행합니다. 공개 스키마는 기본 `public`을 사용합니다.

**2. GitHub / Streamlit Cloud**  
저장소에 `app.py`와 `requirements.txt` 두 파일을 업로드합니다. Python 3.11 또는 3.12를 선택하고 메인 파일을 `app.py`로 지정합니다. 앱의 Advanced settings → Secrets에 아래 세 값을 입력합니다. 별도 설정 파일을 저장소에 올리지 않습니다.
""")
    st.code('SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"\nSUPABASE_ANON_KEY = "YOUR_ANON_OR_PUBLISHABLE_KEY"\nAPP_URL = "https://YOUR_APP.streamlit.app"', language="toml")
    st.caption("Project Settings → API에서 URL과 anon(public) 또는 publishable 키를 확인하세요. service_role / secret 키를 넣지 마세요. DB 비밀번호도 필요 없습니다.")
    st.code(INITIAL_SQL, language="sql")
    st.markdown("""**3. 가족 연결**  
첫 사용자가 가족 냉장고를 생성하고 코드를 안전하게 보관합니다. 다른 가족은 동일 앱 주소에서 코드를 입력해 접속한 뒤 이름을 선택합니다. QR은 앱 주소만 포함합니다.

**4. 확인 순서**  
다른 기기 두 대로 같은 가족에 접속 → 식재료 등록 → 10초 뒤 재고 확인 → 일부 소비 → 장보기 구매 완료 → 재고로 이동 → 새로고침 후 유지 확인. 동시 변경 충돌 메시지가 나오면 최신 데이터를 확인하고 재시도합니다.

**운영 범위**  
한 가족 데이터를 하나의 JSON 상태로 저장하고 revision 비교 후 원자적으로 반영하는 소규모 가족용 구조입니다. 5MB 상태 제한이 있으며 이력은 자동 삭제하지 않습니다. 백업은 통계 탭에서 가능합니다. 다수 가구 상용 운영에는 사용자 인증·코드 회전·접근 제한·정규화 테이블·감사 이력 보호·복구 정책을 별도로 구축하세요. 이 버전의 가족 구성원은 동등한 수정 권한을 가지며 활동 이력은 법적 감사 기록이 아닙니다. Supabase 무료 프로젝트의 일시 중지나 서비스 장애 중에는 저장·동기화를 할 수 없습니다.
""")


def login():
    st.markdown('<div class="hero"><div class="eyebrow">FRIDGE ON · FAMILY KITCHEN</div><h1>🥬 냉장고 ON</h1><p>남김없이 맛있게. 우리 가족의 냉장고를 함께 켜요.</p></div>', unsafe_allow_html=True)
    st.caption("가족 공용 코드로 연결하고 내 이름으로 기록하세요.")
    join, create = st.tabs(["가족 냉장고 접속", "새 가족 냉장고"])
    with join:
        with st.form("join"):
            token = st.text_input("가족 코드", type="password", help="다른 가족에게 받은 22자 이상의 코드를 입력하세요.")
            submitted = st.form_submit_button("냉장고 연결", type="primary", use_container_width=True)
        if submitted:
            st.session_state.token = token.strip()
            try:
                rpc("load")
                st.session_state.connected = True
                st.rerun()
            except Exception as exc:
                st.session_state.pop("token", None)
                st.error(error_message(exc))
    with create:
        st.write("새 가족을 만들면 안전한 무작위 공용 코드가 생성됩니다.")
        if st.button("우리 가족 냉장고 만들기", type="primary", use_container_width=True):
            st.session_state.token = secrets.token_urlsafe(24)
            try:
                rpc("create")
                st.session_state.connected = True
                st.session_state.new_family = True
                st.rerun()
            except Exception as exc:
                st.session_state.pop("token", None)
                st.error(error_message(exc))
    with st.expander("처음 배포하나요? 설정 안내"):
        setup_text()


def choose_member(snapshot):
    st.subheader("누가 사용하나요?")
    if st.session_state.get("new_family"):
        st.warning("먼저 가족 코드를 복사해 보관하세요. 코드를 분실하면 새 기기에서 이 냉장고에 다시 접속할 수 없습니다.")
        st.code(st.session_state.token, language=None)
    options = snapshot["state"]["members"] + ["＋ 새 이름 등록"]
    with st.form("member"):
        choice = st.selectbox("내 이름", options)
        name = st.text_input("새 이름 (등록할 때만 입력)", max_chars=30)
        if st.form_submit_button("이 이름으로 시작", type="primary", use_container_width=True):
            try:
                selected = clean_name(name, "가족 이름") if choice == "＋ 새 이름 등록" else choice
                if len(selected) > 30:
                    raise ValueError("가족 이름은 30자 이내로 입력하세요.")
                if selected not in snapshot["state"]["members"]:
                    state = copy.deepcopy(snapshot["state"])
                    if len(state["members"]) >= 30:
                        raise ValueError("가족 이름은 최대 30명까지 등록할 수 있습니다.")
                    state["members"].append(selected)
                    rpc("save", snapshot["revision"], state)
                st.session_state.member = selected
                st.session_state.pop("new_family", None)
                st.rerun()
            except Exception as exc:
                st.error(error_message(exc))


@st.fragment(run_every="10s")
def dashboard():
    try:
        snapshot = rpc("load")
    except Exception as exc:
        st.error(error_message(exc))
        st.warning("최신 데이터를 불러오지 못했으므로 수정 기능을 잠시 중지합니다. 다음 자동 갱신 또는 아래 버튼으로 다시 시도하세요.")
        if st.button("연결 다시 시도"):
            st.rerun()
        return
    if not st.session_state.get("member"):
        choose_member(snapshot)
        return
    state = snapshot["state"]
    st.markdown('<div class="hero"><div class="eyebrow">FRIDGE ON · FAMILY KITCHEN</div><h1>🥬 냉장고 ON</h1><p>오늘도 신선하게, 함께 쓰는 우리 가족 냉장고</p></div>', unsafe_allow_html=True)
    if "flash" in st.session_state:
        _, message = st.session_state.pop("flash")
        st.success(message)
    left, right = st.columns([3,1])
    left.caption(f'👤 {st.session_state.member} · 한국 시간 {datetime.now(KST):%m.%d %H:%M:%S} 확인 · 10초 자동 동기화')
    if right.button("이름 변경", use_container_width=True):
        st.session_state.pop("member", None)
        st.rerun()
    stock = active(state)
    month = today().strftime("%Y-%m")
    complete = sum(1 for e in state["events"] if e["kind"] == "소비" and e.get("terminal") and e["at"].startswith(month))
    discarded = sum(1 for e in state["events"] if e["kind"] == "폐기" and e["at"].startswith(month))
    c1,c2,c3 = st.columns(3)
    c1.metric("보유 재고 항목", f"{len(stock)}건")
    c2.metric("이번 달 소비 완료", f"{complete}건")
    c3.metric("이번 달 폐기 처리", f"{discarded}회")
    totals = {}
    for i in stock:
        totals[i["unit"]] = totals.get(i["unit"], Decimal("0")) + Decimal(str(i["quantity"]))
    st.caption("보유 총수량 · "+(" / ".join(f"{v:g}{u}" for u,v in totals.items()) if totals else "없음")+" · 소비 완료는 재고가 0이 된 건수, 폐기는 부분 폐기 포함 횟수")
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
    tabs = st.tabs(["🥬 재고", "🍳 요리", "🛒 장보기", "📊 통계", "🔗 공유"])
    with tabs[0]: inventory(snapshot)
    with tabs[1]: cooking(snapshot)
    with tabs[2]: shopping(snapshot)
    with tabs[3]: statistics(snapshot)
    with tabs[4]: sharing(snapshot)
    if st.button("가족 냉장고 로그아웃", use_container_width=True):
        st.session_state.clear()
        st.rerun()


def main():
    global CLIENT
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        url = str(st.secrets.get("SUPABASE_URL", "")).strip()
        key = str(st.secrets.get("SUPABASE_ANON_KEY", "")).strip()
    except Exception:
        url = key = ""
    if not url or not key:
        st.markdown('<div class="hero"><h1>🥬 냉장고 ON</h1><p>처음 한 번만 연결하면 가족의 식재료가 안전하게 저장됩니다.</p></div>', unsafe_allow_html=True)
        st.info("Supabase 연결 정보가 아직 설정되지 않았습니다. 아래 절차로 최초 설정을 완료하세요.")
        setup_text()
        return
    if not url.startswith("https://"):
        st.error("SUPABASE_URL을 https 프로젝트 주소로 설정하세요.")
        return
    try:
        CLIENT = db(url, key)
    except Exception:
        st.error("Supabase 연결 설정을 확인하세요. 키와 주소는 화면에 출력하지 않습니다.")
        return
    if not st.session_state.get("connected"):
        login()
    else:
        dashboard()


if __name__ == "__main__":
    main()
