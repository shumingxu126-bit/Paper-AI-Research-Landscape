# Research Landscape Backend - Part 1

这是第 1 部分：后端完整包。

包含：
- FastAPI 后端
- SQLite / PostgreSQL 兼容数据库层
- OpenAlex + arXiv 抓取
- Claude 摘要接入位（Anthropic Messages API）
- taxonomy 驱动的路线刷新
- 手动 / 定时刷新脚本

## 目录
- `backend/`：后端代码
- `config/taxonomy_full.yaml`：全面知识图谱路线

## 本地启动
1. 创建虚拟环境并安装依赖
2. 复制 `.env.example` 为 `.env`
3. 运行：
   - `cd backend`
   - `uvicorn app.main:app --reload`
4. 手动刷新：
   - `python scripts/run_refresh.py`

## 必填环境变量
- `ANTHROPIC_API_KEY`
- `OPENALEX_EMAIL`（建议）
- `DATABASE_URL`（可选；默认 sqlite）

## 安全说明
不要把 API key 写死到代码或上传到 GitHub。你之前发在对话里的 key 建议立即轮换。
