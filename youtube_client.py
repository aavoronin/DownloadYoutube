import yt_dlp
import os
import time
import re
import cv2
import numpy as np
import shutil
from PIL import Image, ImageDraw, ImageFont


def safe_filename(name):
    # Remove illegal Windows characters
    return re.sub(r'[\\/:*?"<>|]', '', name).strip()


# ---------------------------------------------
# Helper functions from the second project
# ---------------------------------------------
FRAME_SECONDS = 2.0
PRINT_EVERY_N_FRAMES = 50
USE_DECLARED_RATIOS = True

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\consola.ttf",
    r"C:\Windows\Fonts\times.ttf",
    r"C:\Windows\Fonts\calibri.ttf",
]


def parse_srt_file(srt_path: str):
    """Parse SRT/TXT subtitle file into list of (start_sec, end_sec, text) tuples."""
    print(f"DEBUG: Parsing subtitle file: {srt_path}")
    subtitles = []
    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"DEBUG: Read {len(content)} bytes from subtitle file.")
    except Exception as e:
        print(f"WARNING: Could not read subtitle file {srt_path}: {e}")
        return subtitles

    # Split by blank lines to get individual subtitle blocks
    blocks = re.split(r'\n\s*\n', content.strip())
    print(f"DEBUG: Found {len(blocks)} blocks in subtitle file.")

    for i, block in enumerate(blocks):
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue

        # Parse timestamp line (format: 00:00:00,800 --> 00:00:06,120)
        timestamp_line = lines[1].strip()
        match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', timestamp_line)
        if not match:
            continue

        start_str, end_str = match.groups()

        def parse_timestamp(ts):
            h, m, rest = ts.split(':')
            s, ms = rest.split(',')
            return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

        start_sec = parse_timestamp(start_str)
        end_sec = parse_timestamp(end_str)

        # Text is everything after the timestamp line
        text = ' '.join(line.strip() for line in lines[2:] if line.strip())

        if text:
            subtitles.append((start_sec, end_sec, text))
            if i < 5:  # Print first 5 parsed entries for verification
                print(f"DEBUG: Parsed subtitle {i}: {start_sec:.2f}s --> {end_sec:.2f}s : '{text[:60]}...'")

    # Sort by start time
    subtitles.sort(key=lambda x: x[0])
    print(f"DEBUG: Successfully parsed {len(subtitles)} subtitle entries.")
    return subtitles


def get_subtitles_for_interval(subtitles, t_start, t_end):
    """Get all subtitle texts that intersect with the time interval [t_start, t_end].
    Concatenate them with space."""
    texts = []
    for sub_start, sub_end, text in subtitles:
        # Intersection: subtitle overlaps with interval
        if sub_start < t_end and sub_end > t_start:
            texts.append(text)
    return ' '.join(texts)


def find_font_path():
    """Find a suitable font file that supports Cyrillic."""
    for font_path in FONT_CANDIDATES:
        if os.path.isfile(font_path):
            print(f"DEBUG: Found valid font at: {font_path}")
            return font_path
    print("WARNING: No suitable font found in candidates. Subtitles will NOT be rendered.")
    return None


def find_max_font_size(text, max_width, max_height, font_path, padding=4):
    """Binary search for the maximum font size that fits the text within the given area."""
    if not text:
        return 10

    available_width = max_width - 2 * padding
    available_height = max_height - 2 * padding

    if available_width <= 0 or available_height <= 0:
        return 10

    lo, hi = 8, 300
    best_size = 10

    while lo <= hi:
        mid = (lo + hi) // 2
        try:
            font = ImageFont.truetype(font_path, mid)
        except Exception:
            hi = mid - 1
            continue

        words = text.split()
        lines = []
        current_line = []

        for word in words:
            test_line = ' '.join(current_line + [word])
            try:
                left, top, right, bottom = font.getbbox(test_line)
                line_width = right - left
            except Exception:
                # Fallback for older Pillow versions
                line_width = font.getsize(test_line)[0]

            if line_width <= available_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]

        if current_line:
            lines.append(' '.join(current_line))

        if not lines:
            lines = [text]

        # Calculate total height
        try:
            _, top, _, bottom = font.getbbox("Ay")
            line_height = (bottom - top) * 1.2
        except Exception:
            line_height = mid * 1.2

        total_height = len(lines) * line_height

        # Check if fits
        if total_height <= available_height:
            fits = True
            for line in lines:
                try:
                    left, top, right, bottom = font.getbbox(line)
                    line_width = right - left
                except Exception:
                    line_width = font.getsize(line)[0]
                if line_width > available_width:
                    fits = False
                    break

            if fits:
                best_size = mid
                lo = mid + 1
            else:
                hi = mid - 1
        else:
            hi = mid - 1

    return best_size


