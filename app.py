import streamlit as st
import sqlite3
import os
from datetime import datetime
import base64

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="ThreeDimensions Hub", layout="wide")

MODEL_DIR = "models"
DB_FILE = "database.db"

os.makedirs(MODEL_DIR, exist_ok=True)

# =========================
# DATABASE SETUP
# =========================
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    prompt TEXT,
    description TEXT,
    filename TEXT,
    created_at TEXT
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER,
    message TEXT,
    created_at TEXT
)
""")

conn.commit()

# =========================
# SIDEBAR NAVIGATION
# =========================
st.sidebar.title("ThreeDimensions Hub")
page = st.sidebar.radio("Navigate", ["Upload Model", "Explore Models"])

# =========================
# UPLOAD PAGE
# =========================
if page == "Upload Model":
    st.title("Upload Your 3D Model (.OBJ)")

    title = st.text_input("Model Title")
    prompt = st.text_area("Prompt Used")
    description = st.text_area("Description")

    uploaded_file = st.file_uploader("Upload .OBJ file", type=["obj"])

    if st.button("Submit Model"):
        if uploaded_file and title:
            filepath = os.path.join(MODEL_DIR, uploaded_file.name)

            with open(filepath, "wb") as f:
                f.write(uploaded_file.read())

            c.execute("""
                INSERT INTO models (title, prompt, description, filename, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (title, prompt, description, uploaded_file.name, datetime.now().isoformat()))

            conn.commit()
            st.success("Model uploaded successfully!")
        else:
            st.error("Title and OBJ file required!")

# =========================
# EXPLORE PAGE
# =========================
if page == "Explore Models":
    st.title("Explore Community Models")

    models = c.execute("SELECT * FROM models ORDER BY id DESC").fetchall()

    for model in models:
        model_id, title, prompt, description, filename, created_at = model

        st.subheader(title)
        st.write("Prompt:", prompt)
        st.write("Description:", description)

        filepath = os.path.join(MODEL_DIR, filename)

        if os.path.exists(filepath):
            # Encode file to base64
            with open(filepath, "rb") as f:
                encoded = base64.b64encode(f.read()).decode()

            # Render OBJ using Three.js
            st.components.v1.html(f"""
            <!DOCTYPE html>
            <html>
            <head>
            <script src="https://cdn.jsdelivr.net/npm/three@0.152.2/build/three.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/three@0.152.2/examples/js/loaders/OBJLoader.js"></script>
            </head>
            <body style="margin:0;">
            <div id="viewer" style="width:100%; height:400px;"></div>
            <script>
                const scene = new THREE.Scene();
                const camera = new THREE.PerspectiveCamera(75, window.innerWidth/window.innerHeight, 0.1, 1000);
                const renderer = new THREE.WebGLRenderer();
                renderer.setSize(window.innerWidth, 400);
                document.getElementById('viewer').appendChild(renderer.domElement);

                const light = new THREE.DirectionalLight(0xffffff, 1);
                light.position.set(0, 1, 1).normalize();
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
            </body>
            </html>
            """, height=420)

        # Feedback Section
        st.markdown("### Feedback")
        feedbacks = c.execute("SELECT message FROM feedback WHERE model_id=?", (model_id,)).fetchall()

        for fb in feedbacks:
            st.write("- ", fb[0])

        new_feedback = st.text_input("Add feedback", key=f"fb_{model_id}")

        if st.button("Submit Feedback", key=f"btn_{model_id}"):
            if new_feedback:
                c.execute("""
                    INSERT INTO feedback (model_id, message, created_at)
                    VALUES (?, ?, ?)
                """, (model_id, new_feedback, datetime.now().isoformat()))
                conn.commit()
                st.success("Feedback added!")
