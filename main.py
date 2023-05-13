import time
from datetime import datetime, timedelta
from pathlib import Path
from shutil import rmtree
from zipfile import ZipFile
from typing import Optional, List
import aiofiles
# from pydantic import BaseModel
from fastapi import FastAPI, Depends, File, UploadFile, HTTPException, Request, status, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse

# from fastapi.encoders import jsonable_encoder
from xlsxwriter import Workbook
import os, io, glob, uuid, time
import folium as folium
from folium.plugins import PolyLineTextPath
import pandas as pd
import geopandas, fiona
import matplotlib.pyplot as plt
from exif import Image as Img
# from starlette.responses import Response
#mark before deployment
import math
import uvicorn


class GPSExifData:
    Image_name: str
    # GPS_make: str
    # GPS_model: str
    # GPS_time: str
    GPS_latitude: float
    GPS_longitude: float
    # GPS_direction: float


app = FastAPI()

###### Params #####
image_list = []
all_tag = []
Name = []
Time = []
Make = []
Model = []
Direction = []
Lat = []
Long = []
folder_name = "IN_FILES"
temp_path = os.getcwd() + "/" + folder_name
DEL_FOLDER = True
valid_image_list = []

# print(f"new_path {temp_path}")
##### Pandas Data Frame #####
# df1 = pd.DataFrame()
# df2 = pd.DataFrame()

####TODO #####
# folder_name = "FILE_NAME"
# file_path = os.getcwd() + "/" + folder_name
#delete folder#d
def delete_folder(temp_path):
    if DEL_FOLDER:
        rmtree(temp_path)
    else:
        pass


def read_image_name(folder_path):
    files = []
    for ext in ('*.JPEG', '*.JPG', '*.jpg', '*.jpeg'):
      for filename in glob.glob(os.path.join(folder_path, ext)):
        with open(filename, mode='rb') as f:
            text = f.readlines()
            #image_list.clear()
            image_list.append(filename)
            print("get")
            print(f"image_list: {image_list}")
    return image_list


def dms_to_dd(gps_coords, gps_coords_ref):
    d, m, s = gps_coords
    dd = d + m / 60 + s / 3600
    if gps_coords_ref.upper() in ('S', 'W'):
        return -dd
    elif gps_coords_ref.upper() in ('N', 'E'):
        return dd
    else:
        raise RuntimeError('Incorrect gps_coords_ref {}'.format(gps_coords_ref))


def image_to_exif(images_list):
    for image in image_list:
        if Img(image).has_exif:
            with open(image, 'rb') as image_file:
                my_image = Img(image_file)
                gps_latitude_ref = 'N'
                gps_longitude_ref = 'W'
                try:
                    get_all = my_image.get_all()
                    all_tag.append(get_all)
                    # print(f"all_tag: {all_tag}")
                    GPSExifData.GPS_latitude = dms_to_dd(my_image.gps_latitude, my_image.gps_latitude_ref)
                    GPSExifData.GPS_longitude = dms_to_dd(my_image.gps_longitude, my_image.gps_longitude_ref)
                    valid_image_list.append(image)
                except:
                    print(f"No coordinate here!: ")
                    # remove_image_no_coordinate.append()
                    pass
    # print(f"GPS: {valid_image_list}")
    # print(len(all_tag))
    return all_tag


@app.get("/")
async def hello():
    return {"result": "Image to Map - Its working YES! This is a miracle!"}


@app.post("/exif_csv", tags=['text files for downloading'])
async def create_csv(files: List[UploadFile] = File(...)):
    folder_UUID = str(uuid.uuid1())
    for file in files:
        # output file path
        # temp_path = "/Users/kalin/PycharmProjects/ImageToMap/outFiles"
        # path = temp_path+"/directory"
        path = temp_path+"/"+folder_UUID
        os.makedirs(path, exist_ok=True)
        destination_file_path = path+"/"+file.filename
        print(f"destination_file_path: {destination_file_path}")
        async with aiofiles.open(destination_file_path, 'wb') as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
    print(f"path: {path}")
    photo_list = read_image_name(path)
    tags = image_to_exif(photo_list)
    print(photo_list)
    df2 = pd.DataFrame(tags)
    stream = io.StringIO()
    df2.to_csv(stream, index=False, escapechar='\\')
    #, sep='\t'
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv", status_code=200)
    response.headers["Content-Disposition"] = f"{folder_UUID}.csv"
    ######to empty the lists###########
    df2.iloc[0:0]
    tags.clear()
    photo_list.clear()
    ######delete folder######

    return response


@app.post("/exif_excel", tags=['text files for downloading'])
async def create_excel(files: List[UploadFile] = File(...), background_tasks: BackgroundTasks = BackgroundTasks):
    folder_UUID = str(uuid.uuid1())

    for file in files:
        # output file path
        # temp_path = "/Users/kalin/PycharmProjects/ImageToMap/outFiles"
        # path = temp_path+"/directory"
        path = temp_path+"/"+folder_UUID
        os.makedirs(path, exist_ok=True)
        destination_file_path = path+"/"+file.filename
        print(f"destination_file_path: {destination_file_path}")
        async with aiofiles.open(destination_file_path, 'wb') as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
    print(f"path: {path}")
    photo_list = read_image_name(path)
    tags = image_to_exif(photo_list)
    print(photo_list)
    df4 = pd.DataFrame(tags)


    file_excel = io.BytesIO()
    writer = pd.ExcelWriter(file_excel, engine='xlsxwriter')
    df4.to_excel(writer, sheet_name='Sheet1')
    writer.close()
    file_excel.seek(0)
    xlsx_data = file_excel.getvalue()
    try:
        ####remove files after download######
        # background_tasks.add_task(os.remove, path)

        headers = {"Content-Disposition": f'attachment; filename={folder_UUID}.xlsx'}
        response = StreamingResponse(io.BytesIO(xlsx_data),
                                 media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                 headers=headers,
                                 status_code=200, background=background_tasks)
        ######to empty the lists###########
        df4.iloc[0:0]
        tags.clear()
        photo_list.clear()

        return response
    except:
        return "not ok"



