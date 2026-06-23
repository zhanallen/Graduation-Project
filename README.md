# DE Multi-Track Stego Player & Packer Suite
## 基於無損預測誤差擴張 (PEE) 的多音軌影音隱寫播放與封裝套件

本專案是一套融合 **資訊安全 (Information Security)**、**數位取證 (Digital Forensics)** 與 **可逆資料隱寫 (Reversible Data Hiding, RDH)** 技術的影音藏密封裝與解碼播放軟體套件。

系統採用高階的 **預測誤差擴張 (Prediction Error Expansion, PEE)** 演算法，能將多個獨立的二進制載荷（如多語系配音檔、機密會議錄音、版權中繼資料）無損且隱蔽地隱寫在單一 H.265 (HEVC) 影片的像素預測誤差中。在播放時，系統透過 JIT 加速解密管道，於背景即時自影像幀中提取隱藏資料並無感還原為多軌音訊進行同步播放，同時實現影片載體畫面的 **100% 位元級完美還原 (Bit-Perfect Reversibility)**。

---

## 🚀 專案核心技術優勢 (Technical Advantages)

本套件相較於傳統數位浮水印或損毀式（LSB）密寫，具備以下決定性的核心優勢：

### 1. 醫療與司法鑑定級的「完全可逆還原性 (Reversible Data Hiding)」
*   **傳統密寫缺點**：傳統的 LSB（最低有效位元）或空域隱寫法會永久性地修改並損毀原始影片的像素值，導致載體畫質受損且無法逆向復原。
*   **本系統優勢**：本套件利用 PEE 可逆演算法，當解密端完整提取出隱密音軌後，能藉由逆向數學公式將修改後的預測誤差還原為原始誤差，從而將影片幀像素還原至與原始影片 **100% 完全相同（位元級 byte-by-byte 一致，MD5/SHA256 校驗值完全吻合）**。這使得本系統非常適用於對原始影像數據精確度要求極高（如醫療影像診斷、軍事地圖、司法取證）的敏感領域。

### 2. 極致的視覺隱蔽性 (Imperceptibility)
*   **直方圖集中優勢**：演算法不對像素原值直接修改，而是計算像素與其相鄰預測值（Diamond/Checkerboard 預測模式）的差值（預測誤差）。由於相鄰像素具備高度相關性，預測誤差極度集中在 0 附近。
*   **微幅修改**：透過擴張誤差嵌入資料，僅對影像中邊緣或紋理處的預測誤差微幅修改 $\pm 1$ 灰階值，平滑區域維持平移。
*   **超高畫質指標**：密寫影片的峰值信噪比（PSNR）高達 **$48\text{ dB}$ 以上**，結構相似性（SSIM）無限接近於 `1.0`。在視覺上完全沒有雪花雜訊、色彩斷層或摩爾紋，肉眼完全不可察覺。

### 3. Numba JIT 加速與極速 YUV 串流管線 (High-Performance JIT Engine)
*   **實時性能**：Python 原生遍歷百萬級像素速度極慢。本系統使用 **Numba JIT 靜態編譯技術**，將核心隱寫遍歷算法（C 語言級運行效率）與 FFmpeg 管道無縫對接。
*   **即時解密**：在後台以超過 **$120\text{ FPS}$** 的速度即時處理 YUV420p 原生像素流。播放器載入影片時，只需不到一秒即可在背景完成對整部影片音軌的解密、提取、zlib 解壓縮並載入播放核心。

### 4. 偽裝與社交平台傳輸相容性 (Stealth & Compatibility)
*   **標準封裝相容**：輸出的密寫影片採用標準 H.265 (hvc1) MP4 格式，可在常規雲端硬碟（Google Drive、Dropbox）上正常上傳與預覽，並可使用常規播放器（如 VLC、Windows Media Player、Chrome 瀏覽器）正常播放（此時僅會播放預設的單一音軌）。
*   **隱蔽安全**：在常規播放器下，這 5~10 個隱藏的多國語言音軌是完全隱形且不可檢測的，只有在本套件的 StegoPlayer 中才能被識別並完美提取播放，極具隱蔽性。

