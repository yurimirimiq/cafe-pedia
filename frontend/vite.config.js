import { defineConfig } from 'vite'
import process from 'node:process'
import react from '@vitejs/plugin-react'

// 링크 미리보기 이미지(index.html 의 og:image)에 붙일 사이트 주소
// Vercel 이 빌드할 때 알려주는 배포 도메인을 쓴다. 내 컴퓨터에선 비어 있어 '/og.png' 가 된다
const domain = process.env.VERCEL_PROJECT_PRODUCTION_URL
process.env.VITE_SITE_URL ??= domain ? `https://${domain}` : ''

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
})