@app.post("/exif_html_table", tags=['html for viewing'])
async def create_table(files: List[UploadFile] = File(...)):
    folder_UUID = str(uuid.uuid1())
    # output file path
    # temp_path = "/Users/kalin/PycharmProjects/ImageToMap/outFiles"
    # path = temp_path+"/directory"
    path = temp_path + "/" + folder_UUID
    for file in files:
        os.makedirs(path, exist_ok=True)
        destination_file_path = path+"/"+file.filename
        print(f"destination_file_path: {destination_file_path}")
        async with aiofiles.open(destination_file_path, 'wb') as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
    print(f"path: {path}")
    photo_list = read_image_name(path)
    tags = image_to_exif(photo_list)
    df2 = pd.DataFrame(tags)
    stream = io.StringIO()
    html_table_image = df2.to_html(stream, index=False)
    ######to empty the lists###########
    df2.iloc[0:0]
    tags.clear()
    photo_list.clear()
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/html", status_code=200)
    response.headers["Content-Disposition"] = f"{folder_UUID}.html"

    return response


@app.post("/exif_json", tags=['json for viewing'])
async def create_json(files: List[UploadFile] = File(...)):
    folder_UUID = str(uuid.uuid1())
    # output file path
    # temp_path = "/Users/kalin/PycharmProjects/ImageToMap/outFiles"
    path = temp_path + "/" + folder_UUID
    for file in files:
        os.makedirs(path, exist_ok=True)
        destination_file_path = path+"/"+file.filename
        print(f"destination_file_path: {destination_file_path}")
        async with aiofiles.open(destination_file_path, 'wb') as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
    print(f"path: {path}")
    photo_list = read_image_name(path)
    tags = image_to_exif(photo_list)
    df0 = pd.DataFrame(tags)
    stream = io.StringIO()
    #to_json --- orient="table" orient="columns" orient="index"  orient="records"  orient="split"
    df0.to_json(stream, orient="records")
    ######to empty the lists###########
    df0.iloc[0:0]
    tags.clear()
    photo_list.clear()
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/json", status_code=200)
    response.headers["Content-Disposition"] = f"{folder_UUID}.json"


    return response


@app.post("/exif_html_map", tags=['html for viewing'])
async def create_map(files: List[UploadFile] = File(...)):
    folder_UUID = str(uuid.uuid1())
    Lat = []
    Lon = []
    Name = []
    for file in files:
        # output file path
        # temp_path = "/Users/kalin/PycharmProjects/ImageToMap/outFiles"
        # path = temp_path+"/directory"
        path = temp_path + "/" + folder_UUID
        os.makedirs(path, exist_ok=True)
        destination_file_path = path + "/" + file.filename
        print(f"destination_file_path: {destination_file_path}")
        async with aiofiles.open(destination_file_path, 'wb') as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
        Name.append(os.path.basename(file.filename))
    # print(f"path: {path}")
    photo_list = read_image_name(path)
    tags = image_to_exif(photo_list)
    # print(photo_list)
    df5 = pd.DataFrame(tags)


    for x in range(len(df5.index)):
        # Name.append()
        if 'gps_latitude' in df5.columns:
            Lat.append(dms_to_dd(df5.gps_latitude[x], df5.gps_latitude_ref[x]))
            Lon.append(dms_to_dd(df5.gps_longitude[x], df5.gps_longitude_ref[x]))
            # if pd.isnull(df5['gps_latitude'].iloc[x]):
            #     print(f"empty exif, no coordinate ")
            #     Lat.append(0)
            #     Lon.append(0)
            pass
        else:
            print(f"empty exif, no coordinate ")
            Lat.append(0)
            Lon.append(0)
    try:
        df5["Latitude"] = Lat
        df5["Longitude"] = Lon
        df5["Name"] = Name
        # first_column = df5.pop('Name')
        # df5.insert(0, 'Name', first_column)
    except:
        print("No name")
        df5["Name"] = "Name"
        pass
    print(df5.Latitude, df5.Longitude)
    # print(f"Name: {Name}")
    gdf = geopandas.GeoDataFrame(
        df5, geometry=geopandas.points_from_xy(df5.Longitude, df5.Latitude), crs="EPSG:4326")
    print(gdf.head())
    # world = geopandas.read_file(geopandas.datasets.get_path('naturalearth_lowres'))
    world = geopandas.read_file("https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip")
    ax = world.plot(
        color='white', edgecolor='black')
    #########create map######
    m = folium.Map(
        location=[df5.Latitude[0], df5.Longitude[0]],
        zoom_start=7,
        tiles='openstreetmap',
        zoom_control=True,
        scrollWheelZoom=True,
        dragging=True
    )
    folium.TileLayer('openstreetmap').add_to(m)
    folium.TileLayer('Stamen Terrain').add_to(m)
    folium.TileLayer('Stamen Toner').add_to(m)
    folium.TileLayer('Stamen Water Color').add_to(m)
    folium.TileLayer('cartodbpositron').add_to(m)
    folium.TileLayer('cartodbdark_matter').add_to(m)
    loc_1 = []
    for idx, point in df5.iterrows():
            loc_1.append((point['Latitude'], point['Longitude']))
    # print(f"loc_1: {loc_1}")
    m.add_child(folium.LatLngPopup())

    f1 = folium.FeatureGroup("Line")
    polyline = folium.vector_layers.PolyLine(locations=loc_1, color='lightblue', no_clip=True)
    polyline.add_to(f1)
    #####---- ####
    polyline_length = 0.0
    for i in range(len(loc_1) - 1):
        coord1 = loc_1[i]
        coord2 = loc_1[i + 1]
        lat1, lon1 = coord1
        lat2, lon2 = coord2
        # Convert latitude and longitude to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        # Haversine formula
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance = 6371 * c  # Earth's radius in kilometers
        polyline_length += distance

    # Convert the length to kilometers
    polyline_length_km = polyline_length

    # Create the label text
    label_text = "Length: {:.2f} km".format(polyline_length_km)

    f1.add_child(polyline)
    for i in range(len(loc_1) - 1):
        coord1 = loc_1[i]
        coord2 = loc_1[i + 1]
        midpoint = [(coord1[0] + coord2[0]) / 2, (coord1[1] + coord2[1]) / 2]
        label_lat, label_lon = midpoint
        icon_style = 'color: black; font-weight: bold; text-shadow: -1px -1px 1px #fff, 1px -1px 1px #fff, -1px 1px 1px #fff, 1px 1px 1px #fff;'
        popup_style = 'font-size: 20px;'
        folium.Marker(
            location=[label_lat, label_lon],
            icon=folium.DivIcon(html=f'<div style="{icon_style}">{label_text}</div>'),
            popup=folium.Popup(label_text, max_width=200, show=False, sticky=True, style=popup_style)
        ).add_to(f1)
    ##### --- ####

    f1.add_to(m)
    f2 = folium.FeatureGroup("PhotoLocation")
    # print(f"dflat: {df5.columns}")
    #########create marker######
    for _, r in gdf.iterrows():
        lat = r['geometry'].y
        lon = r['geometry'].x
        folium.vector_layers.Marker(location=[lat, lon], popup='Name: {} <br> Time: {} <br> Latitude: {:.4f} <br> Longitude: {:.4f}'.format(r['Name'], r['datetime'], lat, lon ),
                      icon=folium.Icon(icon="cloud"), ).add_to(f2)
    f2.add_to(m)
    folium.LayerControl().add_to(m)
    ######to empty the lists###########
    df5.iloc[0:0]
    tags.clear(), photo_list.clear(), Lat.clear(), Lon.clear(), Name.clear()
    ######create html map#######
    html_map = m._repr_html_()
    # html_map = m.get_root().render()

    response = StreamingResponse(iter([html_map]), media_type="text/html", status_code=200)
    response.headers["Content-Disposition"] = f"{folder_UUID}.html"

    return response


