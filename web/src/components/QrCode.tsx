"use client";

import qrcode from "qrcode-generator";
import { useMemo } from "react";

/** A QR code as one SVG path: black on white whatever the page, so any camera reads it. */
export default function QrCode({
  value,
  label,
  className = "size-40",
}: {
  value: string;
  label: string;
  className?: string;
}) {
  const { size, path } = useMemo(() => {
    const qr = qrcode(0, "M");
    qr.addData(value);
    qr.make();
    const count = qr.getModuleCount();
    const margin = 2;
    let d = "";
    for (let row = 0; row < count; row++) {
      for (let col = 0; col < count; col++) {
        if (qr.isDark(row, col)) d += `M${col + margin} ${row + margin}h1v1h-1z`;
      }
    }
    return { size: count + margin * 2, path: d };
  }, [value]);

  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={label}
      shapeRendering="crispEdges"
      className={className}
    >
      <rect width={size} height={size} fill="#fff" />
      <path d={path} fill="#000" />
    </svg>
  );
}
