import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
from PIL import Image

# ページ設定
st.set_page_config(layout="wide", page_title="Drive Photo Gallery")

# --- 1. Google Drive 認証 ---
def get_drive_service():
    # StreamlitのSecretsから認証情報を読み込む
    info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(info)
    return build('drive', 'v3', credentials=creds)

# --- 2. ファイルリストの取得（高速化のためキャッシュを利用） ---
@st.cache_data(ttl=600)
def fetch_photo_list(folder_id):
    service = get_drive_service()
    # photoMetadata ではなく imageMediaMetadata を指定します
    query = f"'{folder_id}' in parents and mimeType contains 'image/'"
    results = service.files().list(
        q=query, 
        fields="files(id, name, thumbnailLink, imageMediaMetadata, createdTime)",
        pageSize=1000
    ).execute()
    return results.get('files', [])

# --- 3. UI部分 ---
st.title("📸 パロマ瑞穂スタジアム(瑞穂公園陸上競技場)フォトギャラリー")
st.caption(f"写真撮影＆サイト構築： [@konakalab](https://x.com/konakalab)")

# ここにGoogle DriveのフォルダIDを入力してください
# URLの https://drive.google.com/drive/u/0/folders/XXXXX の XXXXX の部分です
FOLDER_ID = "1lHnhd05AZ-0VZ_nk8FpGtAYA7AmOSd6U"

# ズームスライダー（1行あたりの枚数を変える）
zoom_level = st.select_slider(
    "表示モード（ズーム）",
    options=["Year (細かく)", "Month (標準)", "Day (大きく)"],
    value="Month (標準)"
)
cols_map = {"Year (細かく)": 8, "Month (標準)": 4, "Day (大きく)": 1}
num_cols = cols_map[zoom_level]

# 実行
if FOLDER_ID == "あなたのフォルダIDをここに貼り付け":
    st.warning("Google DriveのフォルダIDをコードに入力してください。")
else:
    photos = fetch_photo_list(FOLDER_ID)
    
    if not photos:
        st.info("フォルダに画像が見つかりませんでした。")
    else:
        # --- [修正箇所①] 撮影日を優先する関数 ---
        def get_best_date(x):
            # メタデータ内の撮影時間 ('time') を取得
            meta = x.get('imageMediaMetadata')
            if meta and 'time' in meta:
                return meta['time']
            # 撮影日がない場合は、アップロード日 ('createdTime') を返す
            return x.get('createdTime', '')

        # 撮影日を基準にソート（新しい順）
        photos.sort(key=get_best_date, reverse=True)

        # --- グリッド表示 ---
        idx = 0
        while idx < len(photos):
            cols = st.columns(num_cols)
            for col in cols:
                if idx < len(photos):
                    photo = photos[idx]
                    with col:
                        thumb_url = photo.get('thumbnailLink', '').replace('=s220', '=s1000')
                        if thumb_url:
                            st.image(thumb_url, use_container_width=True)
                        else:
                            st.write("No Image")
                        
                        # --- [修正箇所②] 日付の表示ロジック ---
                        best_date = get_best_date(photo)
                        # Google Driveの撮影日は "2023:10:01 12:00:00" 形式が多いので整形
                        # 先頭10文字(YYYY:MM:DD)を取り、":" を "-" に置換
                        display_date = best_date[:10].replace(':', '-')
                        st.caption(f"📅 {display_date}")
                    idx += 1
