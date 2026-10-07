/**
 * Icon set ported verbatim from the approved SENTINEL-X Tactical Terminal
 * HTML reference — same paths, same viewBoxes. Purely presentational;
 * carries no data of its own.
 */
import type { SVGProps } from "react";

interface IconProps extends SVGProps<SVGSVGElement> {
  className?: string;
}

function Icon({ path, className = "w-4 h-4", viewBox = "0 0 24 24", ...rest }: IconProps & { path: string }) {
  return (
    <svg className={className} viewBox={viewBox} fill="none" stroke="currentColor" strokeWidth={1.75} {...rest}>
      <path strokeLinecap="round" strokeLinejoin="round" d={path} />
    </svg>
  );
}

export const Icons = {
  Shield: (p: IconProps) => <Icon path="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" {...p} />,
  Video: (p: IconProps) => (
    <Icon
      path="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
      {...p}
    />
  ),
  Map: (p: IconProps) => (
    <Icon
      path="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l5.447 2.724A1 1 0 0021 18.818V8.045a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
      {...p}
    />
  ),
  MapPin: (p: IconProps) => (
    <Icon
      path="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0zM15 11a3 3 0 11-6 0 3 3 0 016 0z"
      {...p}
    />
  ),
  Upload: (p: IconProps) => <Icon path="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" {...p} />,
  Settings: (p: IconProps) => (
    <Icon
      path="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
      {...p}
    />
  ),
  AlertTriangle: (p: IconProps) => (
    <Icon
      path="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0zM12 9v4M12 17h.01"
      {...p}
    />
  ),
  Zap: (p: IconProps) => <Icon path="M13 10V3L4 14h7v7l9-11h-7z" {...p} />,
  ChevronRight: (p: IconProps) => <Icon path="M9 5l7 7-7 7" {...p} />,
  X: (p: IconProps) => <Icon path="M6 18L18 6M6 6l12 12" {...p} />,
  Bot: (p: IconProps) => (
    <Icon
      path="M12 2a2 2 0 012 2v2a2 2 0 01-2 2 2 2 0 01-2-2V4a2 2 0 012-2zm-7 7a2 2 0 012-2h10a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V9zm3 3h.01M16 12h.01M9 16h6"
      {...p}
    />
  ),
  Send: (p: IconProps) => <Icon path="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" {...p} />,
  Sparkles: (p: IconProps) => (
    <Icon
      path="M5 3v4M3 5h4M6 17v4m-2-2h4m11-16l1.2 3.6L20 10l-3.6 1.2L15 15l-1.2-3.6L10 10l3.6-1.2L15 4z"
      {...p}
    />
  ),
  Maximize2: (p: IconProps) => <Icon path="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" {...p} />,
  ArrowLeft: (p: IconProps) => <Icon path="M10 19l-7-7m0 0l7-7m-7 7h18" {...p} />,
  Grid: (p: IconProps) => (
    <Icon
      path="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"
      {...p}
    />
  ),
  Home: (p: IconProps) => (
    <Icon
      path="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"
      {...p}
    />
  ),
  Phone: (p: IconProps) => (
    <Icon
      path="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"
      {...p}
    />
  ),
  Radio: (p: IconProps) => (
    <Icon
      path="M12 18a6 6 0 100-12 6 6 0 000 12zM19.07 4.93a10 10 0 010 14.14M4.93 4.93a10 10 0 000 14.14"
      {...p}
    />
  ),
  Check: (p: IconProps) => <Icon path="M5 13l4 4L19 7" {...p} />,
  Copy: (p: IconProps) => (
    <Icon
      path="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
      {...p}
    />
  ),
};