@app.post("/exif_shp", tags=['GIS files for downloading'])
async def create_shp(files: List[UploadFile] = File(...)):
    folder_UUID = str(uuid.uuid1())
    Lat = []
    Lon = []
    Name = []
    check = False
    for file in files:
        # output file path
        path = temp_path+"/"+folder_UUID
        os.makedirs(path, exist_ok=True)
        destination_file_path = path+"/"+file.filename
        print(f"destination_file_path: {destination_file_path}")
        async with aiofiles.open(destination_file_path, 'wb') as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
        Name.append(os.path.basename(file.filename))
    photo_list = read_image_name(path)
    image_to_exif(photo_list)

    # print(f"valid_image_list: {len(valid_image_list)}, {list(set(valid_image_list))}")
    tags = image_to_exif(valid_image_list)
    print(f"len: {len(tags)}")
    if len(tags) > 0:
        df222 = pd.DataFrame(tags)
        df12 = df222.drop_duplicates()
        print(f"df12: {df12.head()}")
        if ('gps_longitude' in df12.columns):
            check = True
            df12.drop(df12.index, inplace=True)
        else:
            check = False
            df12.drop(df12.index, inplace=True)
    else:
        check = False

    print(f"check: {check}")
    #невалидна проверка in tags
    if check:
        df22 = pd.DataFrame(tags)
        df7 = df22.drop_duplicates()
        print(f"df: {df7.empty}")
        if df7.empty == True:
            print("Exif is missing in the photo!")
        else:
            # print(f"Super1: {df7.head()}")
            for x in range(len(df7.index)):
                # Name.append(GPSExifData.Image_name)
                if pd.isnull(df7['gps_latitude'].iloc[x]):
                   # print(f"empty exif, no coordinate ")
                   Lat.append(0)
                   Lon.append(0)
                else:
                    Lat.append(dms_to_dd(df7.gps_latitude[x], df7.gps_latitude_ref[x]))
                    Lon.append(dms_to_dd(df7.gps_longitude[x], df7.gps_longitude_ref[x]))
                    df7.reset_index()
                    # print(f"work: {df7.columns},")
                # print(Lat, Lon)
            try:
                df7["Latitude"] = Lat
                df7["Longitude"] = Lon
                df7["Name"] = Name
                first_column = df7.pop('Name')
                df7.insert(0, 'Name', first_column)
                del df7["datetime"]
                del df7["datetime_original"]
                del df7["datetime_digitized"]
                del df7["flash"]
                del df7["gps_latitude"]
                del df7["gps_longitude"]
            except:
                print("kofti")
                df7["Name"] = "Name"
                pass
            print(f"Super2: {df7.head()}")
            gdf = geopandas.GeoDataFrame(
                df7, geometry=geopandas.points_from_xy(df7.Longitude, df7.Latitude), crs="EPSG:4326")
            # print(gdf.head())
            #and map
            # world = geopandas.read_file(geopandas.datasets.get_path('naturalearth_lowres'))
            world = geopandas.read_file("https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip")

            ax = world.plot(
                color='white', edgecolor='black')
            #########create map######
            m = folium.Map(
                location=[df7.Latitude[0], df7.Longitude[0]],
                zoom_start=7,
                tiles='openstreetmap',
                zoom_control=True,
                scrollWheelZoom=True,
                dragging=True
            )
            folium.TileLayer('openstreetmap').add_to(m)
            folium.TileLayer('Stamen Terrain').add_to(m)
            folium.TileLayer('Stamen Toner').add_to(m)
            folium.TileLayer('Stamen Water Color').add_to(m)
            folium.TileLayer('cartodbpositron').add_to(m)
            folium.TileLayer('cartodbdark_matter').add_to(m)
            folium.LayerControl().add_to(m)
            #########create marker######
            for _, r in gdf.iterrows():
                lat = r['geometry'].y
                lon = r['geometry'].x
                folium.Marker(location=[lat, lon], popup='Name: {} <br> Time: {}'.format(r['Name'], r['Name']),
                              icon=folium.Icon(icon="cloud"), ).add_to(m)
            df7.to_csv(path + '/out.csv', index=True, escapechar='\\')
            ### datetime datetime_original  datetime_digitized

            #######create shp files - point######
            gdf2 = geopandas.GeoDataFrame()
            gdf2["Name"] = gdf["Name"]
            gdf2["geometry"] = gdf["geometry"]
            gdf2["Altitude"] = gdf["gps_altitude"]
            gdf2["Direction"] = gdf["gps_img_direction"]
            gdf2["Latitude"] = gdf["Latitude"]
            gdf2["Longitude"] = gdf["Longitude"]
            gdf2["Model"] = gdf["model"]
            # print(fiona.supported_drivers)
            path_zip = os.path.join(path, "Shp_files")
            try:
                os.mkdir(path_zip)
            except OSError as error:
                print(error)
            #Create shp files and zip
            gdf2.to_file(path_zip + '/points.shp', crs="EPSG:4326")
            path_zip_ID = f"{temp_path}/{folder_UUID}/Shp_files"
            path2 = f"{temp_path}/{folder_UUID}/"
            # print(path2)
            entries = Path(path_zip_ID)
            zip_filename = str(uuid.uuid1())+".zip"
            zip_path = os.path.join(os.path.dirname(path2), zip_filename)
            with ZipFile(zip_path,  mode='w') as myzip:
                for entry in entries.iterdir():
                    myzip.write(entry, arcname=entry.name)
                    # myzip.close()
            # print(gdf.head())
            ######to empty the lists###########
            try:
                df12.iloc[0:0]
                df7.iloc[0:0]
                gdf2.iloc[0:0]
                df7.drop(df7.index, inplace=True)
                gdf2.drop(gdf2.index, inplace=True)
                df12.drop(df12.index, inplace=True)
                tags.clear(), photo_list.clear(), Lat.clear(), Lon.clear(), Name.clear(), valid_image_list.clear()
                del valid_image_list[:]
                print(f"Тук трябва да е празно? {tags,photo_list}, {valid_image_list}")
            except:
                print("Error for del temp data?")
                pass
            file_path = f"{path}/{zip_filename}"
            # print(f"file_path_final: {file_path}")
            response = FileResponse(path=file_path, filename=zip_filename, status_code=200)
            return response


