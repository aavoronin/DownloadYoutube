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
        "format": "best[ext=mp4]/best",  # Fallback to any best format if mp4 not available
        "outtmpl": os.path.join(download_folder, "%(title)s [%(height)sp].%(ext)s"),  # Add resolution number (e.g., 1080p, 720p) to filename
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
        #ydl_opts = {"quiet": True, "extract_flat": True}
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
            "outtmpl": os.path.join(download_folder, f"{prefix} - %(title)s [%(height)sp].%(ext)s"),  # Add resolution number (e.g., 1080p, 720p) to filename
            "quiet": False,
            "cookies_from_browser": "chrome",  # Added for auth
            "js_runtimes": {"deno": {}, "node": {}, "quickjs": {}},  # FIXED: dict format
            "format": "best[ext=mp4]/best",  # Fallback format
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
if __name__ == "__main__":
    # Download specific videos
    video_urls = [
        #"https://www.youtube.com/watch?v=TK6diOwY4_Y",
        #"https://www.youtube.com/watch?v=P3qmqUZJ7l0"
        #"https://www.youtube.com/watch?v=F7W0gJ3DQHU",
        #"https://www.youtube.com/watch?v=sSkAuTqfBA8",
        #"https://www.youtube.com/watch?v=QNdiGZFaUFs",
        #"https://www.youtube.com/watch?v=7pee6_Sq3VY",
        #"https://www.youtube.com/watch?v=PwQN8ewGDiY",
        #"https://www.youtube.com/watch?v=vqBagxnvcKY",
        #"https://www.youtube.com/watch?v=AhGUpgXyE98",
        #"https://www.youtube.com/watch?v=KsFxFNHF8LM",
        #"https://www.youtube.com/watch?v=kReKl74GDHs",
        #"https://www.youtube.com/watch?v=HS92M5ZD7To",
        #"https://www.youtube.com/watch?v=cuMwWvtNmJ0",
        #"https://www.youtube.com/watch?v=o7F-tbBl_hA",
        #"https://www.youtube.com/watch?v=uHRqkGXX55I",
        #"https://www.youtube.com/watch?v=csXmVBw8cdo",
        #"https://www.youtube.com/watch?v=IHZHujXKQb0",
        #"https://www.youtube.com/watch?v=c3jVBT6RHLU",
        #"https://www.youtube.com/watch?v=JT6ac43Nn0I",
        #"https://www.youtube.com/watch?v=4qRc3DXu19s",
        #"https://www.youtube.com/watch?v=A6l45B4Ffgc",
        #"https://www.youtube.com/watch?v=LpFzaPkHCqc",
        #"https://www.youtube.com/watch?v=TreQuklDBFM",
        #"https://www.youtube.com/watch?v=a-yuXz_uV30",
        "https://www.youtube.com/watch?v=01TJisrKhLs",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ]
    download_urls(video_urls)

    for playlist_url in [
        #"https://www.youtube.com/watch?v=wi3PkLK_gNc&list=PL0AYtrUw-NRRVVTnRf0yi0AW-DvtLkaT2",
        #"https://www.youtube.com/watch?v=enWiCb_h9kk&list=PLiUrl-SQRR7IxPyjKXYNQpcJsK13bg_zp",
        #"https://www.youtube.com/watch?v=j7USglwiwWc&list=PLyABYqulvUwZrQzaAVDYWRCrGYy1zj7CM",
        #"https://www.youtube.com/watch?v=j7USglwiwWc&list=PLL1ih-rtU13vcn73BFbQkP9t51MQy7mCy",
        #"https://www.youtube.com/watch?v=j7USglwiwWc&list=PLVHgQku8Z936K1rtxEJaBgrWolp282ayK",
        #"https://www.youtube.com/watch?list=PL5ZlXxM-0LTEfsuDfvh7QBRZI1gq5vWTo",
        #"https://www.youtube.com/watch?list=PLD7svyKaquTkJqKrJTc71V1ffNyZngck6",
        #"https://www.youtube.com/watch?list=PLiUrl-SQRR7IeC174R-WmpiQCB6uA_Ah0",
        #"https://www.youtube.com/watch?list=PLhLKc18P9YOAGdtSpB3y7WMkjJbi7dva_",
        #https://www.youtube.com/watch?list=PLS-oDvHudZ8awjshEFprtlM6W95ciMqHf",
        #"https://www.youtube.com/watch?lisst=PL0AYtrUw-NRQkrV0vscqAJvfvBnVwOP9_",
        "",
        "",
        "",
        "",
    ]:
        if not playlist_url:
            continue
        # Download a playlist into a subfolder with the playlist title
        #playlist_url = "https://www.youtube.com/playlist?list=PLWf6TEjiiuIAouvMboDNw8Uo3EN8O5-2n"
        #playlist_url = "https://www.youtube.com/playlist?list=PLWf6TEjiiuIAouvMboDNw8Uo3EN8O5-2n"
        download_playlist(playlist_url)