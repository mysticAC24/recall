/**
 * Student Alumni Relations — IIT Delhi logo component.
 * Reproduced as SVG to avoid needing an image file.
 */
export function SARLogo({ className = "" }: { className?: string }) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      {/* Graduation cap icon */}
      <svg
        viewBox="0 0 64 64"
        className="w-9 h-9 shrink-0 fill-white"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Board */}
        <polygon points="32,8 64,24 32,40 0,24" />
        {/* Left side of mortarboard body */}
        <path d="M12,28 L12,46 Q32,54 52,46 L52,28 L32,38 Z" />
        {/* Tassel stem */}
        <rect x="60" y="24" width="3" height="14" rx="1.5" />
        {/* Tassel bob */}
        <rect x="58" y="37" width="7" height="5" rx="2" />
      </svg>

      {/* Text */}
      <div className="leading-tight">
        <div className="font-bold text-white text-sm sm:text-base tracking-wide uppercase">
          Student Alumni Relations
        </div>
        <div className="text-white/75 text-xs sm:text-sm font-normal">
          Indian Institute of Technology Delhi
        </div>
      </div>
    </div>
  );
}
