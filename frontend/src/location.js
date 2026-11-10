// 내 위치 (내 주변·검색의 "가까운 순"에서 같이 쓴다)

export const meters = (m) => (m < 1000 ? `${m}m` : `${(m / 1000).toFixed(1)}km`)

// 위치 권한 거절 등 브라우저가 알려주는 이유를 사람이 읽을 문장으로
const LOCATION_ERRORS = {
  1: '위치 권한이 꺼져 있어요. 브라우저 주소창의 위치 아이콘에서 허용한 뒤 다시 눌러 주세요.',
  2: '현재 위치를 알 수 없어요. 잠시 후 다시 시도해 주세요.',
  3: '위치를 찾는 데 시간이 너무 오래 걸렸어요. 다시 시도해 주세요.',
}

// 현재 위치 → { lat, lng }. 실패하면 사람이 읽을 이유를 담은 Error
// 소수점 3자리(약 100m)로 줄여서 보낸다: 주변 검색엔 충분하고 정확한 위치는 남기지 않는다
export function getCoords() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error('이 브라우저는 위치 찾기를 지원하지 않아요.'))
    navigator.geolocation.getCurrentPosition(
      ({ coords: c }) => resolve({ lat: c.latitude.toFixed(3), lng: c.longitude.toFixed(3) }),
      (err) => reject(new Error(LOCATION_ERRORS[err.code] ?? LOCATION_ERRORS[2])),
      { timeout: 10000, maximumAge: 60000 },
    )
  })
}
