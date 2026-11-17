# LOTTO AI｜幸運人生計畫

個人化幸運提示、統計型大樂透選號、公益夢想基金及善意紀錄。這不是台灣彩券官方服務，不代購、不投注、不保證中獎。

## 雲端資料同步

- GitHub Actions 每天台灣時間 22:30（UTC 14:30）執行同步。
- 首次完整同步請勾選 `full_sync`，從 2007 年 1 月起依年度區間取得 API 可提供的歷史紀錄；目前資料檔已回填至 2007 年。
- 每日台灣時間 22:30 執行增量同步，重新抓取前一個月與當月，補上延遲公告或更正資料。
- 修改網站 `index.html` 也會觸發重新部署；單純修改網站畫面不會重新完整回填歷史資料。
- 資料來源是台灣彩券官網目前使用的查詢 API：`https://api.taiwanlottery.com/TLCAPIWeB/Lottery/Lotto649Result`。這是官網查詢介面，並非有永久版本承諾的公開 API；若格式改變，工作流程會失敗並保留舊資料。
- 台彩官方年度下載頁列有各年度大樂透資料，包含期別、開獎日期、獎號1至6及特別號，頁面說明每月5日更新至前一個月。可另匯入官方 CSV 取得更早年度資料。

## 啟用 GitHub Pages

1. Repository → Settings → Pages。
2. Build and deployment → Source 選 `GitHub Actions`。
3. Repository → Actions → `LOTTO AI 自動更新` → Run workflow。
4. 第一次執行勾選 `full_sync`，確認執行成功後即可使用 Pages 網址。

## 個人資料隱私

生日、出生時辰、出生地、夢想基金和善意紀錄只儲存在使用者自己的瀏覽器 `localStorage`，不會寫入 GitHub。公開 Repository 不要提交任何個人資料、Token、密碼或金鑰。

## 統計與中獎機率

歷史出現頻率、冷熱號或生肖生日參考不能預測未來開獎，也不會改變每一組合法號碼相同的中獎機率。請設定小額預算、不借錢投注。
