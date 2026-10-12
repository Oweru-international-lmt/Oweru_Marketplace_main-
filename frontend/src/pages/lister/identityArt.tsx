// Drawn stand-ins for L7's tilted ID card and L9's photo examples, in Oweru's
// gold and navy. Decorative: each example's meaning is in its caption.

export function StartArt() {
  return (
    <div aria-hidden="true" className="relative mx-auto h-[250px] w-[250px]">
      <div className="absolute inset-0 rounded-full bg-gold/10 blur-2xl" />
      <div className="absolute top-3 left-1/2 h-[230px] w-[200px] -translate-x-1/2 rotate-[8deg] rounded-[22px] bg-white shadow-[0_24px_40px_-18px_rgba(15,23,42,0.35)] ring-1 ring-mist/80">
        <div className="absolute inset-5">
          {['top-0 left-0 border-t-[1.5px] border-l-[1.5px]', 'top-0 right-0 border-t-[1.5px] border-r-[1.5px]', 'bottom-0 left-0 border-b-[1.5px] border-l-[1.5px]', 'bottom-0 right-0 border-r-[1.5px] border-b-[1.5px]'].map((corner) => (
            <span key={corner} className={`absolute size-3.5 border-navy-soft/70 ${corner}`} />
          ))}
          <div className="absolute inset-3 grid place-items-center rounded-md bg-[#f6ead2]">
            <svg viewBox="0 0 120 80" className="w-[110px]">
              <ellipse cx="60" cy="40" rx="56" ry="36" fill="none" stroke="#0f172a" strokeWidth="4" />
              <circle cx="60" cy="31" r="14" fill="#e5b972" stroke="#0f172a" strokeWidth="4" />
              <path d="M28 66c6-14 18-20 32-20s26 6 32 20" fill="#e5b972" stroke="#0f172a" strokeWidth="4" />
            </svg>
          </div>
        </div>
      </div>
    </div>
  )
}

type IdVariant = 'good' | 'glare' | 'copy' | 'half'

export function IdSample({ variant }: { variant: IdVariant }) {
  const copy = variant === 'copy'
  const card = (
    <g>
      <rect x="0" y="0" width="140" height="88" rx="8" fill={copy ? '#e7e7e7' : '#f6ead2'} stroke={copy ? '#c9c9c9' : '#e5b972'} />
      <rect x="10" y="9" width="70" height="6" rx="3" fill={copy ? '#9a9a9a' : '#c89128'} opacity="0.8" />
      {[24, 34, 44, 54, 64].map((y, index) => (
        <rect key={y} x="10" y={y} width={index % 2 ? 58 : 72} height="4" rx="2" fill={copy ? '#b0b0b0' : '#2d3a58'} opacity="0.45" />
      ))}
      <rect x="92" y="22" width="38" height="48" rx="5" fill={copy ? '#d0d0d0' : '#ffffff'} />
      <circle cx="111" cy="38" r="8" fill={copy ? '#a8a8a8' : '#d9a77a'} />
      <path d="M97 66c3-9 8-12 14-12s11 3 14 12" fill={copy ? '#a8a8a8' : '#0f172a'} />
    </g>
  )
  return (
    <svg viewBox="0 0 170 120" className="block w-full" aria-hidden="true">
      <rect width="170" height="120" fill="#f1f3f6" />
      {variant === 'good' && <g transform="translate(15 16)">{card}</g>}
      {variant === 'glare' && (
        <g transform="translate(15 16)">
          {card}
          <defs>
            <radialGradient id="glare">
              <stop offset="0" stopColor="#fff" stopOpacity="1" />
              <stop offset="1" stopColor="#fff" stopOpacity="0" />
            </radialGradient>
          </defs>
          <ellipse cx="62" cy="40" rx="60" ry="48" fill="url(#glare)" />
          <ellipse cx="62" cy="40" rx="22" ry="16" fill="#fff" opacity="0.9" />
        </g>
      )}
      {copy && (
        <g transform="translate(20 22) rotate(-7 65 40)">
          <rect x="-6" y="-6" width="152" height="100" fill="#fff" stroke="#d6d6d6" />
          {card}
        </g>
      )}
      {variant === 'half' && <g transform="translate(70 38) rotate(-24 70 44)">{card}</g>}
    </svg>
  )
}

type FaceVariant = 'good' | 'glasses' | 'dark' | 'partial'

export function FaceSample({ variant }: { variant: FaceVariant }) {
  const good = variant === 'good'
  const shift = variant === 'partial' ? 46 : 0
  return (
    <svg viewBox="0 0 170 120" className="block w-full" aria-hidden="true">
      <rect width="170" height="120" fill={variant === 'partial' ? '#e9ecf0' : '#eef0f3'} />
      <g transform={`translate(${shift} 0)`}>
        <path d="M45 128c4-24 20-34 40-34s36 10 40 34Z" fill="#2d3a58" />
        <ellipse cx="85" cy="58" rx="24" ry="29" fill="#d9a77a" />
        <path d="M60 52c0-20 12-29 25-29s26 8 26 28c-6-9-16-13-26-13s-19 5-25 14Z" fill="#0f172a" />
        {variant === 'glasses' ? (
          <g fill="#0f172a">
            <rect x="66" y="52" width="16" height="10" rx="4" />
            <rect x="88" y="52" width="16" height="10" rx="4" />
            <rect x="81" y="55" width="8" height="2" />
          </g>
        ) : (
          <g fill="#0f172a">
            <circle cx="76" cy="57" r="2.4" />
            <circle cx="94" cy="57" r="2.4" />
          </g>
        )}
        <path d="M76 71c5 5 13 5 18 0" fill="none" stroke="#7a3b26" strokeWidth="2.4" strokeLinecap="round" />
      </g>
      <ellipse cx="85" cy="58" rx="33" ry="40" fill="none" stroke={good ? '#1f7a4d' : '#b42318'} strokeWidth="1.6" strokeDasharray="4 3" />
      {variant === 'dark' && <rect width="170" height="120" fill="#0b0f19" opacity="0.62" />}
      {variant === 'partial' && <rect x="0" width="60" height="120" fill="#e9ecf0" opacity="0.6" />}
    </svg>
  )
}