def render_frame_with_subtitles(video_frame, subtitle_text, tw, th, font_path):
    """Render video frame with subtitles in the bottom 20%."""
    print(f"DEBUG render: tw={tw}, th={th}, text='{subtitle_text[:50]}...'")

    if not subtitle_text:
        return cv2.resize(video_frame, (tw, th), interpolation=cv2.INTER_LINEAR)

    # Create output frame
    output = np.zeros((th, tw, 3), dtype=np.uint8)

    # Top 80% for video
    video_height = int(th * 0.8)
    resized_video = cv2.resize(video_frame, (tw, video_height), interpolation=cv2.INTER_LINEAR)
    output[0:video_height, :] = resized_video

    # Bottom 20% for subtitles (white background)
    subtitle_height = th - video_height
    output[video_height:th, :] = 255  # White background (BGR: 255, 255, 255)

    if subtitle_text and font_path:
        try:
            # Convert BGR to RGB for PIL
            output_rgb = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(output_rgb)
            draw = ImageDraw.Draw(pil_img)

            # Find max font size
            font_size = find_max_font_size(subtitle_text, tw, subtitle_height, font_path, padding=8)
            print(f"DEBUG render: Calculated font size: {font_size}")
            font = ImageFont.truetype(font_path, font_size)

            # Wrap text
            words = subtitle_text.split()
            lines = []
            current_line = []
            available_width = tw - 16

            for word in words:
                test_line = ' '.join(current_line + [word])
                try:
                    left, top, right, bottom = font.getbbox(test_line)
                    line_width = right - left
                except Exception:
                    line_width = font.getsize(test_line)[0]

                if line_width <= available_width:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [word]

            if current_line:
                lines.append(' '.join(current_line))

            if not lines:
                lines = [subtitle_text]

            # Calculate total text height
            try:
                _, top, _, bottom = font.getbbox("Ay")
                line_height = (bottom - top) * 1.2
            except Exception:
                line_height = font_size * 1.2

            total_height = len(lines) * line_height

            # Center text vertically in the subtitle area
            y_start = video_height + (subtitle_height - total_height) // 2

            # Draw each line centered horizontally
            for i, line in enumerate(lines):
                try:
                    left, top, right, bottom = font.getbbox(line)
                    line_width = right - left
                except Exception:
                    line_width = font.getsize(line)[0]

                x = (tw - line_width) // 2
                y = int(y_start + i * line_height)
                # Black text (0, 0, 0) on White background
                draw.text((x, y), line, fill=(0, 0, 0), font=font)
                print(f"DEBUG render: Drew line '{line}' at x={x}, y={y}")

            # Convert back to BGR
            output = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            print("DEBUG render: Subtitle rendered successfully to frame.")
        except Exception as e:
            print(f"WARNING: Could not render subtitles: {e}")
            import traceback
            traceback.print_exc()

    return output


