from sqlite3 import DataError
import streamlit as st
import pandas as pd
import numpy as np
import googleapiclient.discovery
import googleapiclient.errors
import mysql.connector
from mysql.connector import Error
from streamlit_option_menu import option_menu
from datetime import datetime

# -------------------YouTube API-------------------
# Set up the YouTube API
api_service_name = "youtube"
api_version = "v3"
api_key = "AIzaSyBorjqk0jIF2HCDp0Fs5eHsOsR0Pn1iNiE"

# Create a YouTube API client
youtube = googleapiclient.discovery.build(api_service_name, api_version, developerKey=api_key)

# -------------------Functions-------------------
def get_channel_data(channel_id):
    try:
        mysqldb = mysql.connector.connect(host="localhost", database="my_database") 
        cursor = mysqldb.cursor(dictionary=True)  # Fetch results as dictionary
        cursor.execute("SELECT * FROM channels WHERE channel_id = %s", (channel_id,))
        existing_channel = cursor.fetchone()

        # ✅ If channel exists, return the data instead of just an error
        if existing_channel:
            cursor.close()
            mysqldb.close()
            st.warning("Channel ID already exists in the database. Showing stored data.")
            return pd.DataFrame([existing_channel])  # ✅ Return existing data as DataFrame
        
        # ✅ If channel doesn't exist, fetch data from YouTube API
        request = youtube.channels().list(part="snippet,contentDetails,statistics", id=channel_id)
        response = request.execute()
        
        if 'items' in response and len(response["items"]) > 0:
            data = {
                'channel_id': response['items'][0]['id'],
                'channel_name': response['items'][0]['snippet']['title'],
                'playlists': response['items'][0]['contentDetails']['relatedPlaylists']['uploads'],
                'channel_type': response['items'][0]['snippet'].get('customUrl', 'N/A'),
                'channel_des': response['items'][0]['snippet']['description'],
                'view_count': int(response['items'][0]['statistics']['viewCount']),
                'subscriber_count': int(response['items'][0]['statistics']['subscriberCount']),
                'video_count': int(response['items'][0]['statistics']['videoCount'])
            }

            # ✅ Insert new channel data into database
            cursor.execute("""
                INSERT INTO channels (channel_id, channel_name, playlists, channel_type, channel_des, view_count, subscriber_count, video_count)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (data['channel_id'], data['channel_name'], data['playlists'], data['channel_type'], data['channel_des'], 
                  data['view_count'], data['subscriber_count'], data['video_count']))
            
            mysqldb.commit()
            cursor.close()
            mysqldb.close()
            return pd.DataFrame([data])  # ✅ Return newly fetched data as DataFrame

        else:
            cursor.close()
            mysqldb.close()
            st.error("No items found in the response.")
            return pd.DataFrame()

    except mysql.connector.DataError as e:
        st.error(f"MySQL Error: {e}")
        return pd.DataFrame()
    except KeyError as e:
        st.error(f"KeyError: {e}. Please make sure the channel ID is correct.")
        return pd.DataFrame()

def get_playlist_video_id(channel_ids):
    all_video_ids = []
    for channel in channel_ids:
        video_ids = []
        try:
            request = youtube.channels().list(part="contentDetails", id=channel)
            response = request.execute()
            if 'items' in response and len(response['items']) > 0:
                playlist_id = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
                next_page_token = None

                while True:
                    request = youtube.playlistItems().list(
                        part="snippet,contentDetails",
                        playlistId=playlist_id,
                        maxResults=50,
                        pageToken=next_page_token
                    )
                    response = request.execute()
                    for item in response.get('items', []):
                        video_id = item['snippet']['resourceId'].get('videoId')
                        if video_id:
                            video_ids.append(video_id)

                    next_page_token = response.get("nextPageToken")
                    if not next_page_token:
                        break
                
        except googleapiclient.errors.HttpError as e:
            print(f"Error fetching videos for channel {channel}: {e}")
        
        all_video_ids.extend(video_ids)
    print("All Video IDs:", all_video_ids)  # Debugging output

    return all_video_ids

def get_video_data(all_video_ids):
    video_data = []
    for video_id in all_video_ids:
        try:
            request = youtube.videos().list(part='snippet,contentDetails,statistics', id=video_id)
            response = request.execute()
            for video in response.get('items', []):
                # ✅ Convert ISO format to MySQL DATETIME format
                published_at = video['snippet']['publishedAt']  # Example: "2025-02-09T10:59:26Z"
                published_at = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")

                data = {
                    'video_id': video['id'],
                    'channel_id': video['snippet']['channelId'],
                    'video_name': video['snippet']['title'],
                    'video_des': video['snippet']['description'],
                    'video_published': published_at,  # ✅ Now MySQL compatible
                    'view_count': video['statistics']['viewCount'],
                    'like_count': int(video['statistics'].get('likeCount', 0)),
                    'favorite_count': int(video['statistics'].get('favoriteCount', 0)),
                    'comment_count': int(video['statistics'].get('commentCount', 0)),
                    'duration': video['contentDetails']['duration'],
                    'thumbnail': video['snippet']['thumbnails']['default']['url'],
                    'caption_status': video['contentDetails']['caption']
                }
                video_data.append(data)
        except googleapiclient.errors.HttpError as e:
            print(f"Error fetching video data: {e}")

    if video_data:
        conn = mysql.connector.connect(host="localhost", database="my_database")
        if conn.is_connected():
            cursor = conn.cursor()
            for data in video_data:
                cursor.execute("""INSERT INTO videos 
                    (video_id, channel_id, video_name, video_des, video_published, view_count, like_count, favorite_count, comment_count, duration, thumbnail, caption_status)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", 
                    (data['video_id'], data['channel_id'], data['video_name'], data['video_des'], 
                    data['video_published'], data['view_count'], data['like_count'], 
                    data['favorite_count'], data['comment_count'], data['duration'], 
                    data['thumbnail'], data['caption_status']))
            conn.commit()
            cursor.close()
            conn.close()
    
    return pd.DataFrame(video_data)

