# Frontend

## 本地联调
默认请求:
- http://127.0.0.1:8000/api/landscape
- http://127.0.0.1:8000/api/refresh

如果你后端地址不是这个，可以在 `index.html` 里把:
`const API_BASE = "..."`
改成你的后端地址。

## 部署方式
- 最简单：把 frontend 作为静态站点部署到 Vercel / Netlify / GitHub Pages
- 后端单独部署到 Render
- 然后把 API_BASE 改成线上 API 地址
