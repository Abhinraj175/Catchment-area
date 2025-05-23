import streamlit as st
import geopandas as gpd
import pandas as pd
import zipfile
import tempfile
import os

st.set_page_config(layout="wide")
st.title("📐 Catchment-wise Feature Category Area Summary")

# Helper: Extract and read shapefile from ZIP
def unzip_shapefile(zip_bytes):
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_bytes, "r") as zip_ref:
            zip_ref.extractall(tmpdir)
        shp_files = [os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.endswith(".shp")]
        if not shp_files:
            st.error("No .shp file found in the uploaded ZIP.")
            return None
        gdf = gpd.read_file(shp_files[0])
        return gdf.to_crs(epsg=32643)  # UTM zone 43N (modify if needed)

# Upload inputs
st.subheader("🗂 Upload Catchment Shapefile (ZIP with .shp, .shx, .dbf, etc.)")
catchment_zip = st.file_uploader("Catchment Shapefile", type=["zip"])

st.subheader("🗂 Upload Feature Shapefile (ZIP with .shp, .shx, .dbf, etc.)")
feature_zip = st.file_uploader("Feature Shapefile", type=["zip"])

if catchment_zip and feature_zip:
    catchments = unzip_shapefile(catchment_zip)
    features = unzip_shapefile(feature_zip)

    if catchments is not None and features is not None:
        st.success("✅ Shapefiles uploaded and read successfully.")

        # Assign IDs and area to catchments
        catchments["Catchment_ID"] = catchments.index + 1
        catchments["Catchment_Area_km2"] = catchments.geometry.area / 1e6

        # Intersect to get only overlapping regions
        intersections = gpd.overlay(features, catchments, how="intersection")
        intersections["Feature_Area_km2"] = intersections.geometry.area / 1e6

        # Try to identify the feature classification column
        possible_category_columns = ['Layer', 'Type', 'Class', 'LandUse', 'Name']
        category_column = None
        for col in intersections.columns:
            if col in possible_category_columns:
                category_column = col
                break

        if not category_column:
            st.warning("⚠️ Could not identify a category column (e.g., 'Category', 'Type', etc.). Using default.")
            intersections["Category"] = "Unknown"
            category_column = "Category"

        # Group and summarize by catchment and category
        summary = intersections.groupby(["Catchment_ID", category_column]).agg(
            Feature_Category_Area_km2=("Feature_Area_km2", "sum")
        ).reset_index()

        # Merge with total catchment areas
        final_summary = pd.merge(
            catchments[["Catchment_ID", "Catchment_Area_km2"]],
            summary,
            on="Catchment_ID",
            how="right"
        )

        # Display table
        st.subheader("📊 Catchment-wise Feature Category Area Summary")
        st.dataframe(final_summary)

        # Download option
        csv_bytes = final_summary.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download CSV Report",
            data=csv_bytes,
            file_name="catchment_feature_category_summary.csv",
            mime="text/csv"
        )