def get_commant_data(channel_id):
    comments_data = []
    video_ids = get_playlist_video_id([channel_id])  # Ensure it's a list

    if not video_ids:
        print("No videos found for this channel.")  # Debugging step
        return pd.DataFrame()  # Return an empty DataFrame early

    for video_id in video_ids:
        try:
            request = youtube.commentThreads().list(
                part='snippet',
                videoId=video_id,
                maxResults=15  # Limit to 15 comments per video
            )
            response = request.execute()
            # print(f"API Response for Video {video_id}:", response)  # Debugging outputs

            for comment in response.get('items', []):
                published_at = comment['snippet']['topLevelComment']['snippet']['publishedAt']
                # ✅ Convert ISO 8601 to MySQL-compatible format
                published_at = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d %H:%M:%S")

                data = {
                    'comment_id': comment['id'],
                    'comment_text': comment['snippet']['topLevelComment']['snippet']['textDisplay'],
                    'comment_author': comment['snippet']['topLevelComment']['snippet']['authorDisplayName'],
                    'comment_published': published_at,  # ✅ Converted date format
                    'video_id': video_id,
                    'channel_id': channel_id
                }
                comments_data.append(data)

        except googleapiclient.errors.HttpError as e:
            print(f"Error fetching comments for video {video_id}: {e}")

    # ✅ Store comments in the database (optional)
    if comments_data:
        conn = mysql.connector.connect(host="localhost", database="my_database")
        if conn.is_connected():
            cursor = conn.cursor()
            for data in comments_data:
                cursor.execute("""INSERT INTO comments (comment_id, comment_text, comment_author, comment_published, video_id, channel_id)
                        VALUES (%s,%s,%s,%s,%s,%s)""",
                        (data['comment_id'], data['comment_text'], data['comment_author'], data['comment_published'], data['video_id'], data['channel_id']))
            conn.commit()
            cursor.close()
            conn.close()

    return pd.DataFrame(comments_data)

def get_db_data(query):
    mysqldb = mysql.connector.connect(host="localhost", database="my_database") # user="root", password="Yourmysql_password",
    df = pd.read_sql(query, mysqldb)
    mysqldb.close()
    return df

