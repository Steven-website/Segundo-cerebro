import hashlib
import json
import os
import streamlit as st

USERS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "users.json")

AVATARS = ["👤", "👨", "👩", "🧑", "👨‍💻", "👩‍💻", "🧑‍💻", "🦸", "🧙", "🧑‍🎓", "👨‍🔬", "🧑‍🚀", "🧑‍🎨", "👨‍🍳", "🤖"]


def _load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_users(users):
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)
    _push_users_to_github()


def _hash_password(password, username):
    return hashlib.sha256(f"{password}{username}".encode()).hexdigest()


def _push_users_to_github():
    try:
        token = st.secrets.get("github_token", "")
        repo_name = st.secrets.get("github_repo", "")
    except Exception:
        return
    if not token or not repo_name:
        return
    try:
        from github import Github
        g = Github(token)
        repo = g.get_repo(repo_name)
        with open(USERS_FILE, "rb") as f:
            content = f.read()
        try:
            existing = repo.get_contents("data/users.json")
            repo.update_file("data/users.json", "Update users", content, existing.sha)
        except Exception:
            repo.create_file("data/users.json", "Create users", content)
    except Exception:
        pass


def render():
    st.header("Perfil")

    username = st.session_state.get("current_user", "")
    users = _load_users()
    user_data = users.get(username, {})

    st.subheader(f"Usuario: {username}")

    # --- Avatar ---
    st.markdown("### Avatar")
    current_avatar = user_data.get("avatar", "👤")
    cols = st.columns(len(AVATARS))
    for i, av in enumerate(AVATARS):
        with cols[i]:
            selected = current_avatar == av
            label = f"**{av}**" if selected else av
            if st.button(av, key=f"av_{i}", use_container_width=True, type="primary" if selected else "secondary"):
                users[username]["avatar"] = av
                _save_users(users)
                st.session_state["user_data"] = users[username]
                st.rerun()

    st.divider()

    # --- Edit name ---
    st.markdown("### Nombre")
    with st.form("profile_name_form"):
        name = st.text_input("Nombre completo", value=user_data.get("name", ""))
        if st.form_submit_button("Actualizar nombre", type="primary"):
            if name.strip():
                users[username]["name"] = name.strip()
                _save_users(users)
                st.session_state["user_data"] = users[username]
                st.success("Nombre actualizado.")
                st.rerun()

    st.divider()

    # --- Change password ---
    st.markdown("### Cambiar contrasena")
    with st.form("change_pass_form"):
        current_pass = st.text_input("Contrasena actual", type="password")
        new_pass = st.text_input("Nueva contrasena", type="password", placeholder="Min 6 caracteres")
        new_pass2 = st.text_input("Confirmar nueva contrasena", type="password")

        if st.form_submit_button("Cambiar contrasena", type="primary"):
            if not current_pass:
                st.error("Ingresa tu contrasena actual.")
            elif _hash_password(current_pass, username) != user_data.get("hash", ""):
                st.error("Contrasena actual incorrecta.")
            elif len(new_pass) < 6:
                st.error("La nueva contrasena debe tener al menos 6 caracteres.")
            elif new_pass != new_pass2:
                st.error("Las contrasenas no coinciden.")
            else:
                users[username]["hash"] = _hash_password(new_pass, username)
                _save_users(users)
                st.success("Contrasena cambiada exitosamente.")

    st.divider()

    # --- Account stats ---
    st.markdown("### Estadisticas de la cuenta")
    from core.data import get_df
    tareas = get_df("tareas")
    proyectos = get_df("proyectos")
    habitos = get_df("habitos")
    txs = get_df("txs")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Proyectos", len(proyectos))
    c2.metric("Tareas", len(tareas))
    c3.metric("Habitos", len(habitos))
    c4.metric("Transacciones", len(txs))
