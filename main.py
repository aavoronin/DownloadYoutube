# pip install --upgrade --force-reinstall --no-cache-dir yt-dlp
import os
from project_to_file.project_to_file import project_to_file_main
from youtube_client import YouTubeClient

if __name__ == "__main__":
    project_to_file_main()

    yt_client = YouTubeClient()

    summary_urls = [
        "https://www.youtube.com/watch?v=rPGJhrunbxo"
    ]
    for url in summary_urls:
        yt_client.generate_video_summary(url, 2, None, None)

    # Download specific videos
    video_urls = [
        # "https://www.youtube.com/watch?v=v4YTsdDXBKM",
        # "https://www.youtube.com/watch?v=8hpSMnCwCxY",
        # "https://www.youtube.com/watch?v=uBWI-sniRt8",
        "https://www.youtube.com/watch?v=6tzQj4YyQyw",
        "https://www.youtube.com/watch?v=rPGJhrunbxo"
    ]
    yt_client.download_urls(video_urls)

    for playlist_url in [
        # "https://www.youtube.com/watch?v=JXBAkOvAu5A&list=PLE1NBPwaJdCDlp3RqO4tW3LzYw6nVtTv3",
        "",
        ""
    ]:
        if not playlist_url:
            continue
        yt_client.download_playlist(playlist_url)

    # ---------------------------------------------
    # Loop over list for downloading transcripts only
    # ---------------------------------------------
    transcript_urls = [
        # "https://www.youtube.com/watch?v=jTDSP7KBavI",
        # "https://www.youtube.com/watch?v=uBWI-sniRt8",
        "https://www.youtube.com/watch?v=6tzQj4YyQyw",
        "https://www.youtube.com/watch?v=rPGJhrunbxo"
    ]
    if transcript_urls:
        print("\n--- Starting Specific Transcript Downloads ---")
        yt_client.download_transcripts_only(transcript_urls,
                                            os.path.join(yt_client.base_download_folder, "transcripts"))

    # ---------------------------------------------
    # NEW: Parse search configs and download transcripts per category
    # ---------------------------------------------
    search_configs = [
        # "https://www.youtube.com/results?search_query=Python+Interview+&sp=EgIYAg%253D%253D|50|python",
        # "https://www.youtube.com/results?search_query=Data+Engineer+Interview+&sp=EgIYAg%253D%253D|60|date_engineering",
        # "https://www.youtube.com/results?search_query=Spark+Interview+&sp=EgIYAg%253D%253D|30|spark",
        # "https://www.youtube.com/results?search_query=Azure+Interview+&sp=EgIYAg%253D%253D|50|azure",
        # "https://www.youtube.com/results?search_query=Data+Modeling+Interview+&sp=EgIYAg%253D%253D|50|data_modeling",
        # "https://www.youtube.com/results?search_query=running+large+ai+models+on+lessmempory+|50|ai_low_mem",
        # "https://www.youtube.com/results?search_query=dbt+Interview+&sp=EgIYAg%253D%253D|50|dbt",
        # "https://www.youtube.com/results?search_query=Developer+soft+skills+Interview+&sp=EgIYAg%253D%253D|50|soft_skills",
        # https://www.youtube.com/results?search_query=Developer+Behavioral+Interview+&sp=EgIYAg%253D%253D|50|Developer",
        "",
        "",
    ]

    print("\n--- Starting Search & Transcript Downloads ---")
    for config in search_configs:
        # Ignore empty list elements
        if not config or not config.strip():
            continue

        # Parse the configuration string: "URL|max_videos|folder_name"
        parts = config.split("|")
        if len(parts) == 3:
            search_url = parts[0].strip()
            max_vids = int(parts[1].strip())
            folder_name = parts[2].strip()
        else:
            # Fallback for backward compatibility or malformed strings
            search_url = config.strip()
            max_vids = 50
            folder_name = "default"

        target_folder = os.path.join(yt_client.base_download_folder, "transcripts", folder_name)
        print(f"\nProcessing search: {search_url}")
        print(f"Target folder: {target_folder}")
        print(f"Max videos: {max_vids}")

        # Pass the search URL as a single-item list to the function
        yt_client.download_transcripts_for_videos([search_url], target_folder, max_videos=max_vids)

# AI-103 DP-700 DP-600 DP-750 AI-300 AI-104