@app.post("/exif_geojson", tags=['GIS files for downloading'])
async def create_geojson(files: List[UploadFile] = File(...)):
###new
    folder_UUID = str(uuid.uuid1())
    Lat = []
    Lon = []
    Name = []
    check = False
    for file in files:
        # output file path
        path = temp_path + "/" + folder_UUID
        os.makedirs(path, exist_ok=True)
        destination_file_path = path + "/" + file.filename
        print(f"destination_file_path: {destination_file_path}")
        async with aiofiles.open(destination_file_path, 'wb') as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
        Name.append(os.path.basename(file.filename))
    photo_list = read_image_name(path)
    image_to_exif(photo_list)

    # print(f"valid_image_list: {len(valid_image_list)}, {list(set(valid_image_list))}")
    tags = image_to_exif(valid_image_list)
    print(f"len: {len(tags)}")
    if len(tags) > 0:
        df222 = pd.DataFrame(tags)
        df12 = df222.drop_duplicates()
        print(f"df12: {df12.head()}")
        if ('gps_longitude' in df12.columns):
            check = True
            df12.drop(df12.index, inplace=True)
        else:
            check = False
            df12.drop(df12.index, inplace=True)
    else:
        check = False

    print(f"check: {check}")
    # невалидна проверка in tags
    if check:
        df22 = pd.DataFrame(tags)
        df7 = df22.drop_duplicates()
        print(f"df: {df7.empty}")
        if df7.empty == True:
            print("Exif is missing in the photo!")
        else:
            # print(f"Super1: {df7.head()}")
            for x in range(len(df7.index)):
                # Name.append(GPSExifData.Image_name)
                if pd.isnull(df7['gps_latitude'].iloc[x]):
                    # print(f"empty exif, no coordinate ")
                    Lat.append(0)
                    Lon.append(0)
                else:
                    Lat.append(dms_to_dd(df7.gps_latitude[x], df7.gps_latitude_ref[x]))
                    Lon.append(dms_to_dd(df7.gps_longitude[x], df7.gps_longitude_ref[x]))
                    df7.reset_index()
                    # print(f"work: {df7.columns},")
                # print(Lat, Lon)
            try:
                df7["Latitude"] = Lat
                df7["Longitude"] = Lon
                df7["Name"] = Name
                first_column = df7.pop('Name')
                df7.insert(0, 'Name', first_column)
                del df7["datetime"]
                del df7["datetime_original"]
                del df7["datetime_digitized"]
                del df7["flash"]
                del df7["gps_latitude"]
                del df7["gps_longitude"]
            except:
                print("kofti")
                df7["Name"] = "Name"
                pass
            print(f"Super2: {df7.head()}")
            gdf = geopandas.GeoDataFrame(
                df7, geometry=geopandas.points_from_xy(df7.Longitude, df7.Latitude), crs="EPSG:4326")
            # print(gdf.head())
            # and map
            # world = geopandas.read_file(geopandas.datasets.get_path('naturalearth_lowres'))
            world = geopandas.read_file("https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip")

            ax = world.plot(
                color='white', edgecolor='black')
            #########create map######
            m = folium.Map(
                location=[df7.Latitude[0], df7.Longitude[0]],
                zoom_start=7,
                tiles='openstreetmap',
                zoom_control=True,
                scrollWheelZoom=True,
                dragging=True
            )
            folium.TileLayer('openstreetmap').add_to(m)
            folium.TileLayer('Stamen Terrain').add_to(m)
            folium.TileLayer('Stamen Toner').add_to(m)
            folium.TileLayer('Stamen Water Color').add_to(m)
            folium.TileLayer('cartodbpositron').add_to(m)
            folium.TileLayer('cartodbdark_matter').add_to(m)
            folium.LayerControl().add_to(m)
            #########create marker######
            for _, r in gdf.iterrows():
                lat = r['geometry'].y
                lon = r['geometry'].x
                folium.Marker(location=[lat, lon], popup='Name: {} <br> Time: {}'.format(r['Name'], r['Name']),
                              icon=folium.Icon(icon="cloud"), ).add_to(m)
            df7.to_csv(path + '/out.csv', index=True, escapechar='\\')
            ### datetime datetime_original  datetime_digitized

            #######create shp files - point######
            gdf2 = geopandas.GeoDataFrame()
            gdf2["Name"] = gdf["Name"]
            gdf2["geometry"] = gdf["geometry"]
            gdf2["Altitude"] = gdf["gps_altitude"]
            gdf2["Direction"] = gdf["gps_img_direction"]
            gdf2["Latitude"] = gdf["Latitude"]
            gdf2["Longitude"] = gdf["Longitude"]
            gdf2["Model"] = gdf["model"]
            # print(fiona.supported_drivers)
            path = f"{temp_path}/{folder_UUID}/"
            name = folder_UUID+".geojson"
            filename = gdf2.to_file(path + "/" + name, driver="GeoJSON")
            ######to empty the lists###########
            try:
                df12.iloc[0:0]
                df7.iloc[0:0]
                gdf2.iloc[0:0]
                df7.drop(df7.index, axis=1, errors='ignore')
                gdf2.drop(gdf2.index, axis=1, errors='ignore')
                df12.drop(df12.index, axis=1, errors='ignore')
                tags.clear(), photo_list.clear(), Lat.clear(), Lon.clear(), Name.clear(), valid_image_list.clear()
                del valid_image_list[:]
                print(f"Тук трябва да е празно? {tags, photo_list}, {valid_image_list}")
            except:
                print("Error for del temp data?")
                pass

            file_path = path+name
            headers = {"Content-Disposition": f'attachment; filename={name}',"Content-Type": "application/octet-stream",}
            response = FileResponse(path=file_path, headers=headers)
            return response


