"""냉장고 ON · 로그인 없는 가족 공용 최종 버전
GitHub 최상위에 app.py와 requirements.txt를 업로드하고 Streamlit Cloud에서
Main file path를 app.py로 지정합니다. SQL 실행이나 Secrets 입력은 필요 없습니다.
DB는 실행 시 자동 생성됩니다. Cloud 로컬 디스크는 영구 보장되지 않습니다.
로컬 실행: streamlit run app.py
"""
from __future__ import annotations

import base64
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


/* 모바일 앱형 레이아웃: 밝은 카드와 가로 탭 */
[data-testid="stAppViewContainer"] {background:#f3f7f1 !important; color:#213b2b;}
.block-container {max-width:850px !important; padding:1.1rem 1rem 3rem !important;}
.hero {background:linear-gradient(125deg,#153e2c,#357d4b) !important;border-radius:24px !important;padding:22px !important;box-shadow:0 8px 24px #173d2814;}
.hero h1,.hero p,.hero .eyebrow {color:#fff !important;}
[data-testid="stTabs"] [role="tablist"] {background:#fff; padding:6px;border-radius:17px;gap:3px;overflow-x:auto;}
[data-testid="stTabs"] [role="tab"] {border-radius:12px;padding:10px 12px;white-space:nowrap;color:#35553e !important;}
[data-testid="stTabs"] [aria-selected="true"] {background:#dff0d3 !important;color:#1d4c2b !important;}
[data-testid="stExpander"] {background:#fff;border:1px solid #dfE8dc !important;border-radius:16px !important;overflow:hidden;}
[data-testid="stForm"] {background:#fff;border-radius:18px !important;border:1px solid #dce7d8 !important;padding:16px !important;}
textarea,input {font-size:16px !important;}
@media(max-width:600px){
.block-container{padding:0.8rem 0.7rem 2.5rem !important;}
h1{font-size:1.7rem !important;} h2{font-size:1.25rem !important;}
.hero{padding:18px !important;border-radius:20px !important;}
[data-testid="stTabs"] [role="tab"]{padding:10px 7px;font-size:14px;}
[data-testid="stButton"] button,[data-testid="stFormSubmitButton"] button{min-height:46px;}
}


.app-title{font-size:1.6rem !important;margin:0 0 12px !important;letter-spacing:-1px;color:#214d35;}
.fridge-top{padding:12px 18px;background:#dce9e8;border:5px solid #b9cccc;border-bottom:0;border-radius:22px 22px 0 0;font-weight:800;margin-top:12px;}
.shelf{height:185px;border:3px solid #c6d9d7;border-bottom:8px solid #a9c4bf;background:linear-gradient(#f5fbfb,#e5f0ed);border-radius:8px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;text-align:center;overflow:hidden;}
.shelf img{width:76px;height:76px;object-fit:cover;border-radius:14px;}
.food-icon{font-size:48px;line-height:1.3;}
.shelf small{font-size:12px;color:#476259;}
.shelf.empty{color:#78968c;}
@media(max-width:600px){[data-testid="stHorizontalBlock"]:has(.shelf){flex-wrap:nowrap !important;}[data-testid="stHorizontalBlock"]:has(.shelf)>[data-testid="stColumn"]{min-width:0 !important;width:50% !important;flex:1 1 0 !important;}.shelf{height:164px;}.block-container{padding-top:0.5rem !important;}}

.food-icon{display:flex;align-items:center;justify-content:center;width:86px;height:82px;border-radius:24px;background:#fff6e9;font-size:48px;letter-spacing:-6px;padding-right:6px;}
[data-testid="stButton"]>button:hover:not(:disabled),
[data-testid="stButton"]>button:active:not(:disabled),
[data-testid="stButton"]>button:focus:not(:disabled),
[data-testid="stFormSubmitButton"] button,
[data-testid="stFormSubmitButton"] button:hover,
[data-testid="stFormSubmitButton"] button:active,
[data-testid="stFormSubmitButton"] button:focus{
background:#e6f3d8 !important;color:#234327 !important;border:1px solid #7aa657 !important;box-shadow:none !important;}
[data-testid="stFormSubmitButton"] button p{color:#234327 !important;-webkit-text-fill-color:#234327 !important;}

.recipe-compact{background:#fff;border:1px solid #dce7d8;border-radius:18px;padding:14px 16px;margin:0 0 8px;}
.recipe-heading{display:flex;align-items:center;justify-content:space-between;gap:10px;font-size:20px;line-height:1.35;}
.recipe-heading small{font-size:13px;color:#61735e;white-space:nowrap;}
.recipe-owned{margin:8px 0 !important;font-size:14px;color:#326044;line-height:1.5;}
.recipe-method{font-size:15px;line-height:1.65;color:#263e2d;overflow-wrap:anywhere;}

/* 주요 메뉴는 스크롤 중에도 상단에 유지 */
[data-testid="stHorizontalBlock"]:has(button[kind="primary"]) {scroll-margin-top:12px;}
@media(max-width:640px){
[data-testid="stButton"] button p{font-size:13px!important;white-space:nowrap;}
[data-testid="stHorizontalBlock"]{gap:6px!important;}
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
# 반찬·국은 밥을 포함한 식사로 구성합니다. 순수 간식/반찬 추천은 제외합니다.
_MEAL_WITH_RICE = {"참치김치찌개", "제육볶음", "된장찌개", "순두부찌개", "소고기미역국", "불고기", "닭볶음탕", "오징어볶음", "고등어조림", "토마토달걀볶음"}
_MEAL_STANDALONE = {"김치볶음밥", "잔치국수", "비빔국수", "알리오올리오", "볶음우동"}
RECIPES = [(title + " 정식", list(dict.fromkeys(required + ["밥"])), method + " 따뜻한 밥을 곁들여 한 끼로 냅니다.")
           if title in _MEAL_WITH_RICE else (title, required, method)
           for title, required, method in RECIPES
           if title in _MEAL_WITH_RICE or title in _MEAL_STANDALONE]
RECIPES += [
    ("달걀볶음밥", ["밥", "달걀", "대파", "간장", "식용유"], "대파를 기름에 볶고 달걀을 넣어 완전히 익힙니다. 밥과 간장을 넣고 골고루 볶습니다."),
    ("참치마요덮밥", ["밥", "참치", "달걀", "마요네즈", "간장"], "달걀을 완전히 익혀 잘게 나눕니다. 밥에 기름 뺀 참치와 달걀을 올리고 마요네즈와 간장을 소량 곁들입니다."),
    ("닭고기채소볶음밥", ["밥", "닭고기", "당근", "양파", "간장", "식용유"], "닭고기를 작게 썰어 속까지 완전히 익히고 잘게 썬 채소를 볶습니다. 밥과 간장을 넣고 고르게 볶습니다."),
    ("소고기채소죽", ["밥", "소고기", "당근", "참기름", "소금"], "잘게 썬 소고기를 참기름에 충분히 익힙니다. 밥과 물, 당근을 넣고 저어 가며 부드럽게 끓여 소금으로 간합니다.")]

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


def flat_panel(*args, **kwargs):
    return st.container()


def item_inputs(prefix, initial=None):
    initial = initial or {}
    name = st.text_input("식재료 이름", value=initial.get("name", ""), max_chars=60, key=prefix+"name")
    c1, c2 = st.columns(2)
    quantity = c1.number_input("수량", min_value=0, max_value=1000000, value=int(initial.get("quantity", 1)), step=1, format="%d", key=prefix+"qty")
    expiry = c2.date_input("유통기한", value=date.fromisoformat(initial["expiry"]) if "expiry" in initial else today(), key=prefix+"exp")
    with flat_panel("추가 설정 · 단위 / 위치 / 카테고리 / 구매일"):
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
    """사과 2개 / 사과 2 개 / 사과2개 모두 수량과 단위로 해석합니다."""
    aliases = {"개":"개", "g":"g", "그램":"g", "kg":"kg", "킬로":"kg",
               "킬로그램":"kg", "ml":"ml", "밀리리터":"ml", "l":"L", "리터":"L",
               "팩":"팩", "봉":"봉", "봉지":"봉", "병":"병", "단":"단"}
    units_pattern = "|".join(sorted(map(re.escape, aliases), key=len, reverse=True))
    text = re.sub(r"(?<=[가-힣a-zA-Z])(?=\d)", " ", text)
    tokens = re.findall(r"[^\s,，;；]+", text.strip())
    entries = []
    for token in tokens:
        match = re.fullmatch(r"(\d+)("+units_pattern+r")?", token, re.I)
        if match:
            if not entries or entries[-1][1] is not None:
                raise ValueError("수량 앞에 재료 이름을 입력하세요. 예: 사과 2개 우유 1L")
            count = int(match.group(1))
            if not 1 <= count <= 1000000:
                raise ValueError("수량은 1~1,000,000의 정수로 입력하세요.")
            entries[-1][1] = count
            if match.group(2): entries[-1][2] = aliases[match.group(2).lower()]
        elif token.lower() in aliases:
            if not entries or entries[-1][1] is None or entries[-1][2] is not None:
                raise ValueError("단위는 수량 뒤에 한 번만 입력하세요. 예: 사과 2 개")
            entries[-1][2] = aliases[token.lower()]
        else:
            if re.search(r"\d", token):
                raise ValueError("수량 또는 단위를 확인하세요: "+token+" (예: 사과 2개, 우유 1L)")
            entries.append([clean_name(token, "식재료 이름"), None, None])
    if not entries:
        raise ValueError("등록할 재료를 입력하세요.")
    if len(entries) > 200:
        raise ValueError("한 번에 최대 200개 재료까지 등록할 수 있습니다.")
    return [make_item(name, auto_category(name), count or 1, row_unit or unit, bought, expiry, auto_location(name) if location == "자동" else location)
            for name, count, row_unit in entries]


def new_ingredient(snapshot):
    with flat_panel("＋ 식재료 한 번에 등록", expanded=False):
        st.caption("공백·쉼표·줄바꿈으로 재료를 나누면 각각 등록됩니다. 예: 사과 복숭아 귤 → 3개 재고 항목. 수량은 사과 3 복숭아 2처럼 입력하며 생략하면 1입니다. 띄어쓴 이름은 각각 나뉘므로 닭가슴살처럼 붙여 쓰세요.")
        generation = st.session_state.get("bulk_generation", 0)
        with st.form(f"bulk_text_form_{generation}"):
            text = st.text_area("여러 식재료 입력", height=180, placeholder="사과 복숭아 귤\n양파 3 달걀 10", key=f"bulk_text_{generation}")
            c1, c2 = st.columns(2)
            unit = c1.selectbox("공통 단위", UNITS, key=f"bulk_unit_{generation}")
            location = c2.selectbox("보관 위치", ["자동"] + LOCATIONS, key=f"bulk_location_{generation}")
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
                st.session_state.screen = "오늘"
                st.session_state.shelf_page = 1
                st.session_state.quick_search = ""
                st.session_state.fridge_location_v2 = "전체"
                st.session_state.flash = ("success", f"식재료 {len(prepared)}건을 등록했습니다.")
                st.rerun()


def quick_remove(state, item_id, discard=False):
    target = next((i for i in state["items"] if i["id"] == item_id), None)
    if target is None or target.get("status") != "active" or target["quantity"] <= 0:
        raise ValueError("이미 처리된 재료입니다. 재고를 새로고침하세요.")
    amount = target["quantity"]
    target["status"] = "discarded" if discard else "deleted"
    target["quantity"] = 0
    touch(target)
    event(state, "폐기" if discard else "삭제", target, amount, discard)


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
        card, actions = st.columns([5, 1], gap="small")
        with card:
            st.markdown(f'<div class="card"><h4>{esc(item["name"])} <span class="pill {tone}">{label}</span></h4><p><b>{item["quantity"]:g} {esc(item["unit"])}</b> · {esc(item["location"])} · {esc(item["category"])} · {esc(item["expiry"])}</p><p>등록 {esc(item["created_by"])} · 최근 수정 {esc(item["updated_by"])}</p></div>', unsafe_allow_html=True)
        with actions:
            if st.button("−", key="quick_delete_"+item["id"], help="재고 전체 즉시 삭제 · 폐기로 기록하지 않음", use_container_width=True):
                commit(snapshot, lambda state, ident=item["id"]: quick_remove(state, ident, False))
            if st.button("폐기", key="quick_discard_"+item["id"], help="남은 수량 전체 즉시 폐기 처리", use_container_width=True):
                commit(snapshot, lambda state, ident=item["id"]: quick_remove(state, ident, True))

        with flat_panel("사용 · 수정 · 폐기 / "+item["name"]+" · "+item["id"][:4]):
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
        if len({norm(r) for r in have}) < 1:
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
    st.caption("기한이 지나지 않은 보유 재료를 1종 이상 활용하는 메뉴를 추천합니다. 임박 재료 활용을 우선하며, 재료명 일치 기준이므로 필요한 분량·알레르기·보관 상태는 직접 확인하세요. 양념도 보유 재료로 등록해야 보유로 표시됩니다.")
    results = recommend_recipes(active(snapshot["state"]))
    only = st.checkbox("부족한 재료 없는 메뉴만", value=False)
    results = [r for r in results if not only or not r["missing"]]
    if not results:
        st.info("보유 재료를 2종 이상 활용할 수 있는 메뉴가 없습니다. 재료를 더 등록하거나 부족 재료 필터를 해제하세요.")
    st.caption(f"기본 레시피 {len(RECIPES)}종 중 조건에 맞는 {len(results)}개를 모두 표시합니다. 정렬: 임박 재료 포함 → 보유 충족률 → 부족 재료 적은 순 → 가장 가까운 기한.")
    for recipe in results:
        with flat_panel("🍽️ "+recipe["title"]+(" · 임박 재료 활용" if recipe["soon"] else "")+f' · 보유 {len(recipe["have"])}/{len(recipe["required"])}', expanded=False):
            st.write(f"**보유 충족률 {recipe['coverage']:.0%} · 부족 {len(recipe['missing'])}종**")
            st.write("**필요 재료** · "+", ".join(recipe["required"]))
            st.success("보유 · "+", ".join(recipe["have"]))
            if recipe["soon"]:
                st.write("**먼저 사용할 재료** · "+", ".join(recipe["soon"]))
            if recipe["missing"]:
                pass  # 부족 재료 표시 생략
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
    with flat_panel("＋ 장보기 항목 추가", expanded=False):
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
        with flat_panel(f'{row["name"]} · {row["quantity"]:g}{row["unit"]} · {label} · {row["id"][:4]}'):
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
    with flat_panel("백업 가져오기 · 현재 가족 데이터 전체 교체"):
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
    with flat_panel("배포 및 저장 안내"):
        st.markdown("""GitHub 최상위에 **app.py**와 **requirements.txt**를 올리고 실행 경로를 **app.py**로 지정하세요. Python 3.12를 권장합니다. SQL 실행이나 Secrets 설정은 필요 없습니다.

SQLite 저장 파일은 자동 생성됩니다. 일반적인 새로고침이나 다른 기기의 접속 시 같은 서버 데이터를 사용합니다. **Cloud 재배포·서버 교체 시 데이터가 사라질 수 있습니다.** 공유·관리 탭에서 정기적으로 JSON 백업을 받으세요. 실제 영구 저장 보장에는 외부 저장소가 필요합니다.

한글 입력 보호를 위해 자동 갱신은 사용하지 않습니다. 다른 가족의 변경은 새로고침 버튼으로 확인하세요. 인터넷 연결이 필요하며 푸시 알림은 제공하지 않습니다.
""")


CATEGORY_PHOTOS = {'수산물': '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', '채소': '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', '과일': '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'}

def auto_location(name):
    text = str(name).replace(" ", "")
    category = auto_category(name)
    if any(w in text for w in ["냉동","만두","아이스크림"]): return "냉동"
    if any(w in text for w in ["통조림","참치캔","건미역","다시마","멸치","감자","고구마","양파","마늘","바나나"]): return "실온"
    if category in ["곡물·면", "양념"]: return "실온"
    return "냉장"


def delete_all_stock(state):
    for item in state["items"]:
        if item.get("status") == "active" and item["quantity"] > 0:
            quick_remove(state,item["id"],False)


KIMCHI_ICON = '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'

def food_icon(name):
    name = str(name).replace(" ", "")
    icons = {"김치":"🥬🌶️", "두부":"◻️", "고등어":"🐟", "갈치":"🐟", "연어":"🍣", "참치":"🐟", "새우":"🦐", "오징어":"🦑", "문어":"🐙", "조개":"🦪", "게":"🦀", "미역":"🌿", "멸치":"🐟",
             "복숭아":"🍑", "사과":"🍎", "귤":"🍊", "오렌지":"🍊", "딸기":"🍓", "포도":"🍇", "수박":"🍉", "바나나":"🍌", "레몬":"🍋", "배":"🍐", "키위":"🥝", "망고":"🥭", "블루베리":"🫐",
             "닭고기":"🍗", "닭가슴살":"🍗", "소고기":"🥩", "쇠고기":"🥩", "돼지고기":"🥩", "삼겹살":"🥓", "베이컨":"🥓", "소시지":"🌭",
             "감자":"🥔", "고구마":"🍠", "양파":"🧅", "마늘":"🧄", "당근":"🥕", "토마토":"🍅", "오이":"🥒", "가지":"🍆", "브로콜리":"🥦", "고추":"🌶️", "버섯":"🍄", "옥수수":"🌽", "양배추":"🥬", "배추":"🥬", "대파":"🌱",
             "달걀":"🥚", "계란":"🥚", "우유":"🥛", "치즈":"🧀", "버터":"🧈", "요거트":"🥛", "밥":"🍚", "쌀":"🌾", "식빵":"🍞", "빵":"🍞", "국수":"🍜", "파스타":"🍝", "만두":"🥟", "소금":"🧂"}
    for word in sorted(icons,key=len,reverse=True):
        if word in name: return icons[word]
    return {"채소":"🥬", "과일":"🍎", "육류":"🥩", "수산물":"🐟", "유제품·달걀":"🥛", "곡물·면":"🍚", "양념":"🧂", "가공식품":"🍱"}.get(auto_category(name),"🍽️")


def go(page):
    current = st.session_state.get("screen", "현황")
    if current != page:
        st.session_state.previous_screen = current
    st.session_state.screen = page
    st.rerun()


def fridge_view(snapshot):
    stock = sorted(active(snapshot["state"]), key=lambda i:i["expiry"])
    search = st.text_input("재료 찾기", placeholder="🔎 재료 이름 검색", label_visibility="collapsed", key="quick_search")
    location = st.segmented_control("보관", ["전체"]+LOCATIONS, default="전체", key="fridge_location_v2", label_visibility="collapsed")
    if location and location != "전체":
        stock = [i for i in stock if i["location"] == location]
    if search.strip():
        stock = [i for i in stock if search.strip().replace(" ", "") in i["name"].replace(" ", "")]
    urgent = sum(0 <= days(i) <= 3 for i in stock)
    expired = sum(days(i) < 0 for i in stock)
    st.caption(f"재고 {len(stock)}종 · 임박 {urgent} · 경과 {expired}")
    if st.session_state.get("last_stock_filter") != (search, location):
        st.session_state.shelf_page = 1
        st.session_state.last_stock_filter = (search, location)
    pages = max(1, (len(stock)+5)//6)
    page = min(max(1, st.session_state.get("shelf_page", 1)), pages)
    if st.session_state.get("undo_deleted"):
        if st.button("↶ 방금 삭제 취소", use_container_width=True):
            saved = st.session_state.undo_deleted
            def restore(state):
                target = next((i for i in state["items"] if i["id"] == saved["id"]), None)
                if target is None or target.get("status") != "deleted":
                    raise ValueError("이미 변경된 재료입니다.")
                target.update(copy.deepcopy(saved))
                touch(target)
                event(state,"삭제 취소",target)
            commit(snapshot,restore)
    st.markdown('<div class="fridge-top">❄️ 냉장고 현황</div>', unsafe_allow_html=True)
    if not stock: st.info("비어 있어요. ＋ 등록으로 채워 보세요.")
    for row in range(min(3, (max(0,len(stock)-(page-1)*6)+1)//2)):
        cols = st.columns(2)
        for col in range(2):
            index = (page-1)*6+row*2+col
            with cols[col]:
                if index >= len(stock):
                    st.markdown('<div class="shelf empty">빈 칸</div>', unsafe_allow_html=True)
                    continue
                item = stock[index]
                d = days(item)
                expiry = "기한 경과" if d < 0 else "오늘까지" if d == 0 else f"D-{d}"
                tone = "#b43434" if d < 0 else "#986000" if d <= 3 else "#266244"
                photo = item.get("photo", "") or (KIMCHI_ICON if "김치" in item["name"] else "")
                picture = ('<img alt="음식 사진" src="data:image/jpeg;base64,'+photo+'">') if photo else '<span class="food-icon">'+food_icon(item["name"])+ '</span>'
                st.markdown(f'<div class="shelf">{picture}<b>{esc(item["name"])}</b><small>{item["quantity"]:g}{esc(item["unit"])} · {esc(item["expiry"])}</small><strong style="color:{tone}">{expiry}</strong></div>', unsafe_allow_html=True)
                if st.button("− 삭제", key="shelf_delete_"+item["id"], use_container_width=True):
                    st.session_state.undo_deleted = copy.deepcopy(item)
                    commit(snapshot,lambda state, ident=item["id"]: quick_remove(state,ident,False))
                if st.button("관리", key="manage_"+item["id"], use_container_width=True):
                    st.session_state.selected_item = item["id"]
                    go("재료 관리")
    left, middle, right = st.columns([1,1,1])
    if left.button("← 이전", disabled=page <= 1, use_container_width=True):
        st.session_state.shelf_page = page-1
        st.rerun()
    middle.markdown(f"**{page} / {pages}**")
    if right.button("다음 →", disabled=page >= pages, use_container_width=True):
        st.session_state.shelf_page = page+1
        st.rerun()


def ingredient_detail(snapshot):
    item = next((i for i in active(snapshot["state"]) if i["id"] == st.session_state.get("selected_item")), None)
    if not item:
        st.info("처리된 재료입니다.")
        if st.button("현황으로"): go("현황")
        return
    st.subheader(item["name"])
    st.caption(f'{item["quantity"]:g}{item["unit"]} · {item["expiry"]}')
    mode = st.segmented_control("기능", ["사용", "수정", "사진", "삭제"], default="사용", label_visibility="collapsed")
    if mode == "사용":
        count = st.number_input("수량", min_value=1, max_value=max(1,int(item["quantity"])), step=1)
        if st.button("사용 완료", type="primary", use_container_width=True):
            def use(state):
                target = next(i for i in state["items"] if i["id"] == item["id"])
                if count > target["quantity"]: raise ValueError("재고가 변경됐습니다.")
                target["quantity"] -= count
                if target["quantity"] == 0: target["status"] = "consumed"
                touch(target)
                event(state,"소비",target,count,target["quantity"] == 0)
            commit(snapshot,use)
    elif mode == "수정":
        with st.form("detail_edit_"+item["id"]):
            vals = item_inputs("detail_"+item["id"],item)
            if st.form_submit_button("저장", use_container_width=True):
                def edit(state):
                    target = next(i for i in state["items"] if i["id"] == item["id"])
                    replacement = make_item(*vals)
                    for key in ("name","quantity","category","unit","bought","expiry","location"):
                        target[key] = replacement[key]
                    touch(target)
                    event(state,"수정",target)
                commit(snapshot,edit)
    elif mode == "사진":
        file = st.file_uploader("음식 사진", type=["jpg","jpeg","png","webp"])
        if file is not None and st.button("사진 저장", type="primary"):
            try:
                from PIL import Image, ImageOps
                image = ImageOps.exif_transpose(Image.open(file))
                image.thumbnail((360,360))
                buf = io.BytesIO()
                image.convert("RGB").save(buf,format="JPEG",quality=75)
                encoded = base64.b64encode(buf.getvalue()).decode("ascii")
                def save_photo(state):
                    target = next(i for i in state["items"] if i["id"] == item["id"])
                    target["photo"] = encoded
                    touch(target)
                commit(snapshot,save_photo)
            except (OSError,ValueError): st.error("사진을 읽지 못했습니다.")
    elif mode == "삭제":
        a,b = st.columns(2)
        if a.button("− 삭제",use_container_width=True): commit(snapshot,lambda state:quick_remove(state,item["id"],False))
        if b.button("폐기",use_container_width=True): commit(snapshot,lambda state:quick_remove(state,item["id"],True))
    if st.button("← 현황", use_container_width=True): go("현황")


def consume_meal(state, amounts):
    changed = 0
    for iid, amount in amounts.items():
        if amount <= 0:
            continue
        item = next((i for i in state["items"] if i["id"] == iid), None)
        if item is None or item["status"] != "active" or days(item) < 0 or amount > item["quantity"]:
            raise ValueError("재고가 변경되었거나 기한이 지났습니다. 다시 확인하세요.")
        item["quantity"] = qty(item["quantity"] - amount)
        finished = item["quantity"] == 0
        if finished:
            item["status"] = "consumed"
        item["updated_by"] = st.session_state.member
        item["updated_at"] = now()
        event(state, "소비", item, amount, terminal=finished, note="요리 후 일괄 소비")
        changed += 1
    if not changed:
        raise ValueError("사용한 재료의 수량을 하나 이상 입력하세요.")


def meal_usage(snapshot):
    title = st.session_state.get("meal_title", "")
    recipe = next((r for r in RECIPES if r[0] == title), None)
    if recipe is None:
        st.info("요리를 먼저 골라 주세요.")
        if st.button("요리로 돌아가기"): go("요리")
        return
    st.subheader(title + " · 사용 기록")
    st.caption("실제로 쓴 양만 입력하세요. 기본값 0 · 재료별 단위 유지")
    names = {norm(n) for n in recipe[1]}
    rows = sorted([i for i in active(snapshot["state"]) if days(i) >= 0 and norm(i["name"]) in names], key=lambda i:i["expiry"])
    with st.form("meal_usage_form"):
        amounts = {}
        for i in rows:
            amounts[i["id"]] = st.number_input(f'{i["name"]} · {i["quantity"]:g}{i["unit"]} · {i["expiry"]}', min_value=0.0, max_value=float(i["quantity"]), value=0.0, step=1.0, key="used_"+i["id"])
        if st.form_submit_button("사용한 만큼 함께 차감", type="primary", use_container_width=True):
            commit(snapshot, lambda state: consume_meal(state, amounts))
    if st.button("← 요리로", use_container_width=True): go("요리")


def rescue_today(snapshot):
    rows = sorted([i for i in active(snapshot["state"]) if 0 <= days(i) <= 3], key=lambda i:i["expiry"])
    if not rows:
        st.info("3일 이내에 기한이 오는 재료가 없어요.")
        if st.button("냉장고 보기", use_container_width=True): go("현황")
        return
    st.caption("기한이 지난 재료는 제외합니다. 냄새·상태와 포장 안내를 먼저 확인하세요.")
    selected = st.selectbox("먼저 쓸 재료", [i["id"] for i in rows], format_func=lambda iid: next(f'{i["name"]} · D-{days(i)} · {i["quantity"]:g}{i["unit"]}' for i in rows if i["id"] == iid))
    chosen = next(i for i in rows if i["id"] == selected)
    recipes = [r for r in recommend_recipes(active(snapshot["state"])) if norm(chosen["name"]) in {norm(n) for n in r["have"]}]
    if not recipes:
        st.info("이 재료를 쓰는 기본 레시피가 아직 없어요. 현황에서 직접 소비 처리할 수 있습니다.")
    for r in recipes[:3]:
        st.markdown(f'**{r["title"]}** · 보유 {round(r["coverage"]*100)}%')
        st.caption("보유 · " + ", ".join(r["have"]))
        if r["missing"]: st.caption("추가 재료 확인 필요")
        if st.button("이 메뉴 사용 기록", key="rescue_"+r["title"], use_container_width=True):
            st.session_state.meal_title = r["title"]
            go("사용 기록")


def choose_dinner(state, title):
    if not any(r[0] == title for r in RECIPES):
        raise ValueError("메뉴를 다시 골라 주세요.")
    state["dinner"] = {"title":title, "date":today().isoformat(), "by":st.session_state.member}


def add_meal_shopping(snapshot, title):
    """저장 결과를 확인한 뒤에만 화면 전환과 성공 알림을 설정합니다."""
    try:
        updated = copy.deepcopy(snapshot["state"])
        expected = dinner_shopping(updated, title)
        rpc("save", snapshot["revision"], updated)
        actual = rpc("load")["state"]["shopping"]
        if not all(any(norm(row["name"]) == norm(name) and row["status"] in ("pending", "purchased") for row in actual) for name in expected):
            raise ValueError("장보기 저장 결과를 확인하지 못했습니다. 새로고침 후 확인하세요.")
    except Exception as exc:
        st.error(error_message(exc))
        return
    st.session_state.flash = ("success", f"필요 재료 {len(expected)}종을 장보기에서 확인하세요. 기존 항목은 중복 추가하지 않았습니다.")
    go("장보기")


def dinner_shopping(state, title):
    recipe = next((r for r in recommend_recipes(active(state)) if r["title"] == title), None)
    if recipe is None:
        raise ValueError("재고가 바뀌었습니다. 메뉴를 다시 확인하세요.")
    for name in recipe["missing"]:
        if any(norm(r["name"]) == norm(name) and r["status"] in ("pending", "purchased") for r in state["shopping"]):
            continue
        row = {"id":uid(), "name":name, "quantity":1, "unit":"개", "status":"pending", "note":"요리용 · 필요한 양 확인", "created_by":st.session_state.member, "updated_by":st.session_state.member,"created_at":now()}
        state["shopping"].append(row)
        event(state,"장보기 추가",row,1)
    return recipe["missing"]


def dinner_home(snapshot):
    state = snapshot["state"]
    st.subheader("오늘 뭐 먹지?")
    chosen = state.get("dinner", {})
    if chosen.get("date") == today().isoformat():
        st.success("오늘의 선택 · " + chosen["title"] + " · " + chosen.get("by","가족"))
        if st.button("먹고 남은 것 확인", use_container_width=True): go("남은 재료")
    rows = active(state)
    urgent = sorted([i for i in rows if 0 <= days(i) <= 3],key=lambda i:i["expiry"])
    if urgent:
        st.caption("먼저 먹기 · " + " / ".join(i["name"]+" D-"+str(days(i)) for i in urgent[:3]))
    if not rows:
        st.info("냉장고 전체를 기록할 필요 없어요. 먼저 먹을 재료 몇 개만 알려 주세요.")
        if st.button("＋ 재료 알려주기",type="primary",use_container_width=True): go("＋ 등록")
        return
    results = recommend_recipes(rows)
    if not results:
        st.info("이 재료에 맞는 기본 메뉴가 아직 없어요.")
        if st.button("재료 더 알려주기",use_container_width=True): go("＋ 등록")
        return
    selected = []
    for test in (lambda r:not r["missing"], lambda r:len(r["missing"])==1, lambda r:True):
        r = next((r for r in results if r not in selected and test(r)),None)
        if r: selected.append(r)
    for r in selected:
        with st.container(border=True):
            label = "재료 종류 모두 있음" if not r["missing"] else f'{len(r["missing"])}종 더 필요'
            st.markdown("**"+r["title"]+"** · "+label)
            st.caption("활용 · " + ", ".join(r["have"]))
            if r["soon"]: st.caption("먼저 쓸 재료 · " + ", ".join(r["soon"]))
            st.write(r["method"])
            if st.button("오늘 이거 먹기",key="choose_"+r["title"],type="primary",use_container_width=True):
                commit(snapshot,lambda data,t=r["title"]:choose_dinner(data,t))
            if r["missing"]:
                st.caption("추가 · " + ", ".join(r["missing"]))
                if st.button("부족 재료를 장보기에",key="need_"+r["title"],use_container_width=True):
                    add_meal_shopping(snapshot,r["title"])
    st.caption("분량·조리시간·알레르기는 보장하지 않아요. 장보기 수량은 임시 1개로 추가되니 구매 전 확인하세요.")
    if st.button("다른 메뉴 보기",use_container_width=True): go("요리")


def leftovers(snapshot):
    chosen = snapshot["state"].get("dinner",{})
    recipe = next((r for r in RECIPES if r[0] == chosen.get("title")),None)
    if recipe is None:
        st.info("오늘 메뉴를 먼저 골라 주세요.")
        return
    st.subheader("먹고 남은 것만 확인")
    st.caption("정확한 수량 입력 없이 상태만 남길 수 있어요. ‘없음’만 재고에서 제외합니다.")
    names = {norm(n) for n in recipe[1]}
    rows = [i for i in active(snapshot["state"]) if norm(i["name"]) in names and days(i)>=0]
    with st.form("leftovers"):
        values = {}
        for i in rows:
            values[i["id"]] = st.selectbox(i["name"]+" · "+i["expiry"],["변경 안 함","있음","조금 남음","없음"],key="left_"+i["id"])
        if st.form_submit_button("완료",type="primary",use_container_width=True):
            def change(data):
                for item in data["items"]:
                    v = values.get(item["id"],"변경 안 함")
                    if v == "변경 안 함": continue
                    if item["status"] != "active": raise ValueError("재고가 바뀌었습니다. 다시 확인하세요.")
                    item["stock_hint"] = v
                    if v == "없음":
                        amount=item["quantity"]
                        item["quantity"]=0
                        item["status"]="consumed"
                        event(data,"소비",item,amount,terminal=True,note="식사 후 없음 확인")
                    item["updated_by"]=st.session_state.member
                    item["updated_at"]=now()
                st.session_state.screen="오늘"
            commit(snapshot,change)


def dashboard():
    st.markdown('<h1 class="app-title">🥬 냉장고 ON</h1>', unsafe_allow_html=True)
    try: snapshot = rpc("load")
    except Exception as exc:
        st.error(error_message(exc))
        return
    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash")[1])
    screen = st.session_state.get("screen","오늘")
    nav = st.columns(5)
    for column,label in zip(nav,["오늘","＋ 등록","현황","장보기","더보기"]):
        if column.button(label,key="nav_"+label,use_container_width=True, type="primary" if screen == label else "secondary"): go(label)
    if screen == "오늘": dinner_home(snapshot)
    elif screen == "남은 재료": leftovers(snapshot)
    elif screen == "현황":
        urgent = [i for i in active(snapshot["state"]) if 0 <= days(i) <= 3]
        if urgent and st.button(f"⏰ 먼저 먹기 · {len(urgent)}건 →", use_container_width=True): go("먼저 먹기")
        fridge_view(snapshot)
    elif screen == "먼저 먹기": rescue_today(snapshot)
    elif screen == "사용 기록": meal_usage(snapshot)
    elif screen == "＋ 등록": new_ingredient(snapshot)
    elif screen == "재료 관리": ingredient_detail(snapshot)
    elif screen == "요리":
        results = recommend_recipes(active(snapshot["state"]))
        if not results: st.info("등록된 재료를 활용하는 메뉴가 없어요.")
        else:
            page = min(st.session_state.get("recipe_page",0),len(results)-1)
            recipe = results[page]
            if recipe["missing"]:
                st.caption("일부 추가 재료가 필요한 메뉴예요. 조리 전 재료를 확인하세요.")
            st.markdown(f'<div class="recipe-compact"><div class="recipe-heading"><b>{esc(recipe["title"])}</b><small>{page+1}/{len(results)}</small></div><p class="recipe-owned">보유 · {esc(", ".join(recipe["have"]))}</p><div class="recipe-method">{esc(recipe["method"])}</div></div>', unsafe_allow_html=True)
            if st.button("🍽 이 요리를 먹었어요 · 재고 차감", key="record_meal", use_container_width=True):
                st.session_state.meal_title = recipe["title"]
                go("사용 기록")
            a,b=st.columns(2)
            if a.button("← 이전",disabled=page==0,use_container_width=True):
                st.session_state.recipe_page=page-1
                st.rerun()
            if b.button("다음 →",disabled=page==len(results)-1,use_container_width=True):
                st.session_state.recipe_page=page+1
                st.rerun()
    elif screen == "더보기":
        if st.button("전체 재고 비우기", key="open_clear_all", use_container_width=True):
            st.session_state.confirm_clear_all = True
        if st.session_state.get("confirm_clear_all"):
            st.warning("모든 재고를 삭제합니다. 먼저 백업해 주세요.")
            yes, no = st.columns(2)
            if yes.button("전체 삭제 확인", key="yes_clear_all"):
                st.session_state.confirm_clear_all = False
                commit(snapshot,delete_all_stock)
            if no.button("취소", key="no_clear_all"):
                st.session_state.confirm_clear_all = False
                st.rerun()
        if st.button("장보기",use_container_width=True): go("장보기")
        if st.button("공유 · 백업",use_container_width=True): go("공유")
        st.session_state.member = st.text_input("이름",value=st.session_state.get("member","가족")) or "가족"
        if st.button("↻ 새로고침",use_container_width=True): st.rerun()
    elif screen == "장보기": shopping(snapshot)
    elif screen == "공유":
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
    dashboard()


if __name__ == "__main__":
    main()
