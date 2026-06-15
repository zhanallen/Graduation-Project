import cv2
import numpy as np
import struct
import os
import zlib
import imageio_ffmpeg
import subprocess
import re
import tempfile

# Set Numba cache directory to a writable system temp directory to avoid permission errors when running from _internal
numba_temp = os.path.join(tempfile.gettempdir(), "numba_cache")
os.makedirs(numba_temp, exist_ok=True)
os.environ['NUMBA_CACHE_DIR'] = numba_temp

from numba import njit

# ==========================================
# --- 1. 二進制極速向量化轉換 ---
# ==========================================
def files_to_bits(file_paths):
    """
    Packs multiple files into a single bit array.
    Structure:
        uint16: number of files
        For each file:
            uint16: filename length
            bytes: filename (utf-8)
            uint32: file content length
            bytes: file content
    Then zlib compresses the entire structure, and prepends the 4-byte payload size header.
    """
    print(f"📦 讀取並封裝多個檔案: {file_paths}")
    payload_body = bytearray()
    
    # 寫入檔案數量
    payload_body.extend(struct.pack('>H', len(file_paths)))
    
    for fp in file_paths:
        filename = os.path.basename(fp)
        fname_bytes = filename.encode('utf-8')
        with open(fp, "rb") as f:
            file_bytes = f.read()
            
        payload_body.extend(struct.pack('>H', len(fname_bytes)) + fname_bytes)
        payload_body.extend(struct.pack('>I', len(file_bytes)) + file_bytes)
        
    compressed_data = zlib.compress(bytes(payload_body), level=9)
    payload_size = len(compressed_data)
    final_data = struct.pack('>I', payload_size) + compressed_data
    
    byte_array = np.frombuffer(final_data, dtype=np.uint8)
    bits_array = np.unpackbits(byte_array)
    
    print(f"  -> 多檔案轉為二進制完畢，總長度: {len(bits_array)} bits ({payload_size} bytes)")
    return bits_array

def bits_to_bytes(bits_array):
    return np.packbits(bits_array).tobytes()

def decode_multi_files(compressed_bytes, output_dir):
    """
    Unpacks multiple files from decompressed bytes.
    Returns:
        dict: mapping of lang_code/filename -> path of extracted file
    """
    metadata_packed = zlib.decompress(compressed_bytes)
    offset = 0
    
    # 讀取檔案數量
    num_files = struct.unpack('>H', metadata_packed[offset:offset+2])[0]
    offset += 2
    
    extracted_paths = {}
    
    for _ in range(num_files):
        # 讀取檔名長度
        fname_len = struct.unpack('>H', metadata_packed[offset:offset+2])[0]
        offset += 2
        
        # 讀取檔名
        filename = metadata_packed[offset:offset+fname_len].decode('utf-8')
        offset += fname_len
        
        # 讀取檔案內容長度
        file_len = struct.unpack('>I', metadata_packed[offset:offset+4])[0]
        offset += 4
        
        # 讀取檔案內容
        file_bytes = metadata_packed[offset:offset+file_len]
        offset += file_len
        
        output_file_path = os.path.join(output_dir, filename)
        with open(output_file_path, "wb") as f:
            f.write(file_bytes)
            
        # 解析語言代碼
        match = re.search(r"_audio_(.+)\.(mp3|m4a|webm)$", filename)
        if match:
            lang = match.group(1)
            extracted_paths[lang] = output_file_path
        else:
            extracted_paths[filename] = output_file_path
            
    return extracted_paths

# ==========================================
# --- 2. 容量與預測 ---
# ==========================================
def get_payload_size(file_path):
    if not os.path.exists(file_path): return 0
    with open(file_path, "rb") as f: file_bytes = f.read()
    filename = os.path.basename(file_path)
    fname_bytes = filename.encode('utf-8')
    metadata_packed = struct.pack('>H', len(fname_bytes)) + fname_bytes + file_bytes
    return len(zlib.compress(metadata_packed, level=9)) + 4