@app.post("/exif_kml", tags=['GIS files for downloading'])
async def create_kml(files: List[UploadFile] = File(...)):
    folder_UUID = str(uuid.uuid1())
    Lat = []
    Lon = []
    Name = []
    check = False
    for file in files:
        # output file path
        path = temp_path + "/" + folder_UUID
        os.makedirs(path, exist_ok=True)
        destination_file_path = path + "/" + file.filename
        print(f"destination_file_path: {destination_file_path}")
        async with aiofiles.open(destination_file_path, 'wb') as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
        Name.append(os.path.basename(file.filename))
    photo_list = read_image_name(path)
    image_to_exif(photo_list)

    # print(f"valid_image_list: {len(valid_image_list)}, {list(set(valid_image_list))}")
    tags = image_to_exif(valid_image_list)
    print(f"len: {len(tags)}")
    if len(tags) > 0:
        df222 = pd.DataFrame(tags)
        df12 = df222.drop_duplicates()
        print(f"df12: {df12.head()}")
        if ('gps_longitude' in df12.columns):
            check = True
            df12.drop(df12.index, inplace=True)
        else:
            check = False
            df12.drop(df12.index, inplace=True)
    else:
        check = False

    print(f"check: {check}")
    # невалидна проверка in tags
    if check:
        df22 = pd.DataFrame(tags)
        df7 = df22.drop_duplicates()
        print(f"df: {df7.empty}")
        if df7.empty == True:
            print("Exif is missing in the photo!")
        else:
            # print(f"Super1: {df7.head()}")
            for x in range(len(df7.index)):
                # Name.append(GPSExifData.Image_name)
                if pd.isnull(df7['gps_latitude'].iloc[x]):
                    # print(f"empty exif, no coordinate ")
                    Lat.append(0)
                    Lon.append(0)
                else:
                    Lat.append(dms_to_dd(df7.gps_latitude[x], df7.gps_latitude_ref[x]))
                    Lon.append(dms_to_dd(df7.gps_longitude[x], df7.gps_longitude_ref[x]))
                    df7.reset_index()
                    # print(f"work: {df7.columns},")
                # print(Lat, Lon)
            try:
                df7["Latitude"] = Lat
                df7["Longitude"] = Lon
                df7["Name"] = Name
                first_column = df7.pop('Name')
                df7.insert(0, 'Name', first_column)
                del df7["datetime"]
                del df7["datetime_original"]
                del df7["datetime_digitized"]
                del df7["flash"]
                del df7["gps_latitude"]
                del df7["gps_longitude"]
            except:
                print("kofti")
                df7["Name"] = "Name"
                pass
            print(f"Super2: {df7.head()}")
            gdf = geopandas.GeoDataFrame(
                df7, geometry=geopandas.points_from_xy(df7.Longitude, df7.Latitude), crs="EPSG:4326")
            # print(gdf.head())
            # and map
            # world = geopandas.read_file(geopandas.datasets.get_path('naturalearth_lowres'))
            world = geopandas.read_file("https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip")

            ax = world.plot(
                color='white', edgecolor='black')
            #########create map######
            m = folium.Map(
                location=[df7.Latitude[0], df7.Longitude[0]],
                zoom_start=7,
                tiles='openstreetmap',
                zoom_control=True,
                scrollWheelZoom=True,
                dragging=True
            )
            folium.TileLayer('openstreetmap').add_to(m)
            folium.TileLayer('Stamen Terrain').add_to(m)
            folium.TileLayer('Stamen Toner').add_to(m)
            folium.TileLayer('Stamen Water Color').add_to(m)
            folium.TileLayer('cartodbpositron').add_to(m)
            folium.TileLayer('cartodbdark_matter').add_to(m)
            folium.LayerControl().add_to(m)
            #########create marker######
            for _, r in gdf.iterrows():
                lat = r['geometry'].y
                lon = r['geometry'].x
                folium.Marker(location=[lat, lon], popup='Name: {} <br> Time: {}'.format(r['Name'], r['Name']),
                              icon=folium.Icon(icon="cloud"), ).add_to(m)
            df7.to_csv(path + '/out.csv', index=True, escapechar='\\')
            ### datetime datetime_original  datetime_digitized

            #######create shp files - point######
            gdf2 = geopandas.GeoDataFrame()
            gdf2["Name"] = gdf["Name"]
            gdf2["geometry"] = gdf["geometry"]
            gdf2["Altitude"] = gdf["gps_altitude"]
            gdf2["Direction"] = gdf["gps_img_direction"]
            gdf2["Latitude"] = gdf["Latitude"]
            gdf2["Longitude"] = gdf["Longitude"]
            gdf2["Model"] = gdf["model"]
            # print(fiona.supported_drivers)
            fiona.supported_drivers['KML'] = 'rw'
            path = f"{temp_path}/{folder_UUID}/"
            name = folder_UUID+".kml"
            filename = gdf2.to_file(path + "/" + name, driver='KML', crs="EPSG:4326")
            ######to empty the lists###########
            try:
                df12.iloc[0:0]
                df7.iloc[0:0]
                gdf2.iloc[0:0]
                df7.drop(df7.index, axis=1, errors='ignore')
                gdf2.drop(gdf2.index, axis=1, errors='ignore')
                df12.drop(df12.index, axis=1, errors='ignore')
                tags.clear(), photo_list.clear(), Lat.clear(), Lon.clear(), Name.clear(), valid_image_list.clear()
                del valid_image_list[:]
                print(f"Тук трябва да е празно? {tags, photo_list}, {valid_image_list}")
            except:
                print("Error for del temp data?")
                pass

            file_path = path+name
            # response = FileResponse(path=file_path, filename=name, status_code=200, content_disposition_type="attachment")
            headers = {"Content-Disposition": f'attachment; filename={name}',"Content-Type": "application/octet-stream",}
            response = FileResponse(path=file_path, headers=headers)
            return response