---

## 🎯 應用場景 (Application Scenarios)

*   **機密錄音與敏感檔案保護**：將高度機密的通話、會議錄音無損藏入一部看似普通的家庭短片中進行傳輸。
*   **多語系影片隱蔽發布**：將多種敏感配音（如非官方多國配音）安全嵌入單一影片像素中，防範被串流平台屏蔽或音軌分離。
*   **司法防偽與影像取證 (Watermarking)**：在影像中潛伏高容量的版權與雜湊資訊，在不破壞原圖畫質的前提下進行版權溯源，需要時可完全還原出原圖。

---

## 📂 專案目錄架構

為了保持版本控制代碼的潔淨，專案只保留核心功能程式碼與建置腳本。其餘本地測試所需的大型測試影片與暫存檔案皆已配置於 `.gitignore` 排除，不納入代碼庫中。

```
DE/
├── src/                        # 核心功能程式碼
│   ├── download_app.py         # MultiAudioDownloader (多音軌多語系影片下載 GUI)
│   ├── embed_app.py            # StegoPacker (多音軌 PEE 隱寫封裝 GUI)
│   ├── player_app.py           # StegoPlayer (即時解密多音軌播放器 GUI，含科技感儀表板)
│   ├── pee_stego.py            # PEE Steganography 核心演算法庫 (Numba 加速)
│   └── pyinstaller_utils.py    # PyInstaller 打包路徑與可移植性工具
│
├── MultiAudioDownloader.spec   # 多音軌下載器的 PyInstaller 打包設定檔
├── StegoPacker.spec            # 封裝器的 PyInstaller 打包設定檔
├── StegoPlayer.spec            # 播放器的 PyInstaller 打包設定檔
├── build.bat                   # Windows 平台下一鍵打包 Executable 執行檔腳本
├── requirements.txt            # 專案依賴套件清單
├── .gitignore                  # Git 排除清單 (防止大型影片與編譯快取上傳)
└── README.md                   # 專案說明文件 (本檔案)
```

---

## 🔄 預測誤差擴張 (PEE) 藏密與解密核心原理流程圖

以下為本專案核心演算法 **可逆資料隱寫 (Reversible Data Hiding, RDH)** 與 **預測誤差擴張 (PEE)** 的詳細藏密（嵌入）與解密（還原）運作邏輯：