def estimate_capacity(video_path, sample_size=15):
    if not os.path.exists(video_path): return 0
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened(): return 0

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0: return 0

    # Seek to the middle of the video to avoid black intros/outros/credits
    start_frame = 0
    if total_frames > sample_size:
        start_frame = max(0, (total_frames // 2) - (sample_size // 2))
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    frames_to_read = min(sample_size, total_frames)
    total_embeddable_bits = 0
    actual_read_count = 0

    for _ in range(frames_to_read):
        ret, frame = cap.read()
        if not ret: break

        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        G = gray_frame.astype(np.int16)
        p_hat = G[:-1, :]
        p = G[1:, :]

        safe_mask = (p_hat >= 10) & (p_hat <= 245)
        e = p - p_hat
        total_embeddable_bits += np.sum((e >= -1) & (e <= 1) & safe_mask)
        actual_read_count += 1

    cap.release()
    if actual_read_count == 0: return 0

    avg_bits_per_frame = total_embeddable_bits / actual_read_count
    return max(0, (int(avg_bits_per_frame * total_frames) // 8) - 4)

# ==========================================
# --- 3. Numba 極速引擎 ---
# ==========================================
@njit(nogil=True, cache=True)
def pee_embed_core_numba(G, bits_array, bit_idx, total_bits, height, width):
    for i in range(1, height):
        if bit_idx >= total_bits: break
        p_hat = G[i - 1, :]
        p = G[i, :]
        for j in range(width):
            if bit_idx >= total_bits: break
            if not (10 <= p_hat[j] <= 245): continue

            e = p[j] - p_hat[j]
            if -1 <= e <= 1:
                b = bits_array[bit_idx]
                bit_idx += 1
                if e == -1:
                    e_new = -2 + b
                elif e == 0:
                    e_new = b
                elif e == 1:
                    e_new = 2 + b
            elif e > 1:
                e_new = e + 2
            else:
                e_new = e - 2
            G[i, j] = p_hat[j] + e_new
    return bit_idx

@njit(nogil=True, cache=True)
def pee_extract_core_numba(G, bit_buffer, bit_idx, target_bits, height, width):
    stop_i = height - 1
    stop_j = width - 1
    finished = False
    error_code = 0

    for i in range(1, height):
        if finished: break
        p_hat = G[i - 1, :]
        p_prime = G[i, :]

        for j in range(width):
            if finished: break
            if not (10 <= p_hat[j] <= 245): continue

            e_p = p_prime[j] - p_hat[j]

            if -2 <= e_p <= 3:
                if e_p == -2 or e_p == 0 or e_p == 2:
                    b = 0
                else:
                    b = 1

                bit_buffer[bit_idx] = b
                bit_idx += 1

                if target_bits == 0 and bit_idx == 32:
                    val_len = 0
                    for k in range(32): val_len = (val_len << 1) | bit_buffer[k]
                    if 0 < val_len < 100_000_000:
                        target_bits = 32 + val_len * 8
                    else:
                        error_code = 1
                        finished = True
                        break

                if target_bits > 0 and bit_idx == target_bits:
                    finished = True
                    stop_i = i
                    stop_j = j
                    break

    if error_code == 0:
        for i in range(stop_i, 0, -1):
            p_hat = G[i - 1, :]
            p_prime = G[i, :]
            start_j = stop_j if i == stop_i else width - 1

            for j in range(start_j, -1, -1):
                if not (10 <= p_hat[j] <= 245): continue

                e_p = p_prime[j] - p_hat[j]
                if -2 <= e_p <= 3:
                    if e_p == -2 or e_p == -1:
                        e = -1
                    elif e_p == 0 or e_p == 1:
                        e = 0
                    elif e_p == 2 or e_p == 3:
                        e = 1
                elif e_p >= 4:
                    e = e_p - 2
                elif e_p <= -4:
                    e = e_p + 2
                else:
                    e = e_p

                G[i, j] = p_hat[j] + e

    return bit_idx, target_bits, finished, error_code

# ==========================================
# --- 4. 記憶體管線化多檔案編碼 ---
# ==========================================
def encode_video_multi(video_path, file_paths, output_path, progress_callback=None):
    bits_array = files_to_bits(file_paths)
    total_bits = len(bits_array)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    
    frame_size = int(width * height * 1.5)
    Y_size = width * height

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    temp_audio = os.path.join(tempfile.gettempdir(), f"de_temp_audio_{os.getpid()}_{np.random.randint(100000)}.aac")
    
    # Hide console window on Windows
    startupinfo = None
    creation_flags = 0
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE
        creation_flags = subprocess.CREATE_NO_WINDOW
    
    # 提取影像原有的音軌，維持播放相容性
    subprocess.run([ffmpeg_exe, '-y', '-i', video_path, '-vn', '-c:a', 'aac', '-b:a', '256k', temp_audio],
                   capture_output=True, creationflags=creation_flags, startupinfo=startupinfo)

    # 讀取 YUV420p 管線
    ffmpeg_read_cmd = [
        ffmpeg_exe, '-i', video_path,
        '-f', 'rawvideo', '-pix_fmt', 'yuv420p', '-'
    ]
    p_read = subprocess.Popen(
        ffmpeg_read_cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
        startupinfo=startupinfo
    )

    # 寫入 HEVC 無損 YUV420p 管線 (tag hvc1)
    ffmpeg_cmd = [
        ffmpeg_exe, '-y',
        '-f', 'rawvideo', '-vcodec', 'rawvideo',
        '-s', f'{width}x{height}', '-pix_fmt', 'yuv420p', '-r', str(fps),
        '-i', '-'
    ]
    if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 1024:
        ffmpeg_cmd.extend(['-i', temp_audio, '-c:a', 'copy'])
    ffmpeg_cmd.extend(['-c:v', 'libx265', '-preset', 'ultrafast', '-x265-params', 'lossless=1', '-pix_fmt', 'yuv420p', '-tag:v', 'hvc1', output_path])

    process = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
        startupinfo=startupinfo
    )

    import threading
    from queue import Queue
    read_queue = Queue(maxsize=60)
    write_queue = Queue(maxsize=60)

    def reader():
        while True:
            raw_bytes = p_read.stdout.read(frame_size)
            if not raw_bytes or len(raw_bytes) != frame_size:
                read_queue.put(None)
                break
            frame = np.frombuffer(raw_bytes, dtype=np.uint8).copy()
            read_queue.put(frame)
        p_read.stdout.close()
        p_read.wait()

    def writer():
        while True:
            frame = write_queue.get()
            if frame is None:
                break
            try:
                process.stdin.write(frame.tobytes())
            except Exception:
                pass
        process.stdin.close()

    threading.Thread(target=reader, daemon=True).start()
    threading.Thread(target=writer, daemon=True).start()

    bit_idx = 0
    frame_count = 0

    while True:
        frame = read_queue.get()
        if frame is None:
            write_queue.put(None)
            break
        frame_count += 1

        if bit_idx < total_bits:
            G = frame[:Y_size].reshape((height, width)).astype(np.int16)
            bit_idx = pee_embed_core_numba(G, bits_array, bit_idx, total_bits, height, width)
            frame[:Y_size] = np.clip(G, 0, 255).ravel().astype(np.uint8)

        write_queue.put(frame)

        if progress_callback and frame_count % 10 == 0:
            progress_callback(frame_count, total_frames, bit_idx, total_bits)

        if frame_count % 30 == 0: 
            print(f"  -> 已寫入 {frame_count} 幀, 進度 {bit_idx}/{total_bits} bits")

    process.wait()

    if os.path.exists(temp_audio): os.remove(temp_audio)
    if bit_idx < total_bits:
        raise ValueError(f"💥 容量嚴重不足！還有 {total_bits - bit_idx} bits 未寫入。")
    print("🎉 多檔案編碼寫入無損影片成功！")

# ==========================================
# --- 5. 零內存極速解密多檔案 ---
# ==========================================
def decode_video_multi(video_path, output_dir, progress_callback=None):
    print(f"🔓 啟動 PEE Numba JIT 多檔案極速還原: {video_path}")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    cap = cv2.VideoCapture(video_path)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    frame_size = int(width * height * 1.5)
    Y_size = width * height

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_read_cmd = [
        ffmpeg_exe, '-i', video_path,
        '-f', 'rawvideo', '-pix_fmt', 'yuv420p', '-'
    ]
    # Hide console window on Windows
    startupinfo = None
    creation_flags = 0
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE
        creation_flags = subprocess.CREATE_NO_WINDOW
        
    p_read = subprocess.Popen(
        ffmpeg_read_cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
        startupinfo=startupinfo
    )

    # 800MB 靜態緩衝區 (支援 100MB 檔案)
    bit_buffer = np.zeros(800_000_000, dtype=np.uint8)

    bit_idx = 0
    target_bits = 0
    finished_extracting = False

    import threading
    from queue import Queue
    read_queue = Queue(maxsize=60)
    stop_event = threading.Event()

    def reader():
        while not stop_event.is_set():
            raw_bytes = p_read.stdout.read(frame_size)
            if not raw_bytes or len(raw_bytes) != frame_size:
                read_queue.put(None)
                break
            frame = np.frombuffer(raw_bytes, dtype=np.uint8).copy()
            read_queue.put(frame)
        p_read.stdout.close()
        try:
            p_read.terminate()
        except:
            pass

    threading.Thread(target=reader, daemon=True).start()

    frame_count = 0
    while True:
        frame = read_queue.get()
        if frame is None:
            break
        frame_count += 1

        if not finished_extracting:
            G = frame[:Y_size].reshape((height, width)).astype(np.int16)

            # 🌟 呼叫 Numba 加速引擎，瞬間掃描並還原數百萬像素
            bit_idx, target_bits, finished_extracting, error_code = pee_extract_core_numba(
                G, bit_buffer, bit_idx, target_bits, height, width
            )

            # 如果解析出來的目標位元數大於目前緩衝區大小，動態擴容
            if target_bits > len(bit_buffer):
                print(f"🔄 偵測到目標容量 {target_bits} bits，正在動態擴容緩衝區...")
                new_buffer = np.zeros(target_bits + 10_000_000, dtype=np.uint8)
                new_buffer[:len(bit_buffer)] = bit_buffer
                bit_buffer = new_buffer

            if progress_callback and frame_count % 10 == 0:
                progress_callback(frame_count, total_frames, bit_idx, target_bits)

            if frame_count % 30 == 0:
                print(f"  -> 已掃描 {frame_count} 幀, 提取進度 {bit_idx}/{target_bits} bits")

            if error_code == 1:
                stop_event.set()
                raise ValueError("💥 致命失敗：讀到無效的檔案長度標頭。影片可能無嵌入資訊或已被壓縮失真！")

        if finished_extracting:
            stop_event.set()
            break

    if target_bits > 0 and bit_idx == target_bits:
        payload_bits = bit_buffer[32: target_bits]
        compressed_bytes = bits_to_bytes(payload_bits)

        try:
            print("  -> 進行多檔案 zlib 解壓縮還原...")
            extracted_paths = decode_multi_files(compressed_bytes, output_dir)
            print(f"🎉 逆向多檔案完美還原成功！共還原 {len(extracted_paths)} 個音訊軌。")
            return extracted_paths
        except Exception as e:
            raise ValueError(f"💥 解壓縮解碼失敗：{e}")
    else:
        raise ValueError("💥 致命失敗：無法讀取完整嵌入資訊。")
