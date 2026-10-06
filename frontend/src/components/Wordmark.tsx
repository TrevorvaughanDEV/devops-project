/** The site's wordmark link, with the same ring-and-dot as the favicon. */
export function Wordmark() {
  return (
    <a className="wordmark" href="/">
      <svg className="wordmark-mark" viewBox="0 0 32 32" aria-hidden="true" focusable="false">
        <circle className="ring" cx="16" cy="16" r="13" fill="none" stroke="currentColor" strokeWidth="2.5" opacity="0.55" />
        <circle cx="16" cy="16" r="5.5" fill="currentColor" />
      </svg>
      Who's knocking?
    </a>
  );
}
