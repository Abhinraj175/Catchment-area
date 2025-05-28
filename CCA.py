import streamlit as st
import geopandas as gpd
import pandas as pd
import os, zipfile, tempfile

st.set_page_config(layout="wide")
st.title("📍 Command Area Feature Analyzer")

# --- Upload Shapefiles ---
st.header("📂 Upload Shapefiles")
cmd_area_file = st.file_uploader("Upload Command Area Polygon (.zip)", type="zip")
text_point_file = st.file_uploader("Upload Point TEXT Layer (.zip)", type="zip")
features_file = st.file_uploader("Upload Feature Polygon (.zip)", type="zip")
chaur_file = st.file_uploader("Upload Chaur Polygon (.zip)", type="zip")
line_file = st.file_uploader("Upload Line Feature (.zip)", type="zip")

def unzip_shapefile(uploaded_zip):
    if uploaded_zip:
        temp_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(uploaded_zip, "r") as zip_ref:
            zip_ref.extractall(temp_dir)
        return temp_dir
    return None

# --- Load Shapefiles ---
def load_gdf(zipfile, epsg=32645):
    folder = unzip_shapefile(zipfile)
    if folder:
        gdf = gpd.read_file(folder)
        if gdf.crs is None:
            gdf.set_crs(epsg=4326, inplace=True)
        return gdf.to_crs(epsg=epsg)
    return None

cmd_gdf = load_gdf(cmd_area_file)
text_gdf = load_gdf(text_point_file)
feat_gdf = load_gdf(features_file)
chaur_gdf = load_gdf(chaur_file)
line_gdf = load_gdf(line_file)

# --- Join Nearest TEXTSTRING if missing ---
if cmd_gdf is not None and text_gdf is not None and 'TEXTSTRING' not in cmd_gdf.columns:
    nearest = gpd.sjoin_nearest(cmd_gdf, text_gdf[['TEXTSTRING', 'geometry']], how='left', distance_col='dist')
    cmd_gdf['TEXTSTRING'] = nearest['TEXTSTRING']

# --- Area Matrix Calculation ---
if cmd_gdf is not None and feat_gdf is not None and chaur_gdf is not None:
    st.subheader("📊 Area Matrix")

    cmd_gdf['Command_Area_m2'] = cmd_gdf.geometry.area

    # Intersect features with cmd_gdf
    results = []
    for cmd_row in cmd_gdf.itertuples():
        geom = cmd_row.geometry
        row_data = {'TEXTSTRING': cmd_row.TEXTSTRING, 'Command_Area_m2': geom.area}

        # Chaur Area
        chaur_inter = gpd.overlay(gpd.GeoDataFrame(geometry=[geom], crs=cmd_gdf.crs),
                                  chaur_gdf, how='intersection')
        chaur_area = chaur_inter.area.sum() if not chaur_inter.empty else 0.0
        row_data['Chaur_Area_m2'] = chaur_area

        # Feature Areas
        for ftype in feat_gdf['Layer'].unique():
            fsubset = feat_gdf[feat_gdf['Layer'] == ftype]
            inter = gpd.overlay(gpd.GeoDataFrame(geometry=[geom], crs=cmd_gdf.crs), fsubset, how='intersection')
            if not inter.empty:
                inter = gpd.overlay(inter, chaur_gdf, how='difference')
                row_data[ftype] = inter.area.sum()
            else:
                row_data[ftype] = 0.0

        results.append(row_data)

    df_area = pd.DataFrame(results)
    st.dataframe(df_area)
    st.download_button("📥 Download Area Matrix", df_area.to_csv(index=False), file_name="area_matrix.csv")

# --- Line Length Matrix ---
if cmd_gdf is not None and line_gdf is not None:
    st.subheader("📏 Line Length Matrix")

    line_results = []
    for cmd_row in cmd_gdf.itertuples():
        geom = cmd_row.geometry
        row_data = {'TEXTSTRING': cmd_row.TEXTSTRING}

        for ltype in line_gdf['Layer'].unique():
            lsubset = line_gdf[line_gdf['Layer'] == ltype]
            inter = gpd.overlay(gpd.GeoDataFrame(geometry=[geom], crs=cmd_gdf.crs), lsubset, how='intersection')
            row_data[ltype] = inter.length.sum() if not inter.empty else 0.0

        line_results.append(row_data)

    df_line = pd.DataFrame(line_results)
    st.dataframe(df_line)
    st.download_button("📥 Download Line Length Matrix", df_line.to_csv(index=False), file_name="line_matrix.csv")