@app.post("/exif_gpx", tags=['GIS files for downloading'])
async def create_gpx(files: List[UploadFile] = File(...)):
    folder_UUID = str(uuid.uuid1())
    Lat = []
    Lon = []
    Name = []
    check = False
    for file in files:
        # output file path
        path = temp_path + "/" + folder_UUID
        os.makedirs(path, exist_ok=True)
        destination_file_path = path + "/" + file.filename
        print(f"destination_file_path: {destination_file_path}")
        async with aiofiles.open(destination_file_path, 'wb') as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
        Name.append(os.path.basename(file.filename))
    photo_list = read_image_name(path)
    image_to_exif(photo_list)

    # print(f"valid_image_list: {len(valid_image_list)}, {list(set(valid_image_list))}")
    tags = image_to_exif(valid_image_list)
    print(f"len: {len(tags)}")
    if len(tags) > 0:
        df222 = pd.DataFrame(tags)
        df12 = df222.drop_duplicates()
        print(f"df12: {df12.head()}")
        if ('gps_longitude' in df12.columns):
            check = True
            df12.drop(df12.index, inplace=True)
        else:
            check = False
            df12.drop(df12.index, inplace=True)
    else:
        check = False

    print(f"check: {check}")
    # невалидна проверка in tags
    if check:
        df22 = pd.DataFrame(tags)
        df7 = df22.drop_duplicates()
        print(f"df: {df7.empty}")
        if df7.empty == True:
            print("Exif is missing in the photo!")
        else:
            # print(f"Super1: {df7.head()}")
            for x in range(len(df7.index)):
                # Name.append(GPSExifData.Image_name)
                if pd.isnull(df7['gps_latitude'].iloc[x]):
                    # print(f"empty exif, no coordinate ")
                    Lat.append(0)
                    Lon.append(0)
                else:
                    Lat.append(dms_to_dd(df7.gps_latitude[x], df7.gps_latitude_ref[x]))
                    Lon.append(dms_to_dd(df7.gps_longitude[x], df7.gps_longitude_ref[x]))
                    df7.reset_index()
                    # print(f"work: {df7.columns},")
                # print(Lat, Lon)
            try:
                df7["Latitude"] = Lat
                df7["Longitude"] = Lon
                df7["Name"] = Name
                first_column = df7.pop('Name')
                df7.insert(0, 'Name', first_column)
                del df7["datetime"]
                del df7["datetime_original"]
                del df7["datetime_digitized"]
                del df7["flash"]
                del df7["gps_latitude"]
                del df7["gps_longitude"]
            except:
                print("kofti")
                df7["Name"] = "Name"
                pass
            print(f"Super2: {df7.head()}")
            gdf = geopandas.GeoDataFrame(
                df7, geometry=geopandas.points_from_xy(df7.Longitude, df7.Latitude), crs="EPSG:4326")
            # print(gdf.head())
            # and map
            # world = geopandas.read_file(geopandas.datasets.get_path('naturalearth_lowres'))
            world = geopandas.read_file("https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip")

            ax = world.plot(
                color='white', edgecolor='black')
            #########create map######
            m = folium.Map(
                location=[df7.Latitude[0], df7.Longitude[0]],
                zoom_start=7,
                tiles='openstreetmap',
                zoom_control=True,
                scrollWheelZoom=True,
                dragging=True
            )
            folium.TileLayer('openstreetmap').add_to(m)
            folium.TileLayer('Stamen Terrain').add_to(m)
            folium.TileLayer('Stamen Toner').add_to(m)
            folium.TileLayer('Stamen Water Color').add_to(m)
            folium.TileLayer('cartodbpositron').add_to(m)
            folium.TileLayer('cartodbdark_matter').add_to(m)
            folium.LayerControl().add_to(m)
            #########create marker######
            for _, r in gdf.iterrows():
                lat = r['geometry'].y
                lon = r['geometry'].x
                folium.Marker(location=[lat, lon], popup='Name: {} <br> Time: {}'.format(r['Name'], r['Name']),
                              icon=folium.Icon(icon="cloud"), ).add_to(m)
            df7.to_csv(path + '/out.csv', index=True, escapechar='\\')
            ### datetime datetime_original  datetime_digitized

            #######create shp files - point######
            gdf2 = geopandas.GeoDataFrame()
            gdf2["Name"] = gdf["Name"]
            gdf2["geometry"] = gdf["geometry"]
            gdf2["Altitude"] = gdf["gps_altitude"]
            gdf2["Direction"] = gdf["gps_img_direction"]
            gdf2["Latitude"] = gdf["Latitude"]
            gdf2["Longitude"] = gdf["Longitude"]
            gdf2["Model"] = gdf["model"]
            print(f"fiona.supported_drivers: {fiona.supported_drivers}")
            fiona.supported_drivers['GPX'] = 'rw'
            path = f"{temp_path}/{folder_UUID}/"
            name = folder_UUID + ".gpx"
            filename = gdf2.to_file(path + "/" + name, driver="GPX", GPX_USE_EXTENSIONS="Yes")
            ######to empty the lists###########
            try:
                df12.iloc[0:0]
                df7.iloc[0:0]
                gdf2.iloc[0:0]
                df7.drop(df7.index, axis=1, errors='ignore')
                gdf2.drop(gdf2.index, axis=1, errors='ignore')
                df12.drop(df12.index, axis=1, errors='ignore')
                tags.clear(), photo_list.clear(), Lat.clear(), Lon.clear(), Name.clear(), valid_image_list.clear()
                del valid_image_list[:]
                print(f"Тук трябва да е празно? {tags, photo_list}, {valid_image_list}")
            except:
                print("Error for del temp data?")
                pass

            file_path = path+name
            print(f"file_name: {name}")
            # response = FileResponse(path=file_path, filename=name, media_type="application/octet-stream")
            headers = {"Content-Disposition": f'attachment; filename={name}',"Content-Type": "application/octet-stream",}
            response = FileResponse(path=file_path, headers=headers)
            return response

