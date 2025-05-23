import streamlit as st
import geopandas as gpd
import pandas as pd
import zipfile
import tempfile
import os

st.set_page_config(layout="wide")
st.title("📐 Command Area-wise Feature Category Area Summary")

# Function to unzip shapefile from uploaded ZIP
def unzip_shapefile(zip_bytes):
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_bytes, "r") as zip_ref:
            zip_ref.extractall(tmpdir)
        shp_files = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.endswith(".shp")]
        if not shp_files:
            st.error("No .shp file found in the uploaded ZIP.")
            return None
        gdf = gpd.read_file(shp_files[0])
        return gdf.to_crs(epsg=32643)  # Adjust CRS as needed

# Upload UI
st.subheader("🗂 Upload Command Area Shapefile (.zip including .shp, .shx, .dbf, etc.)")
command_area_zip = st.file_uploader("Command Area Shapefile", type=["zip"])

st.subheader("🗂 Upload Feature Shapefile (.zip including .shp, .shx, .dbf, etc.)")
feature_zip = st.file_uploader("Feature Shapefile", type=["zip"])

if command_area_zip and feature_zip:
    command_areas = unzip_shapefile(command_area_zip)
    features = unzip_shapefile(feature_zip)

    if command_areas is not None and features is not None:
        st.success("✅ Shapefiles uploaded and read successfully.")

        # Check for TEXTSTRING column in command area
        if 'TEXTSTRING' not in command_areas.columns:
            st.error("❌ 'TEXTSTRING' column not found in command area shapefile.")
            st.stop()

        command_areas = command_areas.copy()
        features = features.copy()

        # Calculate total command area in km²
        command_areas["Command_Area_km2"] = command_areas.geometry.area / 1e6

        # Intersect features with command areas
        intersections = gpd.overlay(features, command_areas, how="intersection")
        intersections["Feature_Area_km2"] = intersections.geometry.area / 1e6

        # Detect feature classification column
        possible_category_columns = ['Layer', 'Type', 'Class', 'LandUse', 'Name']
        category_column = None
        for col in intersections.columns:
            if col in possible_category_columns:
                category_column = col
                break

        if not category_column:
            st.warning("⚠️ Could not identify feature category column. Defaulting to 'Unknown'.")
            intersections["Category"] = "Unknown"
            category_column = "Category"

        # Group by command area and feature category
        summary = intersections.groupby(["TEXTSTRING", category_column]).agg(
            Feature_Category_Area_km2=("Feature_Area_km2", "sum")
        ).reset_index()

        # Merge with command area totals
        command_area_totals = command_areas[["TEXTSTRING", "Command_Area_km2"]]
        final_summary = pd.merge(
            summary,
            command_area_totals,
            on="TEXTSTRING",
            how="left"
        )

        # Display result
        st.subheader("📊 Command Area-wise Feature Category Area Summary")
        st.dataframe(final_summary)

        # Download CSV
        csv_bytes = final_summary.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Summary CSV",
            data=csv_bytes,
            file_name="feature_category_area_by_command_area.csv",
            mime="text/csv"
        )
