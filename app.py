import os
import streamlit as st
import soundfile as sf
import subprocess  # Модуль для запуска консольных команд Windows (FFmpeg)

st.set_page_config(page_title="FLAC to WAV Audiophile Player", layout="wide")
st.title("🎛️ Аудиофильский CUE-Сплиттер и Веб-Плеер")

MUSIC_ROOT = "Music"

if not os.path.exists(MUSIC_ROOT):
    os.makedirs(MUSIC_ROOT)
    st.info(f"📁 Создана папка '{MUSIC_ROOT}'. Положите туда папки с вашими альбомами (FLAC+CUE).")

if os.path.exists(MUSIC_ROOT):
    albums = [d for d in os.listdir(MUSIC_ROOT) if os.path.isdir(os.path.join(MUSIC_ROOT, d))]
else:
    albums = []

if not albums:
    st.warning(f"⚠️ В папке '{MUSIC_ROOT}' пока нет альбомов.")
    st.stop()

selected_album = st.selectbox("📂 Выберите альбом из вашей коллекции:", albums)
ALBUM_DIR = os.path.join(MUSIC_ROOT, selected_album)

flac_files = [f for f in os.listdir(ALBUM_DIR) if f.lower().endswith('.flac')]
cue_files = [f for f in os.listdir(ALBUM_DIR) if f.lower().endswith('.cue')]

if not flac_files or not cue_files:
    st.error(f"❌ В папке альбома должен быть один файл .flac и один .cue!")
    st.stop()

TEST_FILE = os.path.join(ALBUM_DIR, flac_files[0])
CUE_FILE = os.path.join(ALBUM_DIR, cue_files[0])
OUTPUT_DIR = os.path.join(ALBUM_DIR, "Tracks_WAV")
PREVIEW_DIR = os.path.join(ALBUM_DIR, ".preview")  # Скрытая папка для MP3-превью

# --- Вспомогательные функции ---
def cue_time_to_seconds(time_str):
    parts = time_str.split(':')
    return int(parts[0]) * 60 + int(parts[1]) + int(parts[2]) / 75.0

def parse_cue(cue_path):
    tracks = []
    current_track = {}
    if not os.path.exists(cue_path): return []
    with open(cue_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line.startswith("TRACK"):
                if current_track: tracks.append(current_track)
                current_track = {"number": line.split()[1]}
            elif line.startswith("TITLE") and current_track:
                current_track["title"] = line.split('"')[1]
            elif line.startswith("PERFORMER") and current_track:
                current_track["performer"] = line.split('"')[1]
            elif line.startswith("INDEX 01") and current_track:
                current_track["start_time"] = cue_time_to_seconds(line.split()[2])
        if current_track: tracks.append(current_track)
    return tracks

# --- ИНТЕРФЕЙС ПРИЛОЖЕНИЯ ---
col1, col2 = st.columns()

with col1:
    st.subheader("🖼️ Обложка")
    art_paths = [ALBUM_DIR, os.path.join(ALBUM_DIR, "Art")]
    cover_found = False
    for path in art_paths:
        if os.path.exists(path):
            for file in os.listdir(path):
                if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                    st.image(os.path.join(path, file), width=300)
                    cover_found = True
                    break
        if cover_found: break
    if not cover_found:
        st.info("Обложка не найдена")

with col2:
    st.subheader("📊 Структура CUE-листа")
    tracks = parse_cue(CUE_FILE)
    
    if tracks:
        track_data = []
        for t in tracks:
            track_data.append({
                "№": t.get("number"),
                "Исполнитель": t.get("performer", "Неизвестно"),
                "Название трека": t.get("title", "Неизвестно")
            })
        st.dataframe(track_data, use_container_width=True, hide_index=True)
        
        if st.button("📀 Нарезать этот альбом на WAV + MP3-превью", type="primary"):
            with st.spinner("Шаг 1: Нарезаем аудиофильские WAV..."):
                data, samplerate = sf.read(TEST_FILE)
                total_samples = len(data)
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                os.makedirs(PREVIEW_DIR, exist_ok=True)
                
                for idx, track in enumerate(tracks):
                    start_sample = int(track["start_time"] * samplerate)
                    end_sample = int(tracks[idx + 1]["start_time"] * samplerate) if idx < len(tracks) - 1 else total_samples
                    
                    track_data = data[start_sample:end_sample]
                    clean_title = "".join([c for c in track.get("title", "Track") if c.isalpha() or c.isdigit() or c==' ']).strip()
                    filename_wav = f"{track['number']} - {clean_title}.wav"
                    filename_mp3 = f"{track['number']} - {clean_title}.mp3"
                    
                    wav_path = os.path.join(OUTPUT_DIR, filename_wav)
                    mp3_path = os.path.join(PREVIEW_DIR, filename_mp3)
                    
                    # 1. Записываем оригинальный WAV
                    sf.write(wav_path, track_data, samplerate, subtype='PCM_16')
                    
                    # 2. Вызываем FFmpeg для генерации легкого MP3 для плеера
                    # Команда: ffmpeg -y -i input.wav -vn -ar 44100 -ac 2 -b:a 192k output.mp3
                    try:
                        cmd = [
                            "ffmpeg", "-y", 
                            "-i", wav_path, 
                            "-vn", 
                            "-ar", "44100", 
                            "-ac", "2", 
                            "-b:a", "192k", 
                            mp3_path
                        ]
                        # Запускаем скрытно в фоне Windows
                        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    except Exception as ffmpeg_err:
                        st.error(f"Ошибка FFmpeg: убедитесь, что он добавлен в PATH. {ffmpeg_err}")
                        st.stop()
                        
            st.success(f"🎉 Успешно! Высококачественные WAV сохранены в 'Tracks_WAV', а превью сгенерированы.")
            st.rerun()

# --- 2. СЕКЦИЯ ВЕБ-ПЛЕЕРА ---
st.write("---")
st.subheader("🎧 Встроенный аудио-плеер (MP3-Превью)")

if os.path.exists(OUTPUT_DIR) and os.path.exists(PREVIEW_DIR):
    wav_files = sorted([f for f in os.listdir(OUTPUT_DIR) if f.lower().endswith('.wav')])
    mp3_files = sorted([f for f in os.listdir(PREVIEW_DIR) if f.lower().endswith('.mp3')])
    
    if wav_files and len(wav_files) == len(mp3_files):
        st.caption("Оригиналы WAV лежат в папке диска. Слушайте мгновенное превью прямо здесь:")
        for idx, wav in enumerate(wav_files):
            mp3_path = os.path.join(PREVIEW_DIR, mp3_files[idx])
            
            player_col1, player_col2 = st.columns([1, 3])
            with player_col1:
                st.write(f"🎵 **{wav.replace('.wav', '')}**")
            with player_col2:
                # Скармливаем плееру легкий MP3 файл!
                st.audio(mp3_path, format="audio/mp3")
    else:
        st.info("💡 Нажмите кнопку выше, чтобы заново нарезать альбом и сгенерировать MP3-превью.")
else:
    st.info("💡 Альбом еще не нарезан. Нажмите кнопку выше.")
