"""가족 부탁함 · Python 3.12 권장
GitHub에 app.py / requirements.txt 업로드 → Streamlit Cloud main file: app.py.
설정 없이 SQLite 자동 생성. Cloud 디스크는 영구 보장되지 않으므로 백업 필요.
공개 링크 방문자는 모두 같은 부탁함을 수정합니다. 민감한 정보는 등록하지 마세요.
"""
import copy
import io
import json
import sqlite3
import uuid
from datetime import datetime, date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import streamlit as st

st.set_page_config(page_title="가족 부탁함", page_icon="🏡", layout="centered")
DB = Path(__file__).with_name("family_requests.sqlite3")
KST = ZoneInfo("Asia/Seoul")
CATEGORIES = ["장보기", "집안일", "외출·심부름", "학교·일정", "기타"]
PRIORITIES = ["오늘까지", "이번 주", "급하지 않음"]
STATUSES = ["대기", "진행 중", "완료", "취소"]
CSS = """<style>
.stApp{background:#f5f7f2;color:#23362c}.block-container{max-width:720px;padding:1rem 1rem 3rem}
h1{font-size:1.85rem!important;color:#254c35!important}h2,h3,p,label{color:#23362c}
[data-testid="stVerticalBlockBorderWrapper"]{background:#fff;border-radius:18px}
[data-testid="stButton"] button,[data-testid="stFormSubmitButton"] button{min-height:46px;border-radius:13px!important;background:#e7f1dd!important;color:#24472d!important;border:1px solid #9ab983!important}
[data-testid="stButton"] button:hover,[data-testid="stButton"] button:active,[data-testid="stButton"] button:focus,[data-testid="stFormSubmitButton"] button:hover{background:#e7f1dd!important;color:#24472d!important;border:1px solid #9ab983!important;box-shadow:none!important}
button p{color:inherit!important}button:disabled{opacity:.45!important}
input,textarea{background:#fff!important;color:#223c2b!important;font-size:16px!important}
[data-baseweb="select"]>div{background:#fff!important;color:#223c2b!important}
button:focus-visible{outline:3px solid #466d38!important}
@media(max-width:600px){.block-container{padding-top:.7rem}h1{font-size:1.6rem!important}[data-testid="stHorizontalBlock"]{gap:.35rem}}
</style>"""

def now(): return datetime.now(KST).isoformat()
def today(): return datetime.now(KST).date()
def uid(): return uuid.uuid4().hex

def validate(data):
    if not isinstance(data,dict) or not isinstance(data.get("tasks"),list) or not isinstance(data.get("templates"),list):
        raise ValueError("백업 형식이 맞지 않습니다.")
    if len(data["tasks"])>3000 or len(data["templates"])>200:
        raise ValueError("항목이 너무 많습니다.")
    seen=set()
    for t in data["tasks"]:
        if not isinstance(t,dict) or not isinstance(t.get("id"),str) or t["id"] in seen: raise ValueError("항목 ID 오류")
        seen.add(t["id"])
        if not isinstance(t.get("title"),str) or not t["title"].strip() or len(t["title"])>100: raise ValueError("제목 오류")
        if t.get("category") not in CATEGORIES or t.get("priority") not in PRIORITIES or t.get("status") not in STATUSES: raise ValueError("분류 오류")
        for k in ("note","creator","owner","created_at","updated_at"):
            if not isinstance(t.get(k),str) or len(t[k])>1500: raise ValueError("내용 오류")
        if t.get("due") is not None: date.fromisoformat(t["due"])
    for t in data["templates"]:
        if not isinstance(t,dict) or not isinstance(t.get("id"),str) or not isinstance(t.get("title"),str) or not 0<len(t["title"])<=100 or t.get("category") not in CATEGORIES or not isinstance(t.get("note"),str) or len(t["note"])>1000: raise ValueError("자주 쓰는 부탁 오류")
    return data

