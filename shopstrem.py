import streamlit as st
import re
import random
import string
from datetime import datetime, timedelta
from tinydb import TinyDB, Query

# ------------------------
# DB 연결
# ------------------------
db = TinyDB("shopdb.json", ensure_ascii=False, indent=4)
users_table = db.table("users")
giftcards_table = db.table("giftcards")
purchases_table = db.table("purchases")   # 구매 기록
stocks_table = db.table("stocks")         # 재고 관리

# ------------------------
# 유틸 함수
# ------------------------
def parse_volume_to_ml(text: str) -> int:
    t = text.strip().lower()
    if t.endswith("ml"):
        return int(float(t[:-2]))
    if t.endswith("l"):
        return int(float(t[:-1]) * 1000)
    return 0

def parse_length_cm(text: str) -> int:
    t = text.strip().lower()
    if t.endswith("cm"):
        return int(float(t[:-2]))
    return 0

def option_price(product: dict, option: str) -> int:
    if "로벅스" in product["name"]:
        return product["sale_price"]
    if "Steam" in product["name"]:
        return product["sale_price"]
    return product["sale_price"]

# ------------------------
# 상품 데이터 (이미지 포함)
# ------------------------
products = [
    {
        "category": "전자기기",
        "name": "노트북 Lenovo X1 Carbon Gen12",
        "price": 1964767,
        "sale_price": 2300000,
        "brand": "Lenovo",
        "link": "https://www.lenovo.com/kr/ko/p/laptops/thinkpad/thinkpadx1/thinkpad-x1-carbon-gen-12-14-inch-intel/21kccto1wwkr1",
        "options": ["터치O", "터치N"],
        "image": "노트북.png",
    },
    {
        "category": "전자기기",
        "name": "모니터 ThinkVision P24q-30 23.8인치",
        "price": 359000,
        "sale_price": 700000,
        "brand": "Lenovo",
        "link": "https://www.lenovo.com/kr/ko/p/accessories-and-software/monitors/professional/63b4gar6ww",
        "options": [],
        "image": "모니터.png",
    },
    {
        "category": "전자기기",
        "name": "[G마켓] 삼성 DM500TGZ-AD74 데스크탑 인텔 14세대 i7 고성능 게이밍 없음 사무용 컴퓨터",
        "price": 1349000,
        "sale_price": 1750000,
        "brand": "Samsung",
        "link": "https://item.gmarket.co.kr/Item?goodscode=368231381",
        "options": [],
        "image": "컴퓨터.png",
    },
    {
        "category": "현질",
        "name": "로벅스(150000원권)",
        "price": 99500,
        "sale_price": 150000,
        "brand": "Roblox",
        "link": "https://www.ssg.com/item/itemView.ssg?itemId=1000585600576&siteNo=6004&salestrNo=6005",
        "options": ["기프트카드 전용, 쿠폰 사용 불가"],
        "image": "로벅스150000.png",
    },
    {
        "category": "현질",
        "name": "[Steam] 충전카드 22000원권",
        "price": 22000,
        "sale_price": 40000,
        "brand": "Steam",
        "link": "https://store.steampowered.com/",
        "options": ["기프트카드 전용, 쿠폰 사용 불가"],
        "image": "흠심.png",
    },
    {
        "category": "전자기기",
        "name": "[LG휘센] 오브제컬렉션 에어컨 2in1 (3세대)",
        "price": 3350000,
        "sale_price": 3700000,
        "brand": "LG",
        "link": "https://www.lge.co.kr/air-conditioners/fq18hv3k2z?skwd=에어컨",
        "options": [],
        "image": "래어큔.png",
    }
]

# ------------------------
# 재고 관리 함수 (2000개 고정, 1주일마다 리셋)
# ------------------------
def reset_stocks():
    meta = stocks_table.get(doc_id=1)
    now = datetime.now()

    if not meta:  # 첫 실행
        stocks_table.insert({
            "last_reset": now.isoformat(),
            "stocks": {p["name"]: 2000 for p in products}
        })
    else:
        last_reset = datetime.fromisoformat(meta["last_reset"])
        if now - last_reset >= timedelta(days=7):
            stocks_table.update({
                "last_reset": now.isoformat(),
                "stocks": {p["name"]: 2000 for p in products}
            }, doc_ids=[1])

def get_stock(product_name):
    meta = stocks_table.get(doc_id=1)
    return meta["stocks"].get(product_name, 0)

def update_stock(product_name, qty):
    meta = stocks_table.get(doc_id=1)
    stocks = meta["stocks"]
    stocks[product_name] = max(0, stocks[product_name] - qty)
    stocks_table.update({"stocks": stocks}, doc_ids=[1])

# ------------------------
# DB 헬퍼 함수
# ------------------------
def get_user(name):
    UserQ = Query()
    return users_table.get(UserQ.name == name)

