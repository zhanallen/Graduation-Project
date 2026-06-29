import os
import sys
import re
import imageio_ffmpeg
import yt_dlp
import pyinstaller_utils
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QListWidget, QListWidgetItem,
    QProgressBar, QFileDialog, QMessageBox, QFrame, QGroupBox,
    QComboBox, QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont

# Mapping of language codes to display names with flag emojis
LANGUAGE_MAP = {
    'de-DE': '🇩🇪 Deutsch (German)',
    'en-US': '🇺🇸 English (United States)',
    'es-US': '🇪🇸 Español (Spanish - US)',
    'fr-FR': '🇫🇷 Français (French)',
    'hi': '🇮🇳 हिन्दी (Hindi)',
    'id': '🇮🇩 Bahasa Indonesia (Indonesian)',
    'it': '🇮🇹 Italiano (Italian)',
    'ja': '🇯🇵 日本語 (Japanese)',
    'ml': '🇮🇳 Malayalam (Malayalam)',
    'pl': '🇵🇱 Polski (Polish)',
    'pt-BR': '🇧🇷 Português (Portuguese - Brazil)',
    'uk': '🇺🇦 Українська (Ukrainian)',
}

class FetchInfoThread(QThread):
    info_signal = Signal(dict)
    error_signal = Signal(str)
    
    def __init__(self, url):
        super().__init__()
        self.url = url
        
    def run(self):
        try:
            node_path = pyinstaller_utils.get_node_path()
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'audio_multistreams': True,
                'js_runtimes': {
                    'node': {'path': node_path} if node_path != 'node' else {}
                },
                'remote_components': ['ejs:github', 'ejs:npm']
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)
            self.info_signal.emit(info)
        except Exception as e:
            self.error_signal.emit(str(e))