def load():
    with sqlite3.connect(str(DB),timeout=20) as c:
        c.execute("CREATE TABLE IF NOT EXISTS household(id INTEGER PRIMARY KEY, data TEXT NOT NULL, rev INTEGER NOT NULL)")
        c.execute("INSERT OR IGNORE INTO household VALUES(1,?,0)",(json.dumps({"tasks":[],"templates":[]}),))
        r=c.execute("SELECT data,rev FROM household WHERE id=1").fetchone()
    return json.loads(r[0]),r[1]

def save(data,rev):
    validate(data)
    encoded=json.dumps(data,ensure_ascii=False,allow_nan=False)
    if len(encoded.encode())>3000000: raise ValueError("데이터가 너무 큽니다. 백업 후 완료 항목을 정리하세요.")
    with sqlite3.connect(str(DB),timeout=20) as c:
        c.execute("BEGIN IMMEDIATE")
        cur=c.execute("UPDATE household SET data=?,rev=rev+1 WHERE id=1 AND rev=?",(encoded,rev))
        if cur.rowcount!=1: raise ValueError("다른 가족이 먼저 변경했습니다. 새로고침 후 다시 시도하세요.")

def mutate(data,rev,fn,message="저장했어요.",page=None):
    try:
        updated=copy.deepcopy(data);fn(updated);save(updated,rev)
    except Exception as e:
        st.error(str(e));return
    st.session_state.flash=message
    if page: st.session_state.page=page
    st.rerun()

def route(page):
    st.session_state.page=page;st.rerun()

def person():
    name=st.session_state.get("name","").strip()
    if not name: raise ValueError("상단에 사용할 이름을 입력해 주세요.")
    return name[:30]

def new_task(title,category,priority,note,who):
    title=title.strip();note=note.strip()
    if not title: raise ValueError("부탁 내용을 입력해 주세요.")
    due=today() if priority=="오늘까지" else today()+timedelta(days=6-today().weekday()) if priority=="이번 주" else None
    return dict(id=uid(),title=title[:100],category=category,priority=priority,note=note[:1000],creator=who,owner="",status="대기",due=due.isoformat() if due else None,created_at=now(),updated_at=now())

def change_task(data,tid,action,who):
    t=next((x for x in data["tasks"] if x["id"]==tid),None)
    if t is None: raise ValueError("부탁을 찾을 수 없습니다.")
    if action=="claim":
        if t["status"]!="대기": raise ValueError("이미 다른 가족이 맡았어요.")
        t.update(status="진행 중",owner=who)
    elif action=="release":
        if t["status"]!="진행 중" or t["owner"]!=who: raise ValueError("담당자만 맡기를 취소할 수 있어요.")
        t.update(status="대기",owner="")
    elif action=="complete":
        if t["status"] not in ("대기","진행 중"): raise ValueError("이미 처리된 부탁입니다.")
        if t["owner"] and t["owner"]!=who: raise ValueError("담당자 이름으로 완료해 주세요.")
        t.update(status="완료",owner=who)
    elif action=="cancel":
        if t["creator"]!=who: raise ValueError("등록한 이름으로 취소해 주세요.")
        if t["status"] not in ("대기","진행 중"): raise ValueError("이미 처리된 부탁입니다.")
        t["status"]="취소"
    elif action=="reopen":
        if t["status"] not in ("완료","취소"): raise ValueError("아직 처리 중인 부탁입니다.")
        t.update(status="대기",owner="")
    t["updated_at"]=now()


