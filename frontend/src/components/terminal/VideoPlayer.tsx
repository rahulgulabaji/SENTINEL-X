import { useEffect, useRef, useState, type ReactNode, type RefObject } from "react";

function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "00:00";
  const mm = Math.floor(seconds / 60);
  const ss = Math.floor(seconds % 60);
  return `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
}

/**
 * Tactical video player: real HTML5 <video> underneath, custom graphite
 * controls on top. No simulated playback state — every value shown
 * (currentTime, duration, playing/paused) is read directly from the real
 * video element's own events.
 *
 * `videoRef` is forwarded so sibling overlays (DetectionOverlay) that
 * position themselves against the real <video> element keep working
 * unchanged.
 *
 * Mount a fresh instance per source (e.g. `key={videoUrl}` at the call
 * site) so switching videos always starts from a clean listener/rAF
 * state rather than trying to reconcile old and new playback state.
 */
export function VideoPlayer({
  videoUrl,
  videoRef,
  overlay,
  onTimeUpdate,
  onDurationChange,
}: {
  videoUrl: string;
  videoRef: RefObject<HTMLVideoElement | null>;
  /** Optional overlay (e.g. DetectionOverlay) rendered inside the same
   * positioned wrapper as the real <video> element, so its absolute
   * positioning aligns with the video's actual on-screen rect. */
  overlay?: ReactNode;
  /** Optional: real video.currentTime, reported on every real sync tick
   * (same rAF + timeupdate mechanism driving the internal playhead below).
   * Lets a parent (e.g. a temporal-evidence timeline) stay in sync with
   * actual playback/seeking without duplicating any tracking logic. */
  onTimeUpdate?: (seconds: number) => void;
  /** Optional: real video.duration, reported whenever it changes. */
  onDurationChange?: (seconds: number | null) => void;
}) {
  const [duration, setDuration] = useState<number | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [autoplayBlocked, setAutoplayBlocked] = useState(false);
  const rafRef = useRef<number | null>(null);
  const scrubberRef = useRef<HTMLDivElement>(null);

  // Drive currentTime from rAF while playing for a smooth playhead, and
  // from the real `timeupdate` event as the baseline/fallback (e.g. tab
  // backgrounded, where rAF is throttled or suspended). Both read the
  // same real video.currentTime — neither ever fabricates a value.
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const syncFromVideo = () => {
      setCurrentTime(video.currentTime);
      onTimeUpdate?.(video.currentTime);
    };

    const tick = () => {
      syncFromVideo();
      rafRef.current = requestAnimationFrame(tick);
    };

    const handleLoadedMetadata = () => {
      const d = Number.isFinite(video.duration) ? video.duration : null;
      setDuration(d);
      onDurationChange?.(d);
      syncFromVideo();
    };
    const handlePlay = () => {
      setIsPlaying(true);
      setAutoplayBlocked(false);
      if (rafRef.current == null) rafRef.current = requestAnimationFrame(tick);
    };
    const handlePause = () => {
      setIsPlaying(false);
      if (rafRef.current != null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      syncFromVideo();
    };
    const handleEnded = () => {
      setIsPlaying(false);
      if (rafRef.current != null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      syncFromVideo();
    };
    const handleDurationChange = () => {
      const d = Number.isFinite(video.duration) ? video.duration : null;
      setDuration(d);
      onDurationChange?.(d);
    };

    video.addEventListener("loadedmetadata", handleLoadedMetadata);
    video.addEventListener("durationchange", handleDurationChange);
    video.addEventListener("timeupdate", syncFromVideo);
    video.addEventListener("play", handlePlay);
    video.addEventListener("pause", handlePause);
    video.addEventListener("ended", handleEnded);

    // If metadata is already available (e.g. fast local blob), pick it up
    // immediately rather than waiting for an event that already fired.
    if (video.readyState >= 1) handleLoadedMetadata();

    // Real autoplay attempt. Browsers only allow this unprompted when the
    // element is muted + playsInline; if the browser still rejects it,
    // the promise rejects and we show a real Play button rather than
    // ever claiming playback started.
    const playAttempt = video.play();
    if (playAttempt && typeof playAttempt.catch === "function") {
      playAttempt.catch(() => {
        setAutoplayBlocked(true);
        setIsPlaying(false);
      });
    }

    return () => {
      video.removeEventListener("loadedmetadata", handleLoadedMetadata);
      video.removeEventListener("durationchange", handleDurationChange);
      video.removeEventListener("timeupdate", syncFromVideo);
      video.removeEventListener("play", handlePlay);
      video.removeEventListener("pause", handlePause);
      video.removeEventListener("ended", handleEnded);
      if (rafRef.current != null) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoUrl]);

  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused || video.ended) {
      video.play().catch(() => setAutoplayBlocked(true));
    } else {
      video.pause();
    }
  };

  const seekToClientX = (clientX: number) => {
    const video = videoRef.current;
    const track = scrubberRef.current;
    if (!video || !track || !duration) return;
    const rect = track.getBoundingClientRect();
    const fraction = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    video.currentTime = fraction * duration;
    setCurrentTime(video.currentTime);
  };

  const handleScrubberPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    seekToClientX(e.clientX);
  };
  const handleScrubberPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.buttons !== 1) return;
    seekToClientX(e.clientX);
  };

  const progressFraction = duration ? Math.min(1, currentTime / duration) : 0;

  return (
    <div className="flex flex-col gap-2 w-full h-full">
      <div className="relative flex-1 min-h-0 flex items-center justify-center">
        <video
          ref={videoRef}
          src={videoUrl}
          muted
          playsInline
          autoPlay
          className="max-h-full max-w-full"
        />
        {overlay}
        {autoplayBlocked && !isPlaying && (
          <button
            onClick={togglePlay}
            className="absolute inset-0 flex items-center justify-center bg-surface-0/40"
            aria-label="Play video"
          >
            <span className="flex items-center justify-center w-14 h-14 rounded-sm bg-surface-1/90 border border-border-strong text-text-primary hover:border-accent hover:text-accent transition-colors">
              <PlayGlyph />
            </span>
          </button>
        )}
      </div>

      <div className="shrink-0 flex items-center gap-3 px-1">
        <button
          onClick={togglePlay}
          className="flex items-center justify-center w-7 h-7 rounded-sm border border-border bg-surface-2 text-text-secondary hover:text-white hover:border-border-strong transition-colors shrink-0"
          aria-label={isPlaying ? "Pause" : "Play"}
        >
          {isPlaying ? <PauseGlyph /> : <PlayGlyph small />}
        </button>

        <div
          ref={scrubberRef}
          onPointerDown={handleScrubberPointerDown}
          onPointerMove={handleScrubberPointerMove}
          className="relative flex-1 h-5 flex items-center cursor-pointer select-none"
        >
          <div className="absolute left-0 right-0 h-[3px] bg-surface-3 rounded-sm" />
          <div
            className="absolute left-0 h-[3px] bg-accent rounded-sm"
            style={{ width: `${progressFraction * 100}%` }}
          />
          <div
            className="absolute w-2.5 h-2.5 rounded-full bg-accent border border-surface-0"
            style={{ left: `calc(${progressFraction * 100}% - 5px)` }}
          />
        </div>

        <div className="font-mono text-[11px] text-text-secondary tabular-nums shrink-0">
          {formatTime(currentTime)} / {duration != null ? formatTime(duration) : "--:--"}
        </div>
      </div>
    </div>
  );
}

function PlayGlyph({ small }: { small?: boolean }) {
  return (
    <svg viewBox="0 0 24 24" className={small ? "w-3 h-3" : "w-5 h-5"} fill="currentColor">
      <path d="M8 5v14l11-7z" />
    </svg>
  );
}

function PauseGlyph() {
  return (
    <svg viewBox="0 0 24 24" className="w-3 h-3" fill="currentColor">
      <path d="M6 5h4v14H6zM14 5h4v14h-4z" />
    </svg>
  );
}