def update_user(name, data):
    UserQ = Query()
    users_table.update(data, UserQ.name == name)

def get_logged_in_user():
    UserQ = Query()
    return users_table.get(UserQ.logged_in == True)

# ------------------------
# 기프트카드 함수
# ------------------------
def generate_giftcard_code():
    return "-".join(
        "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
        for _ in range(3)
    )

def giftcard_issue_page():
    st.header("🎁 기프트카드 발급")
    amount = st.number_input("충전 금액 입력", min_value=1000, step=1000)
    if st.button("발급하기"):
        code = generate_giftcard_code()
        giftcards_table.insert({
            "code": code,
            "amount": amount,
            "used": False
        })
        st.success(f"기프트카드 발급 완료! 코드: **{code}**, 금액: {amount:,}원")

# ------------------------
# 세션 초기값
# ------------------------
if "user" not in st.session_state:
    st.session_state.user = None
if "cart" not in st.session_state:
    st.session_state.cart = {}

# ------------------------
# 회원가입
# ------------------------
def signup_page():
    st.header("📝 회원가입")
    email = st.text_input("이메일")
    name = st.text_input("이름")
    password = st.text_input("비밀번호", type="password")

    if st.button("회원가입"):
        if get_user(name):
            st.error("이미 존재하는 이름입니다.")
        else:
            users_table.insert({
                "name": name,
                "email": email,
                "password": password,
                "wallet": 10000,
                "inventory": {},
                "logged_in": False
            })
            st.success(f"{name}님 가입 완료!")

# ------------------------
# 로그인
# ------------------------
def login_page():
    st.header("🔑 로그인")
    name = st.text_input("이름", key="login_name")
    password = st.text_input("비밀번호", type="password", key="login_pw")

    if st.button("로그인"):
        user = get_user(name)
        if user and user["password"] == password:
            update_user(name, {"logged_in": True})
            st.session_state.user = name
            st.success(f"{name}님 로그인 성공!")
            st.rerun()
        else:
            st.error("이름 또는 비밀번호가 틀렸습니다.")

# ------------------------
# 로그아웃
# ------------------------
def logout_user():
    if st.session_state.user:
        update_user(st.session_state.user, {"logged_in": False})
        st.session_state.user = None
        st.success("로그아웃 되었습니다.")
        st.rerun()

# ------------------------
# 구매 기록
# ------------------------
def record_purchase(user, product, qty):
    purchases_table.insert({
        "buyer": user,
        "product": product,
        "qty": qty,
        "time": datetime.now().isoformat()
    })

# ------------------------
# 접속자 표시
# ------------------------
def show_online_users():
    users = users_table.search(Query().logged_in == True)
    if users:
        st.subheader("🟢 현재 접속자")
        for u in users:
            st.write(f"- {u['name']}")

