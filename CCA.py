import streamlit as st
import geopandas as gpd
import pandas as pd
import zipfile
import tempfile
import os

st.set_page_config(layout="wide")
st.title("📐 Command Area-wise Feature Area Matrix (with Chaur Exclusion)")

# Function to unzip and read shapefile
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

st.subheader("🗂 Upload Feature Shapefile (.zip)")
feature_zip = st.file_uploader("Feature Shapefile", type=["zip"])

st.subheader("🗂 Upload Chaur Area Shapefile (.zip)")
chaur_zip = st.file_uploader("Chaur Area Shapefile", type=["zip"])

if command_area_zip and feature_zip and chaur_zip:
    command_areas = unzip_shapefile(command_area_zip)
    features = unzip_shapefile(feature_zip)
    chaur_areas = unzip_shapefile(chaur_zip)

    if command_areas is not None and features is not None and chaur_areas is not None:
        st.success("✅ Shapefiles loaded successfully!")

        if 'TEXTSTRING' not in command_areas.columns:
            st.error("❌ 'TEXTSTRING' column not found in Command Area shapefile.")
            st.stop()

        # Compute command area
        command_areas["Command_Area_km2"] = command_areas.geometry.area / 1e6

        # Step 1: Calculate Chaur area per command
        chaur_cmd = gpd.overlay(chaur_areas, command_areas, how="intersection")
        chaur_cmd["Area_km2"] = chaur_cmd.geometry.area / 1e6
        chaur_summary = chaur_cmd.groupby("TEXTSTRING")["Area_km2"].sum().reset_index()
        chaur_summary.rename(columns={"Area_km2": "Chaur_Area_km2"}, inplace=True)

        # Step 2: Remove chaur area from features
        features_no_chaur = gpd.overlay(features, chaur_areas, how="difference")

        # Detect feature category column
        possible_cols = ['Layer', 'Type', 'Class', 'LandUse', 'Name']
        category_col = next((col for col in features_no_chaur.columns if col in possible_cols), None)

        if not category_col:
            features_no_chaur["Category"] = "Unknown"
            st.warning("⚠️ Could not find category column. Using 'Unknown'.")
        else:
            features_no_chaur["Category"] = features_no_chaur[category_col]

        # Step 3: Intersect non-chaur features with command area
        intersections = gpd.overlay(features_no_chaur, command_areas, how="intersection")
        intersections["Feature_Area_km2"] = intersections.geometry.area / 1e6

        # Step 4: Group and pivot feature areas
        grouped = intersections.groupby(["TEXTSTRING", "Category"])["Feature_Area_km2"].sum().reset_index()
        pivot = grouped.pivot(index="TEXTSTRING", columns="Category", values="Feature_Area_km2").fillna(0)
        pivot.reset_index(inplace=True)

        # Step 5: Create base with all command areas
        base = command_areas[["TEXTSTRING", "Command_Area_km2"]].drop_duplicates()

        # Merge pivoted feature areas with base
        merged = pd.merge(base, pivot, on="TEXTSTRING", how="left")

        # Merge chaur area
        merged = pd.merge(merged, chaur_summary, on="TEXTSTRING", how="left")

        # Fill missing values with 0 (command areas with no overlap)
        merged = merged.fillna(0)

        # Reorder: TEXTSTRING, Command_Area_km2, Chaur_Area_km2, features...
        fixed_cols = ["TEXTSTRING", "Command_Area_km2", "Chaur_Area_km2"]
        feature_cols = sorted([col for col in merged.columns if col not in fixed_cols])
        final_df = merged[fixed_cols + feature_cols]

        # Display
        st.subheader("📊 Final Area Matrix (All Commands Included)")
        st.dataframe(final_df)

        # Download
        st.download_button(
            "📥 Download CSV",
            data=final_df.to_csv(index=False).encode("utf-8"),
            file_name="command_area_with_chaur_exclusion.csv",
            mime="text/csv"
        )