class DownloadThread(QThread):
    progress_signal = Signal(str, int, str) # status_msg, percent, speed_eta
    finished_signal = Signal(str) # target output directory
    error_signal = Signal(str)
    
    def __init__(self, url, selected_langs, parent_dir, info, download_video=False, download_audio=True):
        super().__init__()
        self.url = url
        self.selected_langs = selected_langs
        self.parent_dir = parent_dir
        self.info = info
        self.download_video = download_video
        self.download_audio = download_audio
        self._is_cancelled = False
        
    def run(self):
        try:
            # 1. Create target directory named after the video title
            title = self.info.get('title', 'youtube_video')
            clean_title = re.sub(r'[\\/*?:"<>|]', ' ', title).strip()
            # Reduce multiple spaces to single
            clean_title = re.sub(r'\s+', ' ', clean_title)
            target_dir = os.path.abspath(os.path.join(self.parent_dir, clean_title))
            os.makedirs(target_dir, exist_ok=True)
            
            ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
            
            # Overall steps count: 1 (video) + len(selected_langs)
            total_steps = len(self.selected_langs) + 1
            current_step = 0
            
            def make_hook(step_name, step_idx):
                def progress_hook(d):
                    if self._is_cancelled:
                        raise Exception("Download cancelled by user")
                        
                    if d['status'] == 'downloading':
                        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                        downloaded = d.get('downloaded_bytes', 0)
                        
                        percent_val = 0
                        if total > 0:
                            percent_val = int((downloaded / total) * 100)
                            
                        # Calculate overall progress
                        overall_percent = int(((step_idx + (percent_val / 100.0)) / total_steps) * 100)
                        
                        speed = d.get('speed', 0)
                        speed_mb = speed / (1024 * 1024) if speed else 0
                        eta = d.get('eta', 0)
                        
                        speed_eta_str = f"{speed_mb:.2f} MB/s | ETA: {eta}s" if speed else "Calculating..."
                        status_msg = f"{step_name}: {percent_val}%"
                        
                        self.progress_signal.emit(status_msg, overall_percent, speed_eta_str)
                return progress_hook

            # 2. Download best video and merge with default audio
            video_outtmpl = os.path.join(target_dir, f"{clean_title}.%(ext)s")
            
            # Check if video file already exists to save time
            video_exists = False
            for ext in ['.mp4', '.webm', '.mkv']:
                if os.path.exists(os.path.join(target_dir, f"{clean_title}{ext}")):
                    video_exists = True
                    break
                    
            if not video_exists:
                self.progress_signal.emit("Downloading Video...", int((current_step/total_steps)*100), "Connecting...")
                node_path = pyinstaller_utils.get_node_path()
                video_opts = {
                    'format': 'bv*+ba/b',
                    'js_runtimes': {
                        'node': {'path': node_path} if node_path != 'node' else {}
                    },
                    'remote_components': ['ejs:github', 'ejs:npm'],
                    'ffmpeg_location': ffmpeg_path,
                    'outtmpl': video_outtmpl,
                    'progress_hooks': [make_hook("Downloading Video", current_step)],
                    'quiet': True,
                    'no_warnings': True
                }
                with yt_dlp.YoutubeDL(video_opts) as ydl:
                    ydl.download([self.url])
            else:
                self.progress_signal.emit("Video file already exists, skipping...", int(((current_step+1)/total_steps)*100), "")
                
            current_step += 1
            
            # 3. Download selected audio languages
            formats = self.info.get('formats', [])
            
            for lang in self.selected_langs:
                if self._is_cancelled:
                    raise Exception("Download cancelled by user")
                    
                # Find best audio format for this language
                lang_formats = [f for f in formats if f.get('language') == lang]
                if not lang_formats:
                    continue
                    
                # Sort formats by bitrate (tbr) descending
                lang_formats.sort(key=lambda x: x.get('tbr') or 0, reverse=True)
                best_format = lang_formats[0]
                format_id = best_format.get('format_id')
                
                self.progress_signal.emit(f"Downloading Audio ({lang})...", int((current_step/total_steps)*100), "Connecting...")
                audio_outtmpl = os.path.join(target_dir, f"{clean_title}_audio_{lang}.%(ext)s")
                
                node_path = pyinstaller_utils.get_node_path()
                audio_opts = {
                    'format': format_id,
                    'js_runtimes': {
                        'node': {'path': node_path} if node_path != 'node' else {}
                    },
                    'remote_components': ['ejs:github', 'ejs:npm'],
                    'ffmpeg_location': ffmpeg_path,
                    'outtmpl': audio_outtmpl,
                    'progress_hooks': [make_hook(f"Downloading Audio ({lang})", current_step)],
                    'quiet': True,
                    'no_warnings': True,
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }]
                }
                
                with yt_dlp.YoutubeDL(audio_opts) as ydl:
                    ydl.download([self.url])
                
                mp3_path = os.path.abspath(os.path.join(target_dir, f"{clean_title}_audio_{lang}.mp3"))
                
                if self.download_video:
                    self.progress_signal.emit(f"Merging Video with Audio ({lang})...", int((current_step/total_steps)*100), "Merging...")
                    # Find base video
                    base_video_file = None
                    for ext in ['.mp4', '.mkv', '.webm']:
                        candidate = os.path.join(target_dir, f"{clean_title}{ext}")
                        if os.path.exists(candidate):
                            base_video_file = candidate
                            break
                    
                    if base_video_file:
                        output_video_path = os.path.join(target_dir, f"{clean_title}_{lang}.mp4")
                        
                        # Hide console window on Windows
                        startupinfo = None
                        creation_flags = 0
                        import subprocess
                        if os.name == 'nt':
                            startupinfo = subprocess.STARTUPINFO()
                            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                            startupinfo.wShowWindow = 0  # SW_HIDE
                            creation_flags = subprocess.CREATE_NO_WINDOW
                            
                        # Run ffmpeg to merge
                        merge_cmd = [
                            ffmpeg_path, '-y',
                            '-i', base_video_file,
                            '-i', mp3_path,
                            '-map', '0:v:0',
                            '-map', '1:a:0',
                            '-c:v', 'copy',
                            '-c:a', 'aac',
                            output_video_path
                        ]
                        subprocess.run(merge_cmd, capture_output=True, creationflags=creation_flags, startupinfo=startupinfo)
                    else:
                        raise Exception("Cannot find downloaded base video for merging.")
                
                # Delete temporary audio file if only video is requested
                if not self.download_audio and os.path.exists(mp3_path):
                    try:
                        os.remove(mp3_path)
                    except Exception:
                        pass
                    
                current_step += 1
                
            self.finished_signal.emit(target_dir)
        except Exception as e:
            self.error_signal.emit(str(e))
            
class YouTubeDownloaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🌐 YouTube Multi-Language Audio Downloader")
        self.resize(650, 720)
        
        self.info = None
        self.fetch_thread = None
        self.download_thread = None
        
        self.init_ui()
        self.apply_stylesheet()
        
        # Default destination path
        app_dir = pyinstaller_utils.get_app_dir()
        default_dl = os.path.join(app_dir, "downloads")
        os.makedirs(default_dl, exist_ok=True)
        self.dest_edit.setText(os.path.abspath(default_dl))
        
    def init_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Header title
        title_label = QLabel("📥 YouTube Multi-Language Downloader")
        title_label.setObjectName("TitleLabel")
        layout.addWidget(title_label)
        
        # 1. URL Selection Group
        url_group = QGroupBox("🔗 YouTube Video URL")
        url_layout = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("Paste YouTube video link here...")
        url_layout.addWidget(self.url_edit)
        
        self.btn_fetch = QPushButton("🔍 Fetch Info")
        self.btn_fetch.setObjectName("FetchButton")
        self.btn_fetch.clicked.connect(self.fetch_info)
        url_layout.addWidget(self.btn_fetch)
        url_group.setLayout(url_layout)
        layout.addWidget(url_group)
        
        # 2. Metadata Card (initially hidden)
        self.metadata_card = QFrame()
        self.metadata_card.setObjectName("MetadataCard")
        meta_layout = QVBoxLayout(self.metadata_card)
        self.lbl_meta_title = QLabel("Title: -")
        self.lbl_meta_title.setWordWrap(True)
        self.lbl_meta_title.setStyleSheet("font-weight: bold; color: #F8FAFC;")
        self.lbl_meta_duration = QLabel("Duration: - | Channel: -")
        self.lbl_meta_duration.setStyleSheet("color: #94A3B8; font-size: 11px;")
        meta_layout.addWidget(self.lbl_meta_title)
        meta_layout.addWidget(self.lbl_meta_duration)
        self.metadata_card.hide()
        layout.addWidget(self.metadata_card)
        
        # 3. Audio Languages Group (initially hidden)
        self.lang_group = QGroupBox("🎵 Select Audio Languages to Download")
        lang_layout = QVBoxLayout()
        self.lang_list = QListWidget()
        self.lang_list.setObjectName("LanguageList")
        lang_layout.addWidget(self.lang_list)
        
        btn_select_row = QHBoxLayout()
        self.btn_select_all = QPushButton("✅ Select All")
        self.btn_select_all.clicked.connect(self.select_all_langs)
        btn_select_row.addWidget(self.btn_select_all)
        
        self.btn_deselect_all = QPushButton("🔳 Clear Selection")
        self.btn_deselect_all.clicked.connect(self.deselect_all_langs)
        btn_select_row.addWidget(self.btn_deselect_all)
        lang_layout.addLayout(btn_select_row)
        
        self.lang_group.setLayout(lang_layout)
        self.lang_group.hide()
        layout.addWidget(self.lang_group)
        
        # 3.5. Download Mode Options Group
        self.mode_group = QGroupBox("📦 Download Mode Options (下載模式設定)")
        mode_layout = QVBoxLayout()
        self.chk_download_video = QCheckBox("📥 下載成獨立語言影片 (.mp4) - 合併視訊與該語言音軌")
        self.chk_download_audio = QCheckBox("🎵 下載成獨立語言音檔 (.mp3) - 僅提取該語言音軌")
        self.chk_download_audio.setChecked(True) # Checked by default
        self.chk_download_video.setStyleSheet("color: #CBD5E1; font-size: 12px;")
        self.chk_download_audio.setStyleSheet("color: #CBD5E1; font-size: 12px;")
        mode_layout.addWidget(self.chk_download_video)
        mode_layout.addWidget(self.chk_download_audio)
        self.mode_group.setLayout(mode_layout)
        self.mode_group.hide()
        layout.addWidget(self.mode_group)
        
        # 4. Save Location Group
        dest_group = QGroupBox("💾 Save Location (選擇儲存路徑)")
        dest_layout = QHBoxLayout()
        self.dest_edit = QLineEdit()
        self.dest_edit.setReadOnly(True)
        dest_layout.addWidget(self.dest_edit)
        
        btn_browse_dest = QPushButton("Browse")
        btn_browse_dest.setObjectName("BrowseButton")
        btn_browse_dest.clicked.connect(self.browse_destination)
        dest_layout.addWidget(btn_browse_dest)
        dest_group.setLayout(dest_layout)
        layout.addWidget(dest_group)
        
        # 5. Progress Frame
        self.progress_frame = QFrame()
        self.progress_frame.setObjectName("ProgressFrame")
        progress_layout = QVBoxLayout(self.progress_frame)
        progress_layout.setContentsMargins(12, 12, 12, 12)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        
        self.lbl_status = QLabel("Status: System Ready")
        self.lbl_status.setObjectName("StatusLabel")
        progress_layout.addWidget(self.lbl_status)
        
        self.lbl_speed_eta = QLabel("")
        self.lbl_speed_eta.setObjectName("SpeedLabel")
        progress_layout.addWidget(self.lbl_speed_eta)
        
        self.progress_frame.hide()
        layout.addWidget(self.progress_frame)
        
        # 6. Action Button
        self.btn_download = QPushButton("📥 Start Download")
        self.btn_download.setObjectName("StartButton")
        self.btn_download.clicked.connect(self.start_download)
        self.btn_download.hide()
        layout.addWidget(self.btn_download)
        
        layout.addStretch()

    def apply_stylesheet(self):
        stylesheet = """
            QMainWindow {
                background-color: #0F172A; /* Deep Slate 900 */
            }
            QWidget#CentralWidget {
                background-color: #0F172A;
            }
            QLabel#TitleLabel {
                color: #F8FAFC;
                font-size: 18px;
                font-weight: bold;
                padding-bottom: 5px;
                border-bottom: 2px solid #334155;
            }
            QGroupBox {
                color: #CBD5E1;
                font-weight: bold;
                font-size: 13px;
                border: 1px solid #334155;
                border-radius: 8px;
                margin-top: 5px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px 0 3px;
            }
            QLineEdit {
                background-color: #1E293B;
                color: #E2E8F0;
                border: 1px solid #475569;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
            }
            QListWidget#LanguageList {
                background-color: #1E293B;
                color: #E2E8F0;
                border: 1px solid #475569;
                border-radius: 6px;
                min-height: 150px;
                max-height: 250px;
            }
            QListWidget#LanguageList::item {
                padding: 8px;
                color: #E2E8F0;
                border-bottom: 1px solid #334155;
            }
            QListWidget#LanguageList::item:hover {
                background-color: #334155;
            }
            QPushButton {
                background-color: #334155;
                color: #F8FAFC;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #475569;
            }
            QPushButton:pressed {
                background-color: #1E293B;
            }
            QPushButton#FetchButton {
                background-color: #4F46E5;
            }
            QPushButton#FetchButton:hover {
                background-color: #6366F1;
            }
            QPushButton#StartButton {
                background-color: #059669;
                font-size: 14px;
                padding: 12px;
                border-radius: 8px;
            }
            QPushButton#StartButton:hover {
                background-color: #10B981;
            }
            QPushButton#StartButton:pressed {
                background-color: #047857;
            }
            QProgressBar {
                background-color: #1E293B;
                color: white;
                border: 1px solid #334155;
                border-radius: 6px;
                text-align: center;
                height: 20px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #4F46E5;
                border-radius: 5px;
            }
            QFrame#MetadataCard {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 8px;
            }
            QFrame#ProgressFrame {
                background-color: #1E293B;
                border: 1px solid #334155;
                border-radius: 8px;
            }
            QLabel#StatusLabel {
                color: #CBD5E1;
                font-size: 13px;
                font-style: italic;
            }
            QLabel#SpeedLabel {
                color: #94A3B8;
                font-size: 12px;
                font-family: Consolas, monospace;
            }
            QCheckBox {
                color: #CBD5E1;
                spacing: 5px;
            }
            QCheckBox:hover {
                color: #F8FAFC;
            }
        """
        self.setStyleSheet(stylesheet)
        
    def fetch_info(self):
        url = self.url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Warning", "Please paste a valid YouTube video URL.")
            return
            
        self.btn_fetch.setEnabled(False)
        self.lbl_status.setText("Status: Fetching video metadata...")
        
        # Hide layout elements
        self.metadata_card.hide()
        self.lang_group.hide()
        self.mode_group.hide()
        self.btn_download.hide()
        self.progress_frame.show()
        self.progress_bar.setValue(0)
        self.lbl_speed_eta.setText("")
        
        # Start fetch thread
        self.fetch_thread = FetchInfoThread(url)
        self.fetch_thread.info_signal.connect(self.on_fetch_success)
        self.fetch_thread.error_signal.connect(self.on_fetch_error)
        self.fetch_thread.start()
        
    def on_fetch_success(self, info):
        self.info = info
        self.btn_fetch.setEnabled(True)
        
        # Display Metadata Card
        title = info.get('title', 'Unknown Title')
        channel = info.get('uploader', 'Unknown Channel')
        duration_sec = info.get('duration', 0)
        m, s = divmod(duration_sec, 60)
        h, m = divmod(m, 60)
        duration_str = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
        
        self.lbl_meta_title.setText(title)
        self.lbl_meta_duration.setText(f"⏱️ Duration: {duration_str} | 📺 Channel: {channel}")
        self.metadata_card.show()
        
        # Populating language list
        self.lang_list.clear()
        formats = info.get('formats', [])
        
        # Gather unique languages with audio formats
        unique_langs = set()
        for f in formats:
            lang = f.get('language')
            # Check if format has language code and it is not storyboards/images
            if lang and not f.get('format_id').startswith('sb'):
                unique_langs.add(lang)
                
        sorted_langs = sorted(list(unique_langs))
        
        if not sorted_langs:
            QMessageBox.warning(self, "No Dubbed Audio Tracks", 
                                "No separate language tracks found in this video's metadata.\n\nOnly the default audio track will be downloaded.")
            # Fallback to default en-US
            sorted_langs = ['en-US']
            
        for lang in sorted_langs:
            display_name = LANGUAGE_MAP.get(lang, f"({lang}) Audio Track")
            item = QListWidgetItem(display_name)
            item.setData(Qt.UserRole, lang)
            # Add checkbox
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked) # Check by default
            self.lang_list.addItem(item)
            
        self.lang_group.show()
        self.mode_group.show()
        self.btn_download.show()
        self.progress_frame.hide()
        
    def on_fetch_error(self, err_msg):
        self.btn_fetch.setEnabled(True)
        self.progress_frame.hide()
        self.mode_group.hide()
        QMessageBox.critical(self, "Metadata Fetch Failed", f"💥 Failed to fetch metadata:\n\n{err_msg}")
        
    def select_all_langs(self):
        for i in range(self.lang_list.count()):
            self.lang_list.item(i).setCheckState(Qt.Checked)
            
    def deselect_all_langs(self):
        for i in range(self.lang_list.count()):
            self.lang_list.item(i).setCheckState(Qt.Unchecked)
            
    def browse_destination(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Save Directory", self.dest_edit.text())
        if folder_path:
            self.dest_edit.setText(os.path.abspath(folder_path))
            
    def start_download(self):
        # Gather selected languages
        selected_langs = []
        for i in range(self.lang_list.count()):
            item = self.lang_list.item(i)
            if item.checkState() == Qt.Checked:
                selected_langs.append(item.data(Qt.UserRole))
                
        if not selected_langs:
            QMessageBox.warning(self, "Warning", "Please select at least one language track to download.")
            return
            
        download_video = self.chk_download_video.isChecked()
        download_audio = self.chk_download_audio.isChecked()
        
        if not download_video and not download_audio:
            QMessageBox.warning(self, "Warning", "Please select at least one download mode (Download as Video or Download as Audio).")
            return
            
        dest_dir = self.dest_edit.text()
        if not os.path.exists(dest_dir):
            QMessageBox.warning(self, "Warning", "Select folder location doesn't exist.")
            return
            
        url = self.url_edit.text().strip()
        
        # Setup UI for downloading state
        self.set_ui_enabled(False)
        self.progress_frame.show()
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Status: Initiating download pipeline...")
        self.lbl_speed_eta.setText("")
        
        # Start background download thread
        self.download_thread = DownloadThread(url, selected_langs, dest_dir, self.info, download_video, download_audio)
        self.download_thread.progress_signal.connect(self.on_download_progress)
        self.download_thread.finished_signal.connect(self.on_download_success)
        self.download_thread.error_signal.connect(self.on_download_error)
        self.download_thread.start()
        
    def set_ui_enabled(self, enabled):
        self.btn_fetch.setEnabled(enabled)
        self.btn_download.setEnabled(enabled)
        self.url_edit.setEnabled(enabled)
        self.dest_edit.setEnabled(enabled)
        self.lang_list.setEnabled(enabled)
        self.chk_download_video.setEnabled(enabled)
        self.chk_download_audio.setEnabled(enabled)
        self.btn_select_all.setEnabled(enabled)
        self.btn_deselect_all.setEnabled(enabled)
        for child in self.findChildren(QPushButton):
            if child != self.btn_download:
                child.setEnabled(enabled)
                
    def on_download_progress(self, status_msg, percent_val, speed_eta_str):
        self.progress_bar.setValue(percent_val)
        self.lbl_status.setText(f"Status: {status_msg}")
        self.lbl_speed_eta.setText(speed_eta_str)
        
    def on_download_success(self, target_dir):
        self.progress_bar.setValue(100)
        self.lbl_status.setText("Status: Finished successfully!")
        self.lbl_speed_eta.setText("")
        self.set_ui_enabled(True)
        
        QMessageBox.information(
            self, "Download Complete", 
            f"🎉 All requested tracks downloaded successfully!\n\nSaved in folder:\n{target_dir}"
        )
        
    def on_download_error(self, err_msg):
        self.progress_bar.setValue(0)
        self.lbl_status.setText("Status: Error occurred")
        self.lbl_speed_eta.setText("")
        self.set_ui_enabled(True)
        QMessageBox.critical(self, "Download Failed", f"💥 Downloading failed:\n\n{err_msg}")
        
    def closeEvent(self, event):
        if self.download_thread and self.download_thread.isRunning():
            self.download_thread.cancel()
            self.download_thread.terminate()
            self.download_thread.wait()
        event.accept()

def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = YouTubeDownloaderApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
