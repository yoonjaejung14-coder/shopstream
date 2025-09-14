import streamlit as st
import random, string
from datetime import datetime, timedelta
from tinydb import TinyDB, Query

# ------------------------
# DB 연결 (캐싱)
# ------------------------
@st.cache_resource
def get_db():
    return TinyDB("shopdb.json", ensure_ascii=False, indent=4)

db = get_db()
users_table = db.table("users")
giftcards_table = db.table("giftcards")
purchases_table = db.table("purchases")
stocks_table = db.table("stocks")

# ------------------------
# 상품 데이터
# ------------------------
products = [
    {"name": "노트북", "price": 2300000},
    {"name": "모니터", "price": 700000},
    {"name": "로벅스150000", "price": 150000},
    {"name": "에어컨", "price": 3700000},
]

# ------------------------
# 재고 초기화 (2000개, 1주마다)
# ------------------------
def reset_stocks():
    meta = stocks_table.get(doc_id=1)
    now = datetime.now()
    if not meta:
        stocks_table.insert({"last_reset": now.isoformat(),
                             "stocks": {p["name"]: 2000 for p in products}})
    else:
        last_reset = datetime.fromisoformat(meta["last_reset"])
        if now - last_reset >= timedelta(days=7):
            stocks_table.update({"last_reset": now.isoformat(),
                                 "stocks": {p["name"]: 2000 for p in products}}, doc_ids=[1])

def get_stock(name):
    return stocks_table.get(doc_id=1)["stocks"].get(name, 0)

def update_stock(name, qty):
    meta = stocks_table.get(doc_id=1)
    stocks = meta["stocks"]
    stocks[name] = max(0, stocks[name] - qty)
    stocks_table.update({"stocks": stocks}, doc_ids=[1])

# ------------------------
# 사용자 관련
# ------------------------
def get_user(name): return users_table.get(Query().name == name)
def update_user(name, data): users_table.update(data, Query().name == name)
def get_logged_in_user(): return users_table.get(Query().logged_in == True)
def set_logged_in(name): users_table.update({"logged_in": True}, Query().name == name)
def set_logged_out(name): users_table.update({"logged_in": False}, Query().name == name)
def get_online_users(): return [u["name"] for u in users_table.search(Query().logged_in == True)]

# ------------------------
# 구매 기록
# ------------------------
def record_purchase(user, product, qty):
    purchases_table.insert({"buyer": user, "product": product, "qty": qty,
                            "time": datetime.now().isoformat()})

# ------------------------
# 세션 초기값
# ------------------------
if "user" not in st.session_state: st.session_state.user = None
if "cart" not in st.session_state: st.session_state.cart = {}

# ------------------------
# 회원가입 / 로그인 / 로그아웃
# ------------------------
def signup_page():
    st.header("📝 회원가입")
    email = st.text_input("이메일")
    name = st.text_input("이름")
    pw = st.text_input("비밀번호", type="password")
    if st.button("회원가입"):
        if get_user(name): st.error("이미 존재하는 이름입니다.")
        else:
            users_table.insert({"name": name, "email": email, "password": pw,
                                "wallet": 10000, "inventory": {}, "logged_in": False})
            st.success(f"{name}님 가입 완료!")

def login_page():
    st.header("🔑 로그인")
    name = st.text_input("이름")
    pw = st.text_input("비밀번호", type="password")
    if st.button("로그인"):
        user = get_user(name)
        if user and user["password"] == pw:
            set_logged_in(name)
            st.session_state.user = name
            st.rerun()
        else: st.error("이름 또는 비밀번호가 틀렸습니다.")

def logout_user():
    if st.session_state.user:
        set_logged_out(st.session_state.user)
        st.session_state.user = None
        st.rerun()

