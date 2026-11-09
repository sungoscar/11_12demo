# 投稿審查系統

Python + FastAPI、Jinja2、PostgreSQL 17（psycopg3）的課堂 Demo。
目前 `main` 提供共用登入、登出、Session 與角色驗證；作者 CRUD、編輯審查尚未實作。

## 1. 安裝（Windows PowerShell）

在 `11_12demo` 專案根目錄執行。本機已使用 Python 3.14 驗證。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

若系統的 `python` 指向無法啟動的 WindowsApps 別名，請改用實際 Python 安裝路徑。
後續指令直接使用虛擬環境 Python，無須調整 PowerShell 執行原則。

## 2. 設定環境

只有尚無 `.env` 時才複製範本，請保留既有資料庫設定：

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

編輯 `.env` 的 `DB_HOST`、`DB_PORT`、`DB_NAME=submission_review`、`DB_USER`、`DB_PASSWORD`。
首次設定 Session 金鑰可用以下指令直接寫入 `.env`，金鑰不會印到終端機：

```powershell
.\.venv\Scripts\python.exe -c "import secrets; from dotenv import set_key; set_key('.env', 'SESSION_SECRET', secrets.token_urlsafe(48))"
```

此指令會更換金鑰，請勿每次啟動都執行，否則既有 Session 會失效。
`SESSION_SECRET` 缺少或不足 32 字元時，啟動會提供明確錯誤。
本機使用 `APP_ENV=development`、`SESSION_HTTPS_ONLY=false`，支援 HTTP。
外部環境變數優先於 `.env`；`.env`、模板與靜態檔案都以程式所在目錄定位。
`.env` 與 `.env.*` 已忽略，只有不含真實機密的 `.env.example` 可加入 Git。

## 3. PostgreSQL 設定

先啟動 PostgreSQL 17，並透過 pgAdmin 或 `psql` 建立 `submission_review` 資料庫。
新資料庫可執行：

```powershell
psql -h localhost -p 5432 -U postgres -d submission_review -v ON_ERROR_STOP=1 -f database/schema.sql
```

若 `psql` 不在 PATH，使用 PostgreSQL 安裝目錄下的 `bin\psql.exe`，或在 pgAdmin Query Tool 執行 SQL。
既有資料庫請先核對結構。`schema.sql` 使用 `IF NOT EXISTS`，不會修復舊表的欄位；不得刪表重建。
本次已唯讀確認現有兩張表符合需求，沒有執行 schema 或 migration，也沒有新增或修改正式資料。

- `users`：id、唯一 username、password_hash、author/editor role、created_at。
- `articles`：id、author_id 外鍵、category、title、content、status、created_at、updated_at。
- 稿件狀態：editing（編輯中）、reviewing（審查中）、approved（已通過）。

`db.py` 使用 psycopg3 連線，連線逾時為 5 秒，查詢使用 `%s` 與獨立參數，並由 context manager 關閉連線與處理交易。
`DB_SSLMODE=prefer` 適用本機；遠端正式資料庫應設定 `verify-full` 並配置可信 CA。

## 4. 建立測試帳號

```powershell
.\.venv\Scripts\python.exe seed_users.py
```

工具依序以不回顯方式詢問 `author1`（作者）、`editor1`（編輯）的密碼與確認密碼，須為 12 至 1024 字元。
不支援隱藏輸入的終端機會拒絕輸入，避免密碼回顯。
自動化可由機密管理工具提供 `SEED_AUTHOR_PASSWORD` 與 `SEED_EDITOR_PASSWORD` 環境變數，請勿將明文放入指令歷史或版本控制。
密碼只以 pwdlib Argon2id 雜湊儲存，不列印密碼或雜湊。
既有帳號直接跳過，保留原密碼與角色；`ON CONFLICT DO NOTHING` 防止並行執行產生重複帳號。
兩個帳號在同一交易建立，任一步驟失敗皆回復本次新增。

## 5. 啟動與 Demo

```powershell
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

開啟 <http://127.0.0.1:8000/>。

1. 未登入可看到介紹首頁與 `/login` 登入頁。
2. 以 `author1` 登入，自動前往 `/author/`，顯示帳號與作者角色。
3. 直接開啟 `/editor/`，應顯示繁體中文 403 權限錯誤。
4. 點選登出，再開啟 `/author/`，應導回登入頁。
5. 以 `editor1` 登入，導向 `/editor/`；直接開啟 `/author/` 應回應 403。
6. 輸入錯誤密碼或不存在的帳號，一律顯示「帳號或密碼錯誤」。

路由：`GET /`、`GET /login`、`POST /login`、`POST /logout`、`GET /author/`、`GET /editor/`。
已登入者開啟 `/` 或 `/login` 會自動回到其角色首頁。
角色 Router 使用共用 dependency 保護，後續新增角色功能時，保留此 dependency；不可只隱藏前端按鈕。
每個請求都重新依 user_id 查詢資料庫的目前角色，不採用表單提交的 role。

## 6. 自動化驗證

```powershell
.\.venv\Scripts\python.exe -m compileall -q main.py config.py db.py auth_utils.py seed_users.py routers tests
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -c "from main import app; print(app.title)"
.\.venv\Scripts\python.exe -m pip check
```

測試使用 FastAPI TestClient、記憶體使用者資料與 mock 連線。
自動 fixture 禁止測試連線正式資料庫，測試不需要本機 `.env`、不寫入正式 users/articles。
涵蓋公開頁面、兩種角色登入與導向、錯誤憑證、未登入保護、跨角色 403、登出、CSRF、簽章 Cookie、角色變動、刪除帳號、Argon2 與安全設定，另驗證 seed 冪等性與參數化查詢。

## 7. Session 與部署

- SessionMiddleware 使用簽章 Cookie，內容可被讀取，只存放 user_id 與必要 CSRF token，不存帳號、角色、密碼或雜湊。
- Cookie 設為 HttpOnly、SameSite=Lax，壽命 8 小時（以簽章時間驗證）；活動請求可能重新簽發。
- 登入成功會清除舊 Session 並輪替 CSRF；登入與登出均須 POST 表單的 CSRF token。
- 登出清除瀏覽器 Session Cookie；受保護頁面使用 no-store，避免快取顯示帳號資訊。
- 正式環境設定 `APP_ENV=production`、`SESSION_HTTPS_ONLY=true`，在可信反向代理終結 HTTPS，僅信任指定代理來源，並限制對外入口。正式模式會拒絕停用 Secure Cookie。
- 簽章 Cookie 並非伺服器端 Session 儲存。已被複製的 Cookie 在到期前仍可能重放；需要跨裝置撤銷時，應另加伺服器端 Session 儲存與撤銷機制。刪除帳號或變更角色會在下次請求生效。
- 公網正式部署還需於入口設定登入速率限制；本階段為課堂 Demo，未加入分散式限流或帳號復原功能。

API 設定參考：[Starlette SessionMiddleware](https://www.starlette.io/middleware/#sessionmiddleware)、[FastAPI 密碼雜湊說明](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)。
