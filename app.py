import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
from PIL import Image, ImageDraw, ImageFont  # ImageDraw, ImageFontを追加

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

# --- 33行目付近に追加 ---
@st.cache_data(show_spinner=False)
def get_watermarked_image(file_id, text="photo by konakalab"):
    service = get_drive_service()
    # 1. Google Driveから画像をダウンロード
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
    
    # 2. Pillowで開いて文字入れ
    img = Image.open(fh).convert("RGBA")
    txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
    
    # フォントサイズを画像サイズに合わせて調整（短辺の約4%）
    font_size = int(min(img.size) * 0.04)
    # Streamlit Cloud環境でも動作するデフォルトフォントを使用
    font = ImageFont.load_default() 
    
    draw = ImageDraw.Draw(txt_layer)
    
    # 右下に配置（マージンをとる）
    margin = int(img.size[0] * 0.02)
    # 簡易的に右下に配置
    draw.text((img.size[0] - (font_size * 10), img.size[1] - (font_size * 2)), text, font=font, fill=(255, 255, 255, 160))
    
    # 合成してRGBに変換
    combined = Image.alpha_composite(img, txt_layer).convert("RGB")
    return combined
    
# --- 3. UI部分 ---
st.title("📸 パロマ瑞穂スタジアム(瑞穂公園陸上競技場)フォトギャラリー")
st.caption(f"写真撮影＆サイト構築： [@konakalab](https://x.com/konakalab)")

# Google DriveのフォルダID
FOLDER_ID = "1lHnhd05AZ-0VZ_nk8FpGtAYA7AmOSd6U"

if FOLDER_ID == "あなたのフォルダIDをここに貼り付け":
    st.warning("Google DriveのフォルダIDをコードに入力してください。")
else:
    photos = fetch_photo_list(FOLDER_ID)
    
    if not photos:
        st.info("フォルダに画像が見つかりませんでした。")
    else:
        # 撮影日（または作成日）を取得する共通関数
        def get_best_date(x):
            meta = x.get('imageMediaMetadata')
            if meta and 'time' in meta:
                return meta['time']
            return x.get('createdTime', '')

        # --- 新機能：期間指定スライダーの実装 ---
        # 1. 全写真から日付(YYYY-MM-DD)を抽出して重複を除去し、昇順に並べる
        all_dates = sorted(list(set([get_best_date(p)[:10].replace(':', '-') for p in photos])))

        if len(all_dates) > 1:
            # st.select_slider の value にタプル (開始, 終了) を渡すと2点スライダーになる
            start_date, end_date = st.select_slider(
                "📅 表示する期間を選択してください",
                options=all_dates,
                value=(all_dates[0], all_dates[-1])
            )
        else:
            # 写真が1日分しかない場合
            start_date = end_date = all_dates[0] if all_dates else None
            st.info(f"対象期間: {start_date}")

        # ズームスライダー
        zoom_level = st.select_slider(
            "🔍 表示モード（ズーム）",
            options=["Year (細かく)", "Month (標準)", "Day (大きく)"],
            value="Month (標準)"
        )
        cols_map = {"Year (細かく)": 8, "Month (標準)": 4, "Day (大きく)": 1}
        num_cols = cols_map[zoom_level]

        # --- フィルタリングと表示 ---
        # スライダーで選んだ期間内の写真だけを抽出
        filtered_photos = [
            p for p in photos 
            if start_date <= get_best_date(p)[:10].replace(':', '-') <= end_date
        ]

        # 撮影日を基準にソート（新しい順）
        filtered_photos.sort(key=get_best_date, reverse=True)

        # 統計情報の表示
        st.write(f"📊 {len(filtered_photos)} 枚を表示中 ({start_date} ～ {end_date})")

        # グリッド表示
        idx = 0
        while idx < len(filtered_photos):
            cols = st.columns(num_cols)
            for col in cols:
                if idx < len(filtered_photos):
                    photo = filtered_photos[idx]
                    with col:
                        # サムネイルURLではなく、合成後の画像を取得
                        try:
                            wm_img = get_watermarked_image(photo['id'])
                            st.image(wm_img, use_container_width=True)
                        except Exception as e:
                            st.error("画像読み込み失敗")
                        
                        # 日付の表示
                        best_date = get_best_date(photo)
                        display_date = best_date[:10].replace(':', '-')
                        st.caption(f"📅 {display_date}")
                    idx += 1
