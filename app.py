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
st.info(f"パロマ瑞穂スタジアム(瑞穂公園陸上競技場)の改修前(2019年)から改修後(2026年)に私が撮影した写真を公開します．写真の二次利用をご希望の方は[@konakalab](https://x.com/konakalab)へご相談下さい．")
st.caption(f"写真撮影＆サイト構築： [@konakalab](https://x.com/konakalab)")

# 右クリック禁止と、ドラッグでの保存を抑制するCSS
st.markdown("""
    <style>
    img {
        pointer-events: none; /* 画像を直接クリック/保存できないようにする */
        -webkit-touch-callout: none;
    }
    </style>
    """, unsafe_allow_html=True)

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

        # --- グリッド表示（日付グループ化版） ---
        
        # 1. ズームレベルに応じた日付フォーマットの定義
        if zoom_level == "Year (細かく)":
            fmt = lambda d: f"{d[:4]}年"
        elif zoom_level == "Month (標準)":
            fmt = lambda d: f"{d[:7].replace('-', '年')}月"
        else: # Day
            fmt = lambda d: f"{d[:10].replace('-', '/')}（{d[:10]}）"

        # 2. 写真をグループ化
        from collections import defaultdict
        grouped_photos = defaultdict(list)
        for p in filtered_photos:
            date_key = fmt(get_best_date(p)[:10].replace(':', '-'))
            grouped_photos[date_key].append(p)

        # 3. グループごとに表示
        for date_label, group in grouped_photos.items():
            # 日付の見出しを表示
            st.subheader(date_label)
            
            # そのグループ内の写真をグリッド表示
            cols = st.columns(num_cols)
            for i, photo in enumerate(group):
                col = cols[i % num_cols] # カラムをループさせる
                with col:
                    thumb_url = photo.get('thumbnailLink', '').replace('=s220', '=s1000')
                    if thumb_url:
                        st.image(thumb_url, use_container_width=True)
                    else:
                        st.write("No Image")
            
            # グループ間に少し余白を入れる
            st.markdown("---")
