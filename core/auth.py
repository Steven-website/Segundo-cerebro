import hashlib
import json
import os
import streamlit as st

USERS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "users.json")


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


def render_auth():
    st.markdown("---")
    col_spacer1, col_auth, col_spacer2 = st.columns([1, 2, 1])

    with col_auth:
        st.markdown("## \U0001f9e0 Segundo Cerebro")
        st.caption("Sistema PKM Personal")
        st.markdown("---")

        tab_login, tab_register = st.tabs(["Iniciar sesion", "Crear cuenta"])

        with tab_login:
            with st.form("login_form"):
                username = st.text_input("Usuario", placeholder="tu_usuario")
                password = st.text_input("Contrasena", type="password", placeholder="******")
                submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)

                if submitted:
                    if not username.strip() or not password.strip():
                        st.error("Completa todos los campos.")
                    else:
                        users = _load_users()
                        username = username.strip().lower()
                        if username not in users:
                            st.error("Usuario no encontrado.")
                        else:
                            hashed = _hash_password(password, username)
                            if hashed != users[username]["hash"]:
                                st.error("Contrasena incorrecta.")
                            else:
                                st.session_state["logged_in"] = True
                                st.session_state["current_user"] = username
                                st.session_state["user_data"] = users[username]
                                st.rerun()


        with tab_register:
            with st.form("register_form"):
                name = st.text_input("Nombre completo", placeholder="Juan Perez")
                new_user = st.text_input("Usuario", placeholder="juanperez (min 3 caracteres)")
                new_pass = st.text_input("Contrasena", type="password", placeholder="Min 6 caracteres")
                new_pass2 = st.text_input("Confirmar contrasena", type="password")
                submitted = st.form_submit_button("Crear cuenta", type="primary", use_container_width=True)

                if submitted:
                    new_user = new_user.strip().lower()
                    if not name.strip():
                        st.error("Ingresa tu nombre.")
                    elif len(new_user) < 3:
                        st.error("El usuario debe tener al menos 3 caracteres.")
                    elif len(new_pass) < 6:
                        st.error("La contrasena debe tener al menos 6 caracteres.")
                    elif new_pass != new_pass2:
                        st.error("Las contrasenas no coinciden.")
                    else:
                        users = _load_users()
                        if new_user in users:
                            st.error("Ese usuario ya existe.")
                        else:
                            users[new_user] = {
                                "name": name.strip(),
                                "hash": _hash_password(new_pass, new_user),
                            }
                            _save_users(users)
                            st.success(f"Cuenta creada! Ahora inicia sesion como '{new_user}'.")