# ------------------------
# 쇼핑몰
# ------------------------
def shop_page():
    user = get_user(st.session_state.user)
    st.header(f"🛍 {st.session_state.user}님의 쇼핑몰")

    # 현재 접속자 표시
    show_online_users()

    menu = st.sidebar.radio("📂 메뉴", ["상품", "지갑", "장바구니", "인벤토리", "구매 기록", "기프트카드", "로그아웃"])

    # ---------- 상품 ----------
    if menu == "상품":
        for p in products:
            stock = get_stock(p["name"])
            with st.expander(f"{p['name']} ➕ 상세 / 옵션"):
                if "image" in p and p["image"]:
                    st.image(p["image"], width=250)

                st.write(f"정가: {p['price']:,}원 / 판매가: {p['sale_price']:,}원")
                st.write(f"브랜드: {p['brand']}")
                st.write(f"현재 재고: {stock}개")

                if "link" in p and p["link"]:
                    st.write(f"[상품 링크]({p['link']})")

                qty = st.number_input(
                    f"{p['name']} 수량 입력",
                    min_value=0,
                    max_value=stock,
                    step=1,
                    key=f"qty-{p['name']}"
                )

                if qty > 0:
                    if p["options"]:
                        option = st.radio(f"{p['name']} 옵션 선택", p["options"], key=f"opt-{p['name']}")
                        unit_price = option_price(p, option)
                        total_price = unit_price * qty
                        st.write(f"선택: {option}, 수량: {qty}개 → 총 {total_price:,}원")

                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button(f"🛒 장바구니 담기", key=f"cart-{p['name']}"):
                                st.session_state.cart[f"{p['name']} ({option})"] = {"product": p, "count": qty, "option": option}
                                st.success("장바구니에 담김!")
                        with col2:
                            if st.button(f"💳 바로구매", key=f"buy-{p['name']}"):
                                if user["wallet"] >= total_price and qty <= stock:
                                    new_wallet = user["wallet"] - total_price
                                    inv = user["inventory"]
                                    inv[f"{p['name']} ({option})"] = inv.get(f"{p['name']} ({option})", 0) + qty
                                    update_user(st.session_state.user, {"wallet": new_wallet, "inventory": inv})
                                    update_stock(p["name"], qty)
                                    record_purchase(user["name"], p["name"], qty)
                                    st.success("바로구매 완료! 🎉")
                                else:
                                    st.error("잔액 부족 또는 재고 부족!")

                    else:
                        unit_price = p["sale_price"]
                        total_price = unit_price * qty
                        st.write(f"수량: {qty}개 → 총 {total_price:,}원")

                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button(f"🛒 장바구니 담기", key=f"cart-{p['name']}"):
                                st.session_state.cart[p["name"]] = {"product": p, "count": qty, "option": None}
                                st.success("장바구니에 담김!")
                        with col2:
                            if st.button(f"💳 바로구매", key=f"buy-{p['name']}"):
                                if user["wallet"] >= total_price and qty <= stock:
                                    new_wallet = user["wallet"] - total_price
                                    inv = user["inventory"]
                                    inv[p["name"]] = inv.get(p["name"], 0) + qty
                                    update_user(st.session_state.user, {"wallet": new_wallet, "inventory": inv})
                                    update_stock(p["name"], qty)
                                    record_purchase(user["name"], p["name"], qty)
                                    st.success("바로구매 완료! 🎉")
                                else:
                                    st.error("잔액 부족 또는 재고 부족!")

    # ---------- 지갑 ----------
    elif menu == "지갑":
        st.subheader("💳 지갑")
        st.write(f"현재 잔액: **{user['wallet']:,}원**")
        add = st.number_input("충전 금액", min_value=0, step=1000)
        if st.button("충전하기"):
            new_wallet = user["wallet"] + add
            update_user(st.session_state.user, {"wallet": new_wallet})
            st.success(f"{add:,}원 충전 완료! 현재 잔액 {new_wallet:,}원")

    # ---------- 장바구니 ----------
    elif menu == "장바구니":
        st.subheader("🛒 장바구니")
        if st.session_state.cart:
            total = 0
            for name, data in st.session_state.cart.items():
                unit = option_price(data["product"], data["option"])
                subtotal = unit * data["count"]
                total += subtotal
                st.write(f"- {name}: {data['count']}개 (단가 {unit:,}원 → {subtotal:,}원)")
            st.write(f"총합: **{total:,}원**")
            if st.button("💳 결제하기"):
                if user["wallet"] >= total:
                    new_wallet = user["wallet"] - total
                    inv = user["inventory"]
                    for name, data in st.session_state.cart.items():
                        if data["count"] <= get_stock(data["product"]["name"]):
                            inv[name] = inv.get(name, 0) + data["count"]
                            update_stock(data["product"]["name"], data["count"])
                            record_purchase(user["name"], data["product"]["name"], data["count"])
                        else:
                            st.error(f"{name} 재고 부족!")
                            return
                    update_user(st.session_state.user, {"wallet": new_wallet, "inventory": inv})
                    st.session_state.cart.clear()
                    st.success("결제 완료! 🎉 전챠쿄뜌✨")
                else:
                    st.error("잔액 부족!")
        else:
            st.info("장바구니가 비어 있습니다.")

    # ---------- 인벤토리 ----------
    elif menu == "인벤토리":
        st.subheader("🎒 인벤토리")
        if user["inventory"]:
            for item, count in user["inventory"].items():
                st.write(f"- {item}: {count}개")
        else:
            st.write("인벤토리 비어 있음")

    # ---------- 구매 기록 ----------
    elif menu == "구매 기록":
        st.subheader("🧾 구매 기록")
        records = purchases_table.all()
        if records:
            for r in records:
                st.write(f"{r['time']} - {r['buyer']} 님이 {r['product']} {r['qty']}개 구매")
        else:
            st.info("구매 기록이 없습니다.")

    # ---------- 기프트카드 ----------
    elif menu == "기프트카드":
        giftcard_issue_page()

    # ---------- 로그아웃 ----------
    elif menu == "로그아웃":
        st.subheader("🚪 로그아웃")
        if st.button("✅ 네, 로그아웃"):
            logout_user()

# ------------------------
# 메인 실행
# ------------------------
st.set_page_config(page_title="윤재마켓", page_icon="🛒")
reset_stocks()

if not st.session_state.user:
    logged_in_user = get_logged_in_user()
    if logged_in_user:
        st.session_state.user = logged_in_user["name"]

if st.session_state.user:
    shop_page()
else:
    menu_top = st.sidebar.radio("메뉴", ["회원가입", "로그인"])
    if menu_top == "회원가입":
        signup_page()
    elif menu_top == "로그인":
        login_page()