@app.post("/exif_dxf", tags=['GIS files for downloading'])
async def create_dxf(files: List[UploadFile] = File(...)):
    folder_UUID = str(uuid.uuid1())
    Lat = []
    Lon = []
    Name = []
    check = False
    for file in files:
        # output file path
        path = temp_path + "/" + folder_UUID
        os.makedirs(path, exist_ok=True)
        destination_file_path = path + "/" + file.filename
        print(f"destination_file_path: {destination_file_path}")
        async with aiofiles.open(destination_file_path, 'wb') as out_file:
            while content := await file.read(1024):
                await out_file.write(content)
        Name.append(os.path.basename(file.filename))
    photo_list = read_image_name(path)
    image_to_exif(photo_list)

    # print(f"valid_image_list: {len(valid_image_list)}, {list(set(valid_image_list))}")
    tags = image_to_exif(valid_image_list)
    print(f"len: {len(tags)}")
    if len(tags) > 0:
        df222 = pd.DataFrame(tags)
        df12 = df222.drop_duplicates()
        print(f"df12: {df12.head()}")
        if ('gps_longitude' in df12.columns):
            check = True
            df12.drop(df12.index, inplace=True)
        else:
            check = False
            df12.drop(df12.index, inplace=True)
    else:
        check = False

    print(f"check: {check}")
    # невалидна проверка in tags
    if check:
        df22 = pd.DataFrame(tags)
        df7 = df22.drop_duplicates()
        print(f"df: {df7.empty}")
        if df7.empty == True:
            print("Exif is missing in the photo!")
        else:
            # print(f"Super1: {df7.head()}")
            for x in range(len(df7.index)):
                # Name.append(GPSExifData.Image_name)
                if pd.isnull(df7['gps_latitude'].iloc[x]):
                    # print(f"empty exif, no coordinate ")
                    Lat.append(0)
                    Lon.append(0)
                else:
                    Lat.append(dms_to_dd(df7.gps_latitude[x], df7.gps_latitude_ref[x]))
                    Lon.append(dms_to_dd(df7.gps_longitude[x], df7.gps_longitude_ref[x]))
                    df7.reset_index()
                    # print(f"work: {df7.columns},")
                # print(Lat, Lon)
            try:
                df7["Latitude"] = Lat
                df7["Longitude"] = Lon
                df7["Name"] = Name
                first_column = df7.pop('Name')
                df7.insert(0, 'Name', first_column)
                del df7["datetime"]
                del df7["datetime_original"]
                del df7["datetime_digitized"]
                del df7["flash"]
                del df7["gps_latitude"]
                del df7["gps_longitude"]
            except:
                print("kofti")
                df7["Name"] = "Name"
                pass
            print(f"Super2: {df7.head()}")
            gdf = geopandas.GeoDataFrame(
                df7, geometry=geopandas.points_from_xy(df7.Longitude, df7.Latitude), crs="EPSG:4326")
            # print(gdf.head())
            # and map
            # world = geopandas.read_file(geopandas.datasets.get_path('naturalearth_lowres'))
            world = geopandas.read_file("https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip")

            ax = world.plot(
                color='white', edgecolor='black')
            #########create map######
            m = folium.Map(
                location=[df7.Latitude[0], df7.Longitude[0]],
                zoom_start=7,
                tiles='openstreetmap',
                zoom_control=True,
                scrollWheelZoom=True,
                dragging=True
            )
            folium.TileLayer('openstreetmap').add_to(m)
            folium.TileLayer('Stamen Terrain').add_to(m)
            folium.TileLayer('Stamen Toner').add_to(m)
            folium.TileLayer('Stamen Water Color').add_to(m)
            folium.TileLayer('cartodbpositron').add_to(m)
            folium.TileLayer('cartodbdark_matter').add_to(m)
            folium.LayerControl().add_to(m)
            #########create marker######
            for _, r in gdf.iterrows():
                lat = r['geometry'].y
                lon = r['geometry'].x
                folium.Marker(location=[lat, lon], popup='Name: {} <br> Time: {}'.format(r['Name'], r['Name']),
                              icon=folium.Icon(icon="cloud"), ).add_to(m)
            df7.to_csv(path + '/out.csv', index=True, escapechar='\\')
            ### datetime datetime_original  datetime_digitized

            #######create shp files - point######
            gdf2 = geopandas.GeoDataFrame()
            # gdf2["Name"] = gdf["Name"]
            gdf2["geometry"] = gdf["geometry"]
            # gdf2["Altitude"] = gdf["gps_altitude"]
            # gdf2["Direction"] = gdf["gps_img_direction"]
            # gdf2["Latitude"] = gdf["Latitude"]
            # gdf2["Longitude"] = gdf["Longitude"]
            # gdf2["Model"] = gdf["model"]
            # print(f"fiona.supported_drivers: {fiona.supported_drivers}")
            fiona.supported_drivers['DXF'] = 'rw'
            path = f"{temp_path}/{folder_UUID}/"
            name = folder_UUID + ".dxf"
            filename = gdf2.to_file(path + "/" + name, driver="DXF")
            ######to empty the lists###########
            try:
                df12.iloc[0:0]
                df7.iloc[0:0]
                gdf2.iloc[0:0]
                df7.drop(df7.index, axis=1, errors='ignore')
                gdf2.drop(gdf2.index, axis=1, errors='ignore')
                df12.drop(df12.index, axis=1, errors='ignore')
                tags.clear(), photo_list.clear(), Lat.clear(), Lon.clear(), Name.clear(), valid_image_list.clear()
                del valid_image_list[:]
                print(f"Тук трябва да е празно? {tags, photo_list}, {valid_image_list}")
            except:
                print("Error for del temp data?")
                pass

            file_path = path+name
            # response = FileResponse(path=file_path, filename=name, status_code=200, content_disposition_type="attachment")
            headers = {"Content-Disposition": f'attachment; filename={name}',"Content-Type": "application/octet-stream",}
            response = FileResponse(path=file_path, headers=headers)
            return response

