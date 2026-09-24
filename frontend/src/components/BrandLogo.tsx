type BrandLogoProps = {
  className?: string;
  showWordmark?: boolean;
  markClassName?: string;
};

export function BrandMark({ className = "h-10 w-auto" }: { className?: string }) {
  return (
    <svg viewBox="-4 -4 108 126" className={className} fill="none" stroke="currentColor" strokeWidth={6} aria-hidden="true">
      <path d="M76 12.6L50 3L4 20V40L48 80L83.5 34.4" strokeLinejoin="miter" />
      <path d="M50 6V52" />
      <path d="M97 17L75.6 28.3L91.4 40.5Z" fill="currentColor" strokeWidth={2} strokeLinejoin="round" />
      <path d="M4 53V68C4 92 28 108 48 117C68 108 92 92 92 68V55" />
    </svg>
  );
}

export default function BrandLogo({ className = "", showWordmark = true, markClassName = "h-10 w-auto" }: BrandLogoProps) {
  return (
    <span className={`inline-flex items-center gap-3 text-[var(--ink)] ${className}`} aria-label="STYL">
      <BrandMark className={markClassName} />
      {showWordmark ? (
        <span className="text-xl font-bold leading-none tracking-[0.12em]" aria-hidden="true">
          STYL
        </span>
      ) : null}
    </span>
  );
}
