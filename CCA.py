import streamlit as st
import geopandas as gpd
import pandas as pd
import zipfile
import tempfile
import os

st.set_page_config(layout="wide")
st.title("📐 Command Area-wise Feature Area Matrix")

# Function to unzip shapefile and return GeoDataFrame
def unzip_shapefile(zip_bytes):
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_bytes, "r") as zip_ref:
            zip_ref.extractall(tmpdir)
        shp_files = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.endswith(".shp")]
        if not shp_files:
            st.error("No .shp file found in the uploaded ZIP.")
            return None
        gdf = gpd.read_file(shp_files[0])
        return gdf.to_crs(epsg=32643)  # Modify CRS if needed

# File upload interface
st.subheader("🗂 Upload Command Area Shapefile (.zip containing .shp, .shx, .dbf, etc.)")
command_area_zip = st.file_uploader("Command Area Shapefile", type=["zip"])

st.subheader("🗂 Upload Feature Shapefile (.zip containing .shp, .shx, .dbf, etc.)")
feature_zip = st.file_uploader("Feature Shapefile", type=["zip"])

if command_area_zip and feature_zip:
    command_areas = unzip_shapefile(command_area_zip)
    features = unzip_shapefile(feature_zip)

    if command_areas is not None and features is not None:
        st.success("✅ Shapefiles uploaded and read successfully.")

        if 'TEXTSTRING' not in command_areas.columns:
            st.error("❌ 'TEXTSTRING' column not found in command area shapefile.")
            st.stop()

        # Project and compute command area
        command_areas["Command_Area_km2"] = command_areas.geometry.area / 1e6

        # Intersect
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

        # Group and pivot
        grouped = intersections.groupby(["TEXTSTRING", intersections[category_column]])["Feature_Area_km2"].sum().reset_index()
        pivot = grouped.pivot(index="TEXTSTRING", columns=category_column, values="Feature_Area_km2").fillna(0)
        pivot.reset_index(inplace=True)

        # Add command area and total feature area columns
        command_area_totals = command_areas[["TEXTSTRING", "Command_Area_km2"]]
        final_df = pd.merge(command_area_totals, pivot, on="TEXTSTRING", how="left")
        feature_cols = final_df.columns[2:]  # All feature columns
        final_df["Total_Feature_Area_km2"] = final_df[feature_cols].sum(axis=1)

        # Rearranged columns
        final_df = final_df[["TEXTSTRING", "Command_Area_km2"] + list(feature_cols) + ["Total_Feature_Area_km2"]]

        # Display
        st.subheader("📊 Command Area-wise Feature Area Matrix")
        st.dataframe(final_df)

        # Download option
        csv_bytes = final_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="📥 Download Summary CSV",
            data=csv_bytes,
            file_name="command_area_feature_matrix.csv",
            mime="text/csv"
        )
