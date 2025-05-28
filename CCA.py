import streamlit as st
import geopandas as gpd
import pandas as pd
import os

st.set_page_config(layout="wide")
st.title("📍 Command Area Feature Analyzer")

# --- Upload Section ---
st.header("📂 Upload Shapefiles")

cmd_area_file = st.file_uploader("Upload Command Area Polygon Shapefile (.zip)", type="zip", key="cmd")
text_point_file = st.file_uploader("Upload Point TEXT Layer (.zip)", type="zip", key="text")
features_file = st.file_uploader("Upload Feature Polygon Shapefile (.zip)", type="zip", key="feat")
chaur_file = st.file_uploader("Upload Chaur Polygon Shapefile (.zip)", type="zip", key="chaur")
line_file = st.file_uploader("Upload Line Feature Shapefile (.zip)", type="zip", key="line")

def unzip_shapefile(uploaded_zip, extract_to="shp_data"):
    if uploaded_zip:
        import zipfile
        import tempfile
        temp_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(uploaded_zip, "r") as zip_ref:
            zip_ref.extractall(temp_dir)
        return temp_dir
    return None

# --- Load All Shapefiles ---
cmd_gdf, text_gdf, feat_gdf, chaur_gdf, line_gdf = None, None, None, None, None

cmd_dir = unzip_shapefile(cmd_area_file)
if cmd_dir:
    cmd_gdf = gpd.read_file(cmd_dir)
    if cmd_gdf.crs is None:
        cmd_gdf.set_crs(epsg=4326, inplace=True)
    cmd_gdf = cmd_gdf.to_crs(epsg=32645)

text_dir = unzip_shapefile(text_point_file)
if text_dir:
    text_gdf = gpd.read_file(text_dir)
    if text_gdf.crs is None:
        text_gdf.set_crs(epsg=4326, inplace=True)
    text_gdf = text_gdf.to_crs(epsg=32645)

# --- Join Attributes by Nearest ---
if cmd_gdf is not None and text_gdf is not None:
    if 'TEXTSTRING' not in cmd_gdf.columns:
        joined = gpd.sjoin_nearest(cmd_gdf, text_gdf[['TEXTSTRING', 'geometry']], how='left', distance_col='dist')
        cmd_gdf = joined

        cmd_gdf.drop(columns=['dist'], inplace=True)

feat_dir = unzip_shapefile(features_file)
if feat_dir:
    feat_gdf = gpd.read_file(feat_dir)
    if feat_gdf.crs is None:
        feat_gdf.set_crs(epsg=4326, inplace=True)
    feat_gdf = feat_gdf.to_crs(epsg=32645)

chaur_dir = unzip_shapefile(chaur_file)
if chaur_dir:
    chaur_gdf = gpd.read_file(chaur_dir)
    if chaur_gdf.crs is None:
        chaur_gdf.set_crs(epsg=4326, inplace=True)
    chaur_gdf = chaur_gdf.to_crs(epsg=32645)

line_dir = unzip_shapefile(line_file)
if line_dir:
    line_gdf = gpd.read_file(line_dir)
    if line_gdf.crs is None:
        line_gdf.set_crs(epsg=4326, inplace=True)
    line_gdf = line_gdf.to_crs(epsg=32645)

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
            fsubset = feat_gdf[feat_gdf['Layer'] == ftype]
            inter = gpd.overlay(gpd.GeoDataFrame(geometry=[geom], crs=cmd_gdf.crs), fsubset, how='intersection')
            if not inter.empty:
                inter = gpd.overlay(inter, chaur_gdf, how='difference')
                area = inter.area.sum()
            else:
                area = 0.0
            feature_areas[ftype] = area
            row_data[ftype] = area

        row_data['Sum_Features_Area_m2'] = sum(feature_areas.values())
        results.append(row_data)

    df_area = pd.DataFrame(results)
    st.dataframe(df_area)
    st.download_button("📥 Download Area CSV", df_area.to_csv(index=False), file_name="area_matrix.csv")

# --- Line Length Matrix Calculation ---
if cmd_gdf is not None and line_gdf is not None:
    st.subheader("📏 Line Feature Length Matrix (Per Command Area)")

    line_types = line_gdf['Layer'].unique()
    line_results = []

    for _, row in cmd_gdf.iterrows():
        cmd_name = row['TEXTSTRING']
        geom = row['geometry']
        row_data = {'TEXTSTRING': cmd_name}

        for ltype in line_types:
            lsubset = line_gdf[line_gdf['Layer'] == ltype]
            inter = gpd.overlay(gpd.GeoDataFrame(geometry=[geom], crs=cmd_gdf.crs),
                                lsubset, how='intersection')
            if not inter.empty:
                length = inter.length.sum()
            else:
                length = 0.0
            row_data[ltype] = length

        line_results.append(row_data)

    df_line = pd.DataFrame(line_results)
    st.dataframe(df_line)
    st.download_button("📥 Download Line Length CSV", df_line.to_csv(index=False), file_name="line_length_matrix.csv")