def get_queries(list_of_queries):
    queries = {
        "1. What are the names of all the videos and their corresponding channels?" :
          """SELECT channels.channel_name, videos.video_name  FROM  videos left JOIN channels on videos.channel_id = channels.channel_id;""", 
        "2. Which channels have the most number of videos, and how many videos do they have?":
          """select channels.channel_name, count(videos.video_id) as video_count from videos JOIN channels on videos.channel_id = channels.channel_id group by channel_name order by video_count Desc;""",
        "3. What are the top 10 most viewed videos and their respective channels?":
          """SELECT channels.channel_name, videos.video_name, videos.view_count FROM  videos  JOIN channels on videos.channel_id = channels.channel_id ORDER BY view_count DESC LIMIT 10;""",
        "4. How many comments were made on each video, and what are their corresponding video names?":
            """SELECT video_name, comment_count FROM videos order by comment_count desc;""",
        "5. Which videos have the highest number of likes, and what are their corresponding channel names?":
            """SELECT channels.channel_name, videos.video_name, videos.like_count  FROM videos join channels on videos.channel_id = channels.channel_id ORDER BY videos.like_count DESC;""",
        "6. What is the total number of likes and dislikes for each video, and what are their corresponding video names?":
            """SELECT video_name, SUM(view_count) as total_views, SUM(like_count) as total_likes  FROM videos GROUP BY video_name order by total_views desc;""",
        "7. What is the total number of views for each channel, and what are their corresponding channel names?":
            """SELECT channel_name, SUM(view_count) as total_views FROM channels GROUP BY channel_id order by total_views desc;""",
        "8. What are the names of all the channels that have published videos in the year 2024?":
            """SELECT DISTINCT channels.channel_name, videos.video_published FROM channels join videos on channels.channel_id = videos.channel_id WHERE EXTRACT(YEAR FROM video_published) = 2024;""",
        "9. What is the average duration of all videos in each channel, and what are their corresponding channel names?":
            """SELECT 
    channels.channel_name, 
    SEC_TO_TIME(
        AVG(
            COALESCE(
                (SUBSTRING_INDEX(SUBSTRING_INDEX(videos.duration, 'H', 1), 'T', -1) * 3600), 0
            ) + COALESCE(
                (SUBSTRING_INDEX(SUBSTRING_INDEX(videos.duration, 'M', 1), 'H', -1) * 60), 0
            ) + COALESCE(
                (SUBSTRING_INDEX(SUBSTRING_INDEX(videos.duration, 'S', 1), 'M', -1) * 1), 0
            )
        )
    ) AS avg_duration
FROM videos 
JOIN channels ON videos.channel_id = channels.channel_id 
GROUP BY channels.channel_name;""",
        "10. Which videos have the highest number of comments, and what are their corresponding channel names?":
            """SELECT 
    videos.video_name, 
    COUNT(comments.comment_id) AS comment_count, 
    channels.channel_name
FROM videos
JOIN comments ON comments.video_id = videos.video_id 
JOIN channels ON videos.channel_id = channels.channel_id 
GROUP BY videos.video_id, videos.video_name, channels.channel_name 
ORDER BY comment_count DESC;"""
        }
    return queries


# -------------------streamlit-------------------

# Comfiguring Streamlit GUI 
st.set_page_config(
    page_title="Mr.Paul's Youtube analysis", 
    page_icon="🥷", 
    layout="wide")

# Create a Streamlit UI
menu_options = ["Channel_info", "View Table", "List of queries"]
with st.sidebar:
    selected = option_menu(None, menu_options, 
        icons=['info', 'question', "list-task"], 
        menu_icon="cast", default_index=0, orientation="vertical")

if selected == menu_options[0]: 
    st.title("YouTube Channel Data")
    channel_id = st.text_input("Enter YouTube channel ID:")

    if st.button("Get Channel Data"):
        channel_data = get_channel_data(channel_id)
        channel_data.index +=1
        st.subheader("Channel Data")
        st.write(channel_data)

    if st.button("Get Video Data"):
        try:
            channel_ids = [channel_id]  # Convert to list
            video_ids = get_playlist_video_id(channel_ids) 
            print("Video IDs:", video_ids)  # Debugging output
            if not video_ids:
                st.error("No videos found for the given channel ID.")
            else:
                video_data = get_video_data(video_ids)  # ✅ Then, get video details
                video_data.index += 1
                st.subheader("Video Data")
                st.write(video_data)
        except Exception as e:
            st.error(f"Error: {e}")

    if st.button("Get Comments Data"):
        try:
            comment_data = get_commant_data(channel_id)   
            if not comment_data.empty:
                print("Comments retrieved:", comment_data)  # Debugging output
                st.write(comment_data)
            else:
                print("No comments retrieved.")  # Debugging output
                st.error("No comments found for the given Channel ID.")
        except Exception as e:
            st.error(f"Error: {e}")

