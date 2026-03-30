import os
import io
import uuid
import time
import pandas as pd
import streamlit as st

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

SCHEMAS = {
    "notas": {"id": str, "titulo": str, "area": str, "tags": str, "body": str, "pinned": bool, "archived": bool, "ts": float},
    "tareas": {"id": str, "titulo": str, "area": str, "prioridad": str, "fecha": str, "proyecto": str, "notas": str, "subtareas": str, "recurrente": str, "done": bool, "pinned": bool, "archived": bool, "ts": float},
    "proyectos": {"id": str, "nombre": str, "area": str, "emoji": str, "desc": str, "ts": float},
    "txs": {"id": str, "type": str, "desc": str, "amt": float, "cat": str, "fecha": str, "ts": float},
    "savings": {"id": str, "name": str, "goal": float, "current": float, "date": str, "ts": float},
    "debts": {"id": str, "name": str, "total": float, "paid": float, "rate": float, "due": str, "ts": float},
    "habitos": {"id": str, "name": str, "emoji": str, "cat": str, "freq": str, "checks": str, "streak": int, "ts": float},
    "inventario": {"id": str, "name": str, "cat": str, "emoji": str, "val": float, "qty": int, "loc": str, "date": str, "notes": str, "status": str, "ts": float},
    "budget": {"cat": str, "amt": float},
}


def _empty_df(name):
    schema = SCHEMAS[name]
    return pd.DataFrame({col: pd.Series(dtype=dtype) for col, dtype in schema.items()})


def _parquet_path(name):
    return os.path.join(DATA_DIR, f"{name}.parquet")


def load_df(name):
    key = f"df_{name}"
    if key in st.session_state:
        return st.session_state[key]
    path = _parquet_path(name)
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
    key = f"df_{name}"
    st.session_state[key] = df
    os.makedirs(DATA_DIR, exist_ok=True)
    df.to_parquet(_parquet_path(name), index=False)
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
        path_in_repo = f"data/{name}.parquet"
        local_path = _parquet_path(name)
        with open(local_path, "rb") as f:
            content = f.read()
        try:
            existing = repo.get_contents(path_in_repo)
            repo.update_file(path_in_repo, f"Update {name} data", content, existing.sha)
        except Exception:
            repo.create_file(path_in_repo, f"Create {name} data", content)
    except Exception:
        pass


def get_df(name):
    return load_df(name)


def uid():
    return uuid.uuid4().hex[:12]


def now_ts():
    return time.time()