@app.get("/files_info", tags=['admin tools'])
async def files_size_mb():
    result = []
    count = 0
    try:
        total_size = 0
        for path, dirs, files in os.walk(temp_path):
            for f in files:
                fp = os.path.join(path, f)
                total_size += os.path.getsize(fp)
                if f.endswith(".JPG") or f.endswith(".JPEG") or f.endswith(".jpeg") or f.endswith(".jpg"):
                    count += 1
            # print(count)
        size_MB = str("%.2f" % float(total_size/ 1024 ** 2))
        result.append(f"Directory size {folder_name}: {size_MB} MB, Number of Img is: {count}")
        return result
    except:
        return {"Empty folder "}


@app.delete("/delete_all_files", tags=['admin tools'])
async def delete_all_files(min: int = 10):
    try:
        now = time.time()
        for file_name in os.listdir(temp_path):
            file_path = os.path.join(temp_path, file_name)
            if os.path.getmtime(file_path) < now - min * 60:
                try:
                    # os.remove(file_path)
                    delete_folder(file_path)
                    # print(file_path)
                except:
                    print("ne trie")
                    pass
            else:
                print(f"File does not exist: {file_path}")
        return {f"All files older than {min} minutes have been deleted in folder: {temp_path}"}
    except:
        return {"The folder is empty": f"{temp_path}"}


def raise_exception():
    return HTTPException(status_code=404,
                         detail="Input is Not valid!",
                         headers={"X-Header_Error": f"Nothing to be seen"})

#mark before deployment
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=5000, reload=True, log_level="info", workers=2)
print('Ready')
