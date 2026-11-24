# pip install --upgrade --force-reinstall --no-cache-dir yt-dlp
import yt_dlp
import os
import time
import re


def safe_filename(name):
    # Remove illegal Windows characters
    return re.sub(r'[\\/:*?"<>|]', '', name).strip()


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
    urls = [u for u in urls if u and u.startswith("https://www.youtube.com/watch?v=")]
    if not urls:
        print("No valid URLs to download.")
        return

    os.makedirs(download_folder, exist_ok=True)

    # FIX: Use fallback format and handle missing JS runtime gracefully
    ydl_opts = {
        "format": "bestvideo+bestaudio/best",  # Fallback to any best format if mp4 not available
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(download_folder, "%(title)s [%(height)sp].%(ext)s"),
        # Add resolution number (e.g., 1080p, 720p) to filename
        "cookies_from_browser": "chrome",  # Change to "firefox", "edge", etc. if needed
        # js_runtimes as dict (yt-dlp 2024+), but will gracefully degrade if none installed
        "js_runtimes": {"deno": {}, "node": {}, "quickjs": {}},
        "retries": 3,
        "fragment_retries": 3,
        "ignore_no_formats_error": False,  # We'll handle this manually below
        "no_check_certificate": True,  # Sometimes helps with connection issues
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            result = ydl.download(urls)
            if result == 0:
                print(f"✅ Downloaded {len(urls)} videos to: {download_folder}")
            else:
                print(f"⚠️ Some downloads failed. Check logs above.")
        except yt_dlp.utils.DownloadError as e:
            err_str = str(e).lower()
            if "sign in to confirm" in err_str or "authentication" in err_str or "bot" in err_str:
                print(f"❌ YouTube requires authentication.")
                print(f"💡 SOLUTION 1: Keep Chrome OPEN and logged into YouTube, then re-run.")
                print(f"💡 SOLUTION 2: Export cookies.txt (see instructions below) and add to ydl_opts:")
                print(f'   "cookiefile": r"C:\\path\\to\\cookies.txt",')
            elif "no video formats found" in err_str or "no supported javascript runtime" in err_str:
                print(f"❌ Format extraction failed (likely missing JS runtime).")
                print(f"💡 QUICK FIX: Install Deno (takes 30 seconds):")
                print(f"   1. Open PowerShell as Admin")
                print(f"   2. Run: winget install --id Deno.Deno -e")
                print(f"   3. Restart PyCharm/terminal")
                print(f"💡 ALTERNATIVE: Use format 'best' instead of 'mp4/best' in ydl_opts")
            else:
                print(f"❌ Download error: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")


# ---------------------------------------------
# 2.5. Method to download transcripts only
# ---------------------------------------------
def download_transcripts_only(urls, download_folder=BASE_DOWNLOAD_FOLDER):
    """
    Download only transcripts (subtitles) for a list of YouTube URLs.
    Processes URLs one by one, and languages one by one to avoid errors if a language doesn't exist.
    """
    # Filter only valid YouTube video URLs
    urls = [u for u in urls if u and u.startswith("https://www.youtube.com/watch?v=")]
    if not urls:
        print("No valid URLs to download transcripts for.")
        return

    os.makedirs(download_folder, exist_ok=True)

    success_count = 0
    languages_to_try = ["ru", "en"]

    for index, url in enumerate(urls, start=1):
        print(f"\n[{index}/{len(urls)}] Processing transcript for: {url}")

        video_success = False
        for lang in languages_to_try:
            print(f"  -> Attempting to download '{lang}' transcript...")

            ydl_opts = {
                "skip_download": True,
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": [lang],  # Download ONE language at a time
                "subtitlesformat": "srt",  # Save as .srt format (can also use "vtt")
                "outtmpl": os.path.join(download_folder, f"%(title)s.{lang}.%(ext)s"),
                # Include lang in filename to prevent overwrites
                "cookies_from_browser": "chrome",
                "js_runtimes": {"deno": {}, "node": {}, "quickjs": {}},
                "retries": 3,
                "fragment_retries": 3,
                "no_check_certificate": True,
                "sleep_interval": 2,  # Add delay between internal requests to avoid rate limits
                "quiet": False,
            }

            max_retries = 3
            lang_success = False
            for attempt in range(1, max_retries + 1):
                try:
                    # Download one by one to prevent batch rate-limiting
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        result = ydl.download([url])
                        if result == 0:
                            print(f"  ✅ '{lang}' transcript downloaded successfully.")
                            lang_success = True
                            video_success = True
                            break
                        else:
                            raise Exception("Download returned error code")
                except Exception as e:
                    err_str = str(e).lower()

                    # Check if it's a "no subtitles" error to gracefully move to the next language
                    if "no subtitle" in err_str or "not found" in err_str or "unavailable" in err_str or "no subtitles for the requested languages" in err_str:
                        print(f"  ℹ️ '{lang}' transcript not available for this video. Moving to next language.")
                        break

                    if "429" in err_str or "too many requests" in err_str:
                        print(f"  ⚠️ HTTP 429 Too Many Requests (Attempt {attempt}/{max_retries}).")
                        if attempt < max_retries:
                            delay = 5 * attempt  # Exponential backoff: 5s, 10s, 15s
                            print(f"  💡 Waiting {delay} seconds before retrying '{lang}'...")
                            time.sleep(delay)
                        else:
                            print(
                                f"  ❌ Max retries reached for '{lang}' due to rate limiting. Moving to next language.")
                            break
                    elif "sign in to confirm" in err_str or "authentication" in err_str or "bot" in err_str:
                        print(f"  ❌ YouTube requires authentication.")
                        print(f"  💡 SOLUTION: Keep Chrome OPEN and logged into YouTube, or use cookiefile.")
                        break
                    elif "no video formats found" in err_str or "no supported javascript runtime" in err_str:
                        print(f"  ❌ Format extraction failed (likely missing JS runtime).")
                        print(f"  💡 QUICK FIX: Install Deno: winget install --id Deno.Deno -e")
                        break
                    else:
                        print(f"  ❌ Transcript download error for '{lang}': {e}")
                        break

        if video_success:
            success_count += 1

        # Add a deliberate delay between different videos to avoid triggering rate limits
        if index < len(urls):
            print("⏳ Waiting 3 seconds before next video to avoid rate limits...")
            time.sleep(3)

    print(
        f"\n✅ Finished. Successfully downloaded transcripts for {success_count}/{len(urls)} videos to: {download_folder}")


# ---------------------------------------------
# 3. Method to download entire playlist
# ---------------------------------------------
def download_playlist(playlist_url, base_folder=BASE_DOWNLOAD_FOLDER, retries=10, delay=12):
    """
    Download all videos in a YouTube playlist into a subfolder named after the playlist,
    prefixing filenames with a 3-digit code corresponding to their position.
    Retries each video several times with delay between attempts.
    """
    if not playlist_url.startswith("https://www.youtube.com/playlist?") and \
            "list=" not in playlist_url:
        print("Invalid playlist URL")
        return

    # Extract playlist info
    try:
        # ydl_opts = {"quiet": True, "extract_flat": True}
        ydl_opts = {
            "quiet": True,
            "extract_flat": "in_playlist",
            "skip_download": True,
            "cookies_from_browser": "chrome",  # Added for auth
            "js_runtimes": {"deno": {}, "node": {}, "quickjs": {}},  # FIXED: dict format
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
    except Exception as e:
        print(f"Failed to load playlist info: {e}")
        return

    # Playlist title as folder name
    playlist_title = info.get("title", "playlist")

    # safe_filename ensures special characters invalid in directory names are removed
    download_folder = os.path.join(base_folder, safe_filename(playlist_title))
    os.makedirs(download_folder, exist_ok=True)

    # Extract all video URLs
    urls = [entry["url"] for entry in info["entries"] if "url" in entry]

    # Download videos with 3-digit prefix
    for index, url in enumerate(urls, start=1):
        prefix = f"{index:03d}"

        ydl_opts = {
            "outtmpl": os.path.join(download_folder, f"{prefix} - %(title)s [%(height)sp].%(ext)s"),
            # Add resolution number (e.g., 1080p, 720p) to filename
            "quiet": False,
            "cookies_from_browser": "chrome",  # Added for auth
            "js_runtimes": {"deno": {}, "node": {}, "quickjs": {}},  # FIXED: dict format
            "format": "bestvideo+bestaudio/best",  # Fallback format
            "merge_output_format": "mp4",
            "retries": 3,
        }

        for attempt in range(1, retries + 1):
            try:
                print(f"\nDownloading ({index}/{len(urls)}): Attempt {attempt}/{retries}")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    result = ydl.download([url])
                    if result == 0:
                        print("✅ Download successful.")
                        break  # success → exit retry loop
                    else:
                        raise Exception("Download returned error code")
            except yt_dlp.utils.DownloadError as e:
                err_msg = str(e).lower()
                if "sign in" in err_msg or "authentication" in err_msg or "bot" in err_msg:
                    print(f"❌ Authentication required for video {index}. Skipping.")
                    break  # No point retrying auth errors
                elif "no video formats found" in err_msg or "javascript runtime" in err_msg:
                    print(f"❌ Format/JS runtime error for video {index}. Skipping.")
                    break
                print(f"⚠️ Error downloading video: {e}")

                if attempt < retries:
                    print(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                else:
                    print("❌ Max retries reached. Skipping video.\n")
            except Exception as e:
                print(f"⚠️ Unexpected error: {e}")
                if attempt == retries:
                    print("⏭️ Skipping video after unexpected error.\n")


# ---------------------------------------------
# 4. Example usage
# ---------------------------------------------
def download_transcripts_for_videos(search_requests, save_folder, max_videos=20):
    """
    Downloads transcripts for videos found in search requests.
    Identifies up to `max_videos` videos, downloads individual transcripts for EACH
    language separately (ru, en), handles missing languages gracefully, and creates
    a combined transcript file that includes every successfully downloaded language.
    Skips downloading if the transcript for a language already exists.
    """
    os.makedirs(save_folder, exist_ok=True)

    videos = []
    ydl_opts_extract = {
        "quiet": True,
        "extract_flat": True,
        "playlistend": max_videos,
        "cookies_from_browser": "chrome",
        "js_runtimes": {"deno": {}, "node": {}, "quickjs": {}},
    }

    print("Extracting video URLs from search requests...")
    with yt_dlp.YoutubeDL(ydl_opts_extract) as ydl:
        for req in search_requests:
            if not req.startswith("http"):
                req = f"ytsearch{max_videos}:{req}"

            try:
                info = ydl.extract_info(req, download=False)

                # Handle both playlist/search results (has "entries") and single video URLs
                if "entries" in info:
                    entries = info.get("entries", [])
                    for entry in entries:
                        if entry and "url" in entry:
                            videos.append({
                                "url": entry["url"],
                                "title": entry.get("title", "Unknown Title"),
                                "id": entry.get("id", "unknown_id")
                            })
                            if len(videos) >= max_videos:
                                break
                else:
                    if "url" in info:
                        videos.append({
                            "url": info["url"],
                            "title": info.get("title", "Unknown Title"),
                            "id": info.get("id", "unknown_id")
                        })
            except Exception as e:
                print(f"Error extracting info from {req}: {e}")

            if len(videos) >= max_videos:
                break

    # Remove duplicates while preserving order
    seen = set()
    unique_videos = []
    for v in videos:
        if v["url"] not in seen:
            seen.add(v["url"])
            unique_videos.append(v)

    unique_videos = unique_videos[:max_videos]
    print(f"Found {len(unique_videos)} unique videos to process.")

    languages_to_try = ["ru", "en"]
    combined_transcript_path = os.path.join(save_folder, "combined_transcript.txt")

    with open(combined_transcript_path, "w", encoding="utf-8") as combined_file:
        for index, video in enumerate(unique_videos, start=1):
            url = video["url"]
            title = video["title"]
            video_id = video["id"]
            safe_title = safe_filename(title)
            print(f"\n[{index}/{len(unique_videos)}] Processing transcript for: {safe_title}")

            # Collect transcripts for EVERY successfully downloaded language
            downloaded_transcripts = {}

            for lang in languages_to_try:
                print(f"  -> Checking '{lang}' transcript...")

                # Check if it already exists locally
                expected_path = os.path.join(save_folder, f"{safe_title}_{video_id}.{lang}.srt")
                resolved_path = expected_path

                if not os.path.exists(resolved_path):
                    # Fallback scan for variants like .en-orig.srt or if yt-dlp named it slightly differently
                    prefix = f"{safe_title}_{video_id}."
                    candidates = [f for f in os.listdir(save_folder)
                                  if f.startswith(prefix) and f.endswith(".srt") and f".{lang}" in f]
                    if candidates:
                        resolved_path = os.path.join(save_folder, candidates[0])

                if resolved_path and os.path.exists(resolved_path):
                    print(f"  ℹ️ '{lang}' transcript already exists. Loading from file.")
                    try:
                        with open(resolved_path, "r", encoding="utf-8") as f:
                            downloaded_transcripts[lang] = f.read()
                    except Exception as e:
                        print(f"  ⚠️ Error reading existing '{lang}' transcript: {e}")
                    continue  # Skip downloading since we already have it

                print(f"  -> Attempting to download '{lang}' transcript...")

                ydl_opts_sub = {
                    "skip_download": True,
                    "writesubtitles": True,
                    "writeautomaticsub": True,
                    "subtitleslangs": [lang],  # Download ONE language at a time
                    "subtitlesformat": "srt",
                    "outtmpl": os.path.join(save_folder, f"{safe_title}_{video_id}.%(ext)s"),
                    "cookies_from_browser": "chrome",
                    "js_runtimes": {"deno": {}, "node": {}, "quickjs": {}},
                    "retries": 3,
                    "fragment_retries": 3,
                    "no_check_certificate": True,
                    "quiet": True,
                    "no_warnings": True,
                }

                max_retries = 3
                for attempt in range(1, max_retries + 1):
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts_sub) as ydl:
                            ydl.download([url])

                        # Locate the file yt-dlp actually created.
                        resolved_path = expected_path
                        if not os.path.exists(resolved_path):
                            prefix = f"{safe_title}_{video_id}."
                            candidates = [f for f in os.listdir(save_folder)
                                          if f.startswith(prefix) and f.endswith(".srt") and f".{lang}" in f]
                            resolved_path = os.path.join(save_folder, candidates[0]) if candidates else None

                        if resolved_path and os.path.exists(resolved_path):
                            with open(resolved_path, "r", encoding="utf-8") as f:
                                downloaded_transcripts[lang] = f.read()
                            print(f"  ✅ '{lang}' transcript downloaded and saved individually.")
                        else:
                            print(f"  ℹ️ '{lang}' transcript not available for this video.")
                        break  # done with this language (success or missing) → next language

                    except Exception as e:
                        err_str = str(e).lower()

                        # Missing subtitles for this language → gracefully move on
                        if "no subtitle" in err_str or "not found" in err_str or "unavailable" in err_str or "no subtitles for the requested languages" in err_str:
                            print(f"  ℹ️ '{lang}' transcript not available for this video. Moving to next language.")
                            break

                        if "429" in err_str or "too many requests" in err_str:
                            print(f"  ⚠️ HTTP 429 Too Many Requests for '{lang}' (Attempt {attempt}/{max_retries}).")
                            if attempt < max_retries:
                                delay = 10 * attempt  # Exponential backoff: 10s, 20s, 30s
                                print(f"  💡 Waiting {delay} seconds before retrying '{lang}'...")
                                time.sleep(delay)
                            else:
                                print(
                                    f"  ❌ Max retries reached for '{lang}' due to rate limiting. Moving to next language.")
                                break
                        elif "sign in to confirm" in err_str or "authentication" in err_str or "bot" in err_str:
                            print(f"  ❌ YouTube requires authentication. Skipping '{lang}'.")
                            break
                        elif "no video formats found" in err_str or "no supported javascript runtime" in err_str:
                            print(f"  ❌ Format extraction failed (likely missing JS runtime). Skipping '{lang}'.")
                            break
                        else:
                            print(f"  ❌ Transcript download error for '{lang}': {e}")
                            break

                # Small pause between language requests for the same video
                time.sleep(2)

            # Write combined entry: include EVERY successfully downloaded language
            combined_file.write(f"video url: {url}\n")
            combined_file.write(f"video title: {title}\n")

            if downloaded_transcripts:
                for lang in languages_to_try:
                    if lang in downloaded_transcripts:
                        combined_file.write(f"transcript ({lang}):\n")
                        combined_file.write(downloaded_transcripts[lang].strip() + "\n\n")
            else:
                combined_file.write("No transcript available.\n")

            combined_file.write("=========================\n")

            # Deliberate delay between videos to avoid triggering rate limits
            if index < len(unique_videos):
                print("⏳ Waiting 5 seconds before next video to avoid rate limits...")
                time.sleep(5)

    print(f"\n✅ Finished. Combined transcript saved to: {combined_transcript_path}")


if __name__ == "__main__":
    # Download specific videos
    video_urls = [
        "https://www.youtube.com/watch?v=v4YTsdDXBKM",
        "https://www.youtube.com/watch?v=8hpSMnCwCxY",
    ]
    download_urls(video_urls)

    for playlist_url in [
        # "https://www.youtube.com/watch?v=JXBAkOvAu5A&list=PLE1NBPwaJdCDlp3RqO4tW3LzYw6nVtTv3",
        "",
        ""
    ]:
        if not playlist_url:
            continue
        download_playlist(playlist_url)

    # ---------------------------------------------
    # Loop over list for downloading transcripts only
    # ---------------------------------------------
    transcript_urls = [
        # "https://www.youtube.com/watch?v=jTDSP7KBavI"
    ]
    if transcript_urls:
        print("\n--- Starting Specific Transcript Downloads ---")
        download_transcripts_only(transcript_urls, os.path.join(BASE_DOWNLOAD_FOLDER, "transcripts"))

    # ---------------------------------------------
    # NEW: Parse search configs and download transcripts per category
    # ---------------------------------------------
    search_configs = [
        #"https://www.youtube.com/results?search_query=Python+Interview+&sp=EgIYAg%253D%253D|50|python",
        #"https://www.youtube.com/results?search_query=Data+Engineer+Interview+&sp=EgIYAg%253D%253D|60|date_engineering",
        #"https://www.youtube.com/results?search_query=Spark+Interview+&sp=EgIYAg%253D%253D|30|spark",
        #"https://www.youtube.com/results?search_query=Azure+Interview+&sp=EgIYAg%253D%253D|50|azure",
        #"https://www.youtube.com/results?search_query=Data+Modeling+Interview+&sp=EgIYAg%253D%253D|50|data_modeling",
        "https://www.youtube.com/results?search_query=dbt+Interview+&sp=EgIYAg%253D%253D|50|dbt",
        "https://www.youtube.com/results?search_query=Developer+soft+skills+Interview+&sp=EgIYAg%253D%253D|50|soft_skills",
        "https://www.youtube.com/results?search_query=Developer+Behavioral+Interview+&sp=EgIYAg%253D%253D|50|Developer",
        "https://www.youtube.com/results?search_query=running+large+ai+models+on+lessmempory+|50|ai_low_mem",
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

        target_folder = os.path.join(BASE_DOWNLOAD_FOLDER, "transcripts", folder_name)
        print(f"\nProcessing search: {search_url}")
        print(f"Target folder: {target_folder}")
        print(f"Max videos: {max_vids}")

        # Pass the search URL as a single-item list to the function
        download_transcripts_for_videos([search_url], target_folder, max_videos=max_vids)

# AI-103 DP-700 DP-600 DP-750 AI-300 AI-104