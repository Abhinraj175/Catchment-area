import streamlit as st
import geopandas as gpd
import pandas as pd
import os
import tempfile
import zipfile

st.set_page_config(layout="wide")
st.title("📍 Command Area Feature Analyzer")

# --- Upload Section ---
st.header("📂 Upload Shapefiles")
cmd_area_file = st.file_uploader("Upload Command Area Polygon Shapefile (.zip)", type="zip", key="cmd")
text_point_file = st.file_uploader("Upload Point TEXT Layer (.zip)", type="zip", key="text")
features_file = st.file_uploader("Upload Feature Polygon Shapefile (.zip)", type="zip", key="feat")
chaur_file = st.file_uploader("Upload Chaur Polygon Shapefile (.zip)", type="zip", key="chaur")
line_file = st.file_uploader("Upload Line Feature Shapefile (.zip)", type="zip", key="line")

# --- Utility function to unzip and load shapefile ---
def unzip_shapefile(uploaded_zip):
    if uploaded_zip:
        temp_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(uploaded_zip, "r") as zip_ref:
            zip_ref.extractall(temp_dir)
        return temp_dir
    return None

def load_gdf(zipfile, target_crs=32645):
    directory = unzip_shapefile(zipfile)
    if directory:
        gdf = gpd.read_file(directory)
        if gdf.crs is None:
            gdf.set_crs(epsg=4326, inplace=True)
        return gdf.to_crs(epsg=target_crs)
    return None

# --- Load All Shapefiles ---
cmd_gdf = load_gdf(cmd_area_file)
text_gdf = load_gdf(text_point_file)
feat_gdf = load_gdf(features_file)
chaur_gdf = load_gdf(chaur_file)
line_gdf = load_gdf(line_file)

# --- Join Text Labels by Nearest if TEXTSTRING not already in cmd_gdf ---
if cmd_gdf is not None and text_gdf is not None:
    if 'TEXTSTRING' not in cmd_gdf.columns:
        st.info("TEXTSTRING not found in command area; assigning from nearest text point layer...")
        joined = gpd.sjoin_nearest(cmd_gdf, text_gdf[['TEXTSTRING', 'geometry']], how='left', distance_col='dist')
        cmd_gdf['TEXTSTRING'] = joined['TEXTSTRING'].values
        cmd_gdf.drop(columns=['dist'], inplace=True)
    else:
        st.success("TEXTSTRING already present in command area attribute table. Skipping label join.")

# --- Area Matrix Calculation ---
if cmd_gdf is not None and feat_gdf is not None and chaur_gdf is not None:
    st.subheader("📊 Final Area Matrix (All Commands Included)")

    feature_types = feat_gdf['Layer'].unique()
    results = []

    for _, row in cmd_gdf.iterrows():
        cmd_name = row['TEXTSTRING']
        geom = row['geometry']
        row_data = {'TEXTSTRING': cmd_name}

        cmd_area = geom.area
        row_data['Command_Area_m2'] = cmd_area

        chaur_inter = gpd.overlay(gpd.GeoDataFrame(geometry=[geom], crs=cmd_gdf.crs),
                                  chaur_gdf, how='intersection')
        chaur_area = chaur_inter.area.sum() if not chaur_inter.empty else 0.0
        row_data['Chaur_Area_m2'] = chaur_area

        feature_areas = {}
        for ftype in feature_types:
            fsubset = feat_gdf[feat_gdf['Layer]()_]()_