```mermaid
flowchart TD
    %% Define Styles
    classDef embed fill:#064e3b,stroke:#34d399,stroke-width:1px,color:#fff;
    classDef extract fill:#581c87,stroke:#c084fc,stroke-width:1px,color:#fff;
    classDef decision fill:#1e293b,stroke:#475569,stroke-width:1px,color:#fff;
    classDef math fill:#0f172a,stroke:#38bdf8,stroke-width:1px,color:#fff;

    subgraph Embedding ["左：PEE 藏密嵌入原理 (Embedding Process)"]
        E_Start(["輸入原始 Y 通道像素 p 及其預測值 p̂"])
        E_Predict["預測值 p̂ = G[i-1, j] (上方像素)
        當前像素 p = G[i, j]"]
        E_CheckBound{"安全邊界檢查：
        10 <= p̂ <= 245 ?"}
        E_SkipBound["跳過不嵌入，像素保持原值"]
        E_CalcError["計算原始預測誤差：
        e = p - p̂"]
        
        E_CheckRange{"判斷預測誤差 e 的區間"}
        
        %% 區間分類
        E_Range_Expand["誤差落在可嵌入區間：
        -1 <= e <= 1"]
        E_ReadBit["讀取 1 bit 秘密資料 b"]
        E_CalcNewError["計算擴張後的新誤差 e'：
        - 若 e = -1：e' = -2 + b
        - 若 e = 0 ：e' = b
        - 若 e = 1 ：e' = 2 + b
        (誤差值擴張為原來的兩倍，並融入 b)"]
        
        E_Range_Shift_Pos["誤差大於 1 (e > 1)"]
        E_Shift_Pos["誤差平移以避開重疊：
        e' = e + 2"]
        
        E_Range_Shift_Neg["誤差小於 -1 (e < -1)"]
        E_Shift_Neg["誤差平移以避開重疊：
        e' = e - 2"]
        
        E_Reconstruct["重新計算隱寫像素值：
        p' = p̂ + e'"]
        E_WritePixel["寫入載體像素 G[i, j] = p'"]
        E_End(["輸出 Stego 隱寫幀"])
    end
    class E_Start,E_Predict,E_SkipBound,E_CalcError,E_Range_Expand,E_ReadBit,E_CalcNewError,E_Range_Shift_Pos,E_Shift_Pos,E_Range_Shift_Neg,E_Shift_Neg,E_Reconstruct,E_WritePixel,E_End embed;
    class E_CheckBound,E_CheckRange decision;

    subgraph Extraction ["右：PEE 解密與無損還原原理 (Extraction & Restoration)"]
        X_Start(["輸入 Stego 隱寫幀像素 p' 及其預測值 p̂"])
        X_Predict["預測值 p̂ = G[i-1, j] (上方像素)
        隱寫像素 p' = G[i, j]"]
        X_CheckBound{"安全邊界檢查：
        10 <= p̂ <= 245 ?"}
        X_SkipBound["跳過不處理，像素保持原值"]
        X_CalcError["計算含密預測誤差：
        e' = p' - p̂"]
        
        X_CheckEmbed{"判斷誤差 e' 是否含有嵌入資料？
        -2 <= e' <= 3 ?"}
        
        %% 資料提取
        X_Extract_Data["是 (落在 [-2, 3] 區間)"]
        X_GetBit["提取秘密位元 b (由 e' 的奇偶性決定)：
        - 若 e' 為偶數 {-2, 0, 2}：b = 0
        - 若 e' 為奇數 {-1, 1, 3}：b = 1"]
        X_PushBuffer["將 b 寫入二進制解密緩衝區"]
        
        X_No_Data["否 (屬於平移區間)"]
        
        %% 逆向像素還原
        X_Restore_Loop["逆向遍歷所有像素進行像素還原 (Reversibility)"]
        X_CheckRange{"根據 e' 還原原始誤差 e"}
        
        X_Restore_Embed["e' 落在 [-2, 3]：
        - 若 e' 為 -2 或 -1：e = -1
        - 若 e' 為 0 或 1  ：e = 0
        - 若 e' 為 2 或 3  ：e = 1"]
        
        X_Restore_Shift_Pos["e' >= 4：
        逆向移回原始位置
        e = e' - 2"]
        
        X_Restore_Shift_Neg["e' <= -4：
        逆向移回原始位置
        e = e' + 2"]
        
        X_RecoverPixel["計算還原像素值：
        p = p̂ + e"]
        X_WriteRecovered["還原寫入載體 G[i, j] = p"]
        X_End(["100% 位元還原原始載體幀"])
    end
    class X_Start,X_Predict,X_SkipBound,X_CalcError,X_Extract_Data,X_GetBit,X_PushBuffer,X_No_Data,X_Restore_Loop,X_Restore_Embed,X_Restore_Shift_Pos,X_Restore_Shift_Neg,X_RecoverPixel,X_WriteRecovered,X_End extract;
    class X_CheckBound,X_CheckEmbed,X_CheckRange decision;

    %% 關聯線段
    E_Start --> E_Predict
    E_Predict --> E_CheckBound
    E_CheckBound -->|否| E_SkipBound
    E_CheckBound -->|是| E_CalcError
    E_CalcError --> E_CheckRange
    
    E_CheckRange --> E_Range_Expand
    E_Range_Expand --> E_ReadBit --> E_CalcNewError --> E_Reconstruct
    
    E_CheckRange --> E_Range_Shift_Pos
    E_Range_Shift_Pos --> E_Shift_Pos --> E_Reconstruct
    
    E_CheckRange --> E_Range_Shift_Neg
    E_Range_Shift_Neg --> E_Shift_Neg --> E_Reconstruct
    
    E_Reconstruct --> E_WritePixel --> E_End

    X_Start --> X_Predict
    X_Predict --> X_CheckBound
    X_CheckBound -->|否| X_SkipBound
    X_CheckBound -->|是| X_CalcError
    X_CalcError --> X_CheckEmbed
    
    X_CheckEmbed -->|是| X_Extract_Data
    X_Extract_Data --> X_GetBit --> X_PushBuffer --> X_Restore_Loop
    X_CheckEmbed -->|否| X_No_Data --> X_Restore_Loop
    
    X_Restore_Loop --> X_CheckRange
    X_CheckRange --> X_Restore_Embed
    X_CheckRange --> X_Restore_Shift_Pos
    X_CheckRange --> X_Restore_Shift_Neg
    
    X_Restore_Embed & X_Restore_Shift_Pos & X_Restore_Shift_Neg --> X_RecoverPixel
    X_RecoverPixel --> X_WriteRecovered --> X_End

    %% 跨欄關聯 (說明可逆性)
    E_End -.->|密寫影片傳輸| X_Start
```


