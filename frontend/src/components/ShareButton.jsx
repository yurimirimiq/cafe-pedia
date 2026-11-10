import { useRef, useState } from 'react'
import { mediaUrl } from '../api'
import { area } from './PlaceCard'
import useDismiss from './useDismiss'

const KEY = import.meta.env.VITE_KAKAO_JS_KEY
let sdk // 카카오 공유 스크립트는 한 번만 불러온다 (지도 스크립트와는 별개: window.Kakao)

function loadKakaoShare() {
  sdk ??= new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://t1.kakaocdn.net/kakao_js_sdk/2.7.4/kakao.min.js'
    script.crossOrigin = 'anonymous'
    script.onload = () => {
      if (!window.Kakao.isInitialized()) window.Kakao.init(KEY)
      resolve(window.Kakao)
    }
    script.onerror = () => { sdk = null; reject(new Error('카카오 스크립트를 불러오지 못했어요')) }
    document.head.appendChild(script)
  })
  return sdk
}

// 공유하기: 카카오톡으로 보내기, 링크 복사. JavaScript 키가 없으면 링크 복사만
export default function ShareButton({ place }) {
  const [open, setOpen] = useState(false)
  const [msg, setMsg] = useState('')
  const box = useRef(null)
  const url = `${window.location.origin}/place/${place.id}`

  useDismiss(box, open, () => setOpen(false))

  function toggle() {
    if (!open && KEY) loadKakaoShare().catch(() => {}) // 미리 불러 두면 누르자마자 열린다
    setOpen(!open)
  }

  function say(text) {
    setMsg(text)
    setTimeout(() => setMsg(''), 2500)
  }

  async function shareKakao() {
    setOpen(false)
    try {
      const Kakao = await loadKakaoShare()
      const link = { mobileWebUrl: url, webUrl: url }
      const detail = place.category_detail.split(' > ').at(-1)
      const image = mediaUrl(place.thumbnail_url)
      Kakao.Share.sendDefault({
        objectType: 'feed',
        content: {
          title: place.name,
          description: `${place.avg_rating ? `★ ${place.avg_rating} (${place.review_count}명) ` : ''}${area(place.address)} ${detail}`,
          // 카카오가 직접 받아 가야 해서 http(s) 주소인 사진만 넣는다
          imageUrl: image?.startsWith('http') ? image : undefined,
          link,
        },
        buttons: [{ title: '카페피디아에서 보기', link }],
      })
    } catch {
      say('카카오톡 공유를 열지 못했어요. 링크 복사를 이용해 주세요.')
    }
  }

  async function copyLink() {
    setOpen(false)
    try {
      await navigator.clipboard.writeText(url)
      say('링크를 복사했어요')
    } catch {
      window.prompt('이 링크를 복사하세요', url) // 클립보드를 못 쓰는 브라우저
    }
  }

  return (
    <div className="share" ref={box}>
      <button className="btn" onClick={toggle} aria-expanded={open} aria-haspopup="menu">
        <svg className="share-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 15V4M8 8l4-4 4 4M5 12v6.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V12" /></svg>
        <span className="share-label">공유</span>
      </button>
      {open && (
        <div className="share-menu" role="menu">
          {KEY && (
            <button role="menuitem" onClick={shareKakao}>
              <span className="kakao-dot" aria-hidden="true" />카카오톡으로 공유
            </button>
          )}
          <button role="menuitem" onClick={copyLink}>
            <svg className="share-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" /></svg>
            링크 복사
          </button>
        </div>
      )}
      <span className="share-toast" role="status">{msg}</span>
    </div>
  )
}
