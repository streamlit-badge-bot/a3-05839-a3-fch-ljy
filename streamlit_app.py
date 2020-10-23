import streamlit as st
import numpy as np
import pandas as pd
import random
import pydeck as pdk
import datetime
import altair as alt
import sklearn
import sodapy
import plotly

from sklearn.decomposition import PCA, KernelPCA
from sklearn.manifold import TSNE
from sodapy import Socrata
import plotly.express as px

from datasets import *
from dimension_reduction import *


global_hour = -1

def get_month(time):
    try:
        dt = datetime.datetime.strptime(time, '%m/%d/%Y %I:%M:%S %p')
    except:
        dt = datetime.datetime.strptime(time, '%Y-%m-%dT%H:%M:%S.000')
    return dt.month

def get_hour(time):
    try:
        dt = datetime.datetime.strptime(time, '%m/%d/%Y %I:%M:%S %p')
    except:
        dt = datetime.datetime.strptime(time, '%Y-%m-%dT%H:%M:%S.000')
    return dt.hour

def get_one_hot(ds):
    values = list(ds.unique())
    data_dict = {}
    for value in values:
        data_dict[value] = list(ds.apply(lambda x: x==value).astype(np.int))
    one_hot = pd.DataFrame(data_dict)
    return one_hot
    # return one_hot

@st.cache(suppress_st_warning=True)
def read_data(year, mode='offline'):
    if mode == 'offline':
        try:
            csv_cache = st.cache(pd.read_csv)
            results = csv_cache('Crimes.csv')
            return results[results.loc[:,'Year']==year]
        except: # For testing
            st.write('Incomplete Data Readed, Only for testing')
            client = Socrata("data.cityofchicago.org", None)
            results = client.get("ijzp-q8t2", where="year={:d}".format(year), limit=100000)
            results = pd.DataFrame.from_records(results)
            results.columns = ['ID', 'Case Number', 'Date', 'Block', 'IUCR', 'Primary Type',
                               'Description', 'Location Description', 'Arrest', 'Domestic', 'Beat',
                               'District', 'Ward', 'Community Area', 'FBI Code', 'X Coordinate',
                               'Y Coordinate', 'Year', 'Updated On', 'Latitude', 'Longitude',
                               'Location']
            return results[results.loc[:,'Year']==str(year)]
    else:
        client = Socrata("data.cityofchicago.org", None)
        results = client.get_all("ijzp-q8t2", where="year={:d}".format(year))
        results = pd.DataFrame.from_records(results)
        results.columns = ['ID', 'Case Number', 'Date', 'Block', 'IUCR', 'Primary Type',
            'Description', 'Location Description', 'Arrest', 'Domestic', 'Beat',
            'District', 'Ward', 'Community Area', 'FBI Code', 'X Coordinate',
            'Y Coordinate', 'Year', 'Updated On', 'Latitude', 'Longitude',
            'Location']
        return results[results.loc[:,'Year']==str(year)]

@st.cache
def add_extra_columns(selected_data):
    selected_data = selected_data.copy()
    selected_data.loc[:,'Month'] = selected_data.loc[:,'Date'].apply(lambda x:get_month(x))
    selected_data.loc[:,'Hour'] = selected_data.loc[:,'Date'].apply(lambda x:get_hour(x))
    return selected_data.loc[:,['Date', 'Block', 'Primary Type', 'Description', 'Location Description', 'Arrest', 'Domestic', 'Community Area', "Year", 'Month', 'Latitude', 'Longitude', 'Case Number', 'Hour']]

@st.cache
def random_select(data, target_num):
    total_num = data.shape[0]
    target_list = list(range(total_num))
    random.shuffle(target_list)
    target_list = target_list[:target_num]
    return data.iloc[target_list].reset_index()

def preprocess_data(data):
    data_columns = data.loc[:,['Primary Type', 'Month', 'Hour', 'Location Description', 'Arrest', 'Domestic', 'Community Area', 'Latitude', 'Longitude']]
    one_hot = [False, True, True, True, False, False, True, False, False]
    var_list = data_columns.columns.unique()
    data_columns = data_columns.dropna()
    object_list = []
    for i in range(8):
        var_name = var_list[i]
        if one_hot[i]:
            obj = get_one_hot(data.loc[:,var_name])
        else:
            if var_name != 'Primary Type':
                obj = data.loc[:,var_name].astype(np.float)
            else:
                obj = data.loc[:,var_name]
        if var_name in ['Latitude', 'Longitude']:
            obj = (obj-obj.mean())/obj.std()
        object_list.append(obj)
    data = pd.concat(object_list, axis=1)
    data = data.dropna()
    return data.iloc[:,0], np.array(data.iloc[:,1:])
    
