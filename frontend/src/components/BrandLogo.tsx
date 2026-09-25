type BrandLogoProps = {
  className?: string;
  showWordmark?: boolean;
  markClassName?: string;
};

export function BrandMark({ className = "h-10 w-auto" }: { className?: string }) {
  return (
    <svg viewBox="66 20 430 558" className={className} fill="currentColor" aria-hidden="true">
      <path d="M82 121C151 104 216 77 276 36C327 70 386 96 440 113L412 125C368 112 324 91 289 68V267L266 291V69C218 99 163 122 107 138V222L263 360L417 180L369 163L480 119L478 223L455 189L267 407L82 233Z" />
      <path d="M82 260L107 285C109 402 174 474 278 534C389 472 454 391 453 284V242L477 256V294C477 414 400 499 278 561C151 504 81 410 82 260Z" />
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
