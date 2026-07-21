import { useEffect, type RefObject } from "react";

/** Call `onClose` when a mousedown/touch happens outside `ref` (while `active`). */
// close a popover when the user clicks anywhere outside of it.
export function useClickOutside(
  ref: RefObject<HTMLElement | null>,
  onClose: () => void,
  active: boolean
) {
  useEffect(() => {
    if (!active) return;
    function handler(e: MouseEvent | TouchEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    document.addEventListener("mousedown", handler);
    document.addEventListener("touchstart", handler);
    return () => {
      document.removeEventListener("mousedown", handler);
      document.removeEventListener("touchstart", handler);
    };
  }, [ref, onClose, active]);
}
