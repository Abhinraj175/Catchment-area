import streamlit as st
import geopandas as gpd
import pandas as pd
import zipfile
import tempfile
import os
from io import BytesIO

st.set_page_config(layout="wide")
st.title("📐 Command Area-wise Feature & Line Matrix (with Chaur Exclusion)")

def unzip_shapefile(zip_bytes):
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_bytes, "r") as zip_ref:
            zip_ref.extractall(tmpdir)
        shp_files = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.endswith(".shp")]
        if not shp_files:
            st.error("No .shp file found in the uploaded ZIP.")
            return None
        gdf = gpd.read_file(shp_files[0])
        return gdf.to_crs(epsg=32643)

# Upload widgets
st.subheader("🗂 Upload Command Area Shapefile (.zip)")
command_area_zip = st.file_uploader("Command Area Shapefile", type=["zip"])

st.subheader("🗂 Upload TEXT Point Shapefile (.zip with TEXTSTRING column)")
text_point_zip = st.file_uploader("TEXT Point Layer", type=["zip"])

st.subheader("🗂 Upload Feature Shapefile (.zip)")
feature_zip = st.file_uploader("Feature Shapefile", type=["zip"])

st.subheader("🗂 Upload Chaur Area Shapefile (.zip)")
chaur_zip = st.file_uploader("Chaur Area Shapefile", type=["zip"])

st.subheader("🗂 Upload Line Feature Shapefile (.zip)")
line_zip = st.file_uploader("Line Feature Shapefile", type=["zip"])

area_df, line_df = None, None

# Area matrix computation
if command_area_zip and text_point_zip and feature_zip and chaur_zip:
    raw_command_areas = unzip_shapefile(command_area_zip)
    text_points = unzip_shapefile(text_point_zip)
    features = unzip_shapefile(feature_zip)
    chaur_areas = unzip_shapefile(chaur_zip)

    if raw_command_areas is not None and text_points is not None:
        if 'TEXTSTRING' not in text_points.columns:
            st.error("❌ 'TEXTSTRING' column missing in TEXT point shapefile.")
            st.stop()

        # Join attributes from nearest point
        raw_command_areas["geometry_centroid"] = raw_command_areas.geometry.centroid
        joined = gpd.sjoin_nearest(
            raw_command_areas.set_geometry("geometry_centroid"),
            text_points[["geometry", "TEXTSTRING"]],
            how="left",
            distance_col="distance"
        )
        command_areas = raw_command_areas.drop(columns=["geometry_centroid"])
        command_areas["TEXTSTRING"] = joined["TEXTSTRING"].values
        command_areas = command_areas.dropna(subset=["TEXTSTRING"])

        if command_areas.empty:
            st.error("❌ No command areas matched with TEXT points.")
            st.stop()

        command_areas["Command_Area_m2"] = command_areas.geometry.area

        chaur_cmd = gpd.overlay(chaur_areas, command_areas, how="intersection")
        chaur_cmd["Area_m2"] = chaur_cmd.geometry.area
        chaur_summary = chaur_cmd.groupby("TEXTSTRING")["Area_m2"].sum().reset_index()
        chaur_summary.rename(columns={"Area_m2": "Chaur_Area_m2"}, inplace=True)

        features_no_chaur = gpd.overlay(features, chaur_areas, how="difference")

        possible_cols = ['Layer', 'Type', 'Class', 'LandUse', 'Name']
        category_col = next((col for col in features_no_chaur.columns if col in possible_cols), None)
        if not category_col:
            features_no_chaur["Category"] = "Unknown"
            st.warning("⚠️ Feature category column not found. Using 'Unknown'.")
        else:
            features_no_chaur["Category"] = features_no_chaur[category_col]

        intersections = gpd.overlay(features_no_chaur, command_areas, how="intersection")
        intersections["Feature_Area_m2"] = intersections.geometry.area

        grouped = intersections.groupby(["TEXTSTRING", "Category"])["Feature_Area_m2"].sum().reset_index()
        pivot = grouped.pivot(index="TEXTSTRING", columns="Category", values="Feature_Area_m2").fillna(0)
        pivot.reset_index(inplace=True)

        base = command_areas[["TEXTSTRING", "Command_Area_m2"]].drop_duplicates()
        merged = pd.merge(base, pivot, on="TEXTSTRING", how="left")
        merged = pd.merge(merged, chaur_summary, on="TEXTSTRING", how="left").fillna(0)

        fixed_cols = ["TEXTSTRING", "Command_Area_m2", "Chaur_Area_m2"]
        feature_cols = sorted([col for col in merged.columns if col not in fixed_cols])
        area_df = merged[fixed_cols + feature_cols]

        st.subheader("📊 Final Area Matrix (All Commands Included)")
        st.dataframe(area_df)

        st.download_button(
            label="📥 Download Area CSV",
            data=area_df.to_csv(index=False).encode("utf-8"),
            file_name="command_area_with_chaur_exclusion.csv",
            mime="text/csv"
        )

