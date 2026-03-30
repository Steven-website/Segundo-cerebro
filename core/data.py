import os
import uuid
import time
import base64
import pandas as pd
import streamlit as st

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

SCHEMAS = {
    "notas": {"id": str, "titulo": str, "area": str, "tags": str, "body": str, "proyecto": str, "pinned": bool, "archived": bool, "ts": float},
    "tareas": {"id": str, "titulo": str, "area": str, "prioridad": str, "fecha_inicio": str, "fecha": str, "proyecto": str, "notas": str, "subtareas": str, "recurrente": str, "depende_de": str, "etiqueta": str, "done": bool, "pinned": bool, "archived": bool, "ts": float},
    "proyectos": {"id": str, "nombre": str, "area": str, "emoji": str, "desc": str, "estado": str, "fecha_inicio": str, "fecha_fin": str, "plantilla": bool, "compartido": str, "ts": float},
    "txs": {"id": str, "type": str, "desc": str, "amt": float, "cat": str, "fecha": str, "ts": float},
    "savings": {"id": str, "name": str, "goal": float, "current": float, "date": str, "ts": float},
    "debts": {"id": str, "name": str, "total": float, "paid": float, "rate": float, "due": str, "ts": float},
    "habitos": {"id": str, "name": str, "emoji": str, "cat": str, "freq": str, "checks": str, "streak": int, "ts": float},
    "inventario": {"id": str, "name": str, "cat": str, "emoji": str, "val": float, "qty": int, "loc": str, "date": str, "garantia": str, "notes": str, "status": str, "ts": float},
    "audios": {"id": str, "titulo": str, "fecha": str, "comentario": str, "formato": str, "tamano": int, "transcript": str, "resumen": str, "puntos_clave": str, "pendientes": str, "ts": float},
    "pomo_sessions": {"id": str, "tarea": str, "minutos": int, "fecha": str, "ts": float},
    "task_comments": {"id": str, "tarea_id": str, "texto": str, "autor": str, "ts": float},
    "debt_payments": {"id": str, "debt_id": str, "monto": float, "fecha": str, "nota": str, "ts": float},
    "metas": {"id": str, "titulo": str, "tipo": str, "periodo": str, "objetivo": str, "progreso": float, "completada": bool, "proyecto_id": str, "ts": float},
    "tx_recurrentes": {"id": str, "type": str, "desc": str, "amt": float, "cat": str, "frecuencia": str, "dia": int, "activa": bool, "ts": float},
    "budget": {"cat": str, "amt": float},
    "papelera": {"id": str, "tipo": str, "nombre": str, "data": str, "deleted_ts": float},
}


def _get_user_dir():
    user = st.session_state.get("current_user", "default")
    user_dir = os.path.join(DATA_DIR, user)
    os.makedirs(user_dir, exist_ok=True)
    return user_dir


def _empty_df(name):
    schema = SCHEMAS[name]
    return pd.DataFrame({col: pd.Series(dtype=dtype) for col, dtype in schema.items()})


def _parquet_path(name):
    return os.path.join(_get_user_dir(), f"{name}.parquet")


def _pull_from_github(name):
    """Download a parquet file from GitHub if it doesn't exist locally."""
    try:
        token = st.secrets.get("github_token", "")
        repo_name = st.secrets.get("github_repo", "")
    except Exception:
        return False
    if not token or not repo_name:
        return False
    try:
        from github import Github
        g = Github(token)
        repo = g.get_repo(repo_name)
        user = st.session_state.get("current_user", "default")
        path_in_repo = f"data/{user}/{name}.parquet"
        contents = repo.get_contents(path_in_repo)
        data = base64.b64decode(contents.content)
        local_path = _parquet_path(name)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(data)
        return True
    except Exception:
        return False


def load_df(name):
    user = st.session_state.get("current_user", "default")
    key = f"df_{user}_{name}"
    if key in st.session_state:
        return st.session_state[key]
    path = _parquet_path(name)
    # If local file doesn't exist, try to pull from GitHub
    if not os.path.exists(path):
        _pull_from_github(name)
    if os.path.exists(path):
        try:
            df = pd.read_parquet(path)
            # Add missing columns for schema evolution
            schema = SCHEMAS.get(name, {})
            for col, dtype in schema.items():
                if col not in df.columns:
                    if dtype == bool:
                        df[col] = False
                    elif dtype == str:
                        df[col] = ""
                    elif dtype == float:
                        df[col] = 0.0
                    elif dtype == int:
                        df[col] = 0
            st.session_state[key] = df
            return df
        except Exception:
            pass
    df = _empty_df(name)
    st.session_state[key] = df
    return df


def save_df(name, df):
    user = st.session_state.get("current_user", "default")
    key = f"df_{user}_{name}"
    st.session_state[key] = df
    os.makedirs(_get_user_dir(), exist_ok=True)
    df.to_parquet(_parquet_path(name), index=False)
    # Push to GitHub immediately on save
    _push_to_github(name)


def _push_to_github(name):
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
        user = st.session_state.get("current_user", "default")
        path_in_repo = f"data/{user}/{name}.parquet"
        local_path = _parquet_path(name)
        with open(local_path, "rb") as f:
            content = f.read()
        try:
            existing = repo.get_contents(path_in_repo)
            repo.update_file(path_in_repo, f"Update {user}/{name}", content, existing.sha)
        except Exception:
            repo.create_file(path_in_repo, f"Create {user}/{name}", content)
    except Exception:
        pass


def get_df(name):
    return load_df(name)


def uid():
    return uuid.uuid4().hex[:12]


def now_ts():
    return time.time()