# ------------------------
# 쇼핑몰
# ------------------------
def shop_page():
    user = get_user(st.session_state.user)
    st.header(f"🛍 {user['name']}님의 쇼핑몰")

    st.subheader("🟢 현재 접속자")
    for u in get_online_users(): st.write(f"- {u}")

    menu = st.sidebar.radio("📂 메뉴", ["상품", "지갑", "장바구니", "인벤토리", "구매 기록", "기프트카드", "로그아웃"])

    # 상품
    if menu == "상품":
        for p in products:
            stock = get_stock(p["name"])
            with st.expander(p["name"]):
                st.write(f"가격: {p['price']:,}원")
                st.write(f"재고: {stock}개")
                qty = st.number_input(f"{p['name']} 수량", 0, stock, 0, 1, key=f"qty-{p['name']}")
                if qty > 0:
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("🛒 장바구니 담기", key=f"cart-{p['name']}"):
                            st.session_state.cart[p["name"]] = {"product": p, "count": qty}
                            st.success("장바구니 담김!")
                    with col2:
                        if st.button("💳 바로구매", key=f"buy-{p['name']}"):
                            if user["wallet"] >= p["price"]*qty:
                                update_stock(p["name"], qty)
                                inv = user["inventory"]
                                inv[p["name"]] = inv.get(p["name"], 0) + qty
                                update_user(user["name"], {"wallet": user["wallet"]-p["price"]*qty,
                                                           "inventory": inv})
                                record_purchase(user["name"], p["name"], qty)
                                st.success("바로구매 완료!")
                            else: st.error("잔액 부족!")

    # 지갑
    elif menu == "지갑":
        st.write(f"현재 잔액: {user['wallet']:,}원")
        add = st.number_input("충전 금액", 0, step=1000)
        if st.button("충전하기"):
            update_user(user["name"], {"wallet": user["wallet"]+add})
            st.success(f"{add:,}원 충전 완료!")

    # 장바구니
    elif menu == "장바구니":
        if st.session_state.cart:
            total = sum(p["product"]["price"]*p["count"] for p in st.session_state.cart.values())
            for name, data in st.session_state.cart.items():
                st.write(f"{name} {data['count']}개 → {data['product']['price']*data['count']:,}원")
            st.write(f"총합: {total:,}원")
            if st.button("💳 결제하기"):
                if user["wallet"] >= total:
                    inv = user["inventory"]
                    for name, data in st.session_state.cart.items():
                        if data["count"] <= get_stock(data["product"]["name"]):
                            inv[name] = inv.get(name, 0) + data["count"]
                            update_stock(data["product"]["name"], data["count"])
                            record_purchase(user["name"], name, data["count"])
                    update_user(user["name"], {"wallet": user["wallet"]-total, "inventory": inv})
                    st.session_state.cart.clear()
                    st.success("결제 완료! 🎉")
                else: st.error("잔액 부족!")
        else: st.info("장바구니가 비어 있음")

    # 인벤토리
    elif menu == "인벤토리":
        if user["inventory"]:
            for item, count in user["inventory"].items(): st.write(f"- {item}: {count}개")
        else: st.write("비어 있음")

    # 구매 기록
    elif menu == "구매 기록":
        records = purchases_table.search(Query().buyer == user["name"])
        if records:
            for r in records: st.write(f"{r['time']} - {r['product']} {r['qty']}개")
        else: st.info("없음")

    # 기프트카드
    elif menu == "기프트카드":
        amount = st.number_input("금액 입력", 1000, step=1000)
        if st.button("발급하기"):
            code = "-".join("".join(random.choices(string.ascii_uppercase+string.digits, k=4)) for _ in range(3))
            giftcards_table.insert({"code": code, "amount": amount, "used": False})
            st.success(f"코드 {code}, 금액 {amount:,}원 발급 완료!")

    # 로그아웃
    elif menu == "로그아웃": logout_user()

# ------------------------
# 메인 실행
# ------------------------
st.set_page_config(page_title="윤재마켓", page_icon="🛒")
reset_stocks()

if not st.session_state.user:
    u = get_logged_in_user()
    if u: st.session_state.user = u["name"]

if st.session_state.user: shop_page()
else:
    menu = st.sidebar.radio("메뉴", ["회원가입", "로그인"])
    if menu == "회원가입": signup_page()
    elif menu == "로그인": login_page()
