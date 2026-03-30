import streamlit as st
import pandas as pd
import zipfile
import io
import os
from core.data import get_df, save_df, DATA_DIR, SCHEMAS, _get_user_dir


def render():
    st.header("\U0001f4be Backup & Importar")

    col_backup, col_import = st.columns(2)

    # --- BACKUP (ZIP download) ---
    with col_backup:
        st.subheader("\U0001f4e5 Descargar backup")
        st.caption("Descarga todos tus datos como un archivo ZIP con CSVs.")

        if st.button("Generar backup ZIP", type="primary", use_container_width=True):
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for name in SCHEMAS:
                    df = get_df(name)
                    if not df.empty:
                        csv_data = df.to_csv(index=False)
                        zf.writestr(f"{name}.csv", csv_data)

            zip_buffer.seek(0)
            st.download_button(
                "\U0001f4e6 Descargar ZIP",
                zip_buffer.getvalue(),
                "segundo_cerebro_backup.zip",
                "application/zip",
                use_container_width=True,
            )

        st.divider()

        # Individual CSV exports
        st.subheader("Exportar individual")
        for name in SCHEMAS:
            df = get_df(name)
            if not df.empty:
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    f"\U0001f4c4 {name}.csv ({len(df)} registros)",
                    csv,
                    f"{name}.csv",
                    "text/csv",
                    key=f"export_{name}",
                    use_container_width=True,
                )

    # --- IMPORT (CSV upload) ---
    with col_import:
        st.subheader("\U0001f4e4 Importar datos")
        st.caption("Sube un archivo CSV para importar datos. El CSV debe tener las columnas correctas.")

        import_type = st.selectbox(
            "Tipo de datos a importar",
            list(SCHEMAS.keys()),
            format_func=lambda x: x.capitalize(),
        )

        uploaded = st.file_uploader(
            f"Subir CSV de {import_type}",
            type=["csv"],
            key=f"import_{import_type}",
        )

        if uploaded:
            try:
                new_data = pd.read_csv(uploaded)
                st.markdown(f"**Vista previa** ({len(new_data)} registros):")
                st.dataframe(new_data.head(10), use_container_width=True)

                schema_cols = list(SCHEMAS[import_type].keys())
                missing = [c for c in schema_cols if c not in new_data.columns]
                if missing:
                    st.warning(f"Columnas faltantes (se llenaran con valores por defecto): {', '.join(missing)}")
                    for col in missing:
                        dtype = SCHEMAS[import_type][col]
                        if dtype == bool:
                            new_data[col] = False
                        elif dtype == str:
                            new_data[col] = ""
                        elif dtype == float:
                            new_data[col] = 0.0
                        elif dtype == int:
                            new_data[col] = 0

                import_mode = st.radio(
                    "Modo de importacion",
                    ["Agregar a datos existentes", "Reemplazar datos existentes"],
                    help="Agregar: combina con los datos actuales. Reemplazar: borra los datos actuales.",
                )

                if st.button(f"Importar {len(new_data)} registros", type="primary"):
                    existing = get_df(import_type)
                    if import_mode == "Agregar a datos existentes" and not existing.empty:
                        combined = pd.concat([existing, new_data], ignore_index=True)
                    else:
                        combined = new_data
                    save_df(import_type, combined)
                    st.success(f"Importados {len(new_data)} registros de {import_type}!")
                    st.rerun()
            except Exception as e:
                st.error(f"Error leyendo CSV: {str(e)}")

    st.divider()

    # --- Data summary ---
    st.subheader("\U0001f4ca Resumen de datos")
    summary_data = []
    for name in SCHEMAS:
        df = get_df(name)
        summary_data.append({"Modulo": name.capitalize(), "Registros": len(df)})
    st.dataframe(pd.DataFrame(summary_data), use_container_width=True, hide_index=True)