def visualize_ml(selected_data):
    labels, feats = preprocess_data(selected_data)
    algorithms = {'PCA': pca,
                  'KPCA': kpca,
                  't-SNE': tsne}
    
    algo_opt = st.selectbox('Select an algorithm:', list(algorithms.keys()))
    
    
    n_samples = st.slider('Number of Samples', 
                          min_value=0, 
                          max_value=len(feats), 
                          value=min(2500, len(feats)), 
                          step=1)
    results, indices = algorithms[algo_opt](feats, n_samples)

    reduced = pd.DataFrame(results, columns=['x', 'y', 'z'])
    reduced_labels = labels.iloc[list(indices)].reset_index().iloc[:,1]
    reduced.loc[:,'class'] = reduced_labels
    
    fig = px.scatter_3d(reduced, x='x', y='y', z='z', color='class', opacity=1)
    fig.update_layout(autosize=False,
                      width=700,
                      height=800)
    st.plotly_chart(fig)

def visualize_chart(selected_data):
    st.header("Chart Visualization")
    
    selector_type = alt.selection_single(empty='all', fields=['Primary Type'])
    selector_loc = alt.selection_single(empty='all', fields=['Location Description'])
    brush = alt.selection(type='interval')
    base = alt.Chart(selected_data).properties(
            width=300,
            height=300
        )

    points = base.mark_bar(filled=True).encode(
            x=alt.X('Primary Type:N', sort=alt.EncodingSortField(field="Case Number", op="count", order='descending'),),
            y=alt.Y('count(Case Number):Q'),
            color=alt.condition(selector_type,
                                'Primary Type:N',
                                alt.value('lightgray')),
            ).properties(
                    title="Total Crime Numbers (Click to Select)",
            ).add_selection(
                selector_type
            ).transform_filter(
                selector_loc
            ).transform_filter(
                brush
            )
    
    chart_main = base.mark_area(filled=True).encode(x='Hour:N',
                                         y='count(Case Number):Q',
                                         color=alt.Color('Primary Type:N')).properties(
                                             title="Hourly Trend of Crime Types (Drag to Select)",
                                             ).add_selection(
                                                 brush
                                             ).transform_filter(
                                                 selector_loc
                                             ).transform_filter(
                                                 selector_type
                                             )
    two_chart = points|chart_main
    chart_location = base.mark_bar(filled=True).encode(
                x=alt.X(
                    'Location Description:N',
                    sort=alt.EncodingSortField(field="Case Number", op="count", order='descending'),
                ),
                y=alt.Y('count(Case Number):Q'),
                color=alt.condition(
                    selector_loc,
                    'Primary Type:N',
                    alt.value('lightgray')
                ),
            ).properties(
                title="Location Distribution (Click to Select)",
                width=700,
                height=200
            ).add_selection(
                selector_loc
            ).transform_filter(
                brush
            ).transform_filter(
                selector_type
            )
    
    background = alt.Chart().mark_geoshape(
                    fill='lightgray',
                    stroke='white'
                ).properties(
                    width=700,
                    height=400
                )
        
    geo_chart = base.mark_circle(
            size=10
        ).encode(
            longitude='Longitude:Q',
            latitude='Latitude:Q',
            color='Primary Type:N',
            tooltip=['Date', 'Block', 'Primary Type', 'Description', 'Location Description']
        ).properties(
                title="Geography Distribution (Details given in Points)",
                width=700,
                height=400
        ).transform_filter(
            selector_loc
        ).transform_filter(
            brush
        ).transform_filter(
            selector_type
        )
        
    st.altair_chart(alt.vconcat(two_chart, chart_location, background + geo_chart))
    

def visualize_map(data, crime_list = ['THEFT','BATTERY', 'CRIMINAL DAMAGE', 'NARCOTICS', 'ASSAULT', 'OTHER']):
    st.header("Map Visualization")
    options = st.multiselect("Visualization Type", ['HeatMap', 'ScatterPlot', 'Hexagon'], default=['ScatterPlot', 'Hexagon'])
    view_in_hour = st.checkbox("View In Single Hour")
    global global_hour
    if view_in_hour:
        hour = st.slider('Select specific hour', 0, 23, value=0, step=1)
        selected_data = data[data.loc[:,'Hour']==hour]
        global_hour = hour
    else:
        selected_data = data
        global_hour = -1
    selected_data.loc[:,['Latitude','Longitude']] = selected_data.loc[:,['Latitude','Longitude']].astype(np.float)
    selected_data = selected_data.dropna()
    view_state = pdk.ViewState(
        longitude=-87.65, latitude=41.8, pitch=40.5, bearing=-10, zoom=10
    )
    layers = []
    if 'Hexagon' in options:
        layer = pdk.Layer(
            "HexagonLayer",
            data=selected_data,
            get_position='[Longitude, Latitude]',
            elevation_scale=8,
            elevation_range=[0, 1500],
            radius = 100,
            extruded=True,
            pickable=True,
            coverage=1)
        layers.append(layer)
            
    if "ScatterPlot" in options:
        separate_types_of_crime = st.checkbox("Separate Crimes")
        if separate_types_of_crime:
            i = 0
            for crime in crime_list:
                if crime != 'OTHER':
                    crime_data = selected_data[selected_data.loc[:,'Primary Type']==crime]
                else:
                    target_list = crime_list[:-1]
                    crime_data = selected_data[selected_data.loc[:,'Primary Type'].apply(lambda x:x not in target_list)]
                layer = pdk.Layer(
                    'ScatterplotLayer',    
                    data=crime_data,
                    get_position='[Longitude, Latitude]',
                    auto_highlight=True,
                    get_radius=100,
                    get_fill_color=[125+25*i, 250-50*i, 50*i],
                    pickable=True)
                layers.append(layer)
                i += 1
        else:
            layer = pdk.Layer(
                'ScatterplotLayer',
                data=selected_data,
                get_position='[Longitude, Latitude]',
                auto_highlight=True,
                get_radius=100,
                get_fill_color=[180, 0, 200, 140],
                pickable=True)
            layers.append(layer)
    if 'HeatMap' in options:
        layer = pdk.Layer(
            "HeatmapLayer",
            data=selected_data,
            get_position='[Longitude, Latitude]',
            opacity=0.5,
            aggregation='"MEAN"')
        layers.append(layer)
    deck_cache = st.cache(pdk.Deck)
    deck = deck_cache(map_style='mapbox://styles/mapbox/light-v9',layers=layers, initial_view_state=view_state)
    st.pydeck_chart(deck)

