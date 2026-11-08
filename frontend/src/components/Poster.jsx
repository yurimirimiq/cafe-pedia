// 사진이 없는 장소의 포스터: 커피색 타일 + 이름 첫 글자 (README 디자인 방향)
const TONES = [
  ['#3B2A21', '#EFE6DC'], // 에스프레소
  ['#C8A27C', '#3B2A21'], // 크레마
  ['#EFE6DC', '#7A4A2B'], // 라떼
  ['#7A4A2B', '#EFE6DC'], // 브라운
]

export default function Poster({ place, size }) {
  // 같은 장소는 항상 같은 색이 나오도록 id 로 고른다
  const [bg, fg] = TONES[place.id % TONES.length]
  const first = place.name.replace(/^(카페|cafe)\s*/i, '')[0] ?? place.name[0]
  return (
    <div className="poster" style={{ background: bg, color: fg, width: size }} aria-hidden="true">
      {first}
    </div>
  )
}