# Line matrix computation
if command_area_zip and text_point_zip and line_zip:
    raw_command_areas = unzip_shapefile(command_area_zip)
    text_points = unzip_shapefile(text_point_zip)
    lines = unzip_shapefile(line_zip)

    if raw_command_areas is not None and text_points is not None:
        if 'TEXTSTRING' not in text_points.columns:
            st.error("❌ 'TEXTSTRING' column missing in TEXT point shapefile.")
            st.stop()

        raw_command_areas["geometry_centroid"] = raw_command_areas.geometry.centroid
        joined = gpd.sjoin_nearest(
            raw_command_areas.set_geometry("geometry_centroid"),
            text_points[["geometry", "TEXTSTRING"]],
            how="left",
            distance_col="distance"
        )
        command_areas = raw_command_areas.drop(columns=["geometry_centroid"])
        command_areas["TEXTSTRING"] = joined["TEXTSTRING"].values
        command_areas = command_areas.dropna(subset=["TEXTSTRING"])

        intersected_lines = gpd.overlay(lines, command_areas, how="intersection")
        intersected_lines["Length_m"] = intersected_lines.geometry.length

        possible_cols = ['Layer', 'Name', 'RoadType', 'Class']
        line_col = next((col for col in intersected_lines.columns if col in possible_cols), None)

        if not line_col:
            intersected_lines["Category"] = "Unknown"
            st.warning("⚠️ Could not detect line feature type. Using 'Unknown'.")
        else:
            intersected_lines["Category"] = intersected_lines[line_col]

        line_summary = intersected_lines.groupby(["TEXTSTRING", "Category"])["Length_m"].sum().reset_index()
        line_pivot = line_summary.pivot(index="TEXTSTRING", columns="Category", values="Length_m").fillna(0)
        line_pivot.reset_index(inplace=True)

        base = command_areas[["TEXTSTRING"]].drop_duplicates()
        line_df = pd.merge(base, line_pivot, on="TEXTSTRING", how="left").fillna(0)

        st.subheader("🛣️ Line Feature Length Matrix (per Command Area)")
        st.dataframe(line_df)

        st.download_button(
            "📥 Download Line Feature CSV",
            data=line_df.to_csv(index=False).encode("utf-8"),
            file_name="command_area_line_lengths.csv",
            mime="text/csv"
        )

# Combined Excel Download
if area_df is not None and line_df is not None:
    output_excel = BytesIO()
    with pd.ExcelWriter(output_excel, engine='xlsxwriter') as writer:
        area_df.to_excel(writer, index=False, sheet_name="Area_Features")
        line_df.to_excel(writer, index=False, sheet_name="Line_Features")
    output_excel.seek(0)

    st.download_button(
        label="📥 Download Combined Excel File",
        data=output_excel,
        file_name="command_area_analysis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