def main_chart():
    
    st.title("Exploring the Pattern of Chicago Crimes")
    
    #General data selection and preprocessing
    year = st.sidebar.slider('Year', 2001, 2020, value=2020)
    st.sidebar.write("Year Value Will Be Fixed Here (2020)")
    year = 2020
    num_of_samples = st.sidebar.slider('Total Case Number', 2000, 100000, value=10000, step=2000)
    data_cache = st.cache(read_data)
    results = data_cache(year, 'online')
    selected_data = random_select(results, num_of_samples)
    selected_data = add_extra_columns(selected_data)
    
    #Detailed Selection
    location_list = list(selected_data.groupby('Location Description').agg('count').sort_values('Case Number', ascending = False).index)
    location_list = location_list[:15]+['OTHER']
    
    crime_list = list(selected_data.groupby('Primary Type').agg('count').sort_values('Case Number', ascending = False).index)
    crime_list = crime_list[:10]+['OTHER']
    
    crimetype = st.sidebar.multiselect('Crime Type', crime_list, default = crime_list[:-5])
    location = st.sidebar.multiselect('Location', location_list, default = location_list[:-1])
    month = st.sidebar.selectbox('Month', ['All Month'] +list(range(1,12)))
    if crimetype != []:
        if 'OTHER' not in crimetype:
            selected_data = selected_data[selected_data.loc[:,'Primary Type'].apply(lambda x:x in crimetype)]
        else:
            target_list = crime_list
            for crime in crimetype:
                target_list.remove(crime)
            selected_data = selected_data[selected_data.loc[:,'Primary Type'].apply(lambda x:x not in target_list)]
            
    if location != []:
        if 'OTHER' not in location:
            selected_data = selected_data[selected_data.loc[:,'Location Description'].apply(lambda x:x in location)]
        else:
            target_list = location_list
            for loc in location:
                target_list.remove(loc)
            selected_data = selected_data[selected_data.loc[:,'Location Description'].apply(lambda x:x not in target_list)]
    if month != 'All Month':
        selected_data = selected_data[selected_data.loc[:,'Month']==month]
    selected_data = selected_data.reset_index().iloc[:,1:]
    st.subheader('Selected Data')
    st.write(selected_data)
    visualization_type = st.multiselect('Select the way you want to explore the data', ['Explore In Charts', 'Visualize In A Map', 'Machine Learning'], default = ['Explore In Charts'])
    if 'Visualize In A Map' in visualization_type:
        visualize_map(selected_data, crime_list)
    if 'Explore In Charts' in visualization_type:
        visualize_chart(selected_data)
    if 'Machine Learning' in visualization_type:
        visualize_ml(selected_data)

def main_dim_reduce():
    st.title('Dimentionality Reduction')

    datasets = {'MNIST': mnist}
    algorithms = {'PCA': pca,
                  'KPCA': kpca,
                  'Isomap': isomap,
                  't-SNE': tsne,
                  'UMAP': umap,
                  'Autoencoder': ae}

    ds_opt = st.sidebar.selectbox('Please select a dataset:', list(datasets.keys()))
    algo_opt = st.sidebar.selectbox('Please select an algorithm:', list(algorithms.keys()))


    feats, labels = datasets[ds_opt]()

    n_samples = st.sidebar.slider('Number of Samples', 
                          min_value=500, 
                          max_value=len(feats), 
                          value=min(2500, len(feats)), 
                          step=500)

    results, indices = algorithms[algo_opt](feats, n_samples)

    reduced = pd.DataFrame(results, columns=['x', 'y', 'z'])
    reduced['class'] = labels[indices]

    fig = px.scatter_3d(reduced, x='x', y='y', z='z', color='class', opacity=1)
    fig.update_layout(autosize=False,
                      width=700,
                      height=800)

    st.plotly_chart(fig)
        
        
def main():
    st.sidebar.title("Settings")
    dataset = st.sidebar.selectbox('Please select a task:', ['Chart Exploration', 'Dimensionality Reduction'])
    if dataset == 'Chart Exploration':
        main_chart()
    elif dataset == 'Dimensionality Reduction':
        main_dim_reduce()


if __name__ == '__main__':
    main()