def cards(data,rev):
    a,b=st.columns(2)
    category=a.selectbox("분류",["전체"]+CATEGORIES,key="category_filter")
    view=b.selectbox("보기",["진행할 부탁","내가 맡은 일","내가 부탁한 일","완료·취소"],key="view_filter")
    query=st.text_input("검색",placeholder="부탁 찾기",label_visibility="collapsed")
    rows=data["tasks"]
    rows=[t for t in rows if (t["status"] in ("완료","취소"))==(view=="완료·취소")]
    if category!="전체":rows=[t for t in rows if t["category"]==category]
    if view=="내가 맡은 일":rows=[t for t in rows if t["owner"]==st.session_state.get("name","").strip()]
    if view=="내가 부탁한 일":rows=[t for t in rows if t["creator"]==st.session_state.get("name","").strip()]
    rows=[t for t in rows if query.strip().casefold() in (t["title"]+" "+t["note"]).casefold()]
    rows.sort(key=lambda t:(t["due"] or "9999",t["created_at"]))
    if view=="완료·취소": rows.sort(key=lambda t:t["updated_at"],reverse=True)
    signature=(category,view,query)
    if st.session_state.get("list_signature")!=signature:st.session_state.list_page=0;st.session_state.list_signature=signature
    pages=max(1,(len(rows)+3)//4);page=min(st.session_state.get("list_page",0),pages-1)
    st.caption(f"{len(rows)}개 · {page+1}/{pages}페이지")
    if not rows:st.info("해당하는 부탁이 없어요.")
    for t in rows[page*4:page*4+4]:
        with st.container(border=True):
            overdue=bool(t["due"] and t["due"]<today().isoformat() and t["status"] in ("대기","진행 중"))
            st.markdown("### "+t["title"])
            st.caption(t["category"]+" · "+t["status"]+" · "+("기한 지남 · " if overdue else "")+(t["due"] or "기한 없음"))
            st.write("담당: "+(t["owner"] or "아직 없어요")+" · 부탁한 사람: "+t["creator"])
            if t["note"]:st.write(t["note"])
            actions=[]
            if t["status"]=="대기":actions=[("내가 할게","claim"),("바로 완료","complete")]
            elif t["status"]=="진행 중" and t["owner"]==st.session_state.get("name","").strip():actions=[("완료","complete"),("맡기 취소","release")]
            elif t["status"] in ("완료","취소"):actions=[("다시 열기","reopen")]
            cols=st.columns(max(1,len(actions)))
            for col,(label,action) in zip(cols,actions):
                if col.button(label,key=action+t["id"],use_container_width=True):
                    try:who=person()
                    except ValueError as e:st.error(str(e))
                    else:mutate(data,rev,lambda d,tid=t["id"],act=action:change_task(d,tid,act,who))
            if t["status"] in ("대기","진행 중") and t["creator"]==st.session_state.get("name","").strip():
                if st.button("이 부탁 취소",key="cancel"+t["id"]):mutate(data,rev,lambda d,tid=t["id"]:change_task(d,tid,"cancel",person()))
    prev,nxt=st.columns(2)
    if prev.button("← 이전",disabled=page==0,use_container_width=True):st.session_state.list_page=page-1;st.rerun()
    if nxt.button("다음 →",disabled=page==pages-1,use_container_width=True):st.session_state.list_page=page+1;st.rerun()

def register(data,rev):
    st.subheader("무엇을 부탁할까요?")
    templates=data["templates"]
    source=st.selectbox("자주 쓰는 부탁",[""]+[t["id"] for t in templates],format_func=lambda x:"새로 작성" if not x else next(t["title"] for t in templates if t["id"]==x))
    template=next((t for t in templates if t["id"]==source),{})
    with st.form("register_"+source):
        title=st.text_input("부탁",value=template.get("title",""),max_chars=100,placeholder="예: 오는 길에 세탁물 찾아오기")
        category=st.selectbox("종류",CATEGORIES,index=CATEGORIES.index(template.get("category","기타")))
        priority=st.radio("언제까지?",PRIORITIES,horizontal=True)
        note=st.text_area("추가 설명 (선택)",value=template.get("note",""),max_chars=1000,height=85)
        keep=st.checkbox("자주 쓰는 부탁으로 저장")
        if st.form_submit_button("부탁 올리기",type="primary",use_container_width=True):
            try:task=new_task(title,category,priority,note,person())
            except ValueError as e:st.error(str(e))
            else:
                def add(d):
                    if any(t["title"]==task["title"] and t["status"] in ("대기","진행 중") for t in d["tasks"]):raise ValueError("같은 제목의 진행 중인 부탁이 있어요. 목록을 먼저 확인해 주세요.")
                    d["tasks"].append(task)
                    if keep and not any(t["title"]==task["title"] for t in d["templates"]):d["templates"].append({"id":uid(),"title":task["title"],"category":category,"note":task["note"]})
                mutate(data,rev,add,"부탁을 올렸어요.","부탁함")

def settings(data,rev):
    st.subheader("백업·안내")
    st.info("앱 링크를 아는 사람은 같은 부탁함을 보고 수정합니다. 이름은 본인 인증이 아닙니다. 주소·비밀번호·민감한 일정은 넣지 마세요.")
    st.warning("Cloud 서버 교체·재배포 시 데이터가 사라질 수 있어요. 정기적으로 백업해 주세요. 자동 푸시 알림은 제공하지 않습니다.")
    st.download_button("백업 다운로드",json.dumps({"app":"family_requests","version":1,"data":data},ensure_ascii=False,indent=2),file_name="family_requests_"+today().isoformat()+".json",mime="application/json",use_container_width=True)
    with st.form("restore"):
        upload=st.file_uploader("JSON 백업 가져오기",type=["json"])
        confirm=st.checkbox("현재 부탁함 전체를 백업 내용으로 교체합니다.")
        if st.form_submit_button("복원"):
            try:
                if not upload or not confirm:raise ValueError("파일을 선택하고 교체에 동의해 주세요.")
                if upload.size>3000000:raise ValueError("백업 파일이 너무 큽니다.")
                payload=json.loads(upload.getvalue())
                if payload.get("app")!="family_requests" or payload.get("version")!=1:raise ValueError("가족 부탁함 백업만 가져올 수 있어요.")
                restored=validate(payload["data"])
            except Exception as e:st.error(str(e))
            else:mutate(data,rev,lambda d:(d.clear(),d.update(restored)),"복원했어요.","부탁함")
    if data["templates"]:
        tid=st.selectbox("자주 쓰는 부탁 관리",[t["id"] for t in data["templates"]],format_func=lambda x:next(t["title"] for t in data["templates"] if t["id"]==x))
        if st.button("선택한 양식 삭제"):mutate(data,rev,lambda d:d.update(templates=[t for t in d["templates"] if t["id"]!=tid]))
    st.caption("다른 가족의 변경은 상단 새로고침으로 확인하세요. 입력 중 끊김을 줄이기 위해 자동 갱신은 사용하지 않습니다.")

def main():
    st.markdown(CSS,unsafe_allow_html=True)
    st.title("🏡 가족 부탁함")
    st.caption("혼자 기억하지 말고, 함께 끝내요.")
    st.text_input("사용할 이름",key="name",max_chars=30,placeholder="엄마 / 아빠 / 민준")
    try:data,rev=load()
    except Exception:
        st.error("저장 공간을 열지 못했어요. Streamlit 로그를 확인해 주세요.");return
    if "flash" in st.session_state:st.success(st.session_state.pop("flash"))
    page=st.session_state.get("page","부탁함")
    cols=st.columns(3)
    for c,label in zip(cols,["부탁함","＋ 부탁","관리"]):
        if c.button(label,use_container_width=True,key="nav"+label):route(label)
    pending=sum(t["status"]=="대기" for t in data["tasks"]);working=sum(t["status"]=="진행 중" for t in data["tasks"])
    if page=="부탁함":
        st.caption(f"맡아줄 부탁 {pending}개 · 진행 중 {working}개")
        a,b=st.columns(2)
        if a.button("🛒 장 보러 가요",use_container_width=True):
            st.session_state.category_filter="장보기";st.session_state.view_filter="진행할 부탁";st.session_state.list_page=0;st.rerun()
        if b.button("↻ 새로고침",use_container_width=True):st.rerun()
        cards(data,rev)
    elif page=="＋ 부탁":register(data,rev)
    else:settings(data,rev)

if __name__=="__main__":main()