if selected == menu_options[1]:
    st.title("Queries")
    list_of_queries = ["SELECT * FROM channels;", "SELECT * FROM videos;", "SELECT * FROM comments;"]
    st.header("Select a query to execute:")
    list_of_queries = st.selectbox("Queries", list_of_queries)
    st.write(get_db_data(list_of_queries))

if selected == menu_options[2]:
    st.title("List of queries")
    list_of_queries = [
        "1. What are the names of all the videos and their corresponding channels?",
        "2. Which channels have the most number of videos, and how many videos do they have?",
        "3. What are the top 10 most viewed videos and their respective channels?",
        "4. How many comments were made on each video, and what are their corresponding video names?",
        "5. Which videos have the highest number of likes, and what are their corresponding channel names?",
        "6. What is the total number of likes and dislikes for each video, and what are their corresponding video names?",
        "7. What is the total number of views for each channel, and what are their corresponding channel names?",
        "8. What are the names of all the channels that have published videos in the year 2024?",
        "9. What is the average duration of all videos in each channel, and what are their corresponding channel names?",
        "10. Which videos have the highest number of comments, and what are their corresponding channel names?"
    ]
    query = get_queries(list_of_queries)
    selected_query = st.selectbox("Queries", list(query.keys()))
    st.write(get_db_data(query[selected_query]))

# -------------------streamlit-------------------

#-------------------Table creation-------------------

# query = """SELECT * FROM channel;"""


#-------------------Table creation-------------------

# #       id int auto_increment primary key
# channels = """create table channels(
#         channel_id varchar(100) primary key,
#         channel_name varchar(100),
#         playlists varchar(100),
#         channel_type varchar(100),
#         channel_des text,
#         view_count int,
#         subscriber_count int,
#         video_count int
#         );"""
# #        id int auto_increment primary key,
# videos = """create table videos(
#         video_id varchar(100) primary key,
#         channel_id varchar(100),
#         video_name varchar(100),
#         video_des text,
#         video_published datetime,
#         view_count int,
#         like_count int,
#         favorite_count int,
#         comment_count int,
#         duration varchar(100),
#         thumbnail varchar(100),
#         caption_status varchar(100)
#         );"""
# #         id int auto_increment ,
# comments = """create table comments( 
#         comment_id varchar(100) primary key,
#         comment_text text,
#         comment_author varchar(100),
#         comment_published datetime,
#         video_id varchar(100),
#         channel_id varchar(100)
#         );"""
# def save_to_db(comments):
#     conn = mysql.connector.connect(host="localhost",database="my_database")
#     if conn.is_connected():
#         cursor = conn.cursor()
        
#         # Create table with modified column types
#         cursor.execute(comments)
#         print("Table created")
#         conn.commit()
#         cursor.close()
#         conn.close()
#         print("MySQL connection is closed")
    
# # save_to_db(comments)

# #-------------------Table creation-------------------



# print(get_channel_data("UC4JX40jDee_tINbkjycV4Sg"))
# print(get_channel_playlist("UC4JX40jDee_tINbkjycV4Sg"))
# print(get_video("PLzMcBGfZo4-lKuOp1lq_OToZloZEtXJuE"))
# print(get_video("UU4JX40jDee_tINbkjycV4Sg"))
# print(get_playlist_video_id("UC4JX40jDee_tINbkjycV4Sg"))

# video_ids = ['EqtOAGq5JbE', 'xKhEyAkB79A', 'zr7PpbRxq3c', 'EABFumsYHRc', 'woX0_KrGttE']

# print(get_video_data(video_ids))

# print(get_commant_data("UC4JX40jDee_tINbkjycV4Sg"))


