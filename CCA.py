import streamlit as st
import geopandas as gpd
import pandas as pd
import zipfile
import tempfile
import os
from io import BytesIO

st.set_page_config(layout="wide")
st.title("📐 Catchment-wise Feature Area Calculator")

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

# Upload shapefiles
st.subheader("Upload Catchment Shapefile (.zip of .shp, .shx, .dbf, etc.)")
catchment_zip = st.file_uploader("Catchment Shapefile (ZIP)", type=["zip"])

st.subheader("Upload Feature Shapefile (.zip of .shp, .shx, .dbf, etc.)")
feature_zip = st.file_uploader("Feature Shapefile (ZIP)", type=["zip"])

if catchment_zip and feature_zip:
    catchments = unzip_shapefile(catchment_zip)
    features = unzip_shapefile(feature_zip)

    if catchments is not None and features is not None:
        st.success("Shapefiles uploaded and read successfully.")

        # Assign IDs and area
        catchments["Catchment_ID"] = catchments.index + 1
        catchments["Catchment_Area_km2"] = catchments.geometry.area / 1e6

        # Intersect
        intersections = gpd.overlay(features, catchments, how="intersection")
        intersections["Feature_Area_km2"] = intersections.geometry.area / 1e6

        # Grouping logic
        if "Name" in intersections.columns:
            group_cols = ["Catchment_ID", "Name"]
        else:
            group_cols = ["Catchment_ID"]

        summary = intersections.groupby(group_cols).agg(
            Feature_Total_Area_km2=("Feature_Area_km2", "sum")
        ).reset_index()

        final_summary = pd.merge(
            catchments[["Catchment_ID", "Catchment_Area_km2"]],
            summary,
            on="Catchment_ID",
            how="left"
        ).fillna({"Feature_Total_Area_km2": 0})

        st.subheader("📊 Area Summary Table")
        st.dataframe(final_summary)

        # Download
        csv_bytes = final_summary.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Download CSV", data=csv_bytes, file_name="catchment_feature_area_summary.csv", mime="text/csv")
