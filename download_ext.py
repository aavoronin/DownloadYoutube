import yt_dlp
import os

# ---------------------------------------------
# 1. Base download folder
# ---------------------------------------------
BASE_DOWNLOAD_FOLDER = r"D:\youtube_downloads"  # Change to your preferred base folder
os.makedirs(BASE_DOWNLOAD_FOLDER, exist_ok=True)

# ---------------------------------------------
# 2. Method to download individual URLs
# ---------------------------------------------
def download_urls(urls, download_folder=BASE_DOWNLOAD_FOLDER):
    """
    Download a list of YouTube URLs to the specified folder.
    """
    # Filter only valid YouTube video URLs
    urls = [u for u in urls if u.startswith("https://www.youtube.com/watch?v=")]
    if not urls:
        print("No valid URLs to download.")
        return

    os.makedirs(download_folder, exist_ok=True)

    ydl_opts = {
        "format": "mp4/best",
        "outtmpl": os.path.join(download_folder, "%(title)s.%(ext)s"),
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download(urls)

    print(f"Downloaded {len(urls)} videos to: {download_folder}")


# ---------------------------------------------
# 3. Method to download entire playlist
# ---------------------------------------------
def download_playlist(playlist_url, base_folder=BASE_DOWNLOAD_FOLDER):
    """
    Download all videos in a YouTube playlist into a subfolder named after the playlist.
    """
    if not playlist_url.startswith("https://www.youtube.com/playlist?") and \
       "list=" not in playlist_url:
        print("Invalid playlist URL")
        return

    # Use yt-dlp to extract playlist info
    ydl_opts = {"quiet": True, "extract_flat": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)

    # Playlist title as folder name
    playlist_title = info.get("title", "playlist")
    download_folder = os.path.join(base_folder, playlist_title)
    os.makedirs(download_folder, exist_ok=True)

    # Extract all video URLs from the playlist
    urls = [entry["url"] for entry in info["entries"] if "url" in entry]

    # Download all videos
    download_urls(urls, download_folder)


# ---------------------------------------------
# 4. Example usage
# ---------------------------------------------
if __name__ == "__main__":
    # Download specific videos
    video_urls = [
        "https://www.youtube.com/watch?v=sSkAuTqfBA8",
        "https://www.youtube.com/watch?v=QNdiGZFaUFs",
        "https://www.youtube.com/watch?v=7pee6_Sq3VY",
    ]
    download_urls(video_urls)

    # Download a playlist into a subfolder with the playlist title
    playlist_url = "https://www.youtube.com/playlist?list=PLWf6TEjiiuIAouvMboDNw8Uo3EN8O5-2n"
    download_playlist(playlist_url)
