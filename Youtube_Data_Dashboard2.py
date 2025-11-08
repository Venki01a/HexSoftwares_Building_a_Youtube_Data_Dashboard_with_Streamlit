import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pandas as pd
import plotly.express as px
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# ----------------------------
# 🎯 PAGE CONFIGURATION
# ----------------------------
st.set_page_config(page_title="🎥 YouTube Data Dashboard", layout="wide")
st.title("📊 YouTube Data Dashboard")
st.markdown("### Analyze any YouTube Channel by typing its name or handle!")

# ----------------------------
# 🔑 API CONFIGURATION
# ----------------------------
API_KEY = st.text_input("🔐 Enter your YouTube Data API Key:", type="password")

if API_KEY:
    try:
        youtube = build("youtube", "v3", developerKey=API_KEY)
        st.success("✅ API key authenticated successfully.")
    except Exception as e:
        st.error(f"❌ Error connecting to API: {e}")
        st.stop()
else:
    st.info("Enter your YouTube API key above to start.")
    st.stop()

# ----------------------------
# 🔍 FUNCTION: Get Channel ID from name or handle
# ----------------------------
def get_channel_id_from_name(youtube, name):
    try:
        request = youtube.search().list(
            part="snippet",
            q=name,
            type="channel",
            maxResults=1
        )
        response = request.execute()
        if response.get("items"):
            return response["items"][0]["snippet"]["channelId"]
        else:
            return None
    except HttpError as e:
        st.error(f"API Error: {e}")
        return None

# ----------------------------
# 📊 FUNCTION: Get Channel Stats
# ----------------------------
def get_channel_stats(youtube, channel_id):
    try:
        request = youtube.channels().list(
            part="snippet,contentDetails,statistics",
            id=channel_id
        )
        response = request.execute()

        if not response.get("items"):
            return None

        item = response["items"][0]
        data = {
            "Channel_Name": item["snippet"]["title"],
            "Description": item["snippet"]["description"],
            "Subscribers": int(item["statistics"].get("subscriberCount", 0)),
            "Total_Views": int(item["statistics"].get("viewCount", 0)),
            "Total_Videos": int(item["statistics"].get("videoCount", 0)),
            "Playlist_ID": item["contentDetails"]["relatedPlaylists"]["uploads"]
        }
        return data
    except HttpError as e:
        st.error(f"Error fetching channel stats: {e}")
        return None

# ----------------------------
# 🎥 FUNCTION: Get Videos from Uploads Playlist
# ----------------------------
def get_videos(youtube, playlist_id, max_results=20):
    videos = []
    try:
        request = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=max_results
        )
        response = request.execute()

        for item in response["items"]:
            video_title = item["snippet"]["title"]
            video_id = item["contentDetails"]["videoId"]
            videos.append({
                "Video_Title": video_title,
                "Video_ID": video_id,
                "Video_URL": f"https://www.youtube.com/watch?v={video_id}"
            })
        return videos
    except Exception as e:
        st.error(f"Error fetching videos: {e}")
        return []

# ----------------------------
# 📈 FUNCTION: Get Video Statistics
# ----------------------------
def get_video_stats(youtube, video_ids):
    stats = []
    try:
        for i in range(0, len(video_ids), 50):
            request = youtube.videos().list(
                part="snippet,statistics",
                id=",".join(video_ids[i:i + 50])
            )
            response = request.execute()
            for item in response["items"]:
                stats.append({
                    "Video_Title": item["snippet"]["title"],
                    "Views": int(item["statistics"].get("viewCount", 0)),
                    "Likes": int(item["statistics"].get("likeCount", 0)),
                    "Comments": int(item["statistics"].get("commentCount", 0))
                })
        return pd.DataFrame(stats)
    except Exception as e:
        st.error(f"Error fetching video stats: {e}")
        return pd.DataFrame()

# ----------------------------
# 📄 FUNCTION: Generate PDF Report
# ----------------------------
def generate_pdf_report(channel_info, df):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 50, "📊 YouTube Channel Report")

    c.setFont("Helvetica", 12)
    y = height - 100
    for key, value in channel_info.items():
        if key != "Playlist_ID":
            c.drawString(50, y, f"{key}: {value}")
            y -= 20

    y -= 20
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Video Performance Summary")
    y -= 30

    for _, row in df.iterrows():
        c.setFont("Helvetica", 10)
        c.drawString(50, y, f"{row['Video_Title'][:70]}")
        c.drawString(60, y - 12, f"Views: {row['Views']:,} | Likes: {row['Likes']:,} | Comments: {row['Comments']:,}")
        y -= 30
        if y < 100:
            c.showPage()
            y = height - 50

    c.save()
    buffer.seek(0)
    return buffer

# ----------------------------
# 🧭 SIDEBAR INPUT
# ----------------------------
st.sidebar.header("🔍 Channel Search")
channel_name = st.sidebar.text_input("Enter YouTube Channel Name or @handle:")

if channel_name:
    with st.spinner("Fetching Channel ID..."):
        channel_id = get_channel_id_from_name(youtube, channel_name)

    if not channel_id:
        st.error("❌ Channel not found. Please check the spelling or try another name.")
    else:
        st.success(f"✅ Channel found! ID: `{channel_id}`")

        # Fetch channel stats
        channel_info = get_channel_stats(youtube, channel_id)

        if channel_info:
            st.subheader(f"📺 Channel: {channel_info['Channel_Name']}")
            st.write(channel_info["Description"])

            col1, col2, col3 = st.columns(3)
            col1.metric("Subscribers", f"{channel_info['Subscribers']:,}")
            col2.metric("Total Views", f"{channel_info['Total_Views']:,}")
            col3.metric("Total Videos", f"{channel_info['Total_Videos']:,}")

            # Fetch videos
            videos = get_videos(youtube, channel_info["Playlist_ID"])
            if videos:
                df_videos = pd.DataFrame(videos)
                st.write("### 🎬 Latest Videos")
                st.dataframe(df_videos)

                # Fetch stats for those videos
                video_ids = [v["Video_ID"] for v in videos]
                video_stats_df = get_video_stats(youtube, video_ids)

                if not video_stats_df.empty:
                    st.write("### 📊 Video Performance Analytics")

                    tab1, tab2 = st.tabs(["Views vs Likes", "Views vs Comments"])

                    with tab1:
                        fig1 = px.bar(video_stats_df, x="Video_Title", y=["Views", "Likes"],
                                      barmode="group", title="Views vs Likes")
                        st.plotly_chart(fig1, use_container_width=True)

                    with tab2:
                        fig2 = px.bar(video_stats_df, x="Video_Title", y=["Views", "Comments"],
                                      barmode="group", title="Views vs Comments")
                        st.plotly_chart(fig2, use_container_width=True)

                    # 📥 Download Reports Section
                    st.subheader("📥 Download Reports")
                    csv = video_stats_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="⬇️ Download CSV Report",
                        data=csv,
                        file_name=f"{channel_info['Channel_Name']}_YouTube_Report.csv",
                        mime="text/csv"
                    )

                    pdf_buffer = generate_pdf_report(channel_info, video_stats_df)
                    st.download_button(
                        label="📄 Download PDF Report",
                        data=pdf_buffer,
                        file_name=f"{channel_info['Channel_Name']}_YouTube_Report.pdf",
                        mime="application/pdf"
                    )
                else:
                    st.warning("No detailed video stats available.")
        else:
            st.error("❌ Could not fetch channel statistics.")