# # Fetch channel data and save it to the database
# channel_data = get_channel_data("UCuxhTSKtnMJizinblLs9xOA")
# save_to_db(channel_data)

# # Create a Streamlit UI
# menu_options = ["Channel_info", "Queris", "Tasks", 'Settings']
# selected = option_menu(None, menu_options, 
#     icons=['info', 'question', "list-task", 'gear'], 
#     menu_icon="cast", default_index=0, orientation="horizontal")

# if selected == menu_options[0]: 
#     st.title("YouTube Channel Data")
#     channel_id = st.text_input("Enter YouTube channel ID:")
#     if st.button("Get Channel Data"):
#         try:
#             channel_data = get_channel_data(channel_id)
#             if channel_data:
#                 st.write("Channel Name:", channel_data['channel_name'])
#                 # st.write("Channel Description:", channel_data['channel_des'])
#                 st.write("View Count:", channel_data['view_count'])
#                 st.write("Subscriber Count:", channel_data['subscriber_count'])
#                 st.write("Video Count:", channel_data['video_count'])
#             else:
#                 st.error("Error: Invalid channel ID or API error")
#         except Exception as e:
#             st.error(f"Error: {e}")
# else:
#     st.title("YouTube Channel Data")  



#-------------------
# video:
# for item in playlist_videos:
#             video_id = item['snippet']['resourceId']['videoId']
#             video_response = youtube.videos().list(
#                 part='snippet,statistics,contentDetails',
#                 id=video_id
#             ).execute()

#             if video_response['items']:
#                 video_information = {
#                     "Video_Id": video_id,
#                     "Video_Name": video_response['items'][0]['snippet']['title'] if 'title' in video_response['items'][0]['snippet'] else "Not Available",
#                     "Video_Description": video_response['items'][0]['snippet']['description'],}

# commant:
# for comment in comments_response['items']:
#                       comment_information = {
#                           "Comment_Id": comment['snippet']['topLevelComment']['id'],
#                           "Comment_Text": comment['snippet']['topLevelComment']['snippet']['textDisplay'],
#                           "Comment_Author": comment['snippet']['topLevelComment']['snippet']['authorDisplayName'],
#                           "Comment_PublishedAt": comment['snippet']['topLevelComment']['snippet']['publishedAt']
#                       }
#                       video_information['Comments'][comment_information['Comment_Id']] = comment_information

#                   videos[video_id] = video_information

# video info:
# video_information = {
#                     "Video_Id": video_id,
#                     "Video_Name": video_response['items'][0]['snippet']['title'] 
#                     "Video_Description": video_response['items'][0]['snippet']['description'],
#                     "comment_information":{}
#                     }


# Example formar:
# # Example format : {
#                     "Channel_Name": {
#                         "Channel_Name": "Example Channel",
#                         "Channel_Id": "UC1234567890",
#                         "Subscription_Count": 10000,
#                         "Channel_Views": 1000000,
#                         "Channel_Description": "This is an example channel.",
#                         "Playlist_Id": "PL1234567890"
#                         },
#                     "Video_Id_1": {
#                         "Video_Id": "V1234567890",
#                         "Video_Name": "Example Video 1",
#                         "Video_Description": "This is an example video.",
#                         "Tags": ["example", "video"],
#                         "PublishedAt": "2022-01-01T00:00:00Z",
#                         "View_Count": 1000,
#                         "Like_Count": 100,
#                         "Dislike_Count": 10,
#                         "Favorite_Count": 5,
#                         "Comment_Count": 20,
#                         "Duration": "00:05:00",
#                         "Thumbnail": "https://example.com/thumbnail.jpg",
#                         "Caption_Status": "Available",
#                   "Comments": {
#                       "Comment_Id_1": {
#                           "Comment_Id": "C1234567890",
#                           "Comment_Text": "This is a comment.",
#                           "Comment_Author": "Example User",
#                           "Comment_PublishedAt": "2022-01-01T00:01:00Z"
#                       },
#                       "Comment_Id_2": {
#                           "Comment_Id": "C2345678901",
#                           "Comment_Text": "This is another comment.",
#                           "Comment_Author": "Another User",
#                           "Comment_PublishedAt": "2022-01-01T00:02:00Z"
#                       }
#                   }
#               },
