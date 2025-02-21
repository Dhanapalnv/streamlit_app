# YouTube Channel Data Extraction

This project is a Streamlit web application that interacts with the YouTube API to fetch and store channel, video, and comment data in a MySQL database. Users can retrieve, store, and query YouTube channel data efficiently.

## Features

- Fetch channel details from YouTube API.
- Store channel, video, and comment data in a MySQL database.
- Retrieve and display stored data.
- Perform predefined SQL queries to analyze video and channel data.

## Technologies Used

- Python
- Streamlit
- YouTube Data API
- MySQL
- Pandas
- NumPy

## Installation

### Prerequisites

Ensure you have Python installed along with the required libraries.

### Clone the Repository

```bash
git clone <repository-url>
cd <repository-folder>
```

### Install Required Packages

```bash
pip install streamlit pandas numpy mysql-connector-python google-api-python-client streamlit-option-menu
```

## Setup

### Configure YouTube API Key

Replace `api_key` in the script with your actual YouTube API key.

```python
api_key = "your_api_key_here"
youtube = googleapiclient.discovery.build("youtube", "v3", developerKey=api_key)
```

### Setup MySQL Database

Ensure MySQL is installed and running. Create a database and required tables:

```sql
CREATE DATABASE my_database;
USE my_database;

CREATE TABLE channels (
    channel_id VARCHAR(255) PRIMARY KEY,
    channel_name VARCHAR(255),
    playlists VARCHAR(255),
    channel_type VARCHAR(255),
    channel_des TEXT,
    view_count INT,
    subscriber_count INT,
    video_count INT
);

CREATE TABLE videos (
    video_id VARCHAR(255) PRIMARY KEY,
    channel_id VARCHAR(255),
    video_name VARCHAR(255),
    video_des TEXT,
    video_published DATETIME,
    view_count INT,
    like_count INT,
    favorite_count INT,
    comment_count INT,
    duration VARCHAR(255),
    thumbnail VARCHAR(255),
    caption_status VARCHAR(255),
    FOREIGN KEY (channel_id) REFERENCES channels(channel_id)
);

CREATE TABLE comments (
    comment_id VARCHAR(255) PRIMARY KEY,
    comment_text TEXT,
    comment_author VARCHAR(255),
    comment_published DATETIME,
    video_id VARCHAR(255),
    channel_id VARCHAR(255),
    FOREIGN KEY (video_id) REFERENCES videos(video_id),
    FOREIGN KEY (channel_id) REFERENCES channels(channel_id)
);
```

## Running the Application

```bash
streamlit run app.py
```

## Usage

1. Enter a YouTube channel ID to fetch and store data.
2. Retrieve stored video and comment data.
3. Execute SQL queries to analyze video trends.

## Query Options

- Retrieve all video names and their channels.
- Identify channels with the most videos.
- Find the most viewed videos.
- Count comments per video.
- List videos with the highest likes.
- Compute total likes per video.
- Aggregate total views per channel.
- List channels with videos published in 2024.
- Calculate average video duration per channel.
- Identify videos with the highest comments.

## Author
Dhanapal N

## License

MIT License



