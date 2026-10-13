import { useRef, useState } from "react";
import type { CameraRecord } from "../../services/cameraApi";
import type { ActiveSource, EngineType, UploadedSource } from "./types";
import { Icons } from "./icons";
import { CopilotPanelInline } from "./SingleCameraView";

const EMPTY_SLOT_COUNT = 4;

type Slot =
  | { kind: "camera"; camera: CameraRecord }
  | { kind: "empty"; emptyIndex: number };

/**
 * Camera matrix — left column lists every camera slot as a small thumbnail,
 * the selected slot is shown large in the center, and the right column is
 * the real (not fabricated) Copilot panel, same component used in the
 * single-camera workspace.
 *
 * There is no real camera registry today, so `cameras` is always []. Per
 * explicit instruction, this must NOT be filled with fabricated camera
 * records (not even demo-labeled ones) — each slot instead renders a
 * genuine "no camera configured" empty state with a real upload action.
 * Once `cameras` is non-empty (a real registry or the Map API), those
 * entries render as real camera cards instead.
 */
export function CameraMatrix({
  cameras,
  onOpenSource,
}: {
  cameras: CameraRecord[];
  onOpenSource: (source: ActiveSource) => void;
}) {
  const slotCount = Math.max(EMPTY_SLOT_COUNT, cameras.length);
  const emptySlotCount = slotCount - cameras.length;

  const slots: Slot[] = [
    ...cameras.map((camera): Slot => ({ kind: "camera", camera })),
    ...Array.from({ length: emptySlotCount }, (_, i): Slot => ({ kind: "empty", emptyIndex: i })),
  ];

  const [selected, setSelected] = useState(0);
  const selectedSlot = slots[selected] ?? slots[0];

  return (
    <div className="flex-1 flex overflow-hidden">
      {/* Left: compact thumbnail list */}
      <div className="w-64 shrink-0 border-r border-border bg-surface-1 flex flex-col overflow-hidden">
        <div className="px-3 py-3 border-b border-border shrink-0">
          <div className="font-mono text-xs font-semibold text-text-primary tracking-wide">CAMERA MATRIX</div>
          <div className="font-mono text-[11px] text-text-tertiary mt-0.5">
            {cameras.length} CONFIGURED · {emptySlotCount} UNCONFIGURED
          </div>
        </div>
        <div className="flex-1 overflow-auto p-2 flex flex-col gap-2">
          {slots.map((slot, i) =>
            slot.kind === "camera" ? (
              <ThumbnailCameraCard
                key={slot.camera.id}
                camera={slot.camera}
                active={i === selected}
                onSelect={() => setSelected(i)}
              />
            ) : (
              <ThumbnailEmptySlot
                key={`empty-${slot.emptyIndex}`}
                active={i === selected}
                onSelect={() => setSelected(i)}
                onUploaded={onOpenSource}
              />
            ),
          )}
        </div>
      </div>

      {/* Center: large preview of the selected slot */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 p-4 flex items-center justify-center">
          {selectedSlot.kind === "camera" ? (
            <LargeCameraPreview camera={selectedSlot.camera} onOpen={() => onOpenSource({ ...selectedSlot.camera, kind: "registry" })} />
          ) : (
            <LargeEmptySlot onUploaded={onOpenSource} />
          )}
        </div>
      </div>

      {/* Right: AI panel — real, honest "not connected" state */}
      <aside className="w-80 shrink-0 border-l border-border bg-surface-1 flex flex-col overflow-hidden">
        <div className="px-3 py-3 border-b border-border shrink-0 flex items-center gap-1.5 font-mono text-xs font-semibold text-text-primary tracking-wide">
          <Icons.Bot className="w-3.5 h-3.5" />
          AI COPILOT
        </div>
        <div className="flex-1 overflow-auto">
          <CopilotPanelInline />
        </div>
      </aside>
    </div>
  );
}

function ThumbnailCameraCard({
  camera,
  active,
  onSelect,
}: {
  camera: CameraRecord;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      className={`shrink-0 rounded-sm border p-2 flex items-center gap-2.5 text-left transition-colors ${
        active ? "border-accent bg-accent/10" : "border-border bg-surface-2 hover:border-accent/40"
      }`}
    >
      <div className="w-16 aspect-video shrink-0 bg-surface-0 border border-border rounded-sm flex items-center justify-center">
        <Icons.Video className="w-4 h-4 text-accent" />
      </div>
      <div className="min-w-0">
        <div className="font-mono text-[11px] font-semibold text-white truncate">{camera.title}</div>
        <div className="text-[10px] text-text-tertiary truncate">{camera.location}</div>
      </div>
    </button>
  );
}

function ThumbnailEmptySlot({
  active,
  onSelect,
  onUploaded,
}: {
  active: boolean;
  onSelect: () => void;
  onUploaded: (source: UploadedSource) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = (file: File | undefined, engineType: EngineType) => {
    if (!file) return;
    onUploaded({
      kind: "uploaded",
      id: `upload-${Date.now()}`,
      file,
      objectUrl: URL.createObjectURL(file),
      engineType,
    });
  };

  return (
    <button
      onClick={onSelect}
      className={`shrink-0 rounded-sm border border-dashed p-2 flex items-center gap-2.5 text-left transition-colors ${
        active ? "border-accent bg-accent/10" : "border-border bg-surface-2 hover:border-accent/40"
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept="video/*"
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0], "anomaly")}
      />
      <div className="w-16 aspect-video shrink-0 bg-surface-0 border border-border rounded-sm flex items-center justify-center">
        <Icons.Video className="w-4 h-4 text-text-tertiary" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="font-mono text-[11px] font-semibold text-text-secondary truncate">NO CAMERA CONFIGURED</div>
        <div
          role="button"
          onClick={(e) => {
            e.stopPropagation();
            inputRef.current?.click();
          }}
          className="mt-1 inline-flex items-center gap-1 text-[10px] font-mono text-accent hover:underline"
        >
          <Icons.Upload className="w-3 h-3" />
          ADD VIDEO SOURCE
        </div>
      </div>
    </button>
  );
}

function LargeCameraPreview({ camera, onOpen }: { camera: CameraRecord; onOpen: () => void }) {
  return (
    <button
      onClick={onOpen}
      className="w-full h-full max-w-4xl aspect-video bg-surface-1 border border-border hover:border-accent/50 rounded-sm flex flex-col items-center justify-center gap-3 p-6 transition-colors"
    >
      <Icons.Video className="w-10 h-10 text-accent" />
      <div className="font-mono text-sm font-semibold text-white">{camera.title}</div>
      <div className="text-xs text-text-tertiary">{camera.location}</div>
      <div className="mt-2 flex items-center gap-1.5 px-3 py-1.5 text-[11px] font-mono text-accent border border-accent/40 rounded-sm">
        <Icons.Maximize2 className="w-3 h-3" />
        OPEN FEED
      </div>
    </button>
  );
}

/** Genuine unconfigured state for the large preview pane — no fabricated
 * name, ID, coordinates, threat level, resolution, or sample video. The
 * only real content here is the upload action itself. */
function LargeEmptySlot({ onUploaded }: { onUploaded: (source: UploadedSource) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = (file: File | undefined, engineType: EngineType) => {
    if (!file) return;
    onUploaded({
      kind: "uploaded",
      id: `upload-${Date.now()}`,
      file,
      objectUrl: URL.createObjectURL(file),
      engineType,
    });
  };

  return (
    <div className="w-full h-full max-w-4xl aspect-video bg-surface-1 border border-dashed border-border rounded-sm flex flex-col items-center justify-center gap-3 p-6 text-center">
      <input
        ref={inputRef}
        type="file"
        accept="video/*"
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0], "anomaly")}
      />
      <Icons.Video className="w-10 h-10 text-text-tertiary" />
      <div className="font-mono text-sm font-semibold text-text-secondary">NO CAMERA CONFIGURED</div>
      <div className="text-xs text-text-tertiary max-w-xs">No live source is connected to this slot.</div>
      <button
        onClick={() => inputRef.current?.click()}
        className="mt-1 flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono text-accent border border-accent/40 hover:bg-accent/10 rounded-sm transition-colors"
      >
        <Icons.Upload className="w-3.5 h-3.5" />
        ADD VIDEO SOURCE
      </button>
    </div>
  );
}
