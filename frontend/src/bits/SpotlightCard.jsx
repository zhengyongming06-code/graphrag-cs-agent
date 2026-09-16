import { useRef } from "react";
import "./SpotlightCard.css";

/** Vendored from React Bits (MIT): https://github.com/DavidHDev/react-bits */
export default function SpotlightCard({
  children,
  className = "",
  spotlightColor = "rgba(31, 77, 58, 0.14)",
}) {
  const ref = useRef(null);

  function onMove(e) {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    el.style.setProperty("--mouse-x", `${e.clientX - rect.left}px`);
    el.style.setProperty("--mouse-y", `${e.clientY - rect.top}px`);
    el.style.setProperty("--spotlight-color", spotlightColor);
  }

  return (
    <div ref={ref} className={`card-spotlight ${className}`} onMouseMove={onMove}>
      {children}
    </div>
  );
}
