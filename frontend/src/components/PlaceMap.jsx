import { useEffect, useRef, useState } from 'react'

const KEY = import.meta.env.VITE_KAKAO_JS_KEY
let sdk // 카카오 지도 스크립트는 한 번만 불러온다

function loadKakaoMaps() {
  sdk ??= new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${KEY}&autoload=false`
    script.onload = () => window.kakao.maps.load(() => resolve(window.kakao))
    script.onerror = reject
    document.head.appendChild(script)
  })
  return sdk
}

// 장소 위치 지도. JavaScript 키(VITE_KAKAO_JS_KEY)가 없거나 불러오기에 실패하면 카카오맵 링크만 보여준다
export default function PlaceMap({ place }) {
  const ref = useRef(null)
  const [failed, setFailed] = useState(!KEY)

  useEffect(() => {
    if (!KEY) return
    loadKakaoMaps()
      .then((kakao) => {
        const pos = new kakao.maps.LatLng(place.latitude, place.longitude)
        const map = new kakao.maps.Map(ref.current, { center: pos, level: 3 })
        new kakao.maps.Marker({ position: pos, map })
      })
      .catch(() => setFailed(true))
  }, [place.latitude, place.longitude])

  return (
    <div className="map-box">
      {failed ? <div className="map map-empty">지도</div> : <div className="map" ref={ref} />}
      <a className="map-link" href={`https://place.map.kakao.com/${place.kakao_id}`} target="_blank" rel="noreferrer">
        카카오맵에서 보기 (영업시간, 메뉴)
      </a>
    </div>
  )
}
