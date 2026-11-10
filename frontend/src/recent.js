// 최근 본 장소: 이 브라우저에만 저장한다 (서버에 보내지 않음)
// shortcut: 볼 때의 별점·사진을 그대로 저장, 오래되면 실제와 다를 수 있다. 정확해야 하면 id 만 저장하고 서버에서 다시 불러온다
const KEY = 'recentPlaces'
const MAX = 10

export function loadRecent() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) ?? []
  } catch {
    return []
  }
}

export function saveRecent(place) {
  const { id, name, category, category_label, category_detail, address, avg_rating, review_count, top_tags, thumbnail_url } = place
  const item = { id, name, category, category_label, category_detail, address, avg_rating, review_count, top_tags, thumbnail_url }
  try {
    localStorage.setItem(KEY, JSON.stringify([item, ...loadRecent().filter((p) => p.id !== id)].slice(0, MAX)))
  } catch {
    // 저장 공간이 막힌 브라우저(사생활 보호 모드 등)에서는 기록하지 않는다
  }
}
