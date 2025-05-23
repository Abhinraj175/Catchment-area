import streamlit as st
import geopandas as gpd
import pandas as pd
import zipfile
import tempfile
import os

st.set_page_config(layout="wide")
st.title("📐 Command Area-wise Feature Area Matrix (with Chaur Area Handling)")

# Function to unzip and read shapefiles
def unzip_shapefile(zip_bytes):
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_bytes, "r") as zip_ref:
            zip_ref.extractall(tmpdir)
        shp_files = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.endswith(".shp")]
        if not shp_files:
            st.error("No .shp file found in the uploaded ZIP.")
            return None
        gdf = gpd.read_file(shp_files[0])
        return gdf.to_crs(epsg=32643)  # Set CRS as per your project

# Upload interface
st.subheader("🗂 Upload Command Area Shapefile (.zip)")
command_area_zip = st.file_uploader("Command Area Shapefile", type=["zip"])

st.subheader("🗂 Upload Feature Shapefile (.zip)")
feature_zip = st.file_uploader("Feature Shapefile", type=["zip"])

st.subheader("🗂 Upload Chaur Area Shapefile (.zip)")
chaur_zip = st.file_uploader("Chaur Area Shapefile", type=["zip"])

if command_area_zip and feature_zip and chaur_zip:
    command_areas = unzip_shapefile(command_area_zip)
    features = unzip_shapefile(feature_zip)
    chaur_areas = unzip_shapefile(chaur_zip)

    if command_areas is not None and features is not None and chaur_areas is not None:
        st.success("✅ All shapefiles loaded successfully!")

        if 'TEXTSTRING' not in command_areas.columns:
            st.error("❌ 'TEXTSTRING' column not found in Command Area shapefile.")
            st.stop()

        # Calculate command area size
        command_areas["Command_Area_km2"] = command_areas.geometry.area / 1e6

        # Step 1: Chaur-overlapping features → Category = "Chaur"
        chaur_overlap = gpd.overlay(features, chaur_areas, how="intersection")
        chaur_overlap["Category"] = "Chaur"

        # Step 2: Remaining features (not overlapping Chaur)
        non_chaur = gpd.overlay(features, chaur_areas, how="difference")

        # Detect category column
        possible_cols = ['Layer', 'Type', 'Class', 'LandUse', 'Name']
        category_col = next((col for col in non_chaur.columns if col in possible_cols), None)

        if not category_col:
            non_chaur["Category"] = "Unknown"
            st.warning("⚠️ No category column found. Using 'Unknown'.")
        else:
            non_chaur["Category"] = non_chaur[category_col]

        # Merge both feature sets
        all_features = pd.concat([chaur_overlap, non_chaur], ignore_index=True)

        # Intersect with command areas
        intersections = gpd.overlay(all_features, command_areas, how="intersection")
        intersections["Feature_Area_km2"] = intersections.geometry.area / 1e6

        # Pivot table to wide format
        grouped = intersections.groupby(["TEXTSTRING", "Category"])["Feature_Area_km2"].sum().reset_index()
        pivot = grouped.pivot(index="TEXTSTRING", columns="Category", values="Feature_Area_km2").fillna(0)
        pivot.reset_index(inplace=True)

        # Merge with command area
        summary = pd.merge(command_areas[["TEXTSTRING", "Command_Area_km2"]], pivot, on="TEXTSTRING", how="left")

        # Reorder: TEXTSTRING, Command_Area_km2, then feature columns alphabetically
        fixed_cols = ["TEXTSTRING", "Command_Area_km2"]
        feature_cols = sorted([col for col in summary.columns if col not in fixed_cols])
        summary = summary[fixed_cols + feature_cols]

        # Display and download
        st.subheader("📊 Command Area-wise Feature Area Matrix (with Chaur Areas handled)")
        st.dataframe(summary)

        st.download_button(
            "📥 Download CSV",
            data=summary.to_csv(index=False).encode("utf-8"),
            file_name="command_area_feature_matrix_with_chaur.csv",
            mime="text/csv"
        )