def format_timestamp(seconds: float) -> str:
    """float seconds -> HH:MM:SS.sss"""
    ms_total = int(round(max(0.0, seconds) * 1000.0))
    hours, ms_total = divmod(ms_total, 3_600_000)
    minutes, ms_total = divmod(ms_total, 60_000)
    secs, ms = divmod(ms_total, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


def choose_target_size(w: int, h: int, target_size=None):
    """Pick target size. If target_size provided, use it based on orientation."""
    if target_size is not None:
        if w > h:  # horizontal
            tw = target_size
            th = round(target_size * h / w)
        elif h > w:  # vertical
            th = target_size
            tw = round(target_size * w / h)
        else:  # square
            tw = target_size
            th = target_size

        # Ensure even dimensions for video encoding
        tw = tw + (tw % 2)
        th = th + (th % 2)

        return (tw, th), f"custom {tw}x{th}", w / h

    # If target_size is None, keep original dimensions.
    # render_frame_with_subtitles will add space for subtitles in the bottom 20%
    # without changing the width of the video.
    tw = w + (w % 2)
    th = h + (h % 2)
    return (tw, th), "original", w / h


def process_video(input_path: str, frame_seconds: float = FRAME_SECONDS, target_size=None, subtitle_path=None,
                  output_name: str = None) -> None:
    print("=" * 78)
    print(f"Input : {input_path}")
    if target_size is not None:
        print(f"Target size override: {target_size}")
    if subtitle_path is not None:
        print(f"Subtitle file: {subtitle_path}")

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print(f"Error: Could not open {input_path}")
        return

    try:
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if fps <= 0:
            fps = 30.0
            print("Warning: source FPS unknown - assuming 30.0")

        duration = total_frames / fps if fps > 0 else 0.0

        (tw, th), ratio_name, src_ratio = choose_target_size(w, h, target_size)
        out_fps = max(1, int(round(1.0 / frame_seconds)))
        repeat_count = max(1, round(frame_seconds * out_fps))

        print(f"Size  : {w}x{h} (ratio {src_ratio:.4f}) -> {tw}x{th} [{ratio_name}]")
        print(f"Source: fps={fps:.6f}  duration={format_timestamp(duration)}  frames={total_frames}")
        print(f"Output: fps={out_fps}  slide length={frame_seconds}s  repeat={repeat_count}x")
        print("-" * 78)

        # Parse subtitles if provided
        subtitles = []
        if subtitle_path:
            subtitles = parse_srt_file(subtitle_path)
            print(f"DEBUG: Loaded {len(subtitles)} subtitle entries")
        else:
            print("DEBUG: No subtitle path provided or file not found.")

        font_path = find_font_path()
        if subtitles and not font_path:
            print("WARNING: Subtitles exist but no font found. They will be skipped.")
        elif font_path:
            print(f"DEBUG: Using font for rendering: {font_path}")

        out_dir = os.path.dirname(input_path)
        base = os.path.splitext(os.path.basename(input_path))[0]
        if output_name:
            final_output_path = os.path.join(out_dir, output_name)
        else:
            final_output_path = os.path.join(out_dir, base + "_short.mp4")

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(final_output_path, fourcc, out_fps, (tw, th))

        if not writer.isOpened():
            print("Error: Could not open video writer")
            return

        # Calculate target frame indices for sampling
        target_frame_indices = [0]
        next_target_time = frame_seconds
        frame_idx = 0

        while frame_idx < total_frames:
            t = frame_idx / fps
            if t + 1e-6 >= next_target_time:
                target_frame_indices.append(frame_idx)
                next_target_time += frame_seconds
            frame_idx += 1

        if total_frames > 0 and target_frame_indices[-1] != total_frames - 1:
            target_frame_indices.append(total_frames - 1)

        print(f"Extracting {len(target_frame_indices)} frames...")

        # Extract and write frames
        for i, target_idx in enumerate(target_frame_indices):
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
            ret, frame = cap.read()

            if not ret:
                print(f"Warning: Could not read frame {target_idx}")
                continue

            # Get subtitle text for this frame's interval
            t_current = target_idx / fps
            t_next = t_current + frame_seconds
            subtitle_text = ""
            if subtitles:
                subtitle_text = get_subtitles_for_interval(subtitles, t_current, t_next)

            # Print first 10 frames' subtitle status for debugging
            if i < 10:
                print(
                    f"DEBUG: Frame {i} (t={t_current:.2f} to {t_next:.2f}) -> subtitle_text: '{subtitle_text[:80]}...'")

            # Render frame with subtitles
            if subtitle_text and font_path:
                print(f"DEBUG: Rendering frame {i} with subtitles...")
                resized = render_frame_with_subtitles(frame, subtitle_text, tw, th, font_path)
            else:
                if subtitles and not subtitle_text:
                    pass  # Silent, normal for gaps
                elif subtitles and not font_path:
                    print("DEBUG: Skipping subtitle render because font_path is None")

                resized = cv2.resize(frame, (tw, th), interpolation=cv2.INTER_LINEAR)

            for _ in range(repeat_count):
                writer.write(resized)

            if i % PRINT_EVERY_N_FRAMES == 0:
                t = target_idx / fps
                print(f"{format_timestamp(t)} {target_idx}", flush=True)

        writer.release()
        cap.release()

        print("-" * 78)
        print(f"Saved : {final_output_path}")
        print(f"Output duration: {format_timestamp(len(target_frame_indices) * frame_seconds)}")

    except Exception as e:
        print(f"Error processing {input_path}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'cap' in locals():
            cap.release()
        if 'writer' in locals():
            writer.release()


# ---------------------------------------------
# YouTube Client Class
# ---------------------------------------------
class YouTubeClient:
    def __init__(self, base_download_folder=r"D:\youtube_downloads"):
        self.base_download_folder = base_download_folder
        os.makedirs(self.base_download_folder, exist_ok=True)

    # ---------------------------------------------
    # 2. Method to download individual URLs
    # ---------------------------------------------
    def download_urls(self, urls, download_folder=None):
        if download_folder is None:
            download_folder = self.base_download_folder

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
    def download_transcripts_only(self, urls, download_folder=None):
        if download_folder is None:
            download_folder = self.base_download_folder

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
    def download_playlist(self, playlist_url, base_folder=None, retries=10, delay=12):
        if base_folder is None:
            base_folder = self.base_download_folder

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
    def download_transcripts_for_videos(self, search_requests, save_folder, max_videos=20):
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
                                print(
                                    f"  ℹ️ '{lang}' transcript not available for this video. Moving to next language.")
                                break

                            if "429" in err_str or "too many requests" in err_str:
                                print(
                                    f"  ⚠️ HTTP 429 Too Many Requests for '{lang}' (Attempt {attempt}/{max_retries}).")
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

    # ---------------------------------------------
    # 5. Method to generate video summary with subtitles
    # ---------------------------------------------
    def generate_video_summary(
            self,
            url: str,
            frame_seconds: float = FRAME_SECONDS,
            output_path: str = None,
            target_size: int = None,
            priority_language: str = "ru"
    ):
        """
        Downloads video and transcripts, then generates a summarized video
        with subtitles using the specified frame_seconds and target_size.
        Relies on download_urls and download_transcripts_only to handle downloads.
        """
        print(f"Starting video summary generation for: {url}")

        # 1. Get video info to determine filenames
        ydl_opts_info = {
            "quiet": True,
            "extract_flat": False,
            "cookies_from_browser": "chrome",
            "js_runtimes": {"deno": {}, "node": {}, "quickjs": {}},
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            print(f"❌ Failed to extract video info: {e}")
            return

        title = info.get("title", "video")
        video_id = info.get("id", "unknown")
        safe_title = safe_filename(title)

        # 2. Download video using existing method (handles resume/skip if exists)
        self.download_urls([url], self.base_download_folder)

        # 3. Download transcripts into the SAME folder as the video
        # This method attempts to download all supported languages independently
        self.download_transcripts_only([url], self.base_download_folder)

        # 4. Identify what transcripts were actually downloaded
        found_lang = None
        transcript_path = None

        # Check priority language first
        if priority_language:
            for f in os.listdir(self.base_download_folder):
                if f.startswith(safe_title) and f".{priority_language}" in f and f.endswith(".srt"):
                    transcript_path = os.path.join(self.base_download_folder, f)
                    found_lang = priority_language
                    break

        # If priority language was not downloaded, check the other supported language
        if not found_lang:
            other_lang = "en" if priority_language == "ru" else "ru"
            for f in os.listdir(self.base_download_folder):
                if f.startswith(safe_title) and f".{other_lang}" in f and f.endswith(".srt"):
                    transcript_path = os.path.join(self.base_download_folder, f)
                    found_lang = other_lang
                    break

        if found_lang:
            print(f"✅ Using '{found_lang}' transcript at: {transcript_path}")
        else:
            print("⚠️ No transcripts found or downloaded. Proceeding without subtitles.")

        # 5. Locate the downloaded video file
        video_path = None
        for f in os.listdir(self.base_download_folder):
            if f.startswith(safe_title) and (f.endswith(".mp4") or f.endswith(".mkv") or f.endswith(".webm")):
                video_path = os.path.join(self.base_download_folder, f)
                break

        if not video_path or not os.path.exists(video_path):
            print("❌ Could not find downloaded video file.")
            return

        print(f"✅ Video ready at: {video_path}")

        # 6. Create processed video
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        size_str = str(target_size) if target_size is not None else "orig"
        output_name = f"{base_name}_short_{found_lang if found_lang else 'no_sub'}_{size_str}.mp4"
        temp_output_path = os.path.join(self.base_download_folder, output_name)

        print(f"Processing video to: {temp_output_path}")
        process_video(
            input_path=video_path,
            frame_seconds=frame_seconds,
            target_size=target_size,
            subtitle_path=transcript_path,
            output_name=output_name
        )

        # 7. Move to optional output path
        if output_path and os.path.exists(temp_output_path):
            if os.path.isdir(output_path):
                final_dest = os.path.join(output_path, output_name)
            else:
                final_dest = output_path

            try:
                shutil.move(temp_output_path, final_dest)
                print(f"✅ Moved processed video to: {final_dest}")
            except Exception as e:
                print(f"❌ Failed to move video: {e}")