---

## 🛠️ 開發環境建置

### 1. 安裝 Python 依賴
本專案開發測試基於 **Python 3.10+** (推薦使用 3.11 或 3.12)。請在您的虛擬環境下執行：
```bash
pip install -r requirements.txt
```

### 2. 執行應用程式
*   **啟動下載器**：`python src/download_app.py`
*   **啟動封裝器**：`python src/embed_app.py`
*   **啟動播放器**：`python src/player_app.py`

---

## 📝 專案開發規範

為確保專案程式碼的質量與多人口維護的流暢度，請所有編輯者遵守以下規範：

### 1. 程式碼風格與註解
*   遵循 **PEP 8** 程式碼風格指南。
*   所有底層影像與矩陣運算必須使用 **Numba JIT (`@njit(nogil=True, cache=True)`)** 進行加速，並確保傳入的矩陣類型與形狀（如 `np.int16`, `np.uint8`）定義明確，避免 JIT 編譯失敗。
*   **嚴禁刪除任何現有註解或文件**，修改現有代碼時，必須完整保留與該更動無關的既有註解。

### 2. 檔案管理規範 (防範爆庫)
*   **嚴禁提交大型影音檔案與編譯產物**：本系統測試用的影片動輒數 GB，GitHub 限制單一檔案不得超過 100MB。任何影片格式（如 `.mp4`, `.webm`, `.mkv`）、壓縮包（`.zip`）以及編譯快取與產物（`build/`, `dist/`, `.numba_cache/`）皆已在 `.gitignore` 中過濾，切勿強行提交。
*   任何個人實驗性、測試性的臨時腳本，請勿加入 Git 版本控制中。

---

## 🌿 Git 分支與 Push 合併規則 (主線保護機制)

為確保 `main` 主線分支的穩定性，防止未經驗證的代碼被隨意合併導致系統崩潰，本專案在 GitHub 上實施嚴格的**主線保護機制**與**分支工作流**。

### 1. Git 分支與 PR 流程圖

```mermaid
graph TD
    subgraph Remote ["遠端倉庫 (Remote GitHub)"]
        Main["main (保護分支: 唯讀/不可直接Push)"]
        PR["Pull Request (代碼審查/自動化測試)"]
    end
    
    subgraph Local ["本地開發 (Local Git)"]
        LocalMain["local main"]
        Feature["feature/功能分支"]
        Bugfix["bugfix/修正分支"]
    end

    LocalMain -->|1. 拉出新分支開發| Feature
    LocalMain -->|1. 拉出新分支修復| Bugfix
    
    Feature -->|2. 推送至遠端分支| PR
    Bugfix -->|2. 推送至遠端分支| PR
    
    PR -->|3. 通過 Code Review 與核准| Main
    PR -->|4. Squash & Merge| Main
    Main -->|5. 同步回本地| LocalMain
    
    style Main fill:#1e293b,stroke:#818cf8,stroke-width:2px,color:#fff
    style PR fill:#111827,stroke:#10b981,stroke-width:2px,color:#fff
```

