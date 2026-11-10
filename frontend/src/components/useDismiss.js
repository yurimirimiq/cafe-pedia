import { useEffect } from 'react'

// 떠 있는 메뉴: 바깥을 누르거나 Esc 를 누르면 onClose
export default function useDismiss(ref, open, onClose) {
  useEffect(() => {
    if (!open) return
    const close = (e) => (e.key === 'Escape' || (e.type === 'pointerdown' && !ref.current?.contains(e.target))) && onClose()
    document.addEventListener('pointerdown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('pointerdown', close)
      document.removeEventListener('keydown', close)
    }
  }, [ref, open, onClose])
}
