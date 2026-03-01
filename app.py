import streamlit as st
import sqlite3
import os
from datetime import datetime
import hashlib
import base64

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="ThreeDimensions Hub", layout="wide")

BASE_DIR = "/tmp"
MODEL_DIR = os.path.join(BASE_DIR, "models")
DB_FILE = os.path.join(BASE_DIR, "database.db")

os.makedirs(MODEL_DIR, exist_ok=True)

# =========================
# DATABASE
# =========================
@st.cache_resource
def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

conn = get_connection()
c = conn.cursor()

# Users
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    password TEXT
)
""")

# Models
c.execute("""
CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    prompt TEXT,
    description TEXT,
    filename TEXT,
    user_id INTEGER,
    created_at TEXT
)
""")

# Likes
c.execute("""
CREATE TABLE IF NOT EXISTS likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER,
    user_id INTEGER
)
""")

# Ratings
c.execute("""
CREATE TABLE IF NOT EXISTS ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER,
    user_id INTEGER,
    rating INTEGER
)
""")

conn.commit()

# =========================
# SESSION
# =========================
if "user" not in st.session_state:
    st.session_state.user = None

# =========================
# AUTH SYSTEM
# =========================
st.sidebar.title("Account")

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

if not st.session_state.user:
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Password", type="password")

    col1, col2 = st.sidebar.columns(2)

    # SIGNUP
    if col1.button("Signup"):
        try:
            c.execute("INSERT INTO users (email, password) VALUES (?, ?)",
                      (email, hash_password(password)))
            conn.commit()
            st.sidebar.success("Account created! Login now.")
        except:
            st.sidebar.error("User already exists")

    # LOGIN
    if col2.button("Login"):
        user = c.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, hash_password(password))
        ).fetchone()

        if user:
            st.session_state.user = user
            st.rerun()
        else:
            st.sidebar.error("Invalid credentials")

else:
    st.sidebar.success(f"Logged in as {st.session_state.user[1]}")
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.rerun()

# =========================
# NAVIGATION
# =========================
page = st.sidebar.radio("Navigate", ["Explore", "Upload"])

# =========================
# UPLOAD
# =========================
if page == "Upload":

    if not st.session_state.user:
        st.warning("Login required")
        st.stop()

    st.title("Upload 3D Model (.OBJ)")

    title = st.text_input("Title")
    prompt = st.text_area("Prompt Used")
    description = st.text_area("Description")
    uploaded_file = st.file_uploader("Upload OBJ", type=["obj"])

    if st.button("Upload"):
        if uploaded_file and title:

            filepath = os.path.join(MODEL_DIR, uploaded_file.name)
            with open(filepath, "wb") as f:
                f.write(uploaded_file.read())

            c.execute("""
                INSERT INTO models (title, prompt, description, filename, user_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                title,
                prompt,
                description,
                uploaded_file.name,
                st.session_state.user[0],
                datetime.now().isoformat()
            ))

            conn.commit()
            st.success("Model Uploaded!")
            st.rerun()

# =========================
# EXPLORE
# =========================
if page == "Explore":

    st.title("Community Models")

    models = c.execute("""
        SELECT * FROM models ORDER BY id DESC
    """).fetchall()

    for model in models:

        model_id, title, prompt, desc, filename, user_id, created = model

        st.subheader(title)
        st.write(desc)
        st.caption(f"Uploaded on {created}")

        # ================= 3D PREVIEW =================
        filepath = os.path.join(MODEL_DIR, filename)

        if os.path.exists(filepath):
            with open(filepath, "rb") as f:
                encoded = base64.b64encode(f.read()).decode()

            st.components.v1.html(f"""
            <script src="https://cdn.jsdelivr.net/npm/three@0.152.2/build/three.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/three@0.152.2/examples/js/loaders/OBJLoader.js"></script>
            <div id="viewer{model_id}" style="height:400px;"></div>
            <script>
                const scene = new THREE.Scene();
                const camera = new THREE.PerspectiveCamera(75, window.innerWidth/window.innerHeight, 0.1, 1000);
                const renderer = new THREE.WebGLRenderer();
                renderer.setSize(window.innerWidth, 400);
                document.getElementById("viewer{model_id}").appendChild(renderer.domElement);

                const light = new THREE.DirectionalLight(0xffffff, 1);
                scene.add(light);

                const loader = new THREE.OBJLoader();
                const objData = atob("{encoded}");
                const blob = new Blob([objData], {{type: 'text/plain'}});
                const url = URL.createObjectURL(blob);

                loader.load(url, function (object) {{
                    scene.add(object);
                }});

                camera.position.z = 5;
                function animate() {{
                    requestAnimationFrame(animate);
                    renderer.render(scene, camera);
                }}
                animate();
            </script>
            """, height=420)

        # ================= LIKES =================
        like_count = c.execute(
            "SELECT COUNT(*) FROM likes WHERE model_id=?",
            (model_id,)
        ).fetchone()[0]

        col1, col2 = st.columns(2)

        if st.session_state.user:
            if col1.button(f"❤️ Like ({like_count})", key=f"like{model_id}"):
                c.execute(
                    "INSERT INTO likes (model_id, user_id) VALUES (?, ?)",
                    (model_id, st.session_state.user[0])
                )
                conn.commit()
                st.rerun()
        else:
            col1.write(f"❤️ {like_count}")

        # ================= RATINGS =================
        avg_rating = c.execute(
            "SELECT AVG(rating) FROM ratings WHERE model_id=?",
            (model_id,)
        ).fetchone()[0]

        if avg_rating:
            col2.write(f"⭐ {round(avg_rating,1)}/5")
        else:
            col2.write("⭐ No ratings")

        if st.session_state.user:
            rating = st.slider(
                "Rate this model",
                1, 5,
                key=f"rate{model_id}"
            )
            if st.button("Submit Rating", key=f"ratebtn{model_id}"):
                c.execute(
                    "INSERT INTO ratings (model_id, user_id, rating) VALUES (?, ?, ?)",
                    (model_id, st.session_state.user[0], rating)
                )
                conn.commit()
                st.rerun()

        st.divider()