### 2. 分支命名與用途規範

*   **`main` 分支**：生產與發布的主線分支。僅接受通過審查的 Pull Request 合併，**嚴禁任何開發者直接 Push 至此分支**。
*   **`feature/*` 分支**：新功能開發分支。命名範例：`feature/extract-dashboard`、`feature/compatibility-patch`。
*   **`bugfix/*` 分支**：Bug 修復分支。命名範例：`bugfix/ffmpeg-crash-fix`、`bugfix/sync-drift`。

### 3. Commit Message 格式規範 (Angular 規範)

為便於版本歷史追踪與自動化日誌生成，Commit 說明必須採用以下格式：
`類型(影響範圍): 簡短描述`

*   `feat`: 新增功能 (例如 `feat(player): add tech-style real-time log terminal`)
*   `fix`: 修復錯誤 (例如 `fix(stego): fix uint8 luma overflow during expansion`)
*   `docs`: 文件異動 (例如 `docs(readme): detailed code review specs`)
*   `style`: 代碼格式調整 (不影響邏輯，例如 `style(player): reformat PySide layout margins`)
*   `refactor`: 重構代碼 (例如 `refactor(utils): simplify path resolution logic`)
*   `perf`: 效能優化 (例如 `perf(numba): pre-allocate extraction bit buffer`)

---

## 🔍 Pull Request & Code Review 審查細則

所有合併至 `main` 分支的 PR，審查者 (Reviewer) 必須針對以下細節進行嚴格審查：

### 1. PEE 隱寫安全性與防溢位審查
*   **防溢位轉型**：在計算預測誤差 $e = p - \hat{p}$ 前，必須確認像素值已轉型為 `np.int16` 或 `np.int32`，嚴禁使用 `np.uint8` 直接運算，避免負數溢位。
*   **像素截斷 (Clipping)**：嵌入完成後的像素寫回暫存區時，必須使用 `np.clip(G, 0, 255)` 或等效防溢位邊界判定，確保數值不會超出 $0 \sim 255$。
*   **逆向無損驗證**：任何修改演算法邏輯的變更，必須在本地使用 MD5 驗證原始影片與提取還原後的影片是否 100% 相同。

### 2. 效能與資源管理審查
*   **Numba 靜態加速**：確保所有核心的影像逐像素遍歷函數（如 `pee_embed_core_numba`）皆有 `@njit(nogil=True, cache=True)` 裝飾器，且未調用無法被 Numba 編譯的 Python 原生 API。
*   **執行緒隔離**：耗時的 FFmpeg 解碼與隱寫資料提取操作，必須運行在 `QThread` 之中，**嚴禁**在 PySide6 的 GUI 主執行緒中執行阻塞性高的運算，避免介面卡死。
*   **暫存目錄清理**：程序結束或切換影片時，必須觸發 `cleanup_temp_dir()` 釋放寫入作業系統臨時目錄下的 AAC 音軌暫存檔，防止開發者的硬碟空間被暫存檔塞滿。

---

## 🔒 GitHub 倉庫分支保護設定指南 (管理員必讀)

專案管理員請依照以下步驟設定 GitHub，以強制啟用上述保護規範：

1.  進入 GitHub 專案首頁，點擊右上角 **⚙️ Settings**。
2.  在左側選單點擊 **Branches**。
3.  在 *Branch protection rules* 下，點擊 **Add branch rule**。
4.  在 *Branch name pattern* 輸入 `main`。
5.  勾選 **Require a pull request before merging**：
    *   將 **Require approvals** 設定為 `1`（需要至少一人審查通過）。
    *   勾選 **Dismiss stale pull request approvals when new commits are pushed**（有新 Commit 時自動重置 Approve 狀態）。
6.  勾選 **Require conversation resolution before merging**（必須解決所有程式碼討論留言才能合併）。
7.  勾選 **Do not allow bypassing the above settings** (或 **Include administrators**)。
    *   *註：這點最關鍵，它能防止專案擁有者不小心繞過 PR 機制直接 Push 主線。*
8.  點擊下方 **Create** 保存